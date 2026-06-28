import sqlite3
import json
from datetime import datetime, timezone
from typing import Tuple, Dict, Any, List

from backend.memory.embeddings import generate_embedding, get_model_metadata
from backend.memory.vector_store import save_embedding, delete_embedding

def session_to_text(session_id: str, summary: Dict[str, Any]) -> str:
    """Converts a Session Memory summary into a natural language text description."""
    activities = ", ".join(summary.get("major_activities", [])) or "no major activities recorded"
    structures = ", ".join(summary.get("structures_discovered", [])) or "no structures discovered"
    
    resources_list = [f"{v} {k}" for k, v in summary.get("resources_obtained", {}).items()]
    resources = ", ".join(resources_list) or "no resources obtained"
    
    kills_list = [f"{v} {k}" for k, v in summary.get("combat_kills", {}).items()]
    kills = ", ".join(kills_list) or "no kills recorded"
    
    deaths = summary.get("deaths_count", 0)
    damaged = summary.get("player_damaged_count", 0)
    
    text = (
        f"Session memory for session {session_id}. "
        f"Duration was {round(summary.get('duration_seconds', 0.0) / 60.0, 1)} minutes. "
        f"Major activities included: {activities}. "
        f"Discovered structures: {structures}. "
        f"Obtained resources: {resources}. "
        f"Combat performance: defeated {kills}; took damage {damaged} times; died {deaths} times."
    )
    return text

def daily_to_text(date_str: str, summary: Dict[str, Any]) -> str:
    """Converts a Daily Memory summary into a natural language text description."""
    activities = ", ".join(summary.get("major_activities", [])) or "no major activities recorded"
    structures = ", ".join(summary.get("structures_discovered", [])) or "no structures discovered"
    
    resources_list = [f"{v} {k}" for k, v in summary.get("resources_obtained", {}).items()]
    resources = ", ".join(resources_list) or "no resources obtained"
    
    kills_list = [f"{v} {k}" for k, v in summary.get("combat_kills", {}).items()]
    kills = ", ".join(kills_list) or "no kills recorded"
    
    deaths = summary.get("deaths_count", 0)
    
    text = (
        f"Daily memory summary for date {date_str}. "
        f"Total active playtime was {round(summary.get('duration_seconds', 0.0) / 60.0, 1)} minutes. "
        f"Activities performed: {activities}. "
        f"Structures visited: {structures}. "
        f"Resources accumulated: {resources}. "
        f"Combat overview: killed {kills}; died {deaths} times."
    )
    return text

def fact_to_text(fact_key: str, value: Any, history: Dict[str, Any]) -> str:
    """Converts an evolving player fact into a descriptive text statement."""
    if fact_key == "home_location":
        return f"Player's Home Base / spawn point is located at coordinate x={value.get('x')}, y={value.get('y')}, z={value.get('z')} in the {value.get('dimension', 'overworld')} dimension."
    elif fact_key == "favorite_building_materials":
        # value is counts dict, top_list is in history
        top_list = history.get("top_list", [])
        top_str = ", ".join(top_list) or "none"
        return f"Player's favorite building blocks and construction materials are: {top_str}."
    elif fact_key == "preferred_mining_level":
        avg_y = value.get("avg_y", 64.0)
        return f"Player's preferred or average Y level for mining ores is Y={avg_y}."
    elif fact_key == "tamed_animals":
        # value is a list of animal entries
        animals = [f"{a.get('animal_type')} at coordinate x={a.get('position', {}).get('x')}, z={a.get('position', {}).get('z')}" for a in value]
        animals_str = ", ".join(animals) or "no tamed animals"
        return f"Player has tamed the following animals: {animals_str}."
    elif fact_key == "active_projects":
        projects = ", ".join(value) or "no active projects"
        return f"Player is currently working on active construction projects: {projects}."
    elif fact_key == "completed_projects":
        projects = ", ".join(value) or "no completed projects"
        return f"Player has finished the following projects: {projects}."
    elif fact_key.startswith("base:"):
        return f"Player has established a base or shelter at coordinate x={value.get('x')}, z={value.get('z')} in the {value.get('dimension')} dimension."
    elif fact_key.startswith("village:"):
        return f"Player discovered a village structure at coordinate x={value.get('x')}, z={value.get('z')} in the {value.get('dimension')} dimension."
        
    return f"Fact about '{fact_key}': {json.dumps(value)}."

def episode_to_text(episode_type: str, summary: Dict[str, Any]) -> str:
    """Converts a grouped Episode summary into a cohesive text representation."""
    resources_list = [f"{v} {k}" for k, v in summary.get("resources_obtained", {}).items()]
    resources = ", ".join(resources_list) or "no items"
    
    kills_list = [f"{v} {k}" for k, v in summary.get("mobs_defeated", {}).items()]
    kills = ", ".join(kills_list) or "no mobs"
    
    deaths = summary.get("deaths", 0)
    biomes = ", ".join(summary.get("biomes_visited", [])) or "no biomes"
    
    text = (
        f"Episode category: '{episode_type}'. "
        f"Actions performed: mined {resources}; defeated {kills}; died {deaths} times. "
        f"Locations traversed: {biomes}."
    )
    return text

def check_model_compatibility(conn: sqlite3.Connection) -> bool:
    """Checks if the existing vector store matches the current embedding model parameters."""
    cursor = conn.cursor()
    cursor.execute("SELECT embedding_model, embedding_dimension, embedding_version FROM memory_embeddings LIMIT 1;")
    row = cursor.fetchone()
    if not row:
        return True # Empty store is compatible
        
    meta = get_model_metadata()
    return (
        row[0] == meta["embedding_model"] and
        row[1] == meta["embedding_dimension"] and
        row[2] == meta["embedding_version"]
    )

def run_indexing_sync(conn: sqlite3.Connection) -> Tuple[int, int, int]:
    """
    Incrementally synchronizes Memory Engine records into the vector store.
    Checks model compatibility, generates embeddings for new/modified records,
    and prunes deleted ones.
    Returns (inserted_count, updated_count, deleted_count).
    """
    # 1. Verify model compatibility, delete all if incompatible
    if not check_model_compatibility(conn):
        print("[IndexingPipeline] Embedding model parameters changed. Rebuilding index...", flush=True)
        with conn:
            conn.execute("DELETE FROM memory_embeddings;")
            
    model_meta = get_model_metadata()
    
    inserted = 0
    updated = 0
    deleted = 0
    
    # 2. Sync Session Summaries
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT s.session_id, s.summary_json, s.confidence, s.source_event_uuids, s.last_updated, e.last_updated
        FROM sessions_summary s
        LEFT JOIN memory_embeddings e ON s.session_id = e.memory_uuid;
        """
    )
    for r in cursor.fetchall():
        s_id = r[0]
        summary = json.loads(r[1])
        conf = r[2]
        prov = json.loads(r[3])
        s_last = r[4]
        e_last = r[5]
        
        if e_last is None or s_last > e_last:
            text = session_to_text(s_id, summary)
            vector = generate_embedding(text)
            save_embedding(conn, s_id, "session", text, vector, conf, prov, model_meta)
            if e_last is None:
                inserted += 1
            else:
                updated += 1
                
    # 3. Sync Daily Summaries
    cursor.execute(
        """
        SELECT d.date, d.summary_json, d.confidence, d.source_session_ids, d.last_updated, e.last_updated
        FROM daily_summaries d
        LEFT JOIN memory_embeddings e ON d.date = e.memory_uuid;
        """
    )
    for r in cursor.fetchall():
        date_val = r[0]
        summary = json.loads(r[1])
        conf = r[2]
        prov = json.loads(r[3])
        d_last = r[4]
        e_last = r[5]
        
        if e_last is None or d_last > e_last:
            text = daily_to_text(date_val, summary)
            vector = generate_embedding(text)
            save_embedding(conn, date_val, "daily", text, vector, conf, prov, model_meta)
            if e_last is None:
                inserted += 1
            else:
                updated += 1
                
    # 4. Sync Facts
    cursor.execute(
        """
        SELECT f.fact_key, f.fact_value_json, f.history_json, f.confidence, f.source_event_uuids, f.last_updated, e.last_updated
        FROM facts f
        LEFT JOIN memory_embeddings e ON f.fact_key = e.memory_uuid;
        """
    )
    for r in cursor.fetchall():
        key = r[0]
        val = json.loads(r[1])
        hist = json.loads(r[2])
        conf = r[3]
        prov = json.loads(r[4])
        f_last = r[5]
        e_last = r[6]
        
        if e_last is None or f_last > e_last:
            text = fact_to_text(key, val, hist)
            vector = generate_embedding(text)
            save_embedding(conn, key, "fact", text, vector, conf, prov, model_meta)
            if e_last is None:
                inserted += 1
            else:
                updated += 1
                
    # 5. Sync Episodes
    cursor.execute(
        """
        SELECT p.episode_uuid, p.episode_type, p.summary_json, p.confidence, p.event_uuids_json, p.last_updated, e.last_updated
        FROM episodes p
        LEFT JOIN memory_embeddings e ON p.episode_uuid = e.memory_uuid;
        """
    )
    for r in cursor.fetchall():
        ep_uuid = r[0]
        ep_type = r[1]
        summary = json.loads(r[2])
        conf = r[3]
        prov = json.loads(r[4])
        p_last = r[5]
        e_last = r[6]
        
        if e_last is None or p_last > e_last:
            text = episode_to_text(ep_type, summary)
            vector = generate_embedding(text)
            save_embedding(conn, ep_uuid, "episode", text, vector, conf, prov, model_meta)
            if e_last is None:
                inserted += 1
            else:
                updated += 1
                
    # 6. Prune Deleted/Orphaned Vectors
    cursor.execute("SELECT memory_uuid, memory_type FROM memory_embeddings;")
    all_embeddings = cursor.fetchall()
    
    for r in all_embeddings:
        uuid_val = r[0]
        m_type = r[1]
        exists = False
        
        if m_type == "session":
            cursor.execute("SELECT 1 FROM sessions_summary WHERE session_id = ? LIMIT 1;", (uuid_val,))
            exists = cursor.fetchone() is not None
        elif m_type == "daily":
            cursor.execute("SELECT 1 FROM daily_summaries WHERE date = ? LIMIT 1;", (uuid_val,))
            exists = cursor.fetchone() is not None
        elif m_type == "fact":
            cursor.execute("SELECT 1 FROM facts WHERE fact_key = ? LIMIT 1;", (uuid_val,))
            exists = cursor.fetchone() is not None
        elif m_type == "episode":
            cursor.execute("SELECT 1 FROM episodes WHERE episode_uuid = ? LIMIT 1;", (uuid_val,))
            exists = cursor.fetchone() is not None
            
        if not exists:
            delete_embedding(conn, uuid_val)
            deleted += 1
            
    return inserted, updated, deleted

def rebuild_entire_index(conn: sqlite3.Connection) -> Tuple[int, int, int]:
    """Clears the embedding store and fully re-indexes all memories."""
    with conn:
        conn.execute("DELETE FROM memory_embeddings;")
    return run_indexing_sync(conn)
