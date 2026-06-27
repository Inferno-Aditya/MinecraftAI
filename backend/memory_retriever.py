from typing import Dict, Any
try:
    from memory import load_memory
except ImportError:
    from .memory import load_memory

def retrieve_relevant_memory(message: str, required_memory: bool) -> str:
    """
    Retrieves only relevant memory entries matching keywords in the message.
    """
    if not required_memory:
        return ""
        
    mem = load_memory()
    message_lower = message.lower()
    
    retrieved_locations = {}
    retrieved_notes = {}
    retrieved_preferences = {}
    
    # Check locations
    for name, loc in mem.get("locations", {}).items():
        if name.lower() in message_lower:
            retrieved_locations[name] = loc
            
    # Check notes
    for key, val in mem.get("notes", {}).items():
        if key.lower() in message_lower:
            retrieved_notes[key] = val
            
    # Check preferences
    for key, val in mem.get("preferences", {}).items():
        if key.lower() in message_lower:
            retrieved_preferences[key] = val
            
    # Fallback to general list of names if intent was memory but no specific matches
    # but the user asked generic questions
    is_general_query = any(k in message_lower for k in ["list", "show", "all", "what", "where", "notes", "locations", "memory", "preferences"])
    if not retrieved_locations and not retrieved_notes and not retrieved_preferences and is_general_query:
        if mem.get("locations"):
            retrieved_locations = mem["locations"]
        if mem.get("notes"):
            retrieved_notes = mem["notes"]
        if mem.get("preferences"):
            retrieved_preferences = mem["preferences"]

    lines = []
    if retrieved_locations:
        lines.append("Memory Locations:")
        for name, loc in retrieved_locations.items():
            lines.append(f"- {name}: X={loc['x']:.1f}, Y={loc['y']:.1f}, Z={loc['z']:.1f} ({loc['dimension']})")
    if retrieved_notes:
        lines.append("Memory Notes:")
        for key, val in retrieved_notes.items():
            lines.append(f"- {key}: {val}")
    if retrieved_preferences:
        lines.append("Memory Preferences:")
        for key, val in retrieved_preferences.items():
            lines.append(f"- {key}: {val}")
            
    if not lines:
        return "None"
        
    return "\n".join(lines)
