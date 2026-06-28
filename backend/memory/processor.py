import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple

from backend.memory.timeline import get_connection as get_timeline_connection
from backend.memory.timeline import SCHEMA_VERSION as TIMELINE_SCHEMA_VERSION
from backend.memory.sessions import process_events_for_session
from backend.memory.summarizer import merge_session_summaries_into_daily
from backend.memory.facts import extract_and_update_facts
from backend.memory.episodes import process_events_for_episodes

MEMORY_SCHEMA_VERSION = 1

def init_memory_db(db_path: str) -> None:
    """Initializes the memory database tables and indexes if they do not exist."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processing_state (
                    state_key TEXT PRIMARY KEY,
                    state_value TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions_summary (
                    session_id TEXT PRIMARY KEY,
                    summary_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source_event_uuids TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_summaries (
                    date TEXT PRIMARY KEY,
                    summary_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source_session_ids TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    fact_key TEXT PRIMARY KEY,
                    fact_value_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    history_json TEXT NOT NULL,
                    source_event_uuids TEXT NOT NULL,
                    source_session_ids TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    episode_uuid TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    episode_type TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    last_event_time TEXT NOT NULL,
                    event_uuids_json TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    last_updated TEXT NOT NULL
                );
            """)
            
            # Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_session ON episodes (session_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_type ON episodes (episode_type);")
            
            # Initialize schema version
            cursor = conn.cursor()
            cursor.execute("SELECT state_value FROM processing_state WHERE state_key = 'schema_version';")
            if not cursor.fetchone():
                conn.execute(
                    "INSERT INTO processing_state (state_key, state_value) VALUES ('schema_version', ?);",
                    (str(MEMORY_SCHEMA_VERSION),)
                )
                
            # Initialize vector store table
            from backend.memory.vector_store import init_vector_store
            init_vector_store(conn)
    finally:
        conn.close()

def _check_and_close_active_sessions(conn_time: sqlite3.Connection, conn_mem: sqlite3.Connection) -> None:
    """Checks for currently active sessions in memory DB and closes them if closed in timeline DB."""
    cursor_mem = conn_mem.cursor()
    cursor_mem.execute("SELECT session_id, summary_json, created_at FROM sessions_summary WHERE confidence < 1.0;")
    rows = cursor_mem.fetchall()
    if not rows:
        return
        
    cursor_time = conn_time.cursor()
    now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    with conn_mem:
        for r in rows:
            s_id = r["session_id"]
            cursor_time.execute("SELECT end_time FROM sessions WHERE session_id = ? LIMIT 1;", (s_id,))
            s_row = cursor_time.fetchone()
            if s_row and s_row["end_time"] is not None:
                summary = json.loads(r["summary_json"])
                summary["confidence"] = 1.0
                
                conn_mem.execute(
                    """
                    UPDATE sessions_summary
                    SET summary_json = ?, confidence = 1.0, last_updated = ?
                    WHERE session_id = ?;
                    """,
                    (json.dumps(summary), now_str, s_id)
                )
                
                # Update daily summaries affected by this session
                date_str = r["created_at"][:10]
                cursor_mem2 = conn_mem.cursor()
                cursor_mem2.execute("SELECT summary_json FROM sessions_summary WHERE created_at LIKE ?;", (f"{date_str}%",))
                session_rows = cursor_mem2.fetchall()
                if session_rows:
                    session_summaries = [json.loads(s_row2["summary_json"]) for s_row2 in session_rows]
                    daily_summary = merge_session_summaries_into_daily(session_summaries)
                    
                    conn_mem.execute(
                        """
                        INSERT OR REPLACE INTO daily_summaries (date, summary_json, confidence, source_session_ids, last_updated)
                        VALUES (?, ?, ?, ?, ?);
                        """,
                        (
                            date_str,
                            json.dumps(daily_summary),
                            daily_summary["confidence"],
                            json.dumps(daily_summary["source_session_ids"]),
                            now_str
                        )
                    )

def run_incremental_pipeline(timeline_db_path: str, memory_db_path: str) -> int:
    """
    Runs the incremental memory processing pipeline.
    Pulls unprocessed timeline events, aggregates session/daily summaries, evolves facts,
    clusters episodes, and bookmarks progress.
    Returns the number of events processed.
    """
    # 1. Ensure memory database is initialized
    init_memory_db(memory_db_path)
    
    conn_mem = sqlite3.connect(memory_db_path)
    conn_mem.row_factory = sqlite3.Row
    
    # Check if timeline database exists
    import os
    if not os.path.exists(timeline_db_path):
        conn_mem.close()
        return 0
        
    conn_time = sqlite3.connect(timeline_db_path)
    conn_time.row_factory = sqlite3.Row
    
    # Sync closed sessions first
    _check_and_close_active_sessions(conn_time, conn_mem)
    
    total_processed = 0
    BATCH_SIZE = 1000
    
    try:
        while True:
            # 2. Get last processed event ID from memory DB
            cursor_mem = conn_mem.cursor()
            cursor_mem.execute("SELECT state_value FROM processing_state WHERE state_key = 'last_processed_event_id';")
            row = cursor_mem.fetchone()
            last_processed_id = int(row["state_value"]) if row else 0
            
            # 3. Pull next batch of events from timeline DB
            cursor_time = conn_time.cursor()
            cursor_time.execute(
                """
                SELECT id, event_uuid, timestamp, session_id, event_type, subtype, dimension, x, y, z, importance, source, parent_event_uuid, parent_session_uuid, data_json
                FROM events
                WHERE id > ?
                ORDER BY id ASC
                LIMIT ?;
                """,
                (last_processed_id, BATCH_SIZE)
            )
            rows = cursor_time.fetchall()
            if not rows:
                break # All caught up!
                
            # Unpack rows into list of dictionaries
            events = []
            max_id = last_processed_id
            for r in rows:
                max_id = max(max_id, r["id"])
                try:
                    data = json.loads(r["data_json"])
                except Exception:
                    data = {}
                events.append({
                    "id": r["id"],
                    "event_uuid": r["event_uuid"],
                    "timestamp": r["timestamp"],
                    "session_id": r["session_id"],
                    "event_type": r["event_type"],
                    "subtype": r["subtype"],
                    "dimension": r["dimension"],
                    "x": r["x"],
                    "y": r["y"],
                    "z": r["z"],
                    "importance": r["importance"],
                    "source": r["source"],
                    "parent_event_uuid": r["parent_event_uuid"],
                    "parent_session_uuid": r["parent_session_uuid"],
                    "data": data
                })
                
            # 4. Group events by session_id and update session summaries
            sessions_events: Dict[str, List[dict]] = {}
            for e in events:
                s_id = e["session_id"]
                sessions_events.setdefault(s_id, []).append(e)
                
            now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            
            with conn_mem:
                for s_id, s_evts in sessions_events.items():
                    # Check if session is closed in timeline DB
                    cursor_time.execute("SELECT end_time FROM sessions WHERE session_id = ? LIMIT 1;", (s_id,))
                    s_row = cursor_time.fetchone()
                    session_is_closed = (s_row is not None) and (s_row["end_time"] is not None)
                    
                    # Fetch existing summary in memory DB
                    cursor_mem.execute("SELECT summary_json, created_at FROM sessions_summary WHERE session_id = ?;", (s_id,))
                    existing_row = cursor_mem.fetchone()
                    existing_summary = json.loads(existing_row["summary_json"]) if existing_row else None
                    
                    # Process and update summary
                    updated_summary = process_events_for_session(existing_summary, s_evts, session_is_closed)
                    
                    # Save updated summary
                    conn_mem.execute(
                        """
                        INSERT OR REPLACE INTO sessions_summary (session_id, summary_json, confidence, source_event_uuids, created_at, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?);
                        """,
                        (
                            s_id,
                            json.dumps(updated_summary),
                            updated_summary["confidence"],
                            json.dumps(updated_summary["source_event_uuids"]),
                            existing_row["created_at"] if existing_row else now_str,
                            now_str
                        )
                    )
                    
                # 5. Daily Summaries Processing
                # Extract UTC dates for events processed
                dates_to_update = set()
                for e in events:
                    if e["timestamp"]:
                        # Extract YYYY-MM-DD from ISO string
                        dates_to_update.add(e["timestamp"][:10])
                        
                for date_str in dates_to_update:
                    # Query all session summaries starting on this date
                    # We look for sessions starting with the date string in created_at
                    cursor_mem.execute("SELECT summary_json, confidence FROM sessions_summary WHERE created_at LIKE ?;", (f"{date_str}%",))
                    session_rows = cursor_mem.fetchall()
                    if session_rows:
                        session_summaries = [json.loads(row["summary_json"]) for row in session_rows]
                        daily_summary = merge_session_summaries_into_daily(session_summaries)
                        
                        conn_mem.execute(
                            """
                            INSERT OR REPLACE INTO daily_summaries (date, summary_json, confidence, source_session_ids, last_updated)
                            VALUES (?, ?, ?, ?, ?);
                            """,
                            (
                                date_str,
                                json.dumps(daily_summary),
                                daily_summary["confidence"],
                                json.dumps(daily_summary["source_session_ids"]),
                                now_str
                            )
                        )
                        
                # 6. Evolve Facts
                extract_and_update_facts(conn_mem, events)
                
                # 7. Cluster Episodes
                process_events_for_episodes(conn_mem, events)
                
                # 8. Bookmark processed checkpoint bookmark
                conn_mem.execute(
                    """
                    INSERT OR REPLACE INTO processing_state (state_key, state_value)
                    VALUES ('last_processed_event_id', ?);
                    """,
                    (str(max_id),)
                )
                
            total_processed += len(events)
            if len(events) < BATCH_SIZE:
                break # No more events to process in this run
                
        # 9. Sync vector embeddings incrementally (at the end of the entire run, outside main transaction)
        from backend.memory.indexing import run_indexing_sync
        run_indexing_sync(conn_mem)
        
    finally:
        conn_time.close()
        conn_mem.close()
        
    return total_processed
