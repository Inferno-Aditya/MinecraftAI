import sqlite3
import json
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

def get_episode_type(event_type: str, subtype: str, data: dict) -> Optional[str]:
    """Maps a raw event type/subtype to a logical episode category."""
    et = event_type.lower()
    st = subtype.lower()
    
    if et == "mining" or (et == "building" and "break_streak" in st):
        # We categorize underground mining or streak breaking as Mining Expedition
        return "Mining Expedition"
    elif et == "villagers":
        return "Village Project"
    elif et == "combat":
        return "Combat Skirmish"
    elif et == "building":
        return "Building Project"
    elif et == "exploration":
        return "Exploration Tour"
    return None

def get_temporal_threshold(episode_type: str) -> float:
    """Returns inactivity gap threshold in seconds for merging events into episodes."""
    if episode_type == "Combat Skirmish":
        return 120.0 # 2 minutes
    return 300.0 # 5 minutes

def init_episode_summary(episode_type: str, evt: Dict[str, Any]) -> Dict[str, Any]:
    """Initializes structured summary data for a new episode."""
    summary = {
        "mobs_defeated": {},
        "deaths": 0,
        "resources_obtained": {},
        "blocks_placed": {},
        "blocks_broken": {},
        "biomes_visited": [],
        "structures_discovered": [],
        "villager_actions": {"trades": 0, "cured": 0, "bred": 0},
        "description": f"Started {episode_type}"
    }
    _update_summary_with_event(summary, episode_type, evt)
    return summary

def _update_summary_with_event(summary: dict, episode_type: str, evt: Dict[str, Any]) -> None:
    """Updates the episode summary with details from a new event."""
    et = evt["event_type"].lower()
    st = evt["subtype"].lower()
    data = evt["data"] or {}
    
    if et == "combat":
        if st == "mob_killed":
            mob = data.get("mob_type") or data.get("name") or "unknown"
            summary["mobs_defeated"][mob] = summary["mobs_defeated"].get(mob, 0) + 1
        elif st == "player_death":
            summary["deaths"] += 1
            
    elif et == "mining":
        if "ore_mined" in st:
            block = data.get("block_type") or data.get("ore_type") or "unknown"
            qty = int(data.get("quantity") or data.get("count") or 1)
            summary["resources_obtained"][block] = summary["resources_obtained"].get(block, 0) + qty
        elif "break" in st:
            block = data.get("block_type") or "unknown"
            qty = int(data.get("count") or data.get("quantity") or 1)
            summary["blocks_broken"][block] = summary["blocks_broken"].get(block, 0) + qty
            
    elif et == "building":
        if "place" in st:
            block = data.get("block_type") or "unknown"
            qty = int(data.get("count") or data.get("quantity") or 1)
            summary["blocks_placed"][block] = summary["blocks_placed"].get(block, 0) + qty
        elif "break" in st:
            block = data.get("block_type") or "unknown"
            qty = int(data.get("count") or data.get("quantity") or 1)
            summary["blocks_broken"][block] = summary["blocks_broken"].get(block, 0) + qty
            
    elif et == "exploration":
        if st == "enter_biome":
            biome = data.get("biome_name") or "unknown"
            if biome not in summary["biomes_visited"]:
                summary["biomes_visited"].append(biome)
        elif st == "discover_structure":
            struct = data.get("structure_type") or "unknown"
            if struct not in summary["structures_discovered"]:
                summary["structures_discovered"].append(struct)
                
    elif et == "villagers":
        if st == "trade":
            summary["villager_actions"]["trades"] += 1
            output_item = data.get("output_item") or "unknown"
            summary["resources_obtained"][output_item] = summary["resources_obtained"].get(output_item, 0) + int(data.get("output_count", 1))
        elif "cure" in st:
            summary["villager_actions"]["cured"] += 1
        elif "breed" in st:
            summary["villager_actions"]["bred"] += 1

def process_events_for_episodes(conn: sqlite3.Connection, events: List[Dict[str, Any]]) -> None:
    """
    Processes new timeline events and clusters them into logical episodes.
    Inserts new episodes or updates existing ones in the 'episodes' table.
    """
    # Sort events chronologically to process correctly
    events = sorted(events, key=lambda e: e.get("timestamp", ""))
    
    for evt in events:
        session_id = evt["session_id"]
        event_uuid = evt["event_uuid"]
        event_time_str = evt["timestamp"]
        
        episode_type = get_episode_type(evt["event_type"], evt["subtype"], evt["data"] or {})
        if not episode_type:
            continue
            
        try:
            event_time = datetime.fromisoformat(event_time_str.replace("Z", "+00:00"))
        except Exception:
            event_time = datetime.now(timezone.utc)
            
        # Check if there is an active episode for this session and type
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT episode_uuid, start_time, end_time, last_event_time, event_uuids_json, summary_json, confidence
            FROM episodes
            WHERE session_id = ? AND episode_type = ?
            ORDER BY last_event_time DESC LIMIT 1;
            """,
            (session_id, episode_type)
        )
        row = cursor.fetchone()
        
        should_merge = False
        active_episode = None
        
        if row:
            # Check temporal gap
            last_time_str = row["last_event_time"]
            try:
                last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
                gap = (event_time - last_time).total_seconds()
                threshold = get_temporal_threshold(episode_type)
                # If the event happened within the threshold, we merge it
                if 0 <= gap <= threshold:
                    should_merge = True
                    active_episode = dict(row)
            except Exception:
                pass
                
        now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        if should_merge and active_episode:
            # 1. Update existing episode
            episode_uuid_val = active_episode["episode_uuid"]
            event_uuids = json.loads(active_episode["event_uuids_json"])
            summary = json.loads(active_episode["summary_json"])
            
            if event_uuid not in event_uuids:
                event_uuids.append(event_uuid)
                
            _update_summary_with_event(summary, episode_type, evt)
            
            # Recalculate end_time
            end_time_str = active_episode["end_time"]
            try:
                current_end = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                if event_time > current_end:
                    end_time_str = event_time_str
            except Exception:
                end_time_str = event_time_str
                
            # Confidence grows with density/number of events grouped
            new_confidence = min(1.0, 0.5 + (len(event_uuids) * 0.05))
            
            conn.execute(
                """
                UPDATE episodes
                SET end_time = ?, last_event_time = ?, event_uuids_json = ?, summary_json = ?, confidence = ?, last_updated = ?
                WHERE episode_uuid = ?;
                """,
                (
                    end_time_str,
                    event_time_str,
                    json.dumps(event_uuids),
                    json.dumps(summary),
                    new_confidence,
                    now_str,
                    episode_uuid_val
                )
            )
        else:
            # 2. Create new episode
            new_uuid = str(uuid.uuid4())
            event_uuids = [event_uuid]
            summary = init_episode_summary(episode_type, evt)
            confidence = 0.5
            
            conn.execute(
                """
                INSERT INTO episodes (episode_uuid, session_id, episode_type, start_time, end_time, last_event_time, event_uuids_json, summary_json, confidence, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    new_uuid,
                    session_id,
                    episode_type,
                    event_time_str,
                    event_time_str,
                    event_time_str,
                    json.dumps(event_uuids),
                    json.dumps(summary),
                    confidence,
                    now_str
                )
            )
