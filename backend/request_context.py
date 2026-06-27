"""
request_context.py – Lightweight per-request tracing context.

A RequestContext is created once at the entry point of every chat request
and propagated through the entire pipeline:
    chat_endpoint → plan() → execute_llm_request_with_rate_limits()
                          → ResponseGenerator.generate_response()
                          → UsageTracker.record_request()

All logs, timings, exceptions, and telemetry reference the same request_id
so that a single request can be traced end-to-end in the log file.
"""

import uuid
import time
from typing import Any, Dict, List, Optional


class StageTimer:
    """
    Records start/end timestamps for a named pipeline stage.
    """
    def __init__(self, name: str):
        self.name: str = name
        self.start_ts: float = time.time()
        self.end_ts: Optional[float] = None
        self.error: Optional[str] = None

    def finish(self, error: Optional[str] = None) -> None:
        self.end_ts = time.time()
        self.error = error

    @property
    def elapsed_ms(self) -> float:
        end = self.end_ts if self.end_ts is not None else time.time()
        return round((end - self.start_ts) * 1000, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.name,
            "elapsed_ms": self.elapsed_ms,
            "error": self.error
        }


class RequestContext:
    """
    Lightweight context object created once per chat request.

    Carries:
    - request_id:       Unique short ID (8-char hex) for log correlation
    - user_message:     The original user message
    - stage_timers:     Ordered list of StageTimer entries for each pipeline stage
    - last_exception:   The last exception message that occurred in this request
    - provider_name:    Resolved provider name
    - model_name:       Resolved model name
    - last_payload:     Sanitized provider request payload (no API keys)
    - response_status:  HTTP-equivalent outcome ('success', '429', '500', etc.)
    - response_time_ms: End-to-end latency from request received to response sent
    - plan_strategy:    The ResponseStrategy chosen by the planner
    - tool_calls_made:  Names of tool calls executed in this request
    """

    def __init__(self, user_message: str = ""):
        self.request_id: str = uuid.uuid4().hex[:8].upper()
        self.user_message: str = user_message
        self.created_at: float = time.time()

        # Pipeline stage timers (in execution order)
        self._stage_timers: List[StageTimer] = []
        self._active_timer: Optional[StageTimer] = None

        # Outcome tracking
        self.last_exception: Optional[str] = None
        self.last_exception_type: Optional[str] = None
        self.response_status: str = "pending"   # 'success' | 'error' | 'rate_limited'
        self.response_time_ms: float = 0.0

        # Resolution info
        self.provider_name: str = ""
        self.model_name: str = ""
        self.plan_strategy: str = ""
        self.tool_calls_made: List[str] = []

        # Provider payload (sanitized – no API keys)
        self.last_payload: Dict[str, Any] = {}

        # Token metrics
        self.input_tokens: int = 0
        self.output_tokens: int = 0

        # Tool execution metrics
        self.last_executed_tool: Optional[str] = None
        self.tool_execution_time_ms: Optional[float] = None
        self.tool_status: Optional[str] = None
        self.tool_output: Optional[str] = None
        self.tool_exception: Optional[str] = None
        
        # Planner Validation & Explainability Diagnostics (v0.4.8)
        self.planner_override: Optional[Dict[str, Any]] = None
        self.dev_warnings: List[str] = []
        self.decision_reasoning: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------ #
    # Stage timing API                                                     #
    # ------------------------------------------------------------------ #

    def begin_stage(self, name: str) -> StageTimer:
        """Start a new named stage timer and return it."""
        timer = StageTimer(name)
        self._stage_timers.append(timer)
        self._active_timer = timer
        return timer

    def end_stage(self, error: Optional[str] = None) -> Optional[StageTimer]:
        """Finish the most recently started stage timer."""
        if self._active_timer:
            self._active_timer.finish(error=error)
            finished = self._active_timer
            self._active_timer = None
            return finished
        return None

    def record_exception(self, exc: Exception) -> None:
        """Record the last exception on this context."""
        self.last_exception = str(exc)
        self.last_exception_type = type(exc).__name__
        if self._active_timer:
            self._active_timer.finish(error=self.last_exception)
            self._active_timer = None

    def finalize(self, status: str = "success") -> None:
        """Mark the request as finalized and compute end-to-end latency."""
        self.response_status = status
        self.response_time_ms = round((time.time() - self.created_at) * 1000, 2)
        # Close any still-open stage timer
        if self._active_timer:
            self._active_timer.finish()
            self._active_timer = None

    # ------------------------------------------------------------------ #
    # Serialization                                                        #
    # ------------------------------------------------------------------ #

    def get_stage_timings(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._stage_timers]

    def to_diagnostics_dict(self) -> Dict[str, Any]:
        """Return a dict suitable for the /api/diagnostics endpoint."""
        return {
            "request_id": self.request_id,
            "user_message": self.user_message[:120] + ("…" if len(self.user_message) > 120 else ""),
            "provider_name": self.provider_name,
            "model_name": self.model_name,
            "plan_strategy": self.plan_strategy,
            "tool_calls_made": self.tool_calls_made,
            "response_status": self.response_status,
            "response_time_ms": self.response_time_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "last_exception": self.last_exception,
            "last_exception_type": self.last_exception_type,
            "last_payload": self.last_payload,
            "stage_timings": self.get_stage_timings(),
            "last_executed_tool": self.last_executed_tool,
            "tool_execution_time_ms": self.tool_execution_time_ms,
            "tool_status": self.tool_status,
            "tool_output": self.tool_output,
            "tool_exception": self.tool_exception,
            "planner_override": self.planner_override,
            "dev_warnings": self.dev_warnings,
            "decision_reasoning": self.decision_reasoning,
        }

    def prefix(self) -> str:
        """Short log prefix for consistent log line tagging."""
        return f"[REQ:{self.request_id}]"
