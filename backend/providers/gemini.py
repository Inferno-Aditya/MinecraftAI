import os
import time
import concurrent.futures
from typing import Optional, TYPE_CHECKING
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from dotenv import load_dotenv
from .base import BaseLLMProvider

if TYPE_CHECKING:
    from request_context import RequestContext


# ──────────────────────────────────────────────────────────────────────────────
# Timeout constants
# ──────────────────────────────────────────────────────────────────────────────
GEMINI_CONNECT_TIMEOUT_S = 10.0   # Time to establish the HTTP connection
GEMINI_READ_TIMEOUT_S    = 30.0   # Time to receive a complete response
GEMINI_HARD_TIMEOUT_S    = 35.0   # Wall-clock hard limit via ThreadPoolExecutor
                                   # (guards against SDK ignoring request_options)


class GeminiProvider(BaseLLMProvider):
    """
    LLM provider implementation for Google Gemini / Google AI Studio.

    Behavior is driven by capability flags set by the factory:
      - supports_json_mode:  If True, enforces response_mime_type=application/json.
                             Gemma models and specialized models set this to False.
      - supports_tools:      Reserved for future function-calling schema injection.

    These flags are set externally by get_provider() after reading the
    active ModelProfile, so no model-specific conditions are needed here.

    Timeout strategy (defense-in-depth):
      1. request_options timeout → asks the Gemini SDK to respect a deadline.
      2. ThreadPoolExecutor.result(timeout=GEMINI_HARD_TIMEOUT_S) → hard wall-clock
         guard that fires even if the SDK ignores or mishandles the SDK timeout.
    """

    _executor = concurrent.futures.ThreadPoolExecutor(max_workers=5, thread_name_prefix="gemini-provider")

    def __init__(self, model_name: str = None):
        try:
            from model_manager import model_manager
        except ImportError:
            from ..model_manager import model_manager

        self.model_name = model_name or model_manager.get_active_model()
        self.last_usage_metadata: Optional[dict] = None
        self.last_request_info: dict = {}  # Exposed for diagnostics endpoint

        load_dotenv(override=True)
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)

    # ------------------------------------------------------------------ #
    # Public generate() API                                                #
    # ------------------------------------------------------------------ #

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        ctx: Optional["RequestContext"] = None
    ) -> str:
        """
        Send a request to the Gemini API and return the raw text response.

        Every failure path:
          - is logged with the Request ID,
          - is assigned a FailureCategory (imported from request_context),
          - re-raises so that execute_llm_request_with_rate_limits() can
            record stats and apply retry logic.

        The hard wall-clock timeout (GEMINI_HARD_TIMEOUT_S) is enforced via a
        ThreadPoolExecutor to protect against the Gemini SDK silently ignoring
        the request_options timeout.
        """
        # Always reload API key in case it was set dynamically
        load_dotenv(override=True)
        self.api_key = os.getenv("GEMINI_API_KEY")

        req_id = ctx.prefix() if ctx else "[REQ:?]"

        if not self.api_key:
            msg = (
                "GEMINI_API_KEY environment variable is missing. "
                "Please add it to your backend/.env file."
            )
            self._log("ERROR", req_id, msg)
            self._set_ctx_failure(ctx, "PROVIDER_INIT_ERROR")
            raise ValueError(msg)

        genai.configure(api_key=self.api_key)
        self.last_usage_metadata = None

        # Build sanitized payload info for diagnostics (no API keys)
        self.last_request_info = {
            "model": self.model_name,
            "supports_json_mode": self.supports_json_mode,
            "supports_tools": self.supports_tools,
            "system_prompt_chars": len(system_prompt),
            "user_prompt_chars": len(user_prompt),
        }

        self._log("INFO", req_id, (
            f"Provider request started – model={self.model_name} "
            f"json_mode={self.supports_json_mode} "
            f"sys_chars={len(system_prompt)} user_chars={len(user_prompt)} "
            f"connect_timeout={GEMINI_CONNECT_TIMEOUT_S}s "
            f"read_timeout={GEMINI_READ_TIMEOUT_S}s "
            f"hard_timeout={GEMINI_HARD_TIMEOUT_S}s"
        ))

        # Run the actual SDK call inside a thread so we can apply a hard
        # wall-clock timeout regardless of what the SDK does internally.
        future = self._executor.submit(self._do_generate, system_prompt, user_prompt, req_id, ctx)
        try:
            result = future.result(timeout=GEMINI_HARD_TIMEOUT_S)
            return result
        except concurrent.futures.TimeoutError:
            future.cancel()
            msg = (
                f"Gemini hard-timeout ({GEMINI_HARD_TIMEOUT_S}s) exceeded – "
                f"model={self.model_name}. SDK did not return within the deadline."
            )
            self._log("ERROR", req_id, msg)
            self.last_request_info["status"] = "hard_timeout"
            self.last_request_info["error"] = msg
            self._set_ctx_failure(ctx, "PROVIDER_TIMEOUT")
            raise TimeoutError(msg)

    def _do_generate(
        self,
        system_prompt: str,
        user_prompt: str,
        req_id: str,
        ctx: Optional["RequestContext"],
    ) -> str:
        """
        Inner method that runs inside the ThreadPoolExecutor thread.
        Performs the actual Gemini SDK call and handles all SDK-level exceptions.
        """
        t_start = time.time()
        try:
            self._log("INFO", req_id, "HTTP connection opening to Gemini API...")

            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt,
            )

            # Capability-driven generation config
            generation_config: dict = {}
            if self.supports_json_mode:
                generation_config["response_mime_type"] = "application/json"

            self._log("INFO", req_id, "Request sent to Gemini API. Awaiting response...")
            t_send = time.time()

            response = model.generate_content(
                user_prompt,
                generation_config=generation_config if generation_config else None,
                request_options={"timeout": GEMINI_READ_TIMEOUT_S},
            )


            t_recv = time.time()
            round_trip_ms = round((t_recv - t_send) * 1000)
            self._log("INFO", req_id, (
                f"Response received – round_trip={round_trip_ms}ms"
            ))

            # ── Validate response ────────────────────────────────────────
            if not response or not response.text:
                msg = f"Received empty/null response from Gemini API – model={self.model_name}."
                self._log("ERROR", req_id, msg)
                self.last_request_info["status"] = "empty_response"
                self._set_ctx_failure(ctx, "INVALID_PROVIDER_RESPONSE")
                self._emit_perf_summary(
                    req_id, t_start, round_trip_ms=round_trip_ms,
                    parse_ms=0, success=False,
                    failure_category="INVALID_PROVIDER_RESPONSE",
                )
                raise ValueError(msg)

            # ── Extract token usage ───────────────────────────────────────
            if response.usage_metadata:
                self.last_usage_metadata = {
                    "prompt_tokens": response.usage_metadata.prompt_token_count,
                    "completion_tokens": response.usage_metadata.candidates_token_count,
                    "total_tokens": (
                        (response.usage_metadata.prompt_token_count or 0)
                        + (response.usage_metadata.candidates_token_count or 0)
                    ),
                }

            # ── Parse / strip response text ──────────────────────────────
            t_parse_start = time.time()
            response_text = response.text.strip()
            parse_ms = round((time.time() - t_parse_start) * 1000)

            self.last_request_info["response_chars"] = len(response_text)
            self.last_request_info["status"] = "success"

            # ── Canonical performance summary ──────────────────────────
            self._emit_perf_summary(
                req_id, t_start,
                round_trip_ms=round_trip_ms,
                parse_ms=parse_ms,
                success=True,
                preview=response_text[:120].replace("\n", " "),
            )

            return response_text

        # ── Exception classification ─────────────────────────────────────
        except (google_exceptions.DeadlineExceeded,) as e:
            category = "PROVIDER_TIMEOUT"
            self._log("ERROR", req_id, f"Gemini DeadlineExceeded – model={self.model_name}: {e}")
            self.last_request_info["status"] = "deadline_exceeded"
            self.last_request_info["error"] = f"{type(e).__name__}: {e}"
            self._set_ctx_failure(ctx, category)
            self._emit_perf_summary(req_id, t_start, success=False, failure_category=category)
            raise TimeoutError(f"Gemini DeadlineExceeded: {e}") from e

        except (google_exceptions.ResourceExhausted,) as e:
            category = "RATE_LIMIT"
            self._log("ERROR", req_id, f"Gemini ResourceExhausted (rate limit) – model={self.model_name}: {e}")
            self.last_request_info["status"] = "rate_limited"
            self.last_request_info["error"] = f"{type(e).__name__}: {e}"
            self._set_ctx_failure(ctx, category)
            self._emit_perf_summary(req_id, t_start, success=False, failure_category=category)
            raise  # re-raise so retry logic in resource_manager detects it

        except (google_exceptions.ServiceUnavailable, google_exceptions.InternalServerError) as e:
            category = "CONNECTION_FAILURE"
            self._log("ERROR", req_id, f"Gemini service error – model={self.model_name}: {type(e).__name__}: {e}")
            self.last_request_info["status"] = "service_error"
            self.last_request_info["error"] = f"{type(e).__name__}: {e}"
            self._set_ctx_failure(ctx, category)
            self._emit_perf_summary(req_id, t_start, success=False, failure_category=category)
            raise

        except (TimeoutError, ConnectionError, OSError) as e:
            category = "NETWORK_TIMEOUT" if isinstance(e, TimeoutError) else "CONNECTION_FAILURE"
            self._log("ERROR", req_id, f"Network error – model={self.model_name}: {type(e).__name__}: {e}")
            self.last_request_info["status"] = "network_error"
            self.last_request_info["error"] = f"{type(e).__name__}: {e}"
            self._set_ctx_failure(ctx, category)
            self._emit_perf_summary(req_id, t_start, success=False, failure_category=category)
            raise

        except ValueError as e:
            # Empty/null response – perf summary already emitted above; re-raise
            raise

        except Exception as e:
            category = "UNKNOWN_PROVIDER_EXCEPTION"
            self._log("ERROR", req_id, (
                f"Unexpected exception in Gemini provider – "
                f"model={self.model_name} "
                f"error={type(e).__name__}: {e}"
            ))
            self.last_request_info["status"] = "error"
            self.last_request_info["error"] = f"{type(e).__name__}: {e}"
            self._set_ctx_failure(ctx, category)
            raise

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _emit_perf_summary(
        self,
        req_id: str,
        t_start: float,
        round_trip_ms: int = 0,
        parse_ms: int = 0,
        success: bool = True,
        failure_category: Optional[str] = None,
        preview: str = "",
    ) -> None:
        """
        Emits the canonical provider performance summary log.
        This is the single authoritative record for every Gemini API call.

        Format:
            [GEMINI PERF SUMMARY]
            Provider      : gemini
            Model         : gemini-2.5-flash
            Request ID    : [REQ:8F334252]
            Prompt Tokens : 1248
            Completion Tokens: 92
            Total Tokens  : 1340
            Round-Trip    : 1540 ms
            Parse Time    : 2 ms
            Total Time    : 1542 ms
            Status        : SUCCESS
        """
        um = self.last_usage_metadata or {}
        prompt_tokens = um.get("prompt_tokens", "?")
        completion_tokens = um.get("completion_tokens", "?")
        total_tokens = um.get("total_tokens", "?")
        total_ms = round((time.time() - t_start) * 1000)
        status_str = "SUCCESS" if success else f"FAILED [{failure_category or 'UNKNOWN'}]"
        preview_str = f"\n  Response Preview : {preview[:100]!r}" if preview else ""
        summary = (
            f"\n[GEMINI PERF SUMMARY]\n"
            f"  Provider         : gemini\n"
            f"  Model            : {self.model_name}\n"
            f"  Request ID       : {req_id}\n"
            f"  Prompt Tokens    : {prompt_tokens}\n"
            f"  Completion Tokens: {completion_tokens}\n"
            f"  Total Tokens     : {total_tokens}\n"
            f"  Round-Trip       : {round_trip_ms} ms\n"
            f"  Parse Time       : {parse_ms} ms\n"
            f"  Total Time       : {total_ms} ms\n"
            f"  Status           : {status_str}"
            f"{preview_str}"
        )
        self._log("INFO" if success else "ERROR", req_id, summary)

    def _set_ctx_failure(self, ctx: Optional["RequestContext"], category: str) -> None:
        """Set failure category on the context if available."""
        if ctx is not None:
            try:
                ctx.set_failure(category)
            except Exception:
                pass

    def _log(self, level: str, prefix: str, message: str) -> None:
        """Emit a log line. Falls back to print if main.log_message is unavailable."""
        try:
            from main import log_message
            log_message(level, f"{prefix} [Gemini] {message}")
        except ImportError:
            print(f"[{level}] {prefix} [Gemini] {message}")
