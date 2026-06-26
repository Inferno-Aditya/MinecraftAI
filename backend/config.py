import os
import json

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

def load_config() -> dict:
    """
    Loads runtime configuration from config.json.
    Falls back to default Gemini configuration if missing or invalid.
    """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                if isinstance(config, dict):
                    return config
        except Exception:
            pass
            
    return {
        "provider": "gemini",
        "model": "gemini-2.5-flash"
    }
