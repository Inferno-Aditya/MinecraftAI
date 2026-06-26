from .base import BaseLLMProvider
from .gemini import GeminiProvider
from .mock import MockProvider

def get_provider(provider_name: str, model_name: str) -> BaseLLMProvider:
    """
    Factory function to retrieve an instance of the configured LLM provider.
    """
    p_name = provider_name.lower().strip()
    if p_name == "gemini":
        return GeminiProvider(model_name=model_name)
    elif p_name == "mock":
        return MockProvider(model_name=model_name)
    else:
        raise ValueError(f"Unsupported LLM provider: '{provider_name}'")
