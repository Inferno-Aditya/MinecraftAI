import unittest
import json
import os
from unittest.mock import patch

from context import PlayerContext
from planner import plan, PlannerResult, ResponseStrategy
from intent_classifier import IntentClassifier
from context_builder import build_context
from memory_retriever import retrieve_relevant_memory
from tool_selector import select_tool_definitions
from prompt_builder import PromptBuilder, PromptProfile
from resource_manager import resource_manager

class TestOptimizationEngine(unittest.TestCase):
    def setUp(self):
        # Back up config file
        self.config_backup = None
        from config import CONFIG_FILE
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config_backup = f.read()
            except Exception:
                pass

        self.context_payload = {
            "player_info": {
                "name": "Steve",
                "uuid": "uuid-123",
                "x": 10.0,
                "y": 64.0,
                "z": -20.0,
                "yaw": 0.0,
                "pitch": 0.0,
                "health": 20.0,
                "food": 20,
                "saturation": 5.0,
                "experience": 0.0,
                "level": 0,
                "gamemode": "survival",
                "dimension": "minecraft:overworld",
                "inventory": [],
                "equipment": {},
                "held_item": None
            },
            "environment": {
                "weather": {"rain": False, "thunder": False, "clear": True, "time_remaining": 1000},
                "world_time": 1000,
                "is_day": True,
                "is_night": False,
                "moon_phase": 0,
                "light_level": {"block": 15, "sky": 15, "combined": 15},
                "biome": {"name": "minecraft:plains", "temperature": 0.8, "rainfall": 0.4, "category": "plains"},
                "nearby_blocks": {"filler_blocks": {}, "interesting_blocks": []},
                "nearby_entities": []
            }
        }
        self.player_context = PlayerContext.model_validate(self.context_payload)

    def tearDown(self):
        from config import CONFIG_FILE
        if self.config_backup is not None:
            try:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    f.write(self.config_backup)
            except Exception:
                pass
        else:
            if os.path.exists(CONFIG_FILE):
                try:
                    os.remove(CONFIG_FILE)
                except Exception:
                    pass
        
        # Reset model manager state
        from model_manager import model_manager
        model_manager.discover_models(force=False)

    def test_intent_classification(self):
        classifier = IntentClassifier()
        
        # Test KNOWLEDGE intent
        res_knowledge = classifier.classify("how do critical hits work?")
        self.assertEqual(res_knowledge["intent"], "KNOWLEDGE")
        self.assertFalse(res_knowledge["tool_execution_expected"])
        self.assertEqual(len(res_knowledge["required_tools"]), 0)
        
        # Test PLAYER intent
        res_player = classifier.classify("what is my health and status?")
        self.assertEqual(res_player["intent"], "PLAYER")
        self.assertTrue(res_player["tool_execution_expected"])
        self.assertIn("get_player_status", res_player["required_tools"])
        
        # Test ENVIRONMENT intent
        res_env = classifier.classify("what is the weather like?")
        self.assertEqual(res_env["intent"], "ENVIRONMENT")
        self.assertTrue(res_env["tool_execution_expected"])
        self.assertIn("get_weather", res_env["required_tools"])

        # Test MEMORY intent
        res_mem = classifier.classify("remember my home coordinate")
        self.assertEqual(res_mem["intent"], "MEMORY")
        self.assertTrue(res_mem["tool_execution_expected"])
        self.assertIn("save_location", res_mem["required_tools"])
        
        # Test HYBRID intent
        res_hybrid = classifier.classify("can I survive the night?")
        self.assertEqual(res_hybrid["intent"], "HYBRID")
        self.assertTrue(res_hybrid["tool_execution_expected"])

    def test_context_builder(self):
        # Only player context
        ctx_player = build_context(self.player_context, ["player_context"])
        self.assertIn("Player Name: Steve", ctx_player)
        self.assertNotIn("Weather:", ctx_player)
        
        # Both player and environment context
        ctx_both = build_context(self.player_context, ["player_context", "environment_snapshot"])
        self.assertIn("Player Name: Steve", ctx_both)
        self.assertIn("Weather: rain=False", ctx_both)

    @patch("memory_retriever.load_memory")
    def test_memory_retrieval(self, mock_load_memory):
        mock_load_memory.return_value = {
            "locations": {
                "home": {"x": 100, "y": 64, "z": -200, "dimension": "minecraft:overworld"}
            },
            "notes": {
                "favorite_block": "spruce"
            },
            "preferences": {}
        }
        
        # Test matched retrieval
        mem_text = retrieve_relevant_memory("go to home", required_memory=True)
        self.assertIn("home", mem_text)
        self.assertNotIn("favorite_block", mem_text)
        
        # Test unmatched but generic retrieval
        mem_generic = retrieve_relevant_memory("show all memories", required_memory=True)
        self.assertIn("home", mem_generic)
        self.assertIn("favorite_block", mem_generic)

    def test_tool_selector(self):
        defs = select_tool_definitions(["get_player_status"])
        self.assertIn("Tool: get_player_status", defs)
        self.assertNotIn("Tool: get_weather", defs)

    def test_prompt_profile_model(self):
        profile = PromptProfile(
            system_prompt_tokens=100,
            context_tokens=50,
            memory_tokens=10,
            tool_tokens=30,
            user_message_tokens=5,
            total_prompt_tokens=195,
            baseline_tokens=500
        )
        self.assertEqual(profile.total_prompt_tokens, 195)
        self.assertEqual(profile.baseline_tokens, 500)

    def test_planner_optimization_savings(self):
        from model_manager import model_manager
        model_manager.set_active_model("mock-model")

        # Test running plan with KNOWLEDGE intent query
        res = plan("How do critical hits work?", self.player_context)
        self.assertEqual(res.response_strategy, ResponseStrategy.KNOWLEDGE)
        
        stats = resource_manager.get_stats()
        self.assertIn("average_prompt_size", stats)
        self.assertIn("average_tokens_saved", stats)
        self.assertIn("percentage_reduction", stats)
        self.assertIn("largest_prompts", stats)
        
        # The prompt was KNOWLEDGE so all tool definitions (very large) should have been pruned, saving a lot of tokens.
        self.assertGreater(stats["average_tokens_saved"], 0)
        self.assertGreater(stats["percentage_reduction"], 0)
