import os
import unittest
import tempfile
import json
import shutil
import sqlite3
import datetime
from unittest.mock import MagicMock, patch

from backend.memory.event_logger import EventLogger
from backend.memory.memory_manager import MemoryManager
from backend.ai.prompt_builder import PromptBuilder, get_last_debug_info
from backend.ai.context_ranker import rank_memories, compute_memory_importance
from backend.ai.memory_formatter import format_memories_by_category

class MockPlayerContext:
    def __init__(self, name="Steve", x=100.0, y=64.0, z=200.0, dimension="overworld", biome="forest", world_time=1000, inventory=None):
        self.name = name
        self.x = x
        self.y = y
        self.z = z
        self.dimension = dimension
        self.gamemode = "survival"
        self.health = 20.0
        self.food = 20.0
        self.biome = biome
        self.world_time = world_time
        
        class MockEnv:
            def __init__(self):
                self.nearby_entities = []
                self.nearby_blocks = []
                self.weather = "clear"
                
        self.environment = MockEnv()
        self.inventory = inventory or {}
        self.equipment = {}

class TestAIIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.timeline_db_path = os.path.join(self.temp_dir, "test_timeline.db")
        self.memory_db_path = os.path.join(self.temp_dir, "test_memory.db")
        
        self.logger = EventLogger()
        self.logger.initialize(
            session_id="test-integration-session",
            db_path=self.timeline_db_path,
            game_version="1.21",
            mod_version="1.0.0"
        )
        
        self.manager = MemoryManager()
        self.manager.initialize(
            memory_db_path=self.memory_db_path,
            timeline_db_path=self.timeline_db_path,
            start_worker=False
        )
        
        # Isolate database queries by overriding global singleton
        MemoryManager._instance = self.manager

        # Isolate legacy JSON memory by mocking retrieve_relevant_memory
        self.legacy_patch = patch("backend.memory_retriever.retrieve_relevant_memory", return_value="None")
        self.legacy_patch.start()

        # Mock Model Manager Profile returns
        from backend.model_manager import model_manager, ModelProfile
        mock_profile = ModelProfile(
            provider="mock",
            model_id="mock-model",
            name="Mock Model",
            context_window=8192,
            output_token_limit=8192,
            supports_chat=True,
            supports_tools=True,
            supports_json_mode=True
        )
        self.model_patch = patch.object(model_manager, "get_active_model", return_value="mock-model")
        self.provider_patch = patch.object(model_manager, "get_active_provider", return_value="mock")
        self.profile_patch = patch.object(model_manager, "get_active_model_profile", return_value=mock_profile)
        self.model_patch.start()
        self.provider_patch.start()
        self.profile_patch.start()

    def tearDown(self):
        self.model_patch.stop()
        self.provider_patch.stop()
        self.profile_patch.stop()
        self.legacy_patch.stop()
        MemoryManager._instance = None
        self.logger.close()
        self.manager.close()
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass

    @patch("backend.memory.MemoryManager.search_memories")
    def test_relevance_threshold_and_exclusion(self, mock_search):
        """Verify that relevant memories are injected and irrelevant ones are filtered out."""
        # Unrelated query returns low similarity score memory
        mock_search.return_value = [
            {
                "memory_uuid": "mining-mem",
                "memory_type": "episode",
                "text_content": "Episode category: 'Mining Expedition'. Highlights: Mined 5 diamond_ore.",
                "similarity_score": 0.35,
                "confidence": 1.0,
                "provenance": ["session-1"],
                "last_updated": "2026-06-28T10:00:00Z"
            }
        ]
        
        player_ctx = MockPlayerContext(x=10, y=11, z=10, biome="plains")
        
        # Test case A: Query unrelated to mining (should exclude mining memory from injection)
        sys_prompt, user_prompt, diagnostics = PromptBuilder.build_prompt_with_budget(
            message="What is the weather outside?",
            player_context=player_ctx,
            live_context_text="Biome: plains",
            tool_results="",
            system_instructions="You are a helper.",
            tool_definitions="",
            req_memory=True
        )
        
        # Verify that the memory was retrieved but filtered out because similarity was low
        retrieved = diagnostics["retrieved_memories"]
        self.assertGreater(len(retrieved), 0)
        
        # The utilization status should be filtered out
        filtered_mem = [m for m in retrieved if m["utilization_status"] == "filtered"]
        self.assertGreater(len(filtered_mem), 0)
        self.assertNotIn("EPISODIC MEMORIES", user_prompt)

        # Related query returns high similarity score memory
        mock_search.return_value = [
            {
                "memory_uuid": "mining-mem",
                "memory_type": "episode",
                "text_content": "Episode category: 'Mining Expedition'. Highlights: Mined 5 diamond_ore.",
                "similarity_score": 0.85,
                "confidence": 1.0,
                "provenance": ["session-1"],
                "last_updated": "2026-06-28T10:00:00Z"
            }
        ]

        # Test case B: Query related to mining (should inject mining memory)
        sys_prompt_rel, user_prompt_rel, diagnostics_rel = PromptBuilder.build_prompt_with_budget(
            message="Where did I find the diamonds?",
            player_context=player_ctx,
            live_context_text="Biome: plains",
            tool_results="",
            system_instructions="You are a helper.",
            tool_definitions="",
            req_memory=True
        )
        
        # Verify that it was successfully injected
        injected = [m for m in diagnostics_rel["retrieved_memories"] if m["utilization_status"] == "injected"]
        self.assertGreater(len(injected), 0)
        self.assertIn("EPISODIC MEMORIES", user_prompt_rel)
        self.assertIn("diamond_ore", user_prompt_rel)

    def test_context_ranking_and_importance(self):
        """Verify combined signal context ranking (similarity, confidence, recency, importance) and tie-breaking."""
        # Verify importance scorer
        high_imp = compute_memory_importance({"text_content": "Found diamonds and netherite at my base spawn!"})
        low_imp = compute_memory_importance({"text_content": "Mined some dirt and cobblestone."})
        self.assertGreater(high_imp, low_imp)
        
        # Create test mock memories with equal similarity/confidence
        now = datetime.datetime.now(datetime.timezone.utc)
        memories = [
            {
                "memory_uuid": "mem-b",
                "memory_type": "fact",
                "text_content": "Mined dirt.",
                "similarity_score": 0.8,
                "confidence": 1.0,
                "last_updated": str(now - datetime.timedelta(days=2))
            },
            {
                "memory_uuid": "mem-a",
                "memory_type": "fact",
                "text_content": "Mined dirt.",
                "similarity_score": 0.8,
                "confidence": 1.0,
                "last_updated": str(now - datetime.timedelta(days=2))
            },
            {
                "memory_uuid": "mem-recent",
                "memory_type": "fact",
                "text_content": "Mined dirt.",
                "similarity_score": 0.8,
                "confidence": 1.0,
                "last_updated": str(now) # highly recent
            }
        ]
        
        ranked = rank_memories(memories, "dirt", now_utc=now)
        # mem-recent must be ranked first because of recency score
        self.assertEqual(ranked[0]["memory_uuid"], "mem-recent")
        # mem-a and mem-b have equal scores, so they must be resolved alphabetically (mem-a before mem-b)
        self.assertEqual(ranked[1]["memory_uuid"], "mem-a")
        self.assertEqual(ranked[2]["memory_uuid"], "mem-b")

    @patch("backend.memory.MemoryManager.search_memories")
    def test_token_budget_pruning_priority(self, mock_search):
        """Verify priority-based token budget section pruning."""
        # Create mock memories
        memories = [
            {"memory_uuid": f"mem-{i}", "memory_type": "fact", "text_content": "x" * 200, "similarity_score": 0.85, "confidence": 1.0, "last_updated": "2026-06-28T10:00:00Z"}
            for i in range(10)
        ]
        mock_search.return_value = memories
        
        # Large prompts that will exceed a small budget
        sys_instructions = "System instructions text."
        player_question = "Where is my home?"
        tool_results = "None."
        live_context = "Status details."
        personality = "You are Steve."
        
        # Test with a very restrictive max_budget of 300 estimated tokens
        sys_prompt, user_prompt, diagnostics = PromptBuilder.build_prompt_with_budget(
            message=player_question,
            player_context=MockPlayerContext(),
            live_context_text=live_context,
            tool_results=tool_results,
            system_instructions=sys_instructions,
            tool_definitions="",
            req_memory=True,
            max_budget=300
        )
        
        # Ensure that some memories were pruned to fit under budget
        self.assertLessEqual(diagnostics["final_prompt_size_tokens"], 300)
        pruned_count = sum(1 for m in diagnostics["retrieved_memories"] if m["utilization_status"] == "pruned")
        self.assertGreater(pruned_count, 0)

    def test_conflict_resolution_and_personality(self):
        """Verify that live context rules are injected and personality is formatted."""
        player_ctx = MockPlayerContext(x=999, y=64, z=999) # current coordinates
        
        sys_prompt, user_prompt, diagnostics = PromptBuilder.build_prompt_with_budget(
            message="Where am I?",
            player_context=player_ctx,
            live_context_text="Location coordinates: X=999, Y=64, Z=999",
            tool_results="",
            system_instructions="Help Steve.",
            tool_definitions="",
            req_memory=False
        )
        
        # Assert that personality instructions were fetched and included in system prompt
        self.assertIn("Conflict Resolution Rules", sys_prompt)
        self.assertIn("Current Live Minecraft Context and Tool Results always override historical memory", sys_prompt)

    @patch("backend.memory.MemoryManager.search_memories")
    def test_prompt_determinism(self, mock_search):
        """Verify that identical inputs yield identical prompt outputs."""
        memories = [
            {
                "memory_uuid": "mem-1",
                "memory_type": "fact",
                "text_content": "Base location established.",
                "similarity_score": 0.85,
                "confidence": 1.0,
                "last_updated": "2026-06-28T10:00:00Z"
            }
        ]
        mock_search.return_value = memories
        player_ctx = MockPlayerContext(x=10, y=11, z=12)
        args = {
            "message": "Where is my old mine?",
            "player_context": player_ctx,
            "live_context_text": "Coordinates: X=10, Y=11, Z=12",
            "tool_results": "Tool results content",
            "system_instructions": "Solve task.",
            "tool_definitions": "Def 1, Def 2",
            "req_memory": True,
            "max_budget": 2048
        }
        
        sys_prompt1, user_prompt1, diag1 = PromptBuilder.build_prompt_with_budget(**args)
        sys_prompt2, user_prompt2, diag2 = PromptBuilder.build_prompt_with_budget(**args)
        
        self.assertEqual(sys_prompt1, sys_prompt2)
        self.assertEqual(user_prompt1, user_prompt2)

    @patch("backend.ai.prompt_builder.execute_llm_request_with_rate_limits", return_value='{"reply": "Synthesized Response", "tool_calls": []}')
    @patch("backend.memory.MemoryManager.search_memories")
    def test_prompt_builder_gateway_and_diagnostics(self, mock_search, mock_llm):
        """Verify the PromptBuilder gateway execution and diagnostic caching."""
        memories = [
            {
                "memory_uuid": "mem-inv",
                "memory_type": "fact",
                "text_content": "Inventory includes iron pickaxe.",
                "similarity_score": 0.85,
                "confidence": 1.0,
                "last_updated": "2026-06-28T10:00:00Z"
            }
        ]
        mock_search.return_value = memories
        player_ctx = MockPlayerContext()
        
        # Test Planner gateway call
        response = PromptBuilder.generate_planner_response(
            message="Check my inventory",
            player_context=player_ctx,
            req_context=["player_context"],
            req_memory=False,
            req_tools=["get_inventory"],
            system_instructions="You are planner.",
            tool_definitions="get_inventory tool definition"
        )
        
        self.assertIn("Synthesized Response", response)
        
        # Get diagnostics from get_last_debug_info
        debug_info = get_last_debug_info()
        self.assertEqual(debug_info["prompt_version"], "1.0.0")
        self.assertEqual(debug_info["builder_version"], "1.0.0")
        self.assertEqual(debug_info["profile_version"], "1.0.0")
        self.assertEqual(debug_info["stage"], "PLANNER")
        self.assertIsInstance(debug_info["prompt_build_time_ms"], float)
        self.assertIsInstance(debug_info["final_prompt_size_tokens"], int)
        self.assertIsInstance(debug_info["retrieved_memories"], list)

if __name__ == "__main__":
    unittest.main()
