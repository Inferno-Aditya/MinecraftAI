import sqlite3
import json
import os
import shutil
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from backend.memory.models import GameplayEvent, SessionMetadata

SCHEMA_VERSION = 1

def get_connection(db_path: str) -> sqlite3.Connection:
    """Returns a SQLite connection with row factory and WAL mode enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for concurrency and performance
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db(db_path: str) -> None:
    """
    Initializes the database schema and performs version migrations if needed.
    Creates tables: schema_version, sessions, events, and indexes.
    """
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = get_connection(db_path)
    try:
        # Check if schema_version table exists
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version';")
        has_schema_table = cursor.fetchone() is not None

        if not has_schema_table:
            # First-time setup
            with conn:
                conn.execute("""
                    CREATE TABLE schema_version (
                        schema_version INTEGER PRIMARY KEY,
                        created_at TEXT NOT NULL,
                        last_migrated TEXT NOT NULL
                    );
                """)
                conn.execute("""
                    CREATE TABLE sessions (
                        session_id TEXT PRIMARY KEY,
                        game_version TEXT,
                        mod_version TEXT,
                        backend_version TEXT,
                        world_seed TEXT,
                        world_name TEXT,
                        start_time TEXT NOT NULL,
                        end_time TEXT,
                        archived INTEGER NOT NULL DEFAULT 0
                    );
                """)
                conn.execute("""
                    CREATE TABLE events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_uuid TEXT NOT NULL UNIQUE,
                        timestamp TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        subtype TEXT NOT NULL,
                        dimension TEXT NOT NULL,
                        x REAL NOT NULL,
                        y REAL NOT NULL,
                        z REAL NOT NULL,
                        importance INTEGER NOT NULL,
                        source TEXT NOT NULL,
                        parent_event_uuid TEXT REFERENCES events(event_uuid) ON DELETE SET NULL,
                        parent_session_uuid TEXT,
                        data_json TEXT NOT NULL,
                        FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                    );
                """)
                
                # Indexes
                conn.execute("CREATE INDEX idx_events_timestamp ON events (timestamp);")
                conn.execute("CREATE INDEX idx_events_session_type ON events (session_id, event_type);")
                conn.execute("CREATE INDEX idx_events_type_subtype ON events (event_type, subtype);")
                conn.execute("CREATE INDEX idx_events_uuid ON events (event_uuid);")
                conn.execute("CREATE INDEX idx_events_parent ON events (parent_event_uuid);")

                # Insert initial schema version
                now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                conn.execute(
                    "INSERT INTO schema_version (schema_version, created_at, last_migrated) VALUES (?, ?, ?);",
                    (SCHEMA_VERSION, now_str, now_str)
                )
        else:
            # Schema table exists, check version
            cursor.execute("SELECT schema_version FROM schema_version ORDER BY schema_version DESC LIMIT 1;")
            row = cursor.fetchone()
            current_version = row["schema_version"] if row else 0
            
            if current_version < SCHEMA_VERSION:
                # Run migrations (placeholder for future migrations)
                # migrate_to_version(conn, current_version, SCHEMA_VERSION)
                pass
            
            # Auto-migration: check if events table has parent_event_uuid column
            cursor.execute("PRAGMA table_info(events);")
            columns = [col["name"] for col in cursor.fetchall()]
            if "parent_event_uuid" not in columns:
                with conn:
                    conn.execute("ALTER TABLE events ADD COLUMN parent_event_uuid TEXT REFERENCES events(event_uuid) ON DELETE SET NULL;")
                    conn.execute("ALTER TABLE events ADD COLUMN parent_session_uuid TEXT;")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_parent ON events (parent_event_uuid);")
            cursor.execute("SELECT schema_version FROM schema_version ORDER BY schema_version DESC LIMIT 1;")
            row = cursor.fetchone()
            current_version = row["schema_version"] if row else 0
            
            if current_version < SCHEMA_VERSION:
                # Run migrations (placeholder for future migrations)
                # migrate_to_version(conn, current_version, SCHEMA_VERSION)
                pass
    finally:
        conn.close()

def write_session(db_path: str, session: SessionMetadata) -> None:
    """Inserts or updates a session metadata row."""
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, game_version, mod_version, backend_version, world_seed, world_name, start_time, end_time, archived)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    game_version=excluded.game_version,
                    mod_version=excluded.mod_version,
                    backend_version=excluded.backend_version,
                    world_seed=excluded.world_seed,
                    world_name=excluded.world_name,
                    start_time=excluded.start_time,
                    end_time=excluded.end_time,
                    archived=excluded.archived
                """,
                (
                    session.session_id,
                    session.game_version,
                    session.mod_version,
                    session.backend_version,
                    session.world_seed,
                    session.world_name,
                    session.start_time,
                    session.end_time,
                    1 if getattr(session, "archived", False) else 0
                )
            )
    finally:
        conn.close()

def close_session(db_path: str, session_id: str, end_time: Optional[str] = None) -> None:
    """Marks a session as closed by setting its end_time."""
    if not end_time:
        end_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                "UPDATE sessions SET end_time = ? WHERE session_id = ?;",
                (end_time, session_id)
            )
    finally:
        conn.close()

def query_events(
    db_path: str,
    session_id: Optional[str] = None,
    event_type: Optional[str] = None,
    subtype: Optional[str] = None,
    dimension: Optional[str] = None,
    min_importance: Optional[int] = None,
    source: Optional[str] = None,
    parent_event_uuid: Optional[str] = None,
    parent_session_uuid: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    sort: str = "desc",
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Queries events in the database with extensive filtering options."""
    conn = get_connection(db_path)
    try:
        query = "SELECT id, event_uuid, timestamp, session_id, event_type, subtype, dimension, x, y, z, importance, source, parent_event_uuid, parent_session_uuid, data_json FROM events WHERE 1=1"
        params: List[Any] = []
        
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if subtype:
            query += " AND subtype = ?"
            params.append(subtype)
        if dimension:
            query += " AND dimension = ?"
            params.append(dimension)
        if min_importance is not None:
            query += " AND importance >= ?"
            params.append(min_importance)
        if source:
            query += " AND source = ?"
            params.append(source)
        if parent_event_uuid:
            query += " AND parent_event_uuid = ?"
            params.append(parent_event_uuid)
        if parent_session_uuid:
            query += " AND parent_session_uuid = ?"
            params.append(parent_session_uuid)
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
            
        order = "ASC" if sort.lower() == "asc" else "DESC"
        query += f" ORDER BY timestamp {order}, id {order} LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        events = []
        for r in rows:
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
        return events
    finally:
        conn.close()

def get_sessions(db_path: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """Gets list of all sessions in reverse-chronological order."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions ORDER BY start_time DESC LIMIT ? OFFSET ?;", (limit, offset))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def get_event_by_uuid(db_path: str, event_uuid: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single event by its UUID."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events WHERE event_uuid = ? LIMIT 1;", (event_uuid,))
        row = cursor.fetchone()
        if row:
            r = dict(row)
            try:
                r["data"] = json.loads(r["data_json"])
            except Exception:
                r["data"] = {}
            return r
        return None
    finally:
        conn.close()

def archive_session(db_path: str, session_id: str, archive_path: str) -> bool:
    """
    Archives a completed session:
    1. Copies session metadata and all corresponding events from db_path into a new SQLite database at archive_path.
    2. Deletes events for the session in db_path to save space.
    3. Updates the 'archived' status of the session in db_path to 1.
    
    This satisfies the constraint of preparing for long sessions without bloating the main database.
    """
    if not os.path.exists(db_path):
        return False
        
    init_db(archive_path)
    
    conn_src = get_connection(db_path)
    conn_dest = get_connection(archive_path)
    
    try:
        # 1. Retrieve session metadata from source
        cursor_src = conn_src.cursor()
        cursor_src.execute("SELECT * FROM sessions WHERE session_id = ? LIMIT 1;", (session_id,))
        session_row = cursor_src.fetchone()
        if not session_row:
            return False
            
        session_data = dict(session_row)
        
        # 2. Retrieve all events for this session from source
        cursor_src.execute("SELECT * FROM events WHERE session_id = ?;", (session_id,))
        event_rows = [dict(r) for r in cursor_src.fetchall()]
        
        # 3. Write to destination
        with conn_dest:
            conn_dest.execute(
                """
                INSERT OR REPLACE INTO sessions (session_id, game_version, mod_version, backend_version, world_seed, world_name, start_time, end_time, archived)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    session_data["session_id"],
                    session_data["game_version"],
                    session_data["mod_version"],
                    session_data["backend_version"],
                    session_data["world_seed"],
                    session_data["world_name"],
                    session_data["start_time"],
                    session_data["end_time"]
                )
            )
            if event_rows:
                conn_dest.executemany(
                    """
                    INSERT OR REPLACE INTO events (event_uuid, timestamp, session_id, event_type, subtype, dimension, x, y, z, importance, source, parent_event_uuid, parent_session_uuid, data_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            e["event_uuid"],
                            e["timestamp"],
                            e["session_id"],
                            e["event_type"],
                            e["subtype"],
                            e["dimension"],
                            e["x"],
                            e["y"],
                            e["z"],
                            e["importance"],
                            e["source"],
                            e.get("parent_event_uuid"),
                            e.get("parent_session_uuid"),
                            e["data_json"]
                        )
                        for e in event_rows
                    ]
                )
                
        # 4. Clean up source: delete events and update archived flag
        with conn_src:
            conn_src.execute("DELETE FROM events WHERE session_id = ?;", (session_id,))
            conn_src.execute("UPDATE sessions SET archived = 1 WHERE session_id = ?;", (session_id,))
            
        return True
    except Exception as e:
        print(f"Failed to archive session {session_id}: {e}", flush=True)
        return False
    finally:
        conn_src.close()
        conn_dest.close()
