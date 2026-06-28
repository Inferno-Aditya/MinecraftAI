from typing import List, Dict, Any

def format_memory_entry(memory: Dict[str, Any]) -> str:
    """
    Formats a single memory dictionary into a concise, human-readable line.
    """
    m_type = str(memory.get("memory_type", "")).lower()
    text = str(memory.get("text_content", "")).strip()
    confidence = memory.get("confidence", 1.0)
    
    # Capitalize the memory type for readability
    label = m_type.upper()
    if label == "DAILY":
        label = "DAILY SUMMARY"
    elif label == "SESSION":
        label = "SESSION SUMMARY"
        
    return f"- [{label}] {text} (Confidence: {confidence:.2f})"

def format_memories_by_category(memories: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Groups a list of memories into three distinct prompt sections:
    1. Long-Term Facts (Facts)
    2. Relevant Episodic Memories (Episodes)
    3. Recent Session Context (Sessions/Daily summaries)
    
    Returns a dictionary of category keys to formatted string paragraphs.
    """
    facts_lines = []
    episodes_lines = []
    sessions_lines = []
    
    for mem in memories:
        m_type = str(mem.get("memory_type", "")).lower()
        formatted = format_memory_entry(mem)
        
        if m_type == "fact":
            facts_lines.append(formatted)
        elif m_type == "episode":
            episodes_lines.append(formatted)
        elif m_type in ("session", "daily"):
            sessions_lines.append(formatted)
            
    return {
        "long_term_facts": "\n".join(facts_lines) if facts_lines else "None",
        "relevant_episodes": "\n".join(episodes_lines) if episodes_lines else "None",
        "recent_sessions": "\n".join(sessions_lines) if sessions_lines else "None"
    }
