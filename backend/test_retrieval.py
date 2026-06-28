import os
import unittest
import tempfile
import json
import shutil
import sqlite3
from datetime import datetime, timezone

from backend.memory.event_logger import EventLogger
from backend.memory.memory_manager import MemoryManager
from backend.memory.embeddings import get_model_metadata, generate_embedding

class TestSemanticRetrieval(unittest.TestCase):
    def setUp(self):
        # Create temp dir for test databases
        self.temp_dir = tempfile.mkdtemp()
        self.timeline_db_path = os.path.join(self.temp_dir, "test_timeline.db")
        self.memory_db_path = os.path.join(self.temp_dir, "test_memory.db")
        
        # Instantiate test event logger
        self.logger = EventLogger()
        self.logger.initialize(
            session_id="test-rag-session",
            db_path=self.timeline_db_path,
            game_version="1.21",
            mod_version="1.0.0"
        )
        
        # Instantiate test memory manager (disable bg worker for deterministic control)
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

    def test_embedding_generation(self):
        """Verify dimensional correctness of locally generated embeddings."""
        meta = get_model_metadata()
        self.assertEqual(meta["embedding_model"], "all-MiniLM-L6-v2")
        self.assertEqual(meta["embedding_dimension"], 384)
        self.assertEqual(meta["embedding_version"], "1.0.0")
        
        vector = generate_embedding("Minecraft exploration")
        self.assertIsInstance(vector, list)
        self.assertEqual(len(vector), 384)
        self.assertIsInstance(vector[0], float)

    def test_incremental_indexing_and_pruning(self):
        """Verify incremental vector sync, model metadata tracking, and orphaned vector pruning."""
        # 1. Log events to trigger session, facts, and episodes
        self.logger.log_event("Mining", "ore_mined", "overworld", 10, 12, 10, {"block_type": "diamond_ore", "quantity": 4})
        self.logger.log_event("Building", "place_block", "overworld", 100, 64, 200, {"block_type": "bed"})
        self.logger.flush()
        
        # Run processing (which triggers incremental indexing automatically)
        self.manager.trigger_processing()
        
        # Check stats
        stats = self.manager.get_index_statistics()
        self.assertEqual(stats["facts_count"], 4) # home_location, base:96_192, favorite_materials, preferred_mining_level
        self.assertEqual(stats["embeddings_count"], 8) # 1 session, 1 daily, 2 episodes, 4 facts
        self.assertEqual(stats["model_info"]["model"], "all-MiniLM-L6-v2")
        self.assertEqual(stats["model_info"]["dimension"], 384)
        
        # 2. Pruning test: manually delete a fact from facts table
        conn = sqlite3.connect(self.memory_db_path)
        with conn:
            conn.execute("DELETE FROM facts WHERE fact_key = 'preferred_mining_level';")
        conn.close()
        
        # Trigger processing again (runs indexing sync)
        self.manager.trigger_processing()
        
        # Assert corresponding embedding vector is deleted (pruned)
        stats = self.manager.get_index_statistics()
        self.assertEqual(stats["facts_count"], 3)
        self.assertEqual(stats["embeddings_count"], 7)

    def test_similarity_search_accuracy_and_filtering(self):
        """Verify semantic similarity rankings, metadata filters, and diagnostic outputs."""
        # 1. Populate memories with distinct themes
        # Episode A: Mining diamonds
        self.logger.log_event("Mining", "ore_mined", "overworld", 12, 11, 12, {"block_type": "diamond_ore", "quantity": 6}, timestamp="2026-06-28T10:00:00Z")
        self.logger.flush()
        self.manager.trigger_processing()
        
        # Episode B: Fighting spiders
        self.logger.log_event("Combat", "mob_killed", "overworld", 50, 64, 50, {"mob_type": "Spider"}, timestamp="2026-06-28T10:10:00Z")
        self.logger.flush()
        self.manager.trigger_processing()
        
        # Fact: Home Base Bed placements
        self.logger.log_event("Building", "place_block", "overworld", 1000, 70, 1000, {"block_type": "bed"}, timestamp="2026-06-28T10:20:00Z")
        self.logger.flush()
        self.manager.trigger_processing()
        
        # 2. Semantic query for mining diamonds
        results = self.manager.search_memories(query="Where did I gather diamonds or mine precious ores?", top_k=3)
        self.assertGreater(len(results), 0)
        
        best = results[0]
        self.assertEqual(best["memory_type"], "episode")
        self.assertEqual(best["retrieval_rank"], 1)
        self.assertIn("Mining Expedition", best["text_content"])
        self.assertIn("diamond_ore", best["text_content"])
        self.assertIsInstance(best["similarity_score"], float)
        self.assertIsInstance(best["confidence"], float)
        self.assertIsInstance(best["provenance"], list)
        self.assertIsInstance(best["source_memory"], dict)
        self.assertEqual(best["source_memory"]["episode_type"], "Mining Expedition")
        
        # 3. Semantic query for combat
        results_combat = self.manager.search_memories(query="Defeating creepy crawlies or fighting monsters", top_k=2)
        best_combat = results_combat[0]
        self.assertEqual(best_combat["memory_type"], "episode")
        self.assertIn("Combat Skirmish", best_combat["text_content"])
        self.assertIn("Spider", best_combat["text_content"])
        
        # 4. Metadata Filtering: search query but filter only on 'fact'
        results_filtered = self.manager.search_memories_by_type(query="bed or home", memory_type="fact", top_k=3)
        for r in results_filtered:
            self.assertEqual(r["memory_type"], "fact")

    def test_rebuild_index_and_persistence(self):
        """Verify full index rebuild and semantic query persistence across manager restarts."""
        self.logger.log_event("Mining", "ore_mined", "overworld", 12, 11, 12, {"block_type": "diamond_ore", "quantity": 2})
        self.logger.flush()
        self.manager.trigger_processing()
        
        # Query results before restart
        before_results = self.manager.search_memories(query="diamond mining")
        self.assertGreater(len(before_results), 0)
        
        # Close and restart MemoryManager
        self.manager.close()
        
        new_manager = MemoryManager()
        new_manager.initialize(
            memory_db_path=self.memory_db_path,
            timeline_db_path=self.timeline_db_path,
            start_worker=False
        )
        
        # Query after restart, assert identical rankings/scores
        after_results = new_manager.search_memories(query="diamond mining")
        self.assertEqual(len(before_results), len(after_results))
        self.assertEqual(before_results[0]["memory_uuid"], after_results[0]["memory_uuid"])
        self.assertEqual(before_results[0]["similarity_score"], after_results[0]["similarity_score"])
        
        # Trigger rebuild
        inserted, updated, deleted = new_manager.rebuild_vector_index()
        self.assertGreater(inserted, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(deleted, 0)
        
        # Verify stats after rebuild
        stats = new_manager.get_index_statistics()
        self.assertEqual(stats["embeddings_count"], inserted)
        
        new_manager.close()

if __name__ == "__main__":
    unittest.main()
