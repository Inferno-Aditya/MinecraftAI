import os
import sqlite3
import json
import threading
import time
from typing import List, Dict, Any, Optional

from backend.memory.processor import init_memory_db, run_incremental_pipeline

class MemoryManager:
    _instance: Optional['MemoryManager'] = None
    _global_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> 'MemoryManager':
        with cls._global_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self.memory_db_path: str = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "memory", "memory.db"
        )
        self.timeline_db_path: str = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "memory", "timeline.db"
        )
        
        self._lock = threading.RLock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._initialized = False

    def initialize(self, memory_db_path: Optional[str] = None, timeline_db_path: Optional[str] = None, start_worker: bool = True) -> None:
        """Initializes database schema and starts the background periodic processing thread if requested."""
        with self._lock:
            if self._initialized:
                return

            if memory_db_path:
                self.memory_db_path = memory_db_path
            if timeline_db_path:
                self.timeline_db_path = timeline_db_path

            # Ensure directory exists and schema is set up
            os.makedirs(os.path.dirname(os.path.abspath(self.memory_db_path)), exist_ok=True)
            init_memory_db(self.memory_db_path)
            
            # Start background processing thread if requested
            if start_worker:
                self._running = True
                self._worker_thread = threading.Thread(
                    target=self._processing_loop, 
                    name="MemoryProcessingWorker", 
                    daemon=True
                )
                self._worker_thread.start()
            
            self._initialized = True

    def trigger_processing(self) -> int:
        """Synchronously triggers the processing pipeline. Useful for tests and direct updates."""
        with self._lock:
            return run_incremental_pipeline(self.timeline_db_path, self.memory_db_path)

    def list_sessions(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Queries session summaries from the memory database."""
        conn = sqlite3.connect(self.memory_db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT session_id, summary_json, confidence, source_event_uuids, created_at, last_updated FROM sessions_summary ORDER BY created_at DESC LIMIT ? OFFSET ?;",
                (limit, offset)
            )
            rows = cursor.fetchall()
            result = []
            for r in rows:
                result.append({
                    "session_id": r["session_id"],
                    "summary": json.loads(r["summary_json"]),
                    "confidence": r["confidence"],
                    "source_event_uuids": json.loads(r["source_event_uuids"]),
                    "created_at": r["created_at"],
                    "last_updated": r["last_updated"]
                })
            return result
        finally:
            conn.close()

    def list_daily_memories(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Queries daily memories from the memory database."""
        conn = sqlite3.connect(self.memory_db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT date, summary_json, confidence, source_session_ids, last_updated FROM daily_summaries ORDER BY date DESC LIMIT ? OFFSET ?;",
                (limit, offset)
            )
            rows = cursor.fetchall()
            result = []
            for r in rows:
                result.append({
                    "date": r["date"],
                    "summary": json.loads(r["summary_json"]),
                    "confidence": r["confidence"],
                    "source_session_ids": json.loads(r["source_session_ids"]),
                    "last_updated": r["last_updated"]
                })
            return result
        finally:
            conn.close()

    def list_facts(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Queries player facts from the memory database."""
        conn = sqlite3.connect(self.memory_db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT fact_key, fact_value_json, confidence, history_json, source_event_uuids, source_session_ids, last_updated FROM facts ORDER BY last_updated DESC LIMIT ? OFFSET ?;",
                (limit, offset)
            )
            rows = cursor.fetchall()
            result = []
            for r in rows:
                result.append({
                    "fact_key": r["fact_key"],
                    "value": json.loads(r["fact_value_json"]),
                    "confidence": r["confidence"],
                    "history": json.loads(r["history_json"]),
                    "source_event_uuids": json.loads(r["source_event_uuids"]),
                    "source_session_ids": json.loads(r["source_session_ids"]),
                    "last_updated": r["last_updated"]
                })
            return result
        finally:
            conn.close()

    def list_episodes(self, limit: int = 100, offset: int = 0, episode_type: Optional[str] = None, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Queries grouped episodes from the memory database with filters."""
        conn = sqlite3.connect(self.memory_db_path)
        conn.row_factory = sqlite3.Row
        try:
            query = "SELECT episode_uuid, session_id, episode_type, start_time, end_time, event_uuids_json, summary_json, confidence, last_updated FROM episodes WHERE 1=1"
            params = []
            
            if episode_type:
                query += " AND episode_type = ?"
                params.append(episode_type)
            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)
                
            query += " ORDER BY start_time DESC LIMIT ? OFFSET ?;"
            params.extend([limit, offset])
            
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            result = []
            for r in rows:
                result.append({
                    "episode_uuid": r["episode_uuid"],
                    "session_id": r["session_id"],
                    "episode_type": r["episode_type"],
                    "start_time": r["start_time"],
                    "end_time": r["end_time"],
                    "event_uuids": json.loads(r["event_uuids_json"]),
                    "summary": json.loads(r["summary_json"]),
                    "confidence": r["confidence"],
                    "last_updated": r["last_updated"]
                })
            return result
        finally:
            conn.close()

    def search_memories(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Performs semantic similarity search over all memories."""
        from backend.memory.retriever import retrieve
        conn = sqlite3.connect(self.memory_db_path)
        try:
            return retrieve(conn, query, top_k)
        finally:
            conn.close()

    def search_memories_by_type(self, query: str, memory_type: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Performs semantic similarity search filtered by memory category."""
        from backend.memory.retriever import retrieve_by_type
        conn = sqlite3.connect(self.memory_db_path)
        try:
            return retrieve_by_type(conn, query, memory_type, top_k)
        finally:
            conn.close()

    def search_similar_memories(self, memory_uuid: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Finds memories semantically similar to an existing memory."""
        from backend.memory.retriever import retrieve_similar
        conn = sqlite3.connect(self.memory_db_path)
        try:
            return retrieve_similar(conn, memory_uuid, top_k)
        finally:
            conn.close()

    def rebuild_vector_index(self) -> Any:
        """Clears the embedding store and fully re-indexes all memories."""
        from backend.memory.indexing import rebuild_entire_index
        conn = sqlite3.connect(self.memory_db_path)
        try:
            return rebuild_entire_index(conn)
        finally:
            conn.close()

    def get_index_statistics(self) -> Dict[str, Any]:
        """Returns statistics about indexed memories and the active embedding model."""
        conn = sqlite3.connect(self.memory_db_path)
        try:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM sessions_summary;")
            sessions_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM daily_summaries;")
            daily_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM facts;")
            facts_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM episodes;")
            episodes_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM memory_embeddings;")
            embeddings_count = cursor.fetchone()[0]
            
            # Fetch model metadata
            cursor.execute("SELECT embedding_model, embedding_dimension, embedding_version FROM memory_embeddings LIMIT 1;")
            row = cursor.fetchone()
            if row:
                model_info = {"model": row[0], "dimension": row[1], "version": row[2]}
            else:
                from backend.memory.embeddings import get_model_metadata
                model_info = get_model_metadata()
                
            return {
                "sessions_count": sessions_count,
                "daily_count": daily_count,
                "facts_count": facts_count,
                "episodes_count": episodes_count,
                "embeddings_count": embeddings_count,
                "model_info": model_info
            }
        finally:
            conn.close()

    def close(self) -> None:
        """Stops the background periodic worker thread."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            
        if self._worker_thread:
            self._worker_thread.join(timeout=3.0)
            self._worker_thread = None
            
        with self._lock:
            self._initialized = False

    def _processing_loop(self) -> None:
        """Loop run by background thread to process new timeline events every 5 seconds."""
        while self._running:
            try:
                run_incremental_pipeline(self.timeline_db_path, self.memory_db_path)
            except Exception as e:
                print(f"[MemoryProcessingWorker] Error in pipeline: {e}", flush=True)
            time.sleep(5.0)
