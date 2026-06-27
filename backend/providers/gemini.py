import os
from typing import Optional, TYPE_CHECKING
import google.generativeai as genai
from dotenv import load_dotenv
from .base import BaseLLMProvider

if TYPE_CHECKING:
    from request_context import RequestContext


class GeminiProvider(BaseLLMProvider):
    """
    LLM provider implementation for Google Gemini / Google AI Studio.

    Behavior is driven by capability flags set by the factory:
      - supports_json_mode:  If True, enforces response_mime_type=application/json.
                             Gemma models and specialized models set this to False.
      - supports_tools:      Reserved for future function-calling schema injection.

    These flags are set externally by get_provider() after reading the
    active ModelProfile, so no model-specific conditions are needed here.
    """

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

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        ctx: Optional["RequestContext"] = None
    ) -> str:
        # Always reload API key in case it was set dynamically
        load_dotenv(override=True)
        self.api_key = os.getenv("GEMINI_API_KEY")

        req_id = ctx.prefix() if ctx else "[REQ:?]"

        if not self.api_key:
            msg = "GEMINI_API_KEY environment variable is missing. Please add it to your backend/.env file."
            self._log("ERROR", req_id, msg)
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
            f"Gemini request – model={self.model_name} "
            f"json_mode={self.supports_json_mode} "
            f"sys_chars={len(system_prompt)} user_chars={len(user_prompt)}"
        ))

        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt
            )

            # Capability-driven generation config
            # supports_json_mode=True  → enforce JSON output (all Gemini 2.x+ models)
            # supports_json_mode=False → plain text, rely on regex/retry JSON cleaning
            generation_config: dict = {}
            if self.supports_json_mode:
                generation_config["response_mime_type"] = "application/json"

            response = model.generate_content(
                user_prompt,
                generation_config=generation_config if generation_config else None,
                request_options={"timeout": 20.0}
            )

            if not response or not response.text:
                raise ValueError("Received empty response from Gemini API.")

            # Extract and store token usage
            if response.usage_metadata:
                self.last_usage_metadata = {
                    "prompt_tokens": response.usage_metadata.prompt_token_count,
                    "completion_tokens": response.usage_metadata.candidates_token_count
                }

            response_text = response.text.strip()
            self._log("INFO", req_id, (
                f"Gemini response OK – model={self.model_name} "
                f"chars={len(response_text)} "
                f"prompt_tokens={self.last_usage_metadata.get('prompt_tokens', '?') if self.last_usage_metadata else '?'} "
                f"completion_tokens={self.last_usage_metadata.get('completion_tokens', '?') if self.last_usage_metadata else '?'}"
            ))

            # Update diagnostics info with outcome
            self.last_request_info["response_chars"] = len(response_text)
            self.last_request_info["status"] = "success"

            return response_text

        except Exception as e:
            self.last_request_info["status"] = "error"
            self.last_request_info["error"] = f"{type(e).__name__}: {e}"
            self._log("ERROR", req_id, f"Gemini request failed – model={self.model_name} error={type(e).__name__}: {e}")
            raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log(self, level: str, prefix: str, message: str) -> None:
        """Emit a log line. Falls back to print if main.log_message is unavailable."""
        try:
            from main import log_message
            log_message(level, f"{prefix} [Gemini] {message}")
        except ImportError:
            print(f"[{level}] {prefix} [Gemini] {message}")
