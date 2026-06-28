import os
import queue
import threading
import time
import json
import uuid
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set, List

from backend.memory.models import GameplayEvent, SessionMetadata
from backend.memory.timeline import init_db, write_session, close_session

# Configuration defaults
AUTO_BATCH_WINDOW_SECONDS = 5.0
AUTO_BATCH_MAX_DURATION_SECONDS = 60.0
MINING_STREAK_THRESHOLD = 5
PICKUP_STREAK_THRESHOLD = 10

COMMON_BLOCKS_AND_ITEMS: Set[str] = {
    "stone", "cobblestone", "dirt", "grass_block", "gravel", "sand", "sandstone",
    "netherrack", "andesite", "diorite", "granite", "tuff", "deepslate", "blackstone",
    "basalt", "oak_planks", "spruce_planks", "birch_planks", "jungle_planks",
    "acacia_planks", "dark_oak_planks", "mangrove_planks", "cherry_planks", "bamboo_planks",
    "crimson_planks", "warped_planks", "cobbled_deepslate", "terracotta", "clay",
    "red_sand", "coal", "charcoal", "stick", "wheat_seeds", "sugar_cane", "oak_leaves",
    "torch"
}

VALUABLE_ORES: Set[str] = {
    "diamond_ore", "deepslate_diamond_ore", "diamond",
    "ancient_debris", "netherite_scrap", "netherite_ingot",
    "emerald_ore", "deepslate_emerald_ore", "emerald",
    "gold_ore", "deepslate_gold_ore", "nether_gold_ore",
    "iron_ore", "deepslate_iron_ore",
    "lapis_ore", "deepslate_lapis_ore",
    "redstone_ore", "deepslate_redstone_ore",
    "spawner", "mob_spawner"
}

RARE_ITEMS: Set[str] = {
    "diamond", "emerald", "netherite_ingot", "netherite_scrap", "ancient_debris",
    "elytra", "totem_of_undying", "dragon_egg", "beacon", "shulker_box",
    "nether_star", "wither_skeleton_skull", "golden_apple", "enchanted_golden_apple"
}

def normalize_name(name: str) -> str:
    """Strips namespace prefixes and lowercases block/item names."""
    if not name:
        return ""
    name = name.lower().strip()
    if name.startswith("minecraft:"):
        name = name[len("minecraft:"):]
    return name

def compute_importance(event_type: str, subtype: str, data: Dict[str, Any]) -> int:
    """Assigns an importance score between 1 and 10 based on approved rules."""
    et = event_type.lower()
    st = subtype.lower()
    
    if et == "progression":
        if "dragon" in st or "dragon" in str(data).lower():
            return 10
        if "wither" in st or "wither" in str(data).lower():
            return 10
        if "beacon" in st or "beacon" in str(data).lower():
            return 10
        return 7
        
    if et == "combat":
        if st == "boss_defeated":
            return 10
        if st == "player_death":
            return 8
        if "totem" in st:
            return 7
        if "wither" in str(data).lower() or "dragon" in str(data).lower() or "warden" in str(data).lower():
            return 9
        if st == "player_damaged":
            return 5
        return 3
        
    if et == "mining":
        block = normalize_name(data.get("block_type") or data.get("ore_type") or "")
        if "diamond" in block:
            return 8
        if "ancient_debris" in block or "netherite" in block:
            return 8
        if "emerald" in block:
            return 8
        if "spawner" in st or "spawner" in block:
            return 8
        if "gold" in block:
            return 6
        if "iron" in block:
            return 6
        return 3
        
    if et == "building":
        if "construction_end" in st:
            return 6
        if "construction_start" in st:
            return 5
        if "place_streak" in st or "break_streak" in st:
            block = normalize_name(data.get("block_type") or "")
            if block in COMMON_BLOCKS_AND_ITEMS:
                return 1
            return 2
        return 1
        
    if et == "crafting":
        item = normalize_name(data.get("item_type") or "")
        if "diamond" in item or "netherite" in item:
            return 7
        if "enchanting_table" in item or "anvil" in item:
            return 6
        if "furnace" in item or "chest" in item:
            return 3
        return 2
        
    if et == "inventory":
        item = normalize_name(data.get("item_type") or "")
        if item in RARE_ITEMS or "elytra" in item or "totem" in item:
            return 7
        if "diamond" in item:
            return 6
        if "death_loss" in st:
            return 8
        return 3
        
    if et == "exploration":
        if "discover_structure" in st:
            struct = normalize_name(data.get("structure_type") or "")
            if struct in {"stronghold", "ancient_city", "bastion", "fortress", "trial_chamber", "ocean_monument", "woodland_mansion"}:
                return 7
            return 5
        if "enter_dimension" in st:
            return 6
        if "enter_biome" in st:
            return 4
        return 4
        
    if et == "villagers":
        if "cure" in st:
            return 9
        if "breed" in st:
            return 4
        if "trade" in st:
            return 5
        return 3
        
    if et == "animals":
        if "tame" in st:
            return 5
        if "breed" in st:
            return 4
        if "ride" in st:
            return 4
        return 3
        
    return 1

class AutoBatch:
    def __init__(self, event_type: str, subtype: str, dimension: str, x: float, y: float, z: float, data: Dict[str, Any], source: str, parent_event_uuid: Optional[str] = None, parent_session_uuid: Optional[str] = None, timestamp: Optional[str] = None):
        self.event_type = event_type
        self.subtype = subtype
        self.dimension = dimension
        self.start_x = x
        self.start_y = y
        self.start_z = z
        self.end_x = x
        self.end_y = y
        self.end_z = z
        self.source = source
        self.parent_event_uuid = parent_event_uuid
        self.parent_session_uuid = parent_session_uuid
        self.timestamp = timestamp
        
        now = time.time()
        self.start_time = now
        self.last_updated = now
        self.count = 1
        
        # Block / Item naming
        self.item_or_block = normalize_name(data.get("block_type") or data.get("item_type") or data.get("name") or "unknown")
        self.data_summary = dict(data)
        if "quantity" in self.data_summary:
            self.data_summary["quantity"] = int(self.data_summary["quantity"])
        else:
            self.data_summary["quantity"] = 1

    def update(self, x: float, y: float, z: float, data: Dict[str, Any]):
        self.end_x = x
        self.end_y = y
        self.end_z = z
        self.last_updated = time.time()
        self.count += 1
        
        # Aggregate quantity if present
        qty = int(data.get("quantity", 1))
        self.data_summary["quantity"] = self.data_summary.get("quantity", 1) + qty

    def is_expired(self, current_time: float) -> bool:
        return (current_time - self.last_updated > AUTO_BATCH_WINDOW_SECONDS) or \
               (current_time - self.start_time > AUTO_BATCH_MAX_DURATION_SECONDS)


class DatabaseWorker(threading.Thread):
    """Background worker thread that writes events to SQLite sequentially using transactions."""
    def __init__(self, db_path: str, write_queue: queue.Queue):
        super().__init__(name="TimelineDBWorker", daemon=True)
        self.db_path = db_path
        self.queue = write_queue
        self.running = True

    def run(self):
        import sqlite3
        init_db(self.db_path)
        conn = sqlite3.connect(self.db_path)
        # WAL mode
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        
        while self.running or not self.queue.empty():
            try:
                # Poll with timeout to check self.running regularly
                item = self.queue.get(timeout=0.2)
            except queue.Empty:
                continue
                
            if item is None:
                # Sentinel shutdown
                self.queue.task_done()
                break
                
            try:
                self._process_item(conn, item)
            except Exception as e:
                print(f"[TimelineDBWorker] Error writing to DB: {e}", flush=True)
            finally:
                self.queue.task_done()
                
        conn.close()

    def _process_item(self, conn: sqlite3.Connection, item: Any):
        with conn:
            if isinstance(item, SessionMetadata):
                # Write session metadata
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sessions (session_id, game_version, mod_version, backend_version, world_seed, world_name, start_time, end_time, archived)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.session_id,
                        item.game_version,
                        item.mod_version,
                        item.backend_version,
                        item.world_seed,
                        item.world_name,
                        item.start_time,
                        item.end_time,
                        1 if getattr(item, "archived", False) else 0
                    )
                )
            elif isinstance(item, GameplayEvent):
                # Write single event
                conn.execute(
                    """
                    INSERT INTO events (event_uuid, timestamp, session_id, event_type, subtype, dimension, x, y, z, importance, source, parent_event_uuid, parent_session_uuid, data_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.event_uuid,
                        item.timestamp,
                        item.session_id,
                        item.event_type,
                        item.subtype,
                        item.dimension,
                        item.x,
                        item.y,
                        item.z,
                        item.importance,
                        item.source,
                        item.parent_event_uuid,
                        item.parent_session_uuid,
                        json.dumps(item.data)
                    )
                )


class EventLogger:
    _instance: Optional['EventLogger'] = None
    _global_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> 'EventLogger':
        with cls._global_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self.db_path: str = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "memory", "timeline.db"
        )
        self.session_id: str = str(uuid.uuid4())
        self.session_metadata: Optional[SessionMetadata] = None
        
        self._write_queue: queue.Queue = queue.Queue()
        self._worker: Optional[DatabaseWorker] = None
        self._flusher_thread: Optional[threading.Thread] = None
        
        self._lock = threading.RLock()
        self._active_batches: Dict[str, GameplayEvent] = {} # explicit batches
        self._auto_batches: Dict[str, AutoBatch] = {}       # automatic/streak batches
        
        self._initialized = False
        self._running = False

    def initialize(
        self,
        session_id: Optional[str] = None,
        db_path: Optional[str] = None,
        game_version: Optional[str] = None,
        mod_version: Optional[str] = None,
        world_seed: Optional[str] = None,
        world_name: Optional[str] = None
    ) -> None:
        """Initializes the logger database connection, worker thread, and starts session."""
        with self._lock:
            if self._initialized:
                return

            if db_path:
                self.db_path = db_path
            if session_id:
                self.session_id = session_id

            # Create Database Schema
            init_db(self.db_path)
            
            # Start Worker Threads
            self._running = True
            self._worker = DatabaseWorker(self.db_path, self._write_queue)
            self._worker.start()
            
            # Start flusher thread for auto-batches
            self._flusher_thread = threading.Thread(target=self._auto_batch_flusher_loop, name="AutoBatchFlusher", daemon=True)
            self._flusher_thread.start()

            # Record Session Metadata
            self.session_metadata = SessionMetadata(
                session_id=self.session_id,
                game_version=game_version,
                mod_version=mod_version,
                world_seed=world_seed,
                world_name=world_name,
                start_time=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            )
            self._write_queue.put(self.session_metadata)
            
            self._initialized = True

    def log_event(
        self,
        event_type: str,
        subtype: str,
        dimension: str,
        x: float,
        y: float,
        z: float,
        data: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
        source: str = "PLAYER",
        importance: Optional[int] = None,
        batch_key: Optional[str] = None,
        parent_event_uuid: Optional[str] = None,
        parent_session_uuid: Optional[str] = None
    ) -> str:
        """
        Logs a gameplay event. 
        If batch_key is given, adds to/updates an explicit batch.
        Otherwise, decides whether to auto-batch/aggregate this event or log it immediately.
        Returns the event_uuid (either immediate, or the one assigned to the batch).
        """
        if data is None:
            data = {}
            
        with self._lock:
            # 1. Explicit Batching
            if batch_key:
                if batch_key in self._active_batches:
                    evt = self._active_batches[batch_key]
                    # Update coordinates
                    evt.x = x
                    evt.y = y
                    evt.z = z
                    
                    if parent_event_uuid:
                        evt.parent_event_uuid = parent_event_uuid
                    if parent_session_uuid:
                        evt.parent_session_uuid = parent_session_uuid
                        
                    # Accumulate counts or merge data
                    evt.data["count"] = evt.data.get("count", 1) + 1
                    # Merge data keys
                    for k, v in data.items():
                        if k == "quantity" or k == "count":
                            evt.data[k] = evt.data.get(k, 1) + v
                        else:
                            evt.data[k] = v
                    return evt.event_uuid
                else:
                    # Initialize explicit batch
                    self.start_batch(batch_key, event_type, subtype, dimension, x, y, z, data, source, importance, parent_event_uuid, parent_session_uuid)
                    return self._active_batches[batch_key].event_uuid

            # 2. Check Auto-Batchability
            if self._is_auto_batchable(event_type, subtype, data):
                block_or_item = normalize_name(data.get("block_type") or data.get("item_type") or data.get("name") or "unknown")
                auto_key = f"{event_type}:{subtype}:{dimension}:{block_or_item}"
                
                # Check for active auto-batch
                if auto_key in self._auto_batches:
                    batch = self._auto_batches[auto_key]
                    if not batch.is_expired(time.time()):
                        batch.update(x, y, z, data)
                        # Accumulate relationship fields if they are updated
                        if parent_event_uuid:
                            batch.parent_event_uuid = parent_event_uuid
                        if parent_session_uuid:
                            batch.parent_session_uuid = parent_session_uuid
                        # We don't have a final UUID yet, return a placeholder or dummy UUID
                        return f"auto_batched:{auto_key}"
                    else:
                        # Flush expired
                        self._flush_auto_batch(auto_key, batch)
                
                # Create a new auto-batch
                self._auto_batches[auto_key] = AutoBatch(event_type, subtype, dimension, x, y, z, data, source, parent_event_uuid, parent_session_uuid, timestamp)
                return f"auto_batched:{auto_key}"

            # 3. Standard immediate event logging
            if not timestamp:
                timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                
            if importance is None:
                importance = compute_importance(event_type, subtype, data)
                
            event = GameplayEvent(
                event_type=event_type,
                subtype=subtype,
                dimension=dimension,
                x=x,
                y=y,
                z=z,
                data=data,
                timestamp=timestamp,
                session_id=self.session_id,
                importance=importance,
                source=source,
                parent_event_uuid=parent_event_uuid,
                parent_session_uuid=parent_session_uuid
            )
            self._write_queue.put(event)
            return event.event_uuid

    def start_batch(
        self,
        batch_key: str,
        event_type: str,
        subtype: str,
        dimension: str,
        x: float,
        y: float,
        z: float,
        initial_data: Optional[Dict[str, Any]] = None,
        source: str = "PLAYER",
        importance: Optional[int] = None,
        parent_event_uuid: Optional[str] = None,
        parent_session_uuid: Optional[str] = None
    ) -> None:
        """Starts an explicit batch recording session."""
        if initial_data is None:
            initial_data = {}
            
        with self._lock:
            if "count" not in initial_data:
                initial_data["count"] = 1
                
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            
            # Start coordinate tracking
            initial_data["start_coords"] = [x, y, z]
            initial_data["start_time"] = timestamp
            
            if importance is None:
                importance = compute_importance(event_type, subtype, initial_data)
                
            event = GameplayEvent(
                event_type=event_type,
                subtype=subtype,
                dimension=dimension,
                x=x,
                y=y,
                z=z,
                data=initial_data,
                timestamp=timestamp,
                session_id=self.session_id,
                importance=importance,
                source=source,
                parent_event_uuid=parent_event_uuid,
                parent_session_uuid=parent_session_uuid
            )
            self._active_batches[batch_key] = event

    def end_batch(self, batch_key: str) -> Optional[str]:
        """Finalizes an explicit batch, computing statistics and queuing the record."""
        with self._lock:
            if batch_key not in self._active_batches:
                return None
                
            evt = self._active_batches.pop(batch_key)
            now = datetime.now(timezone.utc)
            evt.data["end_coords"] = [evt.x, evt.y, evt.z]
            evt.data["end_time"] = now.isoformat().replace("+00:00", "Z")
            
            # Calculate duration
            try:
                start_dt = datetime.fromisoformat(evt.data["start_time"].replace("Z", "+00:00"))
                duration = (now - start_dt).total_seconds()
                evt.data["duration_seconds"] = max(0.1, duration)
            except Exception:
                evt.data["duration_seconds"] = 1.0
                
            # Recompute importance since stats/counts updated
            evt.importance = compute_importance(evt.event_type, evt.subtype, evt.data)
            
            self._write_queue.put(evt)
            return evt.event_uuid

    def flush(self) -> None:
        """Flushes all auto-batches in memory, then blocks until the database queue is fully written."""
        with self._lock:
            # 1. Flush all auto-batches
            for key, batch in list(self._auto_batches.items()):
                self._flush_auto_batch(key, batch)
            self._auto_batches.clear()
            
        # 2. Block until write queue is processed
        if self._worker and self._worker.is_alive():
            self._write_queue.join()

    def close(self) -> None:
        """Closes the current session and stops all worker threads."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            
            # Flush everything
            self.flush()
            
            # Close session metadata in DB
            if self.session_metadata:
                self.session_metadata.end_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                self._write_queue.put(self.session_metadata)
                
            # Stop worker threads
            self._write_queue.put(None) # Sentinel shutdown
            
            if self._worker:
                self._worker.join()
            if self._flusher_thread:
                self._flusher_thread.join()
                
            self._initialized = False

    def _is_auto_batchable(self, event_type: str, subtype: str, data: Dict[str, Any]) -> bool:
        """Determines if an event can be auto-batched/aggregated in memory."""
        et = event_type.lower()
        st = subtype.lower()
        
        # 1. Building placements & breaks
        if et == "building" and st in {"place_block", "break_block"}:
            return True
            
        # 2. Mining ore breaks
        if et == "mining" and st == "ore_mined":
            return True
            
        # 3. Inventory pickups
        if et == "inventory" and st == "pickup":
            return True
            
        return False

    def _flush_auto_batch(self, key: str, batch: AutoBatch) -> None:
        """Converts an AutoBatch into a GameplayEvent if it meets size/streak thresholds."""
        with self._lock:
            self._auto_batches.pop(key, None)
            
        # Determine if streak threshold is met for common items
        item = batch.item_or_block
        is_common = item in COMMON_BLOCKS_AND_ITEMS
        
        if is_common:
            if batch.subtype == "break_block" and batch.count < MINING_STREAK_THRESHOLD:
                # Ignore insignificant mining
                return
            if batch.subtype == "pickup" and batch.count < PICKUP_STREAK_THRESHOLD:
                # Ignore insignificant pickups
                return
                
        # Transform subtypes to streak/aggregate representations
        final_subtype = batch.subtype
        if batch.subtype == "place_block":
            final_subtype = "place_streak"
        elif batch.subtype == "break_block":
            final_subtype = "break_streak"
        elif batch.subtype == "ore_mined":
            final_subtype = "ore_mined_batch"
        elif batch.subtype == "pickup":
            final_subtype = "pickup_streak"

        # Construct final event metadata
        duration = max(0.1, batch.last_updated - batch.start_time)
        final_data = {
            "name": item,
            "block_type" if batch.event_type.lower() != "inventory" else "item_type": item,
            "count": batch.count,
            "start_coords": [batch.start_x, batch.start_y, batch.start_z],
            "end_coords": [batch.end_x, batch.end_y, batch.end_z],
            "duration_seconds": duration,
            **batch.data_summary
        }
        
        if batch.timestamp:
            timestamp = batch.timestamp
        else:
            timestamp = datetime.fromtimestamp(batch.start_time, timezone.utc).isoformat().replace("+00:00", "Z")
        importance = compute_importance(batch.event_type, final_subtype, final_data)
        
        event = GameplayEvent(
            event_type=batch.event_type,
            subtype=final_subtype,
            dimension=batch.dimension,
            x=batch.start_x,
            y=batch.start_y,
            z=batch.start_z,
            data=final_data,
            timestamp=timestamp,
            session_id=self.session_id,
            importance=importance,
            source=batch.source,
            parent_event_uuid=batch.parent_event_uuid,
            parent_session_uuid=batch.parent_session_uuid
        )
        self._write_queue.put(event)

    def _auto_batch_flusher_loop(self) -> None:
        """Periodic thread loop that checks for and flushes expired auto-batches."""
        while self._running:
            try:
                now = time.time()
                expired = []
                with self._lock:
                    for k, batch in self._auto_batches.items():
                        if batch.is_expired(now):
                            expired.append((k, batch))
                            
                for k, batch in expired:
                    self._flush_auto_batch(k, batch)
            except Exception as e:
                print(f"[AutoBatchFlusher] Error in flusher loop: {e}", flush=True)
                
            time.sleep(1.0)
