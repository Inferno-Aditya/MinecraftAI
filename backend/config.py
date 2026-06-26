import os
import json
from dotenv import load_dotenv

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")

DEFAULT_CONFIG = {
    "provider": "gemini",
    "model": "gemini-2.5-flash",
    "temperature": 0.7,
    "max_tokens": 2048,
    "timeout": 15.0,
    "providers": {
        "gemini": {
            "rate_limits": {
                "requests_per_minute": 15,
                "tokens_per_minute": 1000000,
                "requests_per_day": 1500
            }
        },
        "mock": {
            "rate_limits": {
                "requests_per_minute": 60,
                "tokens_per_minute": 10000000,
                "requests_per_day": 86400
            }
        }
    }
}

def load_config() -> dict:
    """
    Loads runtime configuration from config.json.
    Merges with DEFAULT_CONFIG to ensure all keys are present.
    """
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    # Deep merge or key-level override
                    for key, val in loaded.items():
                        if key == "providers" and isinstance(val, dict):
                            if "providers" not in config:
                                config["providers"] = {}
                            for p_name, p_val in val.items():
                                if isinstance(p_val, dict):
                                    if p_name not in config["providers"]:
                                        config["providers"][p_name] = {}
                                    config["providers"][p_name].update(p_val)
                        else:
                            config[key] = val
        except Exception:
            pass
            
    return config

def save_config(config_data: dict) -> None:
    """
    Saves runtime configuration to config.json.
    """
    # Merge existing to preserve unedited keys
    current = load_config()
    for key, val in config_data.items():
        if key == "providers" and isinstance(val, dict):
            for p_name, p_val in val.items():
                if p_name not in current["providers"]:
                    current["providers"][p_name] = {}
                current["providers"][p_name].update(p_val)
        else:
            current[key] = val
            
    # Clean out sensitive info if somehow passed
    current.pop("gemini_api_key", None)
            
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=4, ensure_ascii=False)
    except Exception as e:
        raise IOError(f"Failed to save config: {e}")

def save_api_key(api_key: str) -> None:
    """
    Saves the API key securely to the backend/.env file, preserving other lines.
    """
    lines = []
    key_exists = False
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            pass
            
    new_lines = []
    for line in lines:
        if line.strip().startswith("GEMINI_API_KEY="):
            new_lines.append(f"GEMINI_API_KEY={api_key}\n")
            key_exists = True
        else:
            new_lines.append(line)
            
    if not key_exists:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] = new_lines[-1] + "\n"
        new_lines.append(f"GEMINI_API_KEY={api_key}\n")
        
    try:
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        # Force reload dotenv in the running process
        load_dotenv(ENV_FILE, override=True)
    except Exception as e:
        raise IOError(f"Failed to save API key to .env: {e}")

