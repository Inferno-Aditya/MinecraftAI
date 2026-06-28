import json
from typing import List, Dict, Any, Optional
from backend.memory.models import GameplayEvent

def get_default_session_summary() -> dict:
    return {
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
        "source_event_uuids": [],
        "source_session_ids": []
    }

def process_events_for_session(existing_summary: Optional[dict], events: List[Dict[str, Any]], session_is_closed: bool = False) -> Dict[str, Any]:
    """
    Processes a list of raw timeline events for a single session and updates/returns the session summary.
    Includes memory confidence and provenance tracking.
    """
    summary = dict(existing_summary) if existing_summary else get_default_session_summary()
    
    event_uuids = set(summary.get("source_event_uuids", []))
    session_ids = set(summary.get("source_session_ids", []))
    
    # Sort events chronologically to process correctly
    events = sorted(events, key=lambda e: e.get("timestamp", ""))
    
    for evt in events:
        event_uuids.add(evt["event_uuid"])
        if evt["session_id"]:
            session_ids.add(evt["session_id"])
            
        et = evt["event_type"].lower()
        st = evt["subtype"].lower()
        data = evt["data"] or {}
        
        # 1. Combat
        if et == "combat":
            if st == "mob_killed":
                mob = data.get("mob_type") or data.get("name") or "unknown"
                summary["combat_kills"][mob] = summary["combat_kills"].get(mob, 0) + 1
                _add_activity(summary, "Defeated mob")
            elif st == "player_death":
                summary["deaths_count"] += 1
                _add_activity(summary, "Died")
            elif st == "player_damaged":
                summary["player_damaged_count"] += 1
                
        # 2. Mining & Building / Blocks
        elif et == "mining":
            if "ore_mined" in st:
                block = data.get("block_type") or data.get("ore_type") or "unknown"
                qty = int(data.get("quantity") or data.get("count") or 1)
                summary["resources_obtained"][block] = summary["resources_obtained"].get(block, 0) + qty
                _add_activity(summary, "Mined resources")
            elif "break" in st:
                block = data.get("block_type") or "unknown"
                qty = int(data.get("quantity") or data.get("count") or 1)
                summary["blocks_broken"][block] = summary["blocks_broken"].get(block, 0) + qty
                
        elif et == "building":
            if "place" in st:
                block = data.get("block_type") or "unknown"
                qty = int(data.get("quantity") or data.get("count") or 1)
                summary["blocks_placed"][block] = summary["blocks_placed"].get(block, 0) + qty
                _add_activity(summary, "Built structures")
            elif "break" in st:
                block = data.get("block_type") or "unknown"
                qty = int(data.get("quantity") or data.get("count") or 1)
                summary["blocks_broken"][block] = summary["blocks_broken"].get(block, 0) + qty
                
        # 3. Crafting
        elif et == "crafting":
            item = data.get("item_type") or "unknown"
            qty = int(data.get("quantity") or data.get("count") or 1)
            summary["resources_obtained"][item] = summary["resources_obtained"].get(item, 0) + qty
            _add_activity(summary, "Crafted items")
            
        # 4. Inventory
        elif et == "inventory":
            if "pickup" in st:
                item = data.get("item_type") or data.get("name") or "unknown"
                qty = int(data.get("quantity") or data.get("count") or 1)
                summary["resources_obtained"][item] = summary["resources_obtained"].get(item, 0) + qty
                
        # 5. Exploration
        elif et == "exploration":
            if st == "enter_biome":
                biome = data.get("biome_name") or "unknown"
                _add_activity(summary, f"Explored {biome} biome")
            elif st == "discover_structure":
                struct = data.get("structure_type") or "unknown"
                if struct not in summary["structures_discovered"]:
                    summary["structures_discovered"].append(struct)
                _add_activity(summary, f"Discovered {struct}")
                
        # 6. Villagers
        elif et == "villagers":
            if st == "trade":
                summary["trades_count"] += 1
                output_item = data.get("output_item") or "unknown"
                summary["resources_obtained"][output_item] = summary["resources_obtained"].get(output_item, 0) + int(data.get("output_count", 1))
                _add_activity(summary, "Traded with villagers")
            elif "cure" in st:
                _add_activity(summary, "Cured a zombie villager")
            elif "breed" in st:
                _add_activity(summary, "Bred villagers")
                
        # 7. Animals
        elif et == "animals":
            if st == "tame":
                animal = data.get("animal_type") or "unknown"
                summary["tamed_animals"][animal] = summary["tamed_animals"].get(animal, 0) + 1
                _add_activity(summary, f"Tamed a {animal}")
            elif st == "breed":
                _add_activity(summary, "Bred animals")
                
        # 8. Progression
        elif et == "progression":
            if st == "advancement":
                adv = data.get("advancement_id") or "unknown"
                if adv not in summary["progress_advancements"]:
                    summary["progress_advancements"].append(adv)
                _add_activity(summary, "Achieved progression")
                
    # Update duration from timestamps
    if events:
        try:
            # Simple duration estimation: diff between first and last event timestamps
            from datetime import datetime
            first_time = datetime.fromisoformat(events[0]["timestamp"].replace("Z", "+00:00"))
            last_time = datetime.fromisoformat(events[-1]["timestamp"].replace("Z", "+00:00"))
            duration = (last_time - first_time).total_seconds()
            summary["duration_seconds"] += max(0.0, duration)
        except Exception:
            pass
            
    summary["source_event_uuids"] = sorted(list(event_uuids))
    summary["source_session_ids"] = sorted(list(session_ids))
    
    # Confidence is 1.0 if closed, 0.8 if active/partial
    summary["confidence"] = 1.0 if session_is_closed else 0.8
    
    return summary

def _add_activity(summary: dict, activity: str) -> None:
    if activity not in summary["major_activities"]:
        summary["major_activities"].append(activity)
