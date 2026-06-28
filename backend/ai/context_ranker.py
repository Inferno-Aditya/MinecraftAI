import datetime
import re
from typing import List, Dict, Any, Optional

def parse_timestamp(ts: Any) -> datetime.datetime:
    """
    Robustly parses standard ISO and SQLite timestamp strings/numeric inputs into UTC datetimes.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    if ts is None:
        return now
    if isinstance(ts, (int, float)):
        return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
    
    ts_str = str(ts).strip()
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    
    # Try ISO parsing
    try:
        dt = datetime.datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except ValueError:
        pass
        
    # Try standard SQL format YYYY-MM-DD HH:MM:SS
    try:
        dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        pass
        
    return now

def compute_memory_importance(memory: Dict[str, Any]) -> float:
    """
    Computes a deterministic importance score (0.0 to 1.0) based on content keywords.
    High value items, combat events, deaths, and bases increase importance.
    Basic blocks decrease importance.
    """
    text = str(memory.get("text_content", "")).lower()
    
    # Base importance
    importance = 0.5
    
    # High value / dramatic keywords
    high_keywords = [
        "diamond", "netherite", "elytra", "death", "died", "killed", 
        "portal", "wither", "dragon", "boss", "base", "spawn", 
        "advancement", "gold", "emerald", "ancient debris", "home"
    ]
    
    # Low value keywords
    low_keywords = [
        "cobblestone", "dirt", "stone", "gravel", "granite", "diorite", "andesite"
    ]
    
    high_matches = sum(1 for kw in high_keywords if kw in text)
    low_matches = sum(1 for kw in low_keywords if kw in text)
    
    importance += 0.1 * high_matches
    importance -= 0.1 * low_matches
    
    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, importance))

def rank_memories(
    memories: List[Dict[str, Any]],
    query: str,
    weights: Optional[Dict[str, float]] = None,
    now_utc: Optional[datetime.datetime] = None
) -> List[Dict[str, Any]]:
    """
    Deterministically ranks a list of retrieved memories based on combined signals:
    - Similarity (from vector search)
    - Confidence (from Memory Engine)
    - Importance (from content analysis)
    - Recency (age decay relative to the current time)
    
    Ties in score are broken deterministically by sorting alphabetically by memory_uuid.
    """
    if now_utc is None:
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        
    if weights is None:
        weights = {
            "similarity": 0.5,
            "confidence": 0.2,
            "importance": 0.1,
            "recency": 0.2
        }
        
    ranked_list = []
    
    for mem in memories:
        uuid = mem.get("memory_uuid", "")
        similarity = float(mem.get("similarity_score", 0.0))
        confidence = float(mem.get("confidence", 1.0))
        
        # Calculate Importance
        importance = compute_memory_importance(mem)
        
        # Calculate Recency
        last_updated = mem.get("last_updated") or mem.get("source_memory", {}).get("last_updated")
        dt_updated = parse_timestamp(last_updated)
        
        age_seconds = max(0.0, (now_utc - dt_updated).total_seconds())
        # Half life decay (1 day = 86400s)
        recency = 1.0 / (1.0 + age_seconds / 86400.0)
        
        # Combine signals
        score = (
            weights.get("similarity", 0.5) * similarity +
            weights.get("confidence", 0.2) * confidence +
            weights.get("importance", 0.1) * importance +
            weights.get("recency", 0.2) * recency
        )
        
        # Build ranked dict with breakdown for diagnostics
        ranked_mem = {
            **mem,
            "ranking_details": {
                "similarity_score": similarity,
                "confidence_score": confidence,
                "importance_score": importance,
                "recency_score": recency,
                "combined_score": score
            }
        }
        ranked_list.append(ranked_mem)
        
    # Strictly deterministic sorting:
    # 1. Combined score (descending)
    # 2. Memory UUID (ascending alphabetic) to resolve ties
    ranked_list.sort(
        key=lambda x: (-x["ranking_details"]["combined_score"], x.get("memory_uuid", ""))
    )
    
    return ranked_list
