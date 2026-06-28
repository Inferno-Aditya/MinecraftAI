import os
import json
import tempfile
import threading
from typing import Dict, Any

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "memory")
MEMORY_FILE = os.path.join(MEMORY_DIR, "memory.json")

_memory_lock = threading.RLock()

def load_memory() -> Dict[str, Any]:
    """
    Loads memory from the memory.json file.
    If the file does not exist, or is corrupted, it is automatically initialized
    with the default schema: {"locations": {}, "notes": {}, "preferences": {}}.
    """
    with _memory_lock:
        os.makedirs(MEMORY_DIR, exist_ok=True)
        if not os.path.exists(MEMORY_FILE):
            return init_memory()
        
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure top level structures exist and are dictionaries
                if not isinstance(data, dict):
                    raise ValueError("Memory root must be a JSON object.")
                for key in ["locations", "notes", "preferences"]:
                    if key not in data or not isinstance(data[key], dict):
                        data[key] = {}
                return data
        except Exception:
            # Recreate memory file if it is missing or corrupted
            return init_memory()

def init_memory() -> Dict[str, Any]:
    """Initializes a clean memory file with the default schema."""
    schema = {
        "locations": {},
        "notes": {},
        "preferences": {}
    }
    save_memory(schema)
    return schema

def save_memory(data: Dict[str, Any]) -> None:
    """
    Saves memory data to the memory.json file using an atomic write.
    The write is done first to a temporary file, which is then renamed
    to memory.json. The file is formatted with an indent of 4 spaces and UTF-8 encoding.
    """
    with _memory_lock:
        os.makedirs(MEMORY_DIR, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=MEMORY_DIR, prefix="memory_temp_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            # os.replace performs an atomic replace on Windows and Linux
            os.replace(temp_path, MEMORY_FILE)
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise e

def get_memory_summary() -> str:
    """
    Generates a concise summary of the locations and notes stored in memory.
    Designed to scale as memory grows.
    """
    try:
        mem = load_memory()
    except Exception:
        mem = {"locations": {}, "notes": {}, "preferences": {}}
        
    lines = []
    
    locations = list(mem.get("locations", {}).keys())
    if locations:
        lines.append("Known Locations:")
        for loc in sorted(locations):
            lines.append(f"- {loc}")
    else:
        lines.append("Known Locations: None")
        
    notes = mem.get("notes", {})
    if notes:
        lines.append("\nKnown Notes:")
        for key, val in sorted(notes.items()):
            lines.append(f"- {key}={val}")
    else:
        lines.append("\nKnown Notes: None")
        
    return "\n".join(lines)
