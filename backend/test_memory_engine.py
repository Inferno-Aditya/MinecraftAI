import os
import unittest
import tempfile
import json
import shutil
import sqlite3
from datetime import datetime, timezone

from backend.memory.models import GameplayEvent
from backend.memory.event_logger import EventLogger
from backend.memory.memory_manager import MemoryManager

class TestMemoryEngine(unittest.TestCase):
    def setUp(self):
        # Create temp dir for test databases
        self.temp_dir = tempfile.mkdtemp()
        self.timeline_db_path = os.path.join(self.temp_dir, "test_timeline.db")
        self.memory_db_path = os.path.join(self.temp_dir, "test_memory.db")
        
        # Instantiate test event logger
        self.logger = EventLogger()
        self.logger.initialize(
            session_id="test-session-abc",
            db_path=self.timeline_db_path,
            game_version="1.21",
            mod_version="1.0.0"
        )
        
        # Instantiate test memory manager
        self.manager = MemoryManager()
        self.manager.initialize(
            memory_db_path=self.memory_db_path,
            timeline_db_path=self.timeline_db_path,
            start_worker=False
        )

    def tearDown(self):
        self.logger.close()
        self.manager.close()
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass

    def test_session_summary(self):
        """Verify session summary aggregates event statistics and records provenance/confidence."""
        # Log events in timeline
        self.logger.log_event("Combat", "mob_killed", "overworld", 0, 64, 0, {"mob_type": "Zombie"})
        self.logger.log_event("Combat", "player_death", "overworld", 0, 64, 0, {"reason": "creeper"})
        self.logger.log_event("Mining", "ore_mined", "overworld", 10, 12, 10, {"block_type": "diamond_ore", "quantity": 3})
        self.logger.log_event("Building", "place_block", "overworld", 5, 64, 5, {"block_type": "oak_planks", "quantity": 10})
        
        self.logger.flush()
        
        # Trigger processing
        count = self.manager.trigger_processing()
        self.assertEqual(count, 4)
        
        # Query session summary
        sessions = self.manager.list_sessions()
        self.assertEqual(len(sessions), 1)
        
        sess = sessions[0]
        self.assertEqual(sess["session_id"], "test-session-abc")
        self.assertEqual(sess["confidence"], 0.8) # Session is not closed yet
        self.assertEqual(len(sess["source_event_uuids"]), 4)
        
        summary = sess["summary"]
        self.assertEqual(summary["deaths_count"], 1)
        self.assertEqual(summary["combat_kills"].get("Zombie"), 1)
        self.assertEqual(summary["resources_obtained"].get("diamond_ore"), 3)
        self.assertEqual(summary["blocks_placed"].get("oak_planks"), 10)
        
        # Close the session to mark it closed in timeline
        self.logger.close()
        
        # Re-trigger processing
        self.manager.trigger_processing()
        
        # Query again, confidence should now be 1.0
        sessions = self.manager.list_sessions()
        self.assertEqual(sessions[0]["confidence"], 1.0)

    def test_daily_merge(self):
        """Verify that multiple session summaries in the same day merge correctly."""
        # 1. First session
        self.logger.log_event("Combat", "mob_killed", "overworld", 0, 64, 0, {"mob_type": "Zombie"})
        self.logger.flush()
        self.manager.trigger_processing()
        
        # Close first session
        self.logger.close()
        
        # 2. Start a second session on the same day
        logger2 = EventLogger()
        logger2.initialize(
            session_id="test-session-xyz",
            db_path=self.timeline_db_path,
            game_version="1.21"
        )
        logger2.log_event("Combat", "mob_killed", "overworld", 0, 64, 0, {"mob_type": "Skeleton"})
        logger2.log_event("Mining", "ore_mined", "overworld", 0, 64, 0, {"block_type": "gold_ore", "quantity": 5})
        logger2.flush()
        
        self.manager.trigger_processing()
        logger2.close()
        
        # Trigger processing to finalize
        self.manager.trigger_processing()
        
        # Query daily summary
        daily_list = self.manager.list_daily_memories()
        self.assertEqual(len(daily_list), 1)
        
        daily = daily_list[0]
        # Date should be today's date in UTC YYYY-MM-DD
        today_str = datetime.now(timezone.utc).isoformat()[:10]
        self.assertEqual(daily["date"], today_str)
        self.assertEqual(len(daily["source_session_ids"]), 2)
        self.assertIn("test-session-abc", daily["source_session_ids"])
        self.assertIn("test-session-xyz", daily["source_session_ids"])
        
        summary = daily["summary"]
        self.assertEqual(summary["combat_kills"].get("Zombie"), 1)
        self.assertEqual(summary["combat_kills"].get("Skeleton"), 1)
        self.assertEqual(summary["resources_obtained"].get("gold_ore"), 5)

    def test_fact_evolution_soft_updates(self):
        """Verify that facts evolve gradually and require repeated evidence before replacing active facts."""
        # 1. Propose first Home Location at (100, 64, 200)
        # Rounded chunk coordinates: 16 * (100 // 16) = 96, 16 * (200 // 16) = 192
        self.logger.log_event("Building", "place_block", "overworld", 100, 64, 200, {"block_type": "bed"})
        self.logger.flush()
        self.manager.trigger_processing()
        
        facts = {f["fact_key"]: f for f in self.manager.list_facts()}
        self.assertIn("home_location", facts)
        home = facts["home_location"]
        self.assertEqual(home["value"]["x"], 96)
        self.assertEqual(home["value"]["z"], 192)
        self.assertAlmostEqual(home["confidence"], 0.33, places=2) # 1 occurrence
        
        # 2. Propose second time (increases confidence)
        self.logger.log_event("Building", "place_block", "overworld", 101, 64, 199, {"block_type": "bed"})
        self.logger.flush()
        self.manager.trigger_processing()
        
        home = {f["fact_key"]: f for f in self.manager.list_facts()}["home_location"]
        self.assertAlmostEqual(home["confidence"], 0.66, places=2) # 2 occurrences
        
        # 3. Propose third time (sets high confidence)
        self.logger.log_event("Building", "place_block", "overworld", 98, 64, 202, {"block_type": "bed"})
        self.logger.flush()
        self.manager.trigger_processing()
        
        home = {f["fact_key"]: f for f in self.manager.list_facts()}["home_location"]
        self.assertAlmostEqual(home["confidence"], 0.99, places=2) # 3 occurrences
        
        # 4. Propose a DIFFERENT home at (500, 64, 500)
        # Candidate coordinates: 496, 496.
        # It should NOT replace active base yet because count is 1 < 3
        self.logger.log_event("Building", "place_block", "overworld", 500, 64, 500, {"block_type": "bed"})
        self.logger.flush()
        self.manager.trigger_processing()
        
        home = {f["fact_key"]: f for f in self.manager.list_facts()}["home_location"]
        # Active remains the original base
        self.assertEqual(home["value"]["x"], 96)
        self.assertEqual(home["value"]["z"], 192)
        # Verify candidate is staged in history JSON
        self.assertIn('{"dimension": "overworld", "x": 496, "y": 64, "z": 496}', home["history"]["candidates"])
        self.assertEqual(home["history"]["candidates"]['{"dimension": "overworld", "x": 496, "y": 64, "z": 496}']['count'], 1)
        
        # 5. Propose different home 2 more times (total 3 occurrences)
        # This should promote candidate to active, and push old home to history past_values
        self.logger.log_event("Building", "place_block", "overworld", 501, 64, 499, {"block_type": "bed"})
        self.logger.flush()
        self.manager.trigger_processing()
        
        self.logger.log_event("Building", "place_block", "overworld", 498, 64, 502, {"block_type": "bed"})
        self.logger.flush()
        self.manager.trigger_processing()
        
        home = {f["fact_key"]: f for f in self.manager.list_facts()}["home_location"]
        # Active is now the new base location
        self.assertEqual(home["value"]["x"], 496)
        self.assertEqual(home["value"]["z"], 496)
        self.assertAlmostEqual(home["confidence"], 0.98, places=2)
        
        # Verify old home moved to past_values list in history
        self.assertEqual(len(home["history"]["past_values"]), 1)
        self.assertEqual(home["history"]["past_values"][0]["value"]["x"], 96)
        self.assertEqual(home["history"]["past_values"][0]["value"]["z"], 192)

    def test_episodic_clustering(self):
        """Verify that events are clustered into episodes based on category and temporal proximity."""
        # 1. Log mining events within 5 minute threshold (300 seconds)
        # Event 1: 10:00
        self.logger.log_event("Mining", "ore_mined", "overworld", 10, 12, 10, {"block_type": "coal_ore"}, timestamp="2026-06-28T10:00:00Z")
        # Event 2: 10:02 (2 minutes gap -> merge)
        self.logger.log_event("Mining", "ore_mined", "overworld", 11, 12, 10, {"block_type": "iron_ore"}, timestamp="2026-06-28T10:02:00Z")
        # Event 3: 10:04 (2 minutes gap -> merge)
        self.logger.log_event("Mining", "ore_mined", "overworld", 12, 12, 10, {"block_type": "diamond_ore"}, timestamp="2026-06-28T10:04:00Z")
        
        # 2. Log a mining event outside the 5 minute threshold
        # Event 4: 10:20 (16 minutes gap -> separate episode)
        self.logger.log_event("Mining", "ore_mined", "overworld", -50, 15, 200, {"block_type": "ancient_debris"}, timestamp="2026-06-28T10:20:00Z")
        
        self.logger.flush()
        self.manager.trigger_processing()
        
        episodes = self.manager.list_episodes(episode_type="Mining Expedition")
        # Should create 2 distinct episodes
        self.assertEqual(len(episodes), 2)
        
        # Sorting is newest start_time first in list_episodes
        ep1 = episodes[1] # Earliest starts at 10:00
        ep2 = episodes[0] # Newest starts at 10:20
        
        self.assertEqual(ep1["start_time"], "2026-06-28T10:00:00Z")
        self.assertEqual(ep1["end_time"], "2026-06-28T10:04:00Z")
        self.assertEqual(len(ep1["event_uuids"]), 3)
        self.assertEqual(ep1["summary"]["resources_obtained"].get("coal_ore"), 1)
        self.assertEqual(ep1["summary"]["resources_obtained"].get("iron_ore"), 1)
        self.assertEqual(ep1["summary"]["resources_obtained"].get("diamond_ore"), 1)
        
        self.assertEqual(ep2["start_time"], "2026-06-28T10:20:00Z")
        self.assertEqual(ep2["end_time"], "2026-06-28T10:20:00Z")
        self.assertEqual(len(ep2["event_uuids"]), 1)
        self.assertEqual(ep2["summary"]["resources_obtained"].get("ancient_debris"), 1)

    def test_incremental_processing(self):
        """Verify the pipeline operates incrementally, processing only newly created events."""
        # 1. Log 2 events
        self.logger.log_event("Combat", "mob_killed", "overworld", 0, 64, 0, {"mob_type": "Zombie"})
        self.logger.log_event("Combat", "mob_killed", "overworld", 0, 64, 0, {"mob_type": "Zombie"})
        self.logger.flush()
        
        # Trigger processing
        count1 = self.manager.trigger_processing()
        self.assertEqual(count1, 2)
        
        # Verify processed session summary has 2 zombie kills
        sess = self.manager.list_sessions()[0]
        self.assertEqual(sess["summary"]["combat_kills"].get("Zombie"), 2)
        
        # 2. Log 3 MORE events (bringing total in timeline to 5)
        self.logger.log_event("Combat", "mob_killed", "overworld", 0, 64, 0, {"mob_type": "Zombie"})
        self.logger.log_event("Combat", "mob_killed", "overworld", 0, 64, 0, {"mob_type": "Zombie"})
        self.logger.log_event("Combat", "mob_killed", "overworld", 0, 64, 0, {"mob_type": "Zombie"})
        self.logger.flush()
        
        # Trigger again
        count2 = self.manager.trigger_processing()
        # Should only process the 3 new ones!
        self.assertEqual(count2, 3)
        
        # Verify summary count is updated to 5
        sess = self.manager.list_sessions()[0]
        self.assertEqual(sess["summary"]["combat_kills"].get("Zombie"), 5)

    def test_persistence_across_restart(self):
        """Verify that processed memories survive memory manager shutdowns and restarts."""
        # Log and process event
        self.logger.log_event("Combat", "mob_killed", "overworld", 0, 64, 0, {"mob_type": "Skeleton"})
        self.logger.flush()
        self.manager.trigger_processing()
        
        # Query to verify it exists
        sessions = self.manager.list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["summary"]["combat_kills"].get("Skeleton"), 1)
        
        # Shutdown memory manager
        self.manager.close()
        
        # Create a new memory manager pointing to the same databases
        new_manager = MemoryManager()
        new_manager.initialize(
            memory_db_path=self.memory_db_path,
            timeline_db_path=self.timeline_db_path,
            start_worker=False
        )
        
        # Verify persistence
        restored_sessions = new_manager.list_sessions()
        self.assertEqual(len(restored_sessions), 1)
        self.assertEqual(restored_sessions[0]["summary"]["combat_kills"].get("Skeleton"), 1)
        
        new_manager.close()

if __name__ == "__main__":
    unittest.main()
