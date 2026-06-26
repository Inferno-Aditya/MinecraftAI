from abc import ABC, abstractmethod

class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    All LLM providers (Gemini, OpenAI, Mock, etc.) must subclass this
    and implement the generate method.
    """

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        Sends the system instruction and user prompt to the model
        and returns the raw text response.
        
        Must handle errors internally or raise exceptions to be handled by the caller.
        """
        pass
