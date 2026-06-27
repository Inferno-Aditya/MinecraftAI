from .base import BaseLLMProvider
from .gemini import GeminiProvider
from .mock import MockProvider
from typing import Optional


def get_provider(
    provider_name: Optional[str] = None,
    model_name: Optional[str] = None
) -> BaseLLMProvider:
    """
    Factory function to retrieve an instance of the configured LLM provider.

    Reads the active ModelProfile from ModelManager and injects capability
    flags (supports_json_mode, supports_tools, supports_chat) into the
    provider instance.  This allows provider implementations to adapt their
    behavior based on the model's capabilities rather than hard-coding
    model-specific conditions.
    """
    try:
        from model_manager import model_manager
    except ImportError:
        from ..model_manager import model_manager

    p_name = (provider_name or model_manager.get_active_provider()).lower().strip()
    m_name = model_name or model_manager.get_active_model()

    # Resolve ModelProfile to extract capability flags
    all_models = model_manager.get_supported_models()
    profile = all_models.get(m_name)

    if p_name == "gemini":
        provider = GeminiProvider(model_name=m_name)
        if profile:
            provider.supports_json_mode = profile.supports_json_mode
            provider.supports_tools = profile.supports_tools
        return provider

    elif p_name == "mock":
        provider = MockProvider(model_name=m_name)
        # Mock always supports all modes
        provider.supports_json_mode = True
        provider.supports_tools = True
        return provider

    else:
        raise ValueError(f"Unsupported LLM provider: '{p_name}'")
