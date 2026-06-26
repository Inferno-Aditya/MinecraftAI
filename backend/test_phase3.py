import unittest
import os
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from context import PlayerContext
from planner import plan, ToolCall, PlannerResult, get_tool_definitions, build_system_prompt, build_user_prompt
from config import load_config
from memory import get_memory_summary, load_memory, save_memory, MEMORY_FILE
from tools.registry import registry
from main import app, ChatRequest, ChatResponse
from providers.gemini import GeminiProvider
from providers import get_provider

class TestPhase3(unittest.TestCase):
    def setUp(self):
        # Backup existing memory
        self.memory_backup = None
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    self.memory_backup = f.read()
            except Exception:
                pass
        
        # Fresh memory
        if os.path.exists(MEMORY_FILE):
            try:
                os.remove(MEMORY_FILE)
            except Exception:
                pass
                
        self.context = PlayerContext(
            name="TestPlayer",
            x=10.5,
            y=64.0,
            z=-25.2,
            yaw=90.0,
            pitch=0.0,
            dimension="minecraft:overworld",
            gamemode="survival",
            health=20.0,
            food=20,
            world_time=1000,
            biome="minecraft:forest"
        )
        
        # Use MockProvider for all tests in this file
        self.config_patch = patch("planner.load_config", return_value={
            "provider": "mock",
            "model": "mock-model",
            "enable_prompt_logging": False
        })
        self.config_patch.start()

        self.rg_config_patch = patch("response_generator.load_config", return_value={
            "provider": "mock",
            "model": "mock-model",
            "enable_prompt_logging": False
        })
        self.rg_config_patch.start()

    def tearDown(self):
        if hasattr(self, "config_patch"):
            self.config_patch.stop()
        if hasattr(self, "rg_config_patch"):
            self.rg_config_patch.stop()
            
        # Restore memory
        if os.path.exists(MEMORY_FILE):
            try:
                os.remove(MEMORY_FILE)
            except Exception:
                pass
        if self.memory_backup is not None:
            try:
                with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                    f.write(self.memory_backup)
            except Exception:
                pass

    def test_config_loading_defaults(self):
        """Verify that configuration loads default values if file is missing."""
        with patch("os.path.exists", return_value=False):
            config = load_config()
            self.assertEqual(config["provider"], "gemini")
            self.assertEqual(config["model"], "gemini-2.5-flash")

    def test_memory_summary_formatting(self):
        """Verify that get_memory_summary constructs a concise formatted text representation."""
        # Empty memory
        summary = get_memory_summary()
        self.assertIn("Known Locations: None", summary)
        self.assertIn("Known Notes: None", summary)
        
        # Populated memory
        registry.execute("save_location", self.context, {"name": "spawn"})
        registry.execute("save_note", self.context, {"key": "favorite_food", "value": "apple"})
        
        summary2 = get_memory_summary()
        self.assertIn("Known Locations:\n- spawn", summary2)
        self.assertIn("Known Notes:\n- favorite_food=apple", summary2)

    def test_tool_injection_definitions(self):
        """Verify that tool registry dynamically generates descriptions, schemas, and examples."""
        tool_defs = get_tool_definitions()
        # Should contain save_location details
        self.assertIn("save_location", tool_defs)
        self.assertIn("Saves the player's current location", tool_defs)
        self.assertIn("name", tool_defs)
        self.assertIn("remember this place as home", tool_defs)
        
        # Should contain save_note details
        self.assertIn("save_note", tool_defs)
        self.assertIn("key", tool_defs)
        self.assertIn("value", tool_defs)

    def test_planner_result_backward_compatibility(self):
        """Verify PlannerResult behaves like a list for compatibility with existing Phase 2 code."""
        result = PlannerResult(
            reply="Test Conversational Reply",
            tool_calls=[ToolCall(tool="list_locations", arguments={})]
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].tool, "list_locations")
        
        # Test iteration
        calls = [tc.tool for tc in result]
        self.assertEqual(calls, ["list_locations"])

    def test_gemini_provider_missing_key(self):
        """Verify GeminiProvider raises a ValueError if GEMINI_API_KEY is missing."""
        with patch.dict(os.environ, {}, clear=True):
            provider = GeminiProvider()
            with self.assertRaises(ValueError) as context:
                provider.generate("System prompt", "User prompt")
            self.assertIn("GEMINI_API_KEY environment variable is missing", str(context.exception))

    def test_malformed_json_retry_logic(self):
        """Verify malformed JSON responses are retried once and parsed successfully if corrected."""
        # "simulate malformed JSON" makes MockProvider return invalid JSON first, then corrects it on retry
        result = plan("simulate malformed JSON", self.context)
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0].tool, "save_location")
        self.assertEqual(result.tool_calls[0].arguments, {"name": "home"})
        self.assertEqual(result.reply, "")

    def test_validation_failure_fallback(self):
        """Verify that validation failures (invalid arguments) on both attempts yield a friendly error reply."""
        # "simulate validation failure" returns invalid schema arguments on both attempts
        result = plan("simulate validation failure", self.context)
        self.assertEqual(len(result.tool_calls), 0)
        self.assertEqual(result.reply, "I couldn't understand the planner response.")

    def test_timeout_handling_gracefully(self):
        """Verify that provider timeouts are caught gracefully and return a friendly reply without crashing."""
        result = plan("simulate timeout", self.context)
        self.assertEqual(len(result.tool_calls), 0)
        self.assertIn("I couldn't reach my planner engine", result.reply)

    def test_rate_limiting_handling_gracefully(self):
        """Verify that rate limits are caught gracefully and return a friendly reply."""
        result = plan("simulate rate limiting", self.context)
        self.assertEqual(len(result.tool_calls), 0)
        self.assertIn("Rate limit exceeded", result.reply)

    def test_chat_endpoint_conversation(self):
        """Verify FastAPI /chat endpoint handles normal conversations (no tool calls)."""
        client = TestClient(app)
        request_data = {
            "message": "Hello there, assistant!",
            "player": self.context.model_dump(),
            "memory": {}
        }
        response = client.post("/chat", json=request_data)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("reply", data)
        self.assertEqual(data["tool_calls"], [])
        self.assertIn("Mock response for: Hello there, assistant!", data["reply"])

    def test_chat_endpoint_single_tool_execution(self):
        """Verify FastAPI /chat endpoint executes a tool and returns its response."""
        client = TestClient(app)
        request_data = {
            "message": "remember this place as base_camp",
            "player": self.context.model_dump(),
            "memory": {}
        }
        response = client.post("/chat", json=request_data)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("reply", data)
        self.assertEqual(len(data["tool_calls"]), 1)
        self.assertEqual(data["tool_calls"][0]["tool"], "save_location")
        self.assertEqual(data["tool_calls"][0]["arguments"], {"name": "base_camp"})
        # The reply should be the tool's success output
        self.assertIn("Saved location 'base_camp'", data["reply"])

    def test_chat_endpoint_multiple_tool_execution(self):
        """Verify FastAPI /chat endpoint sequentially executes all returned tool calls and combines replies."""
        client = TestClient(app)
        
        # Mock planner to return multiple tool calls
        multiple_calls = PlannerResult(
            reply="",
            tool_calls=[
                ToolCall(tool="save_location", arguments={"name": "mine_entrance"}),
                ToolCall(tool="save_note", arguments={"key": "ore_type", "value": "iron"})
            ]
        )
        
        with patch("main.plan", return_value=multiple_calls):
            request_data = {
                "message": "save location and note",
                "player": self.context.model_dump(),
                "memory": {}
            }
            response = client.post("/chat", json=request_data)
            self.assertEqual(response.status_code, 200)
            
            data = response.json()
            self.assertEqual(len(data["tool_calls"]), 2)
            self.assertEqual(data["tool_calls"][0]["tool"], "save_location")
            self.assertEqual(data["tool_calls"][1]["tool"], "save_note")
            
            # The reply should be combined output of both tools separated by newline
            self.assertIn("Saved location 'mine_entrance'", data["reply"])
            self.assertIn("Saved note for 'ore_type': 'iron'", data["reply"])

if __name__ == "__main__":
    unittest.main()
