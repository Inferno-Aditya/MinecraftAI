import sqlite3
import json
import numpy as np
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

def init_vector_store(conn: sqlite3.Connection) -> None:
    """Creates the vector store table if it does not exist."""
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_embeddings (
                memory_uuid TEXT PRIMARY KEY,
                memory_type TEXT NOT NULL,
                text_content TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                confidence REAL NOT NULL,
                provenance_json TEXT NOT NULL,
                embedding_model TEXT NOT NULL,
                embedding_dimension INTEGER NOT NULL,
                embedding_version TEXT NOT NULL,
                last_updated TEXT NOT NULL
            );
            """
        )
        # Index on type for filtered queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_type ON memory_embeddings (memory_type);")

def save_embedding(
    conn: sqlite3.Connection,
    memory_uuid: str,
    memory_type: str,
    text_content: str,
    embedding: List[float],
    confidence: float,
    provenance: List[str],
    model_meta: Dict[str, Any]
) -> None:
    """Inserts or replaces an embedding vector and its metadata in the vector store."""
    now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO memory_embeddings (
                memory_uuid, memory_type, text_content, embedding_json, confidence, provenance_json,
                embedding_model, embedding_dimension, embedding_version, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                memory_uuid,
                memory_type,
                text_content,
                json.dumps(embedding),
                confidence,
                json.dumps(provenance),
                model_meta["embedding_model"],
                model_meta["embedding_dimension"],
                model_meta["embedding_version"],
                now_str
            )
        )

def delete_embedding(conn: sqlite3.Connection, memory_uuid: str) -> None:
    """Removes an embedding vector from the vector store."""
    with conn:
        conn.execute("DELETE FROM memory_embeddings WHERE memory_uuid = ?;", (memory_uuid,))

def get_embedding(conn: sqlite3.Connection, memory_uuid: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single embedding entry by its UUID."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT memory_uuid, memory_type, text_content, embedding_json, confidence, provenance_json, last_updated FROM memory_embeddings WHERE memory_uuid = ?;",
        (memory_uuid,)
    )
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "memory_uuid": row[0],
        "memory_type": row[1],
        "text_content": row[2],
        "embedding": json.loads(row[3]),
        "confidence": row[4],
        "provenance": json.loads(row[5]),
        "last_updated": row[6]
    }

def query_candidates(conn: sqlite3.Connection, memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Queries all candidate embeddings (optionally filtered by type) for similarity scoring."""
    cursor = conn.cursor()
    if memory_type:
        cursor.execute(
            "SELECT memory_uuid, memory_type, text_content, embedding_json, confidence, provenance_json, last_updated FROM memory_embeddings WHERE memory_type = ?;",
            (memory_type,)
        )
    else:
        cursor.execute(
            "SELECT memory_uuid, memory_type, text_content, embedding_json, confidence, provenance_json, last_updated FROM memory_embeddings;"
        )
    
    rows = cursor.fetchall()
    candidates = []
    for r in rows:
        candidates.append({
            "memory_uuid": r[0],
            "memory_type": r[1],
            "text_content": r[2],
            "embedding": json.loads(r[3]),
            "confidence": r[4],
            "provenance": json.loads(r[5]),
            "last_updated": r[6]
        })
    return candidates

def calculate_similarity_rankings(query_embedding: List[float], candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Calculates cosine similarity rankings using NumPy-vectorized operations."""
    if not candidates:
        return []
        
    query_vec = np.array(query_embedding, dtype=np.float32)
    matrix = np.array([c["embedding"] for c in candidates], dtype=np.float32)
    
    # Calculate norms
    norm_q = np.linalg.norm(query_vec)
    norm_c = np.linalg.norm(matrix, axis=1)
    
    # Calculate dot product
    dot_products = np.dot(matrix, query_vec)
    
    # Calculate cosine similarity
    norms = norm_q * norm_c
    norms[norms == 0] = 1e-10  # Prevent division by zero
    similarities = dot_products / norms
    
    # Create results with diagnostic info
    results = []
    for idx, sim in enumerate(similarities):
        cand = candidates[idx]
        results.append({
            "memory_uuid": cand["memory_uuid"],
            "memory_type": cand["memory_type"],
            "text_content": cand["text_content"],
            "similarity_score": float(sim),
            "confidence": cand["confidence"],
            "provenance": cand["provenance"],
            "last_updated": cand["last_updated"]
        })
        
    return results

def rank_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ranks the retrieval results.
    Structured to easily combine other parameters (confidence, recency, importance) in the future.
    """
    for r in results:
        # Currently, combined score is just semantic similarity score
        # In the future, this can be: score = similarity_weight * sim + confidence_weight * confidence + ...
        r["combined_score"] = r["similarity_score"]
        
    # Sort descending by combined score
    ranked = sorted(results, key=lambda x: x["combined_score"], reverse=True)
    
    # Add retrieval rank diagnostics
    for idx, r in enumerate(ranked):
        r["retrieval_rank"] = idx + 1
        
    return ranked
