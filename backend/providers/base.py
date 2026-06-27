from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from request_context import RequestContext


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All LLM providers (Gemini, Mock, etc.) must subclass this and implement
    the generate() method.

    The provider receives capability flags from the ModelProfile and is
    expected to adapt its behavior accordingly:
      - supports_json_mode: enforce structured JSON output (e.g. response_mime_type)
      - supports_tools:     include function-calling schemas when available

    Providers should use the optional RequestContext to emit stage-level logs
    that correlate with the upstream request.
    """

    # Capability flags – set by get_provider() factory from ModelProfile
    supports_json_mode: bool = True
    supports_tools: bool = True

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        ctx: Optional["RequestContext"] = None
    ) -> str:
        """
        Sends the system instruction and user prompt to the model
        and returns the raw text response.

        Args:
            system_prompt:  The system instruction / persona prompt.
            user_prompt:    The assembled user-facing prompt.
            ctx:            Optional RequestContext for tracing and diagnostics.

        Must raise exceptions on failure so the caller can handle them.
        """
        pass
