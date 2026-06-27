import os
import json
import time
import datetime
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

MODELS_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "models_config.json")
DISCOVERED_CACHE_FILE = os.path.join(os.path.dirname(__file__), "discovered_models_cache.json")

# ---------------------------------------------------------------------------
# Model-filtering heuristics
# ---------------------------------------------------------------------------
# Patterns in model IDs/names that identify non-chat models that should be
# hidden from the model selection UI.  They remain in the internal registry
# (for diagnostics) but are NOT presented to the user.
_EXCLUDED_MODEL_ID_PATTERNS: List[str] = [
    r"-tts",          # Text-to-speech models
    r"-image",        # Image generation models
    r"lyria-",        # Music / audio generation (Lyria)
    r"deep-research", # Agentic deep research (not chat)
    r"-robotics-",    # Robotics-specific models
    r"computer-use",  # Computer-use agentic models
    r"nano-banana",   # Internal codename image models
    r"antigravity-",  # Internal codename agent preview
]

def _is_hidden_model(model_id: str, model_name: str = "") -> bool:
    """
    Returns True if the model should be hidden from the selection UI.
    Uses model_id (canonical) and optionally the display name for matching.
    """
    target = (model_id + " " + model_name).lower()
    return any(re.search(pattern, target) for pattern in _EXCLUDED_MODEL_ID_PATTERNS)


def _infer_capabilities(model_id: str, model_name: str, description: str) -> Dict[str, bool]:
    """
    Infers capability flags from model metadata.

    Returns:
        supports_chat:      True if model can generate conversational text
        supports_tools:     True if model supports function-calling / tool schemas
        supports_json_mode: True if model reliably supports response_mime_type=application/json
    """
    mid = model_id.lower()
    mname = model_name.lower()
    mdesc = description.lower()

    # Default: full chat + tools + JSON mode
    supports_chat = True
    supports_tools = True
    supports_json_mode = True

    # TTS models: no chat, no tools, no JSON
    if re.search(r"-tts", mid):
        supports_chat = False
        supports_tools = False
        supports_json_mode = False

    # Image-generation models
    elif re.search(r"-image", mid) or "nano banana" in mname:
        supports_chat = False
        supports_tools = False
        supports_json_mode = False

    # Music / audio generation
    elif re.search(r"lyria-", mid):
        supports_chat = False
        supports_tools = False
        supports_json_mode = False

    # Deep Research / Agentic models: chat-like but no tool schemas
    elif re.search(r"deep-research", mid):
        supports_tools = False
        supports_json_mode = False

    # Robotics / computer-use: may not support JSON mode reliably
    elif re.search(r"-robotics-|computer-use", mid):
        supports_tools = False
        supports_json_mode = False

    # Gemma models: support chat but JSON mode is best-effort (not guaranteed)
    elif re.search(r"^gemma-", mid):
        supports_json_mode = False   # Gemma does not guarantee structured JSON output

    return {
        "supports_chat": supports_chat,
        "supports_tools": supports_tools,
        "supports_json_mode": supports_json_mode,
    }


class ModelProfile(BaseModel):
    """
    Encapsulates static metadata, runtime limits, and capability flags for a model.
    """
    model_id: str = Field(..., description="Unique normalized model identifier, e.g. gemini-2.5-flash")
    name: str = Field(..., description="User-friendly model name")
    provider: str = Field(..., description="Provider ID, e.g. gemini, mock")
    description: str = Field(default="", description="Model description")
    rpm: int = Field(default=15, description="Requests per minute limit")
    rpd: int = Field(default=1500, description="Requests per day limit")
    context_window: int = Field(default=1000000, description="Context window token size")
    output_token_limit: int = Field(default=8192, description="Output token limit")
    recommended_usage: str = Field(default="", description="Recommended usage note")

    # Capability flags (capability-driven provider behavior)
    supports_chat: bool = Field(default=True, description="True if model can generate conversational text")
    supports_tools: bool = Field(default=True, description="True if model supports tool/function-calling schemas")
    supports_json_mode: bool = Field(default=True, description="True if model reliably supports JSON output mode")

    # UI flags
    recommended: bool = Field(default=False, description="True if marked as recommended for project tasks")
    badge: str = Field(default="", description="UI badge, e.g. Recommended, Default, Advanced")
    icon: str = Field(default="", description="UI icon emoji")
    is_hidden: bool = Field(default=False, description="True if model is hidden from UI (non-chat models)")

    # Discovery metadata
    last_sync_time: str = Field(default="", description="ISO timestamp of last successful model list sync")
    discovery_source: str = Field(default="hardcoded", description="'api', 'cache', or 'hardcoded'")


class ModelManager:
    """
    Central manager for dynamic model discovery, hybrid metadata merging,
    and active model selection.  Acts as the single source of truth for
    the AI companion model registries.
    """
    _instance: Optional['ModelManager'] = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ModelManager, cls).__new__(cls, *args, **kwargs)
            cls._instance._init_manager()
        return cls._instance

    def _init_manager(self):
        self.supported_models: Dict[str, ModelProfile] = {}
        self.last_sync_time: str = ""
        self.sync_warning: Optional[str] = None
        self.discovery_source: str = "hardcoded"

        self.load_models_config()
        self.discover_models(force=False)

    def load_models_config(self):
        """Loads static metadata and default model identifier from models_config.json."""
        if os.path.exists(MODELS_CONFIG_FILE):
            try:
                with open(MODELS_CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.models_config_data = json.load(f)
            except Exception:
                self.models_config_data = {}
        else:
            self.models_config_data = {}

        self.default_model_id = self.models_config_data.get("default_model", "gemma-4-31b-it")
        self.metadata = self.models_config_data.get("metadata", {})

    def get_default_model_id(self) -> str:
        return self.default_model_id

    def get_active_model(self) -> str:
        """Loads the active model identifier from system configuration, falling back to default."""
        try:
            from config import load_config, CONFIG_FILE
        except ImportError:
            from .config import load_config, CONFIG_FILE

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "model" in data:
                        return data["model"]
            except Exception:
                pass
        return self.get_default_model_id()

    def get_active_provider(self) -> str:
        """Loads the active provider identifier from configuration, matching the active model."""
        active_id = self.get_active_model()
        models = self.get_supported_models()
        if active_id in models:
            return models[active_id].provider
        return "gemini"

    def get_active_model_profile(self) -> ModelProfile:
        """Returns the ModelProfile representing the active model."""
        active_id = self.get_active_model()
        models = self.get_supported_models()
        if active_id in models:
            return models[active_id]

        # Fallback profile – infer capabilities from model ID
        caps = _infer_capabilities(active_id, active_id, "")
        return ModelProfile(
            model_id=active_id,
            name=active_id.replace("-", " ").title(),
            provider="gemini",
            description="Fallback model",
            rpm=15,
            rpd=1500,
            context_window=1000000,
            output_token_limit=8192,
            recommended_usage="Generic fallback",
            supports_chat=caps["supports_chat"],
            supports_tools=caps["supports_tools"],
            supports_json_mode=caps["supports_json_mode"],
            discovery_source="hardcoded"
        )

    def get_supported_models(self) -> Dict[str, ModelProfile]:
        """Returns the dictionary of fully merged runtime ModelProfiles (ALL models, including hidden)."""
        return self.supported_models

    def get_selectable_models(self) -> Dict[str, ModelProfile]:
        """Returns only models that should be shown in the UI (supports_chat=True, is_hidden=False)."""
        return {
            m_id: m for m_id, m in self.supported_models.items()
            if not m.is_hidden and m.supports_chat
        }

    def validate_model(self, model_id: str) -> bool:
        """Checks if model_id is supported in the merged registry."""
        return model_id in self.get_supported_models()

    def discover_models(self, force: bool = False) -> Dict[str, Any]:
        """
        Discovers Google AI Studio models from the live API (if force=True or cache is missing).
        Gracefully falls back to local cache or hardcoded default models.
        Merges immutable discovered model metadata with local models_config.json metadata.
        Applies capability inference and hidden-model flags.
        """
        from dotenv import load_dotenv
        load_dotenv(override=True)
        api_key = os.getenv("GEMINI_API_KEY")

        discovered_raw = []
        sync_success = False
        current_discovery_source = "hardcoded"
        self.sync_warning = None

        # 1. Live API Discovery
        if api_key and (force or not os.path.exists(DISCOVERED_CACHE_FILE)):
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)

                api_models = genai.list_models()
                for m in api_models:
                    methods = getattr(m, "supported_generation_methods", [])
                    if "generateContent" in methods:
                        m_id = m.name.replace("models/", "")
                        m_name = m.display_name or m_id
                        m_desc = m.description or ""

                        caps = _infer_capabilities(m_id, m_name, m_desc)
                        discovered_raw.append({
                            "model_id": m_id,
                            "name": m_name,
                            "provider": "gemini",
                            "description": m_desc,
                            "rpm": 15 if "pro" in m_id else 30,
                            "rpd": 1500 if "pro" in m_id else 4000,
                            "context_window": getattr(m, "input_token_limit", 1000000),
                            "output_token_limit": getattr(m, "output_token_limit", 8192),
                            "supports_chat": caps["supports_chat"],
                            "supports_tools": caps["supports_tools"],
                            "supports_json_mode": caps["supports_json_mode"],
                            "discovery_source": "api"
                        })

                cache_data = {
                    "last_sync_time": datetime.datetime.utcnow().isoformat() + "Z",
                    "discovered_models": discovered_raw
                }
                with open(DISCOVERED_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(cache_data, f, indent=4, ensure_ascii=False)

                sync_success = True
                current_discovery_source = "api"
            except Exception as e:
                self.sync_warning = f"Live model discovery failed: {e}. Falling back to cached registry."

        # 2. Cache Load Fallback
        if not sync_success:
            if os.path.exists(DISCOVERED_CACHE_FILE):
                try:
                    with open(DISCOVERED_CACHE_FILE, "r", encoding="utf-8") as f:
                        cache_data = json.load(f)
                        discovered_raw = cache_data.get("discovered_models", [])
                        self.last_sync_time = cache_data.get("last_sync_time", "")
                    current_discovery_source = "cache"
                except Exception:
                    pass

        # 3. Hardcoded Fallbacks
        if not discovered_raw:
            current_discovery_source = "hardcoded"
            discovered_raw = [
                {
                    "model_id": "gemini-2.5-flash",
                    "name": "Gemini 2.5 Flash",
                    "provider": "gemini",
                    "description": "Standard balanced model providing high-quality reasoning and low latency.",
                    "rpm": 30, "rpd": 4000,
                    "context_window": 1048576, "output_token_limit": 65536,
                    "supports_chat": True, "supports_tools": True, "supports_json_mode": True,
                    "discovery_source": "hardcoded"
                },
                {
                    "model_id": "gemini-2.5-flash-lite",
                    "name": "Gemini 2.5 Flash Lite",
                    "provider": "gemini",
                    "description": "Ultra-lightweight, extremely fast model optimized for high frequency tasks.",
                    "rpm": 30, "rpd": 4000,
                    "context_window": 1048576, "output_token_limit": 65536,
                    "supports_chat": True, "supports_tools": True, "supports_json_mode": True,
                    "discovery_source": "hardcoded"
                },
                {
                    "model_id": "gemma-4-31b-it",
                    "name": "Gemma 4 32B",
                    "provider": "gemini",
                    "description": "State-of-the-art open weights model hosted on Google AI Studio.",
                    "rpm": 30, "rpd": 4000,
                    "context_window": 262144, "output_token_limit": 32768,
                    "supports_chat": True, "supports_tools": True, "supports_json_mode": False,
                    "discovery_source": "hardcoded"
                }
            ]
            if not self.last_sync_time:
                self.last_sync_time = "Never (Bootstrapped defaults)"
        else:
            if sync_success:
                self.last_sync_time = datetime.datetime.utcnow().isoformat() + "Z"

        self.discovery_source = current_discovery_source

        # 4. Hybrid Merging – discovered metadata + local project metadata
        self.load_models_config()
        new_supported = {}

        for item in discovered_raw:
            m_id = item["model_id"]
            meta = self.metadata.get(m_id, {})

            # Re-infer capabilities (in case cache was built before this logic existed)
            caps = _infer_capabilities(
                m_id,
                item.get("name", m_id),
                item.get("description", "")
            )
            # Allow cache to override if it has explicit flags
            supports_chat = item.get("supports_chat", caps["supports_chat"])
            supports_tools = item.get("supports_tools", caps["supports_tools"])
            supports_json_mode = item.get("supports_json_mode", caps["supports_json_mode"])

            is_hidden = _is_hidden_model(m_id, item.get("name", ""))

            item_discovery_source = item.get("discovery_source", current_discovery_source)

            merged_profile = ModelProfile(
                model_id=m_id,
                name=meta.get("name") or item["name"],
                provider=item["provider"],
                description=meta.get("description") or item["description"],
                rpm=item["rpm"],
                rpd=item["rpd"],
                context_window=item["context_window"],
                output_token_limit=item["output_token_limit"],
                recommended_usage=meta.get("recommended_usage") or "",
                supports_chat=supports_chat,
                supports_tools=supports_tools,
                supports_json_mode=supports_json_mode,
                recommended=meta.get("recommended", False) or (m_id == self.default_model_id),
                badge=meta.get("badge", ""),
                icon=meta.get("icon", ""),
                is_hidden=is_hidden,
                last_sync_time=self.last_sync_time,
                discovery_source=item_discovery_source
            )
            new_supported[m_id] = merged_profile

        # 4.5 Merge any other models defined in models_config.json that were not in discovered_raw
        if not force:
            for m_id, meta in self.metadata.items():
                if m_id not in new_supported and m_id != "mock-model":
                    caps = _infer_capabilities(m_id, meta.get("name", m_id), meta.get("description", ""))
                    new_supported[m_id] = ModelProfile(
                        model_id=m_id,
                        name=meta.get("name") or m_id,
                        provider=meta.get("provider") or "gemini",
                        description=meta.get("description") or "Local configuration override model.",
                        rpm=meta.get("rpm") or 15,
                        rpd=meta.get("rpd") or 1500,
                        context_window=meta.get("context_window") or 1048576,
                        output_token_limit=meta.get("output_token_limit") or 8192,
                        recommended_usage=meta.get("recommended_usage") or "",
                        supports_chat=meta.get("supports_chat", caps["supports_chat"]),
                        supports_tools=meta.get("supports_tools", caps["supports_tools"]),
                        supports_json_mode=meta.get("supports_json_mode", caps["supports_json_mode"]),
                        recommended=meta.get("recommended", False) or (m_id == self.default_model_id),
                        badge=meta.get("badge", ""),
                        icon=meta.get("icon", ""),
                        is_hidden=meta.get("is_hidden") or _is_hidden_model(m_id, meta.get("name", "")),
                        last_sync_time=self.last_sync_time,
                        discovery_source="hardcoded"
                    )

        # Add local mock-model manually
        mock_meta = self.metadata.get("mock-model", {})
        new_supported["mock-model"] = ModelProfile(
            model_id="mock-model",
            name=mock_meta.get("name") or "Mock Model (Testing)",
            provider="mock",
            description=mock_meta.get("description") or "Local mock model for offline development and debugging.",
            rpm=60, rpd=86400,
            context_window=32768, output_token_limit=4096,
            recommended_usage=mock_meta.get("recommended_usage") or "Offline debugging and rate limit testing",
            supports_chat=True,
            supports_tools=True,
            supports_json_mode=True,
            recommended=mock_meta.get("recommended", False),
            badge=mock_meta.get("badge", "Mock"),
            icon=mock_meta.get("icon", "🛠️"),
            is_hidden=False,
            last_sync_time=self.last_sync_time,
            discovery_source="hardcoded"
        )

        self.supported_models = new_supported

        # 5. Gracefully switch active model if removed
        active_changed = False
        active_id = self.get_active_model()
        if active_id not in self.supported_models:
            fallback_id = self.get_default_model_id()
            self.set_active_model(fallback_id)
            active_changed = True
            self.sync_warning = (
                f"The previously selected model '{active_id}' is no longer available. "
                f"The active model has been set to the default model: '{fallback_id}'."
            )

        return {
            "status": "success",
            "active_model_changed": active_changed,
            "warning": self.sync_warning,
            "last_sync_time": self.last_sync_time,
            "discovery_source": self.discovery_source
        }

    def set_active_model(self, model_id: str) -> bool:
        """
        Sets the active model in system configuration (hot-reloads configuration).
        Updates rate limits dynamically.
        """
        if not self.validate_model(model_id):
            return False

        try:
            from config import load_config, save_config
        except ImportError:
            from .config import load_config, save_config

        model_info = self.get_supported_models()[model_id]

        sys_config = load_config()
        sys_config["model"] = model_id
        sys_config["provider"] = model_info.provider

        provider = model_info.provider
        if "providers" not in sys_config:
            sys_config["providers"] = {}
        if provider not in sys_config["providers"]:
            sys_config["providers"][provider] = {}

        sys_config["providers"][provider]["rate_limits"] = {
            "requests_per_minute": model_info.rpm,
            "tokens_per_minute": 1000000,
            "requests_per_day": model_info.rpd
        }

        save_config(sys_config)
        return True


# Instantiate global singleton
model_manager = ModelManager()
