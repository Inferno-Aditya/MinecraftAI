from typing import List, Dict, Any

def merge_session_summaries_into_daily(session_summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merges multiple session summaries from the same day into a single, unified daily summary.
    Computes daily confidence and tracks provenance (source session IDs).
    """
    daily = {
        "duration_seconds": 0.0,
        "major_activities": [],
        "structures_discovered": [],
        "resources_obtained": {},
        "combat_kills": {},
        "player_damaged_count": 0,
        "deaths_count": 0,
        "progress_advancements": [],
        "blocks_placed": {},
        "blocks_broken": {},
        "trades_count": 0,
        "tamed_animals": {},
        "source_session_ids": []
    }
    
    if not session_summaries:
        daily["confidence"] = 0.0
        return daily
        
    activities_set = set()
    structures_set = set()
    advancements_set = set()
    session_ids = set()
    total_confidence = 0.0
    
    for summary in session_summaries:
        daily["duration_seconds"] += summary.get("duration_seconds", 0.0)
        daily["player_damaged_count"] += summary.get("player_damaged_count", 0)
        daily["deaths_count"] += summary.get("deaths_count", 0)
        daily["trades_count"] += summary.get("trades_count", 0)
        
        # Merge sets
        activities_set.update(summary.get("major_activities", []))
        structures_set.update(summary.get("structures_discovered", []))
        advancements_set.update(summary.get("progress_advancements", []))
        
        # Merge dictionary counts
        _merge_counts(daily["resources_obtained"], summary.get("resources_obtained", {}))
        _merge_counts(daily["combat_kills"], summary.get("combat_kills", {}))
        _merge_counts(daily["blocks_placed"], summary.get("blocks_placed", {}))
        _merge_counts(daily["blocks_broken"], summary.get("blocks_broken", {}))
        _merge_counts(daily["tamed_animals"], summary.get("tamed_animals", {}))
        
        # Track session ID provenance
        if "source_session_ids" in summary:
            session_ids.update(summary["source_session_ids"])
            
        total_confidence += summary.get("confidence", 1.0)
        
    # Convert sets to sorted lists for determinism
    daily["major_activities"] = sorted(list(activities_set))
    daily["structures_discovered"] = sorted(list(structures_set))
    daily["progress_advancements"] = sorted(list(advancements_set))
    daily["source_session_ids"] = sorted(list(session_ids))
    
    # Average confidence score
    daily["confidence"] = round(total_confidence / len(session_summaries), 2)
    
    return daily

def _merge_counts(target: dict, source: dict) -> None:
    for k, v in source.items():
        target[k] = target.get(k, 0) + v
