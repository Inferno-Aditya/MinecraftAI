import os
import unittest
import tempfile
import time
import shutil
import sqlite3
from datetime import datetime, timezone

from backend.memory.models import GameplayEvent, SessionMetadata
from backend.memory.timeline import query_events, get_sessions, get_event_by_uuid, archive_session
from backend.memory.event_logger import EventLogger, compute_importance, COMMON_BLOCKS_AND_ITEMS, VALUABLE_ORES

class TestTimelineAndLogger(unittest.TestCase):
    def setUp(self):
        # Create a temp directory for tests
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_timeline.db")
        
        # Get a clean/new EventLogger instance for testing
        # We bypass get_instance() to avoid sharing state between test runs
        self.logger = EventLogger()
        self.logger.initialize(
            session_id="test-session-123",
            db_path=self.db_path,
            game_version="1.21",
            mod_version="1.0.0",
            world_seed="987654321",
            world_name="Test World"
        )

    def tearDown(self):
        # Stop threads and clean up
        self.logger.close()
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass

    def test_session_metadata(self):
        """Verify session metadata table is created and written properly."""
        self.logger.flush()
        sessions = get_sessions(self.db_path)
        self.assertEqual(len(sessions), 1)
        session = sessions[0]
        self.assertEqual(session["session_id"], "test-session-123")
        self.assertEqual(session["game_version"], "1.21")
        self.assertEqual(session["mod_version"], "1.0.0")
        self.assertEqual(session["world_seed"], "987654321")
        self.assertEqual(session["world_name"], "Test World")
        self.assertIsNotNone(session["start_time"])
        self.assertIsNone(session["end_time"])
        self.assertEqual(session["archived"], 0)

        # Close session and verify end_time
        self.logger.close()
        sessions = get_sessions(self.db_path)
        self.assertIsNotNone(sessions[0]["end_time"])

    def test_basic_logging(self):
        """Verify basic event logging (zombie kill, player death, Nether entry, trading)."""
        # 1. Log Zombie Kill (Combat)
        uuid_zombie = self.logger.log_event(
            event_type="Combat",
            subtype="mob_killed",
            dimension="overworld",
            x=10.0, y=64.0, z=20.0,
            data={"mob_type": "Zombie", "weapon": "iron_sword"}
        )
        
        # 2. Log Entering Nether (Exploration)
        uuid_nether = self.logger.log_event(
            event_type="Exploration",
            subtype="enter_dimension",
            dimension="the_nether",
            x=0.0, y=80.0, z=0.0,
            data={"dimension": "the_nether"}
        )

        # 3. Log Trade (Villagers)
        uuid_trade = self.logger.log_event(
            event_type="Villagers",
            subtype="trade",
            dimension="overworld",
            x=152.0, y=70.0, z=-400.0,
            data={"villager_profession": "librarian", "input_item": "emerald", "output_item": "mending_book"}
        )

        # 4. Log Player Death (Combat)
        uuid_death = self.logger.log_event(
            event_type="Combat",
            subtype="player_death",
            dimension="the_nether",
            x=-50.0, y=32.0, z=12.0,
            data={"reason": "lava"}
        )

        self.logger.flush()
        
        # Query and verify
        events = query_events(self.db_path, session_id="test-session-123")
        # Reverse chronological by default
        self.assertEqual(len(events), 4)

        # Retrieve specific events to check values
        event_dict = {e["event_uuid"]: e for e in events}
        
        # Verify Zombie event
        self.assertIn(uuid_zombie, event_dict)
        zombie_evt = event_dict[uuid_zombie]
        self.assertEqual(zombie_evt["event_type"], "Combat")
        self.assertEqual(zombie_evt["subtype"], "mob_killed")
        self.assertEqual(zombie_evt["x"], 10.0)
        self.assertEqual(zombie_evt["importance"], 3) # Combat basic is 3
        self.assertEqual(zombie_evt["source"], "PLAYER")
        self.assertEqual(zombie_evt["data"]["mob_type"], "Zombie")

        # Verify Nether event
        self.assertIn(uuid_nether, event_dict)
        nether_evt = event_dict[uuid_nether]
        self.assertEqual(nether_evt["event_type"], "Exploration")
        self.assertEqual(nether_evt["subtype"], "enter_dimension")
        self.assertEqual(nether_evt["dimension"], "the_nether")
        self.assertEqual(nether_evt["importance"], 6) # Enter dimension is 6

        # Verify Trade event
        self.assertIn(uuid_trade, event_dict)
        trade_evt = event_dict[uuid_trade]
        self.assertEqual(trade_evt["event_type"], "Villagers")
        self.assertEqual(trade_evt["subtype"], "trade")
        self.assertEqual(trade_evt["importance"], 5) # Trade is 5

        # Verify Death event
        self.assertIn(uuid_death, event_dict)
        death_evt = event_dict[uuid_death]
        self.assertEqual(death_evt["event_type"], "Combat")
        self.assertEqual(death_evt["subtype"], "player_death")
        self.assertEqual(death_evt["importance"], 8) # Death is 8

    def test_explicit_batching(self):
        """Verify that explicit start_batch/end_batch aggregates events."""
        batch_key = "building_house_wall"
        self.logger.start_batch(
            batch_key=batch_key,
            event_type="Building",
            subtype="place_block",
            dimension="overworld",
            x=100.0, y=64.0, z=100.0,
            initial_data={"block_type": "oak_planks"}
        )
        
        # Add events to batch
        self.logger.log_event("Building", "place_block", "overworld", 101.0, 64.0, 100.0, {"block_type": "oak_planks"}, batch_key=batch_key)
        self.logger.log_event("Building", "place_block", "overworld", 102.0, 64.0, 100.0, {"block_type": "oak_planks"}, batch_key=batch_key)
        
        uuid_val = self.logger.end_batch(batch_key)
        self.logger.flush()
        
        events = query_events(self.db_path, session_id="test-session-123")
        self.assertEqual(len(events), 1)
        evt = events[0]
        self.assertEqual(evt["event_uuid"], uuid_val)
        self.assertEqual(evt["event_type"], "Building")
        self.assertEqual(evt["subtype"], "place_block")
        self.assertEqual(evt["data"]["count"], 3)
        self.assertEqual(evt["data"]["start_coords"], [100.0, 64.0, 100.0])
        self.assertEqual(evt["data"]["end_coords"], [102.0, 64.0, 100.0])
        self.assertIn("duration_seconds", evt["data"])

    def test_automatic_batching_and_thresholds(self):
        """Verify automatic aggregation and common item block/pickup threshold filtering."""
        # 1. Log a few cobblestone block placements (under auto-batching, common block)
        self.logger.log_event("Building", "place_block", "overworld", 0.0, 64.0, 0.0, {"block_type": "cobblestone"})
        self.logger.log_event("Building", "place_block", "overworld", 1.0, 64.0, 0.0, {"block_type": "cobblestone"})
        self.logger.log_event("Building", "place_block", "overworld", 2.0, 64.0, 0.0, {"block_type": "cobblestone"})

        # 2. Log 1 diamond ore mined (valuable, should never be ignored even with low count)
        self.logger.log_event("Mining", "ore_mined", "overworld", 12.0, 11.0, -50.0, {"block_type": "diamond_ore"})

        # 3. Log 1 dirt mined (common block, should be ignored because count < MINING_STREAK_THRESHOLD = 5)
        self.logger.log_event("Building", "break_block", "overworld", 5.0, 64.0, 5.0, {"block_type": "dirt"})

        # 4. Log 6 stone mined (common block, meets streak threshold of 5, should be kept)
        for i in range(6):
            self.logger.log_event("Building", "break_block", "overworld", 10.0 + i, 64.0, 10.0, {"block_type": "stone"})

        self.logger.flush()
        
        # Query results
        events = query_events(self.db_path, session_id="test-session-123")
        
        # We expect:
        # - 1 placement streak for cobblestone (count 3)
        # - 1 mining ore batch for diamond (count 1)
        # - 1 break streak for stone (count 6)
        # - The single stone break (count 1) should have been discarded!
        self.assertEqual(len(events), 3)

        event_subtypes = [e["subtype"] for e in events]
        self.assertIn("place_streak", event_subtypes)
        self.assertIn("ore_mined_batch", event_subtypes)
        self.assertIn("break_streak", event_subtypes)
        
        # Verify counts
        for e in events:
            if e["subtype"] == "place_streak":
                self.assertEqual(e["data"]["count"], 3)
                self.assertEqual(e["data"]["block_type"], "cobblestone")
            elif e["subtype"] == "ore_mined_batch":
                self.assertEqual(e["data"]["count"], 1)
                self.assertEqual(e["data"]["block_type"], "diamond_ore")
            elif e["subtype"] == "break_streak":
                self.assertEqual(e["data"]["count"], 6)
                self.assertEqual(e["data"]["block_type"], "stone")

    def test_database_persistence_restart(self):
        """Verify that logged events survive a logger shutdown and restart."""
        # Log a zombie kill
        self.logger.log_event(
            event_type="Combat", subtype="mob_killed", dimension="overworld",
            x=5.0, y=5.0, z=5.0, data={"mob_type": "Zombie"}
        )
        self.logger.flush()
        self.logger.close()
        
        # Verify the database has the event
        events = query_events(self.db_path, session_id="test-session-123")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["data"]["mob_type"], "Zombie")

        # Restart a new session on same database
        new_logger = EventLogger()
        new_logger.initialize(
            session_id="test-session-456",
            db_path=self.db_path,
            game_version="1.21",
            mod_version="1.0.0"
        )
        
        # Log a skeleton kill in the new session
        new_logger.log_event(
            event_type="Combat", subtype="mob_killed", dimension="overworld",
            x=10.0, y=10.0, z=10.0, data={"mob_type": "Skeleton"}
        )
        new_logger.flush()
        new_logger.close()

        # Query all events from the db
        all_events = query_events(self.db_path)
        self.assertEqual(len(all_events), 2)
        
        sessions = get_sessions(self.db_path)
        self.assertEqual(len(sessions), 2)

    def test_archiving(self):
        """Verify archiving a session moves events to a separate database."""
        # Log some events
        self.logger.log_event(
            event_type="Combat", subtype="mob_killed", dimension="overworld",
            x=5.0, y=5.0, z=5.0, data={"mob_type": "Zombie"}
        )
        self.logger.flush()
        
        # Archive destination
        archive_db_path = os.path.join(self.temp_dir, "archive.db")
        
        success = archive_session(self.db_path, "test-session-123", archive_db_path)
        self.assertTrue(success)
        
        # Verify events are deleted in the main DB
        main_events = query_events(self.db_path, session_id="test-session-123")
        self.assertEqual(len(main_events), 0)
        
        # Verify session is marked as archived in main DB
        main_sessions = get_sessions(self.db_path)
        self.assertEqual(len(main_sessions), 1)
        self.assertEqual(main_sessions[0]["archived"], 1)
        
        # Verify events exist in the archived DB
        archived_events = query_events(archive_db_path, session_id="test-session-123")
        self.assertEqual(len(archived_events), 1)
        self.assertEqual(archived_events[0]["data"]["mob_type"], "Zombie")
        
        archived_sessions = get_sessions(archive_db_path)
        self.assertEqual(len(archived_sessions), 1)
        self.assertEqual(archived_sessions[0]["archived"], 1)

    def test_event_relationships(self):
        """Verify that event relationships (parent UUIDs) are stored and queried correctly."""
        # 1. Log parent event
        parent_uuid = self.logger.log_event(
            event_type="Exploration", subtype="discover_structure", dimension="overworld",
            x=10.0, y=20.0, z=30.0, data={"structure_type": "mineshaft"}
        )
        
        # 2. Log child event referencing the parent (using a non-auto-batched event type like Combat)
        child_uuid = self.logger.log_event(
            event_type="Combat", subtype="mob_killed", dimension="overworld",
            x=12.0, y=18.0, z=31.0, data={"mob_type": "Zombie"},
            parent_event_uuid=parent_uuid,
            parent_session_uuid="some-parent-session-uuid"
        )
        
        self.logger.flush()
        
        # Query events filtered by parent_event_uuid
        child_events = query_events(self.db_path, parent_event_uuid=parent_uuid)
        self.assertEqual(len(child_events), 1)
        self.assertEqual(child_events[0]["event_uuid"], child_uuid)
        self.assertEqual(child_events[0]["parent_event_uuid"], parent_uuid)
        self.assertEqual(child_events[0]["parent_session_uuid"], "some-parent-session-uuid")

    def test_chronological_replay(self):
        """Verify that events can be retrieved in strict ascending chronological order."""
        # Log events with explicit timestamps
        self.logger.log_event(
            event_type="Building", subtype="place_block", dimension="overworld",
            x=1.0, y=1.0, z=1.0, data={"name": "first"}, timestamp="2026-06-28T10:00:00Z"
        )
        self.logger.log_event(
            event_type="Building", subtype="place_block", dimension="overworld",
            x=2.0, y=2.0, z=2.0, data={"name": "second"}, timestamp="2026-06-28T11:00:00Z"
        )
        self.logger.log_event(
            event_type="Building", subtype="place_block", dimension="overworld",
            x=3.0, y=3.0, z=3.0, data={"name": "third"}, timestamp="2026-06-28T12:00:00Z"
        )
        
        self.logger.flush()
        
        # Query in ascending order (chronological replay)
        events_asc = query_events(self.db_path, event_type="Building", sort="asc")
        self.assertEqual(len(events_asc), 3)
        self.assertEqual(events_asc[0]["data"]["name"], "first")
        self.assertEqual(events_asc[1]["data"]["name"], "second")
        self.assertEqual(events_asc[2]["data"]["name"], "third")
        
        # Query in descending order (reverse chronological)
        events_desc = query_events(self.db_path, event_type="Building", sort="desc")
        self.assertEqual(len(events_desc), 3)
        self.assertEqual(events_desc[0]["data"]["name"], "third")
        self.assertEqual(events_desc[1]["data"]["name"], "second")
        self.assertEqual(events_desc[2]["data"]["name"], "first")

if __name__ == "__main__":
    unittest.main()
