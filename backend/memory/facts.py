import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from backend.memory.event_logger import COMMON_BLOCKS_AND_ITEMS

def round_to_16(v: float) -> int:
    return int((v // 16) * 16)

def propose_fact_value(conn: sqlite3.Connection, key: str, value: Any, event_uuid: str, session_id: str) -> None:
    """
    Proposes a fact value. If there's no active fact, sets it immediately with lower confidence.
    If there is an active fact and the new value is different, adds it as a candidate.
    If a candidate reaches 3 counts (Soft Updates), it is promoted to the active fact, 
    and the old active fact is moved to history.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT fact_value_json, confidence, history_json, source_event_uuids, source_session_ids FROM facts WHERE fact_key = ?;", (key,))
    row = cursor.fetchone()
    
    val_repr = json.dumps(value, sort_keys=True)
    now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    if not row:
        # Initialize the fact immediately with initial count of 1 and low confidence
        history = {
            "past_values": [],
            "candidates": {
                val_repr: {
                    "value": value,
                    "count": 1,
                    "uuids": [event_uuid],
                    "sessions": [session_id]
                }
            }
        }
        conn.execute(
            """
            INSERT INTO facts (fact_key, fact_value_json, confidence, history_json, source_event_uuids, source_session_ids, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                key,
                val_repr,
                0.33,
                json.dumps(history),
                json.dumps([event_uuid]),
                json.dumps([session_id]),
                now_str
            )
        )
        return
        
    active_val_json = row["fact_value_json"]
    confidence = row["confidence"]
    history = json.loads(row["history_json"])
    source_events = json.loads(row["source_event_uuids"])
    source_sessions = json.loads(row["source_session_ids"])
    
    # Append provenance
    if event_uuid not in source_events:
        source_events.append(event_uuid)
    if session_id not in source_sessions:
        source_sessions.append(session_id)
        
    # If matching active value, strengthen confidence
    if val_repr == active_val_json:
        new_confidence = min(1.0, confidence + 0.33)
        conn.execute(
            """
            UPDATE facts SET confidence = ?, source_event_uuids = ?, source_session_ids = ?, last_updated = ? WHERE fact_key = ?;
            """,
            (new_confidence, json.dumps(source_events), json.dumps(source_sessions), now_str, key)
        )
        return
        
    # Proposed value is different
    candidates = history.setdefault("candidates", {})
    cand_info = candidates.setdefault(val_repr, {"value": value, "count": 0, "uuids": [], "sessions": []})
    cand_info["count"] += 1
    if event_uuid not in cand_info["uuids"]:
        cand_info["uuids"].append(event_uuid)
    if session_id not in cand_info["sessions"]:
        cand_info["sessions"].append(session_id)
        
    if cand_info["count"] >= 3:
        # Promote to active! Move previous active to history list
        past_values = history.setdefault("past_values", [])
        past_values.append({
            "value": json.loads(active_val_json),
            "last_active": now_str
        })
        
        # Clear candidate from the proposal queue
        del candidates[val_repr]
        
        # New active fact
        new_active = val_repr
        new_confidence = 0.98
        
        # Merge candidate provenance
        for u in cand_info["uuids"]:
            if u not in source_events:
                source_events.append(u)
        for s in cand_info["sessions"]:
            if s not in source_sessions:
                source_sessions.append(s)
    else:
        # Active remains unchanged, but history candidate updated
        new_active = active_val_json
        # Soft decay of confidence for active fact under contrary evidence
        new_confidence = max(0.1, confidence - 0.1)
        
    conn.execute(
        """
        UPDATE facts SET fact_value_json = ?, confidence = ?, history_json = ?, source_event_uuids = ?, source_session_ids = ?, last_updated = ? WHERE fact_key = ?;
        """,
        (new_active, new_confidence, json.dumps(history), json.dumps(source_events), json.dumps(source_sessions), now_str, key)
    )

def extract_and_update_facts(conn: sqlite3.Connection, events: List[Dict[str, Any]]) -> None:
    """
    Extracts and updates evolving facts from a list of timeline events.
    Handles preferred mining levels, base locations, portal networks, favorite materials,
    discovered villages, tamed animals, and projects.
    """
    for evt in events:
        event_uuid = evt["event_uuid"]
        session_id = evt["session_id"]
        et = evt["event_type"].lower()
        st = evt["subtype"].lower()
        data = evt["data"] or {}
        
        # 1. Base / Home Location Proposing
        if et == "building" and st in {"place_block", "place_streak"}:
            block = data.get("block_type") or ""
            if "bed" in block or "respawn_anchor" in block:
                # Sleep/bed placement determines home coordinate chunk
                proposed_home = {
                    "x": round_to_16(evt["x"]),
                    "y": int(evt["y"]),
                    "z": round_to_16(evt["z"]),
                    "dimension": evt["dimension"]
                }
                propose_fact_value(conn, "home_location", proposed_home, event_uuid, session_id)
                propose_fact_value(conn, f"base:{proposed_home['x']}_{proposed_home['z']}", proposed_home, event_uuid, session_id)
                
            # Favorite Materials (no soft update needed, just accumulation)
            block_name = data.get("block_type") or ""
            if block_name:
                _increment_materials_fact(conn, block_name, event_uuid, session_id)
                
        # 2. Preferred Mining Level
        if et == "mining" and "ore_mined" in st:
            _update_preferred_mining_level(conn, evt["y"], event_uuid, session_id)
        elif et == "building" and "break_streak" in st:
            # Player breaking lots of blocks below ground level
            if evt["y"] < 60:
                _update_preferred_mining_level(conn, evt["y"], event_uuid, session_id)
                
        # 3. Tamed Animals
        if et == "animals" and st == "tame":
            animal = data.get("animal_type") or "unknown"
            pos = {"x": evt["x"], "y": evt["y"], "z": evt["z"], "dimension": evt["dimension"]}
            _add_tamed_animal(conn, animal, pos, event_uuid, session_id)
            
        # 4. Discovered Villages
        if et == "exploration" and st == "discover_structure":
            struct = data.get("structure_type") or ""
            if struct == "village":
                # Villages are large, round to 64
                village_pos = {
                    "x": int((evt["x"] // 64) * 64),
                    "z": int((evt["z"] // 64) * 64),
                    "dimension": evt["dimension"]
                }
                propose_fact_value(conn, f"village:{village_pos['x']}_{village_pos['z']}", village_pos, event_uuid, session_id)
                
        # 5. Projects
        if et == "building":
            if st == "construction_start":
                proj_name = data.get("structure_name") or "unknown_project"
                _update_project(conn, proj_name, "active", event_uuid, session_id)
            elif st == "construction_end":
                proj_name = data.get("structure_name") or "unknown_project"
                _update_project(conn, proj_name, "completed", event_uuid, session_id)

def _increment_materials_fact(conn: sqlite3.Connection, material: str, event_uuid: str, session_id: str) -> None:
    cursor = conn.cursor()
    cursor.execute("SELECT fact_value_json, source_event_uuids, source_session_ids FROM facts WHERE fact_key = 'favorite_building_materials';")
    row = cursor.fetchone()
    
    if not row:
        counts = {material: 1}
        source_events = [event_uuid]
        source_sessions = [session_id]
    else:
        counts = json.loads(row["fact_value_json"])
        counts[material] = counts.get(material, 0) + 1
        source_events = json.loads(row["source_event_uuids"])
        source_sessions = json.loads(row["source_session_ids"])
        if event_uuid not in source_events:
            source_events.append(event_uuid)
        if session_id not in source_sessions:
            source_sessions.append(session_id)
            
    # Calculate top materials sorted by count
    top_materials = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_list = [item[0] for item in top_materials]
    
    now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    conn.execute(
        """
        INSERT OR REPLACE INTO facts (fact_key, fact_value_json, confidence, history_json, source_event_uuids, source_session_ids, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (
            "favorite_building_materials",
            json.dumps(counts), # Store raw count dict as fact value
            min(1.0, len(counts) * 0.1), # Confidence grows with variety
            json.dumps({"top_list": top_list}), # Store top list in history/meta
            json.dumps(source_events),
            json.dumps(source_sessions),
            now_str
        )
    )

def _update_preferred_mining_level(conn: sqlite3.Connection, y: float, event_uuid: str, session_id: str) -> None:
    cursor = conn.cursor()
    cursor.execute("SELECT fact_value_json, source_event_uuids, source_session_ids FROM facts WHERE fact_key = 'preferred_mining_level';")
    row = cursor.fetchone()
    
    if not row:
        level_data = {"avg_y": float(y), "count": 1}
        source_events = [event_uuid]
        source_sessions = [session_id]
    else:
        level_data = json.loads(row["fact_value_json"])
        cnt = level_data["count"]
        level_data["avg_y"] = round((level_data["avg_y"] * cnt + y) / (cnt + 1), 2)
        level_data["count"] = cnt + 1
        source_events = json.loads(row["source_event_uuids"])
        source_sessions = json.loads(row["source_session_ids"])
        if event_uuid not in source_events:
            source_events.append(event_uuid)
        if session_id not in source_sessions:
            source_sessions.append(session_id)
            
    now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    # Confidence scales with sample count
    confidence = min(1.0, 0.2 + (level_data["count"] * 0.05))
    
    conn.execute(
        """
        INSERT OR REPLACE INTO facts (fact_key, fact_value_json, confidence, history_json, source_event_uuids, source_session_ids, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (
            "preferred_mining_level",
            json.dumps(level_data),
            confidence,
            json.dumps({}),
            json.dumps(source_events),
            json.dumps(source_sessions),
            now_str
        )
    )

def _add_tamed_animal(conn: sqlite3.Connection, animal: str, position: dict, event_uuid: str, session_id: str) -> None:
    cursor = conn.cursor()
    cursor.execute("SELECT fact_value_json, source_event_uuids, source_session_ids FROM facts WHERE fact_key = 'tamed_animals';")
    row = cursor.fetchone()
    
    entry = {"animal_type": animal, "position": position, "tamed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    
    if not row:
        animals_list = [entry]
        source_events = [event_uuid]
        source_sessions = [session_id]
    else:
        animals_list = json.loads(row["fact_value_json"])
        # Avoid exact duplicates
        if not any(a["position"] == position and a["animal_type"] == animal for a in animals_list):
            animals_list.append(entry)
        source_events = json.loads(row["source_event_uuids"])
        source_sessions = json.loads(row["source_session_ids"])
        if event_uuid not in source_events:
            source_events.append(event_uuid)
        if session_id not in source_sessions:
            source_sessions.append(session_id)
            
    now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    conn.execute(
        """
        INSERT OR REPLACE INTO facts (fact_key, fact_value_json, confidence, history_json, source_event_uuids, source_session_ids, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (
            "tamed_animals",
            json.dumps(animals_list),
            1.0,
            json.dumps({}),
            json.dumps(source_events),
            json.dumps(source_sessions),
            now_str
        )
    )

def _update_project(conn: sqlite3.Connection, project_name: str, status: str, event_uuid: str, session_id: str) -> None:
    """Updates active or completed projects list fact."""
    cursor = conn.cursor()
    
    # We maintain two facts: 'active_projects' and 'completed_projects'
    # Fetch active
    cursor.execute("SELECT fact_value_json, source_event_uuids, source_session_ids FROM facts WHERE fact_key = 'active_projects';")
    active_row = cursor.fetchone()
    active_list = json.loads(active_row["fact_value_json"]) if active_row else []
    active_events = json.loads(active_row["source_event_uuids"]) if active_row else []
    active_sessions = json.loads(active_row["source_session_ids"]) if active_row else []
    
    # Fetch completed
    cursor.execute("SELECT fact_value_json, source_event_uuids, source_session_ids FROM facts WHERE fact_key = 'completed_projects';")
    completed_row = cursor.fetchone()
    completed_list = json.loads(completed_row["fact_value_json"]) if completed_row else []
    completed_events = json.loads(completed_row["source_event_uuids"]) if completed_row else []
    completed_sessions = json.loads(completed_row["source_session_ids"]) if completed_row else []
    
    now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    if status == "active":
        if project_name not in active_list:
            active_list.append(project_name)
        if event_uuid not in active_events:
            active_events.append(event_uuid)
        if session_id not in active_sessions:
            active_sessions.append(session_id)
    else: # completed
        if project_name in active_list:
            active_list.remove(project_name)
        if project_name not in completed_list:
            completed_list.append(project_name)
        if event_uuid not in completed_events:
            completed_events.append(event_uuid)
        if session_id not in completed_sessions:
            completed_sessions.append(session_id)
            
    conn.execute(
        """
        INSERT OR REPLACE INTO facts (fact_key, fact_value_json, confidence, history_json, source_event_uuids, source_session_ids, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (
            "active_projects",
            json.dumps(active_list),
            0.8,
            json.dumps({}),
            json.dumps(active_events),
            json.dumps(active_sessions),
            now_str
        )
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO facts (fact_key, fact_value_json, confidence, history_json, source_event_uuids, source_session_ids, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (
            "completed_projects",
            json.dumps(completed_list),
            1.0,
            json.dumps({}),
            json.dumps(completed_events),
            json.dumps(completed_sessions),
            now_str
        )
    )
