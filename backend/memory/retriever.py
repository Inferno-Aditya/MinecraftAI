import sqlite3
import json
from typing import List, Dict, Any, Optional

from backend.memory.embeddings import generate_embedding
from backend.memory.vector_store import query_candidates, calculate_similarity_rankings, rank_results, get_embedding

def fetch_source_memory(conn: sqlite3.Connection, memory_uuid: str, memory_type: str) -> Optional[Dict[str, Any]]:
    """Retrieves the original structured JSON memory content from the Memory Engine."""
    cursor = conn.cursor()
    if memory_type == "session":
        cursor.execute("SELECT summary_json FROM sessions_summary WHERE session_id = ?;", (memory_uuid,))
        row = cursor.fetchone()
        return json.loads(row[0]) if row else None
    elif memory_type == "daily":
        cursor.execute("SELECT summary_json FROM daily_summaries WHERE date = ?;", (memory_uuid,))
        row = cursor.fetchone()
        return json.loads(row[0]) if row else None
    elif memory_type == "fact":
        cursor.execute("SELECT fact_value_json, history_json FROM facts WHERE fact_key = ?;", (memory_uuid,))
        row = cursor.fetchone()
        if row:
            return {
                "value": json.loads(row[0]),
                "history": json.loads(row[1])
            }
        return None
    elif memory_type == "episode":
        cursor.execute("SELECT summary_json, episode_type FROM episodes WHERE episode_uuid = ?;", (memory_uuid,))
        row = cursor.fetchone()
        if row:
            summary = json.loads(row[0])
            summary["episode_type"] = row[1]
            return summary
        return None
    return None

def retrieve(conn: sqlite3.Connection, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Performs semantic similarity search over all memories."""
    # 1. Generate query vector
    query_emb = generate_embedding(query)
    
    # 2. Get all candidates
    candidates = query_candidates(conn)
    if not candidates:
        return []
        
    # 3. Calculate similarity score
    raw_results = calculate_similarity_rankings(query_emb, candidates)
    
    # 4. Rank combined results
    ranked_results = rank_results(raw_results)
    
    # 5. Fetch source memory content and return top_k
    top_results = ranked_results[:top_k]
    for r in top_results:
        r["source_memory"] = fetch_source_memory(conn, r["memory_uuid"], r["memory_type"])
        
    return top_results

def retrieve_by_type(conn: sqlite3.Connection, query: str, memory_type: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Performs semantic similarity search filtered by memory category."""
    query_emb = generate_embedding(query)
    candidates = query_candidates(conn, memory_type)
    if not candidates:
        return []
        
    raw_results = calculate_similarity_rankings(query_emb, candidates)
    ranked_results = rank_results(raw_results)
    
    top_results = ranked_results[:top_k]
    for r in top_results:
        r["source_memory"] = fetch_source_memory(conn, r["memory_uuid"], r["memory_type"])
        
    return top_results

def retrieve_similar(conn: sqlite3.Connection, memory_uuid: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Finds memories similar to an existing memory."""
    target_emb_record = get_embedding(conn, memory_uuid)
    if not target_emb_record:
        return []
        
    query_emb = target_emb_record["embedding"]
    
    # Query other candidates, excluding the target memory itself
    candidates = query_candidates(conn)
    candidates = [c for c in candidates if c["memory_uuid"] != memory_uuid]
    if not candidates:
        return []
        
    raw_results = calculate_similarity_rankings(query_emb, candidates)
    ranked_results = rank_results(raw_results)
    
    top_results = ranked_results[:top_k]
    for r in top_results:
        r["source_memory"] = fetch_source_memory(conn, r["memory_uuid"], r["memory_type"])
        
    return top_results
