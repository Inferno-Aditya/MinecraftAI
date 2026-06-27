import unittest
import json
import os
from unittest.mock import patch

from context import PlayerContext
from planner import plan, PlannerResult, ResponseStrategy
from intent_classifier import IntentClassifier

class TestRegression(unittest.TestCase):
    def setUp(self):
        # Setup rich mock player context
        self.context_data = {
            "player_info": {
                "name": "TestPlayer",
                "uuid": "12345-abcde",
                "x": 100.5,
                "y": 64.0,
                "z": -200.5,
                "yaw": 90.0,
                "pitch": -10.0,
                "health": 18.5,
                "food": 15,
                "saturation": 8.0,
                "experience": 0.35,
                "level": 12,
                "gamemode": "survival",
                "dimension": "minecraft:overworld",
                "inventory": [
                    {"slot": 0, "item": "minecraft:iron_pickaxe", "count": 1, "durability": 200, "enchantments": {}, "nbt": ""},
                    {"slot": 1, "item": "minecraft:oak_log", "count": 16, "durability": 0, "enchantments": {}, "nbt": ""}
                ],
                "equipment": {
                    "helmet": {"item": "minecraft:iron_helmet", "count": 1, "durability": 150, "enchantments": {}},
                    "chestplate": {"item": "minecraft:air", "count": 0, "durability": 0, "enchantments": {}},
                    "leggings": {"item": "minecraft:air", "count": 0, "durability": 0, "enchantments": {}},
                    "boots": {"item": "minecraft:air", "count": 0, "durability": 0, "enchantments": {}},
                    "offhand": {"item": "minecraft:shield", "count": 1, "durability": 300, "enchantments": {}}
                },
                "held_item": {"item": "minecraft:diamond_sword", "count": 1, "durability": 1500, "enchantments": {}}
            },
            "environment": {
                "weather": {
                    "rain": False,
                    "thunder": False,
                    "clear": True,
                    "time_remaining": 6000
                },
                "world_time": 1000,
                "is_day": True,
                "is_night": False,
                "moon_phase": 0,
                "light_level": {
                    "block": 15,
                    "sky": 15,
                    "combined": 15
                },
                "biome": {
                    "name": "minecraft:forest",
                    "temperature": 0.7,
                    "rainfall": 0.8,
                    "category": "forest"
                },
                "nearby_blocks": {
                    "filler_blocks": {},
                    "interesting_blocks": [
                        {"type": "minecraft:chest", "x": 101, "y": 64, "z": -201}
                    ]
                },
                "nearby_entities": [
                    {"type": "minecraft:zombie", "name": "Zombie", "health": 20.0, "max_health": 20.0, "distance": 4.5, "x": 103.0, "y": 64.0, "z": -197.0, "category": "hostile"}
                ]
            }
        }
        self.context = PlayerContext.model_validate(self.context_data)
        
        # Patch load_config to use mock model
        self.config_patcher = patch("planner.load_config", return_value={
            "provider": "mock",
            "model": "mock-model",
            "enable_prompt_logging": False
        })
        self.config_patcher.start()

        from model_manager import ModelManager, ModelProfile
        mock_profile = ModelProfile(
            model_id="mock-model",
            name="Mock Model (Testing)",
            provider="mock",
            description="Mock model for testing",
            rpm=60,
            rpd=86400,
            context_window=32768,
            output_token_limit=4096,
            recommended_usage="Testing"
        )
        self.model_patch = patch.object(ModelManager, "get_active_model", return_value="mock-model")
        self.model_patch.start()
        self.provider_patch = patch.object(ModelManager, "get_active_provider", return_value="mock")
        self.provider_patch.start()
        self.profile_patch = patch.object(ModelManager, "get_active_model_profile", return_value=mock_profile)
        self.profile_patch.start()

    def tearDown(self):
        self.config_patcher.stop()
        self.model_patch.stop()
        self.provider_patch.stop()
        self.profile_patch.stop()

    def test_intent_classification_and_tool_ranking(self):
        classifier = IntentClassifier()

        # Define robust regression test cases (Query -> Expected Intent & Top Tool candidate)
        test_cases = [
            # Original 14
            {
                "query": "What biome am I in?",
                "expected_intent": "ENVIRONMENT",
                "top_tool": "get_biome"
            },
            {
                "query": "Any Endermen nearby?",
                "expected_intent": "ENVIRONMENT",
                "top_tool": "get_nearby_entities"
            },
            {
                "query": "Is there a village near me?",
                "expected_intent": "ENVIRONMENT",
                "top_tool": "find_nearest"
            },
            {
                "query": "Find the nearest ocean monument.",
                "expected_intent": "ENVIRONMENT",
                "top_tool": "find_nearest"
            },
            {
                "query": "What's my health?",
                "expected_intent": "PLAYER",
                "top_tool": "get_health"
            },
            {
                "query": "What's the weather?",
                "expected_intent": "ENVIRONMENT",
                "top_tool": "get_weather"
            },
            {
                "query": "What's in my inventory?",
                "expected_intent": "PLAYER",
                "top_tool": "get_inventory"
            },
            {
                "query": "Where am I?",
                "expected_intent": "PLAYER",
                "top_tool": "get_player_status"
            },
            {
                "query": "What dimension am I am in?",
                "expected_intent": "PLAYER",
                "top_tool": "get_dimension"
            },
            {
                "query": "Can I craft a shield?",
                "expected_intent": "HYBRID",
                "top_tool": "get_inventory"
            },
            {
                "query": "How do I make a beacon?",
                "expected_intent": "KNOWLEDGE",
                "top_tool": None
            },
            {
                "query": "Is it safe to sleep?",
                "expected_intent": "HYBRID",
                "top_tool": "get_time"
            },
            {
                "query": "Remember this location.",
                "expected_intent": "MEMORY",
                "top_tool": "save_location"
            },
            {
                "query": "Forget my home.",
                "expected_intent": "MEMORY",
                "top_tool": "save_location"
            },
            # Conversational phrasings & edge cases
            {
                "query": "How am I doing?",
                "expected_intent": "PLAYER",
                "top_tool": "get_health"
            },
            {
                "query": "Am I okay?",
                "expected_intent": "PLAYER",
                "top_tool": "get_health"
            },
            {
                "query": "Do I need food?",
                "expected_intent": "PLAYER",
                "top_tool": "get_food"
            },
            {
                "query": "How's my health?",
                "expected_intent": "PLAYER",
                "top_tool": "get_health"
            },
            {
                "query": "Am I injured?",
                "expected_intent": "PLAYER",
                "top_tool": "get_health"
            },
            {
                "query": "What's my condition?",
                "expected_intent": "PLAYER",
                "top_tool": "get_player_status"
            },
            {
                "query": "Anything dangerous nearby?",
                "expected_intent": "ENVIRONMENT",
                "top_tool": "get_nearby_entities"
            },
            {
                "query": "Any creepers around?",
                "expected_intent": "ENVIRONMENT",
                "top_tool": "get_nearby_entities"
            },
            {
                "query": "Can you see any mobs?",
                "expected_intent": "ENVIRONMENT",
                "top_tool": "get_nearby_entities"
            },
            {
                "query": "What's around me?",
                "expected_intent": "ENVIRONMENT",
                "top_tool": "scan_area"
            },
            {
                "query": "Is anything close?",
                "expected_intent": "ENVIRONMENT",
                "top_tool": "get_nearby_entities"
            },
            {
                "query": "Are there any hostile mobs nearby?",
                "expected_intent": "ENVIRONMENT",
                "top_tool": "get_nearby_entities"
            },
            {
                "query": "Should I fight?",
                "expected_intent": "HYBRID",
                "top_tool": "get_nearby_entities"
            },
            {
                "query": "Can I survive this?",
                "expected_intent": "HYBRID",
                "top_tool": "get_nearby_entities"
            },
            {
                "query": "Should I explore this cave?",
                "expected_intent": "HYBRID",
                "top_tool": "scan_area"
            },
            {
                "query": "Is now a good time to travel?",
                "expected_intent": "HYBRID",
                "top_tool": "get_time"
            },
            {
                "query": "Where is my home?",
                "expected_intent": "MEMORY",
                "top_tool": "load_location"
            },
            {
                "query": "Take me back home.",
                "expected_intent": "MEMORY",
                "top_tool": "load_location"
            },
            {
                "query": "Remember this place.",
                "expected_intent": "MEMORY",
                "top_tool": "save_location"
            },
            {
                "query": "Save this location.",
                "expected_intent": "MEMORY",
                "top_tool": "save_location"
            },
            {
                "query": "What locations have I saved?",
                "expected_intent": "MEMORY",
                "top_tool": "list_locations"
            },
            # Edge cases from prompt refinements
            {
                "query": "Am I safe right now?",
                "expected_intent": "HYBRID",
                "top_tool": "get_nearby_entities"
            },
            {
                "query": "Anything scary nearby?",
                "expected_intent": "ENVIRONMENT",
                "top_tool": "get_nearby_entities"
            },
            {
                "query": "How's everything looking?",
                "expected_intent": "ENVIRONMENT",
                "top_tool": "scan_area"
            },
            {
                "query": "Should I run?",
                "expected_intent": "HYBRID",
                "top_tool": "get_nearby_entities"
            },
            {
                "query": "Can I take this fight?",
                "expected_intent": "HYBRID",
                "top_tool": "get_nearby_entities"
            },
            {
                "query": "Where did I save my mining base?",
                "expected_intent": "MEMORY",
                "top_tool": "load_location"
            },
            {
                "query": "Take me back to my home.",
                "expected_intent": "MEMORY",
                "top_tool": "load_location"
            }
        ]

        for case in test_cases:
            q = case["query"]
            res = classifier.classify(q)
            self.assertEqual(res["intent"], case["expected_intent"], f"Failed classification for: {q}")
            if case["top_tool"] is not None:
                self.assertTrue(len(res["required_tools"]) > 0, f"No tools ranked for query: {q}")
                top_ranked = res["required_tools"][0]
                # Since multiple tools can match, make sure top_tool or a highly relevant one is at the top
                self.assertIn(case["top_tool"], res["required_tools"][:3], f"Expected tool {case['top_tool']} to be in top candidate list for: {q}")

    @patch("planner.execute_llm_request_with_rate_limits")
    def test_planner_strategy_and_execution_offline(self, mock_llm_execute):
        # 1. "What biome am I in?" should select get_biome tool and ResponseStrategy.TOOLS
        mock_llm_execute.return_value = '{"response_strategy": "TOOLS", "reply": "", "tool_calls": [{"tool": "get_biome", "arguments": {}}]}'
        res = plan("What biome am I in?", self.context)
        self.assertEqual(res.response_strategy, ResponseStrategy.TOOLS)
        self.assertEqual(len(res.tool_calls), 1)
        self.assertEqual(res.tool_calls[0].tool, "get_biome")

        # 2. "Any Endermen nearby?" should select get_nearby_entities tool and ResponseStrategy.TOOLS
        mock_llm_execute.return_value = '{"response_strategy": "TOOLS", "reply": "", "tool_calls": [{"tool": "get_nearby_entities", "arguments": {}}]}'
        res = plan("Any Endermen nearby?", self.context)
        self.assertEqual(res.response_strategy, ResponseStrategy.TOOLS)
        self.assertEqual(len(res.tool_calls), 1)
        self.assertEqual(res.tool_calls[0].tool, "get_nearby_entities")

        # 3. "Is there a village near me?" should select find_nearest tool and ResponseStrategy.TOOLS
        mock_llm_execute.return_value = '{"response_strategy": "TOOLS", "reply": "", "tool_calls": [{"tool": "find_nearest", "arguments": {"target_type": "village"}}]}'
        res = plan("Is there a village near me?", self.context)
        self.assertEqual(res.response_strategy, ResponseStrategy.TOOLS)
        self.assertEqual(res.tool_calls[0].tool, "find_nearest")

        # 4. "Can I craft a shield?" should request get_inventory and select ResponseStrategy.HYBRID
        mock_llm_execute.return_value = '{"response_strategy": "HYBRID", "reply": "", "tool_calls": [{"tool": "get_inventory", "arguments": {}}]}'
        res = plan("Can I craft a shield?", self.context)
        self.assertEqual(res.response_strategy, ResponseStrategy.HYBRID)
        self.assertEqual(res.tool_calls[0].tool, "get_inventory")

        # 5. "How do I make a beacon?" should be classified as KNOWLEDGE strategy with no tools
        mock_llm_execute.return_value = '{"response_strategy": "KNOWLEDGE", "reply": "To make a beacon, you need 3 obsidian, 5 glass, and 1 nether star...", "tool_calls": []}'
        res = plan("How do I make a beacon?", self.context)
        self.assertEqual(res.response_strategy, ResponseStrategy.KNOWLEDGE)
        self.assertEqual(len(res.tool_calls), 0)
        self.assertTrue(len(res.reply) > 0)
