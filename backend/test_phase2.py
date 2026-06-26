import unittest
import os
import json
from context import PlayerContext
from planner import plan, ToolCall
from tools.registry import registry
from memory import MEMORY_FILE, MEMORY_DIR, load_memory, save_memory

class TestPhase2(unittest.TestCase):
    def setUp(self):
        # Backup existing memory.json if any to avoid wiping development/production memory
        self.memory_backup = None
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    self.memory_backup = f.read()
            except Exception:
                pass
                
        # Remove memory.json to start each test with a clean environment
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

    def tearDown(self):
        # Restore original memory.json file if one was backed up
        if os.path.exists(MEMORY_FILE):
            try:
                os.remove(MEMORY_FILE)
            except Exception:
                pass
        if self.memory_backup is not None:
            try:
                os.makedirs(MEMORY_DIR, exist_ok=True)
                with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                    f.write(self.memory_backup)
            except Exception:
                pass

    def test_missing_memory_file_recreated(self):
        """Verify that the memory.json file is automatically recreated with standard schema if missing."""
        self.assertFalse(os.path.exists(MEMORY_FILE))
        data = load_memory()
        self.assertTrue(os.path.exists(MEMORY_FILE))
        self.assertIn("locations", data)
        self.assertIn("notes", data)
        self.assertIn("preferences", data)

    def test_memory_survives_restart_and_persistence(self):
        """Verify memory survives a simulation of server restarts by writing and re-reading."""
        registry.execute("save_location", self.context, {"name": "home"})
        registry.execute("save_note", self.context, {"key": "test_key", "value": "test_val"})
        
        # Verify content exists in memory dict
        mem1 = load_memory()
        self.assertIn("home", mem1["locations"])
        self.assertEqual(mem1["notes"]["test_key"], "test_val")
        
        # Re-read directly from disk to simulate restart / new memory manager instance
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            disk_data = json.load(f)
        self.assertIn("home", disk_data["locations"])
        self.assertEqual(disk_data["notes"]["test_key"], "test_val")
        
    def test_duplicate_location_names_update(self):
        """Verify that saving a location with a duplicate name overwrites and updates the entry correctly."""
        registry.execute("save_location", self.context, {"name": "home"})
        mem1 = load_memory()
        x1 = mem1["locations"]["home"]["x"]
        
        # Save home with updated player context coordinates
        updated_context = self.context.model_copy(update={"x": 500.0})
        registry.execute("save_location", updated_context, {"name": "home"})
        
        mem2 = load_memory()
        x2 = mem2["locations"]["home"]["x"]
        self.assertEqual(x2, 500.0)
        self.assertNotEqual(x1, x2)

    def test_invalid_names_handled_gracefully(self):
        """Verify that empty, missing, or invalid names are rejected/handled gracefully."""
        # Empty/whitespace name for save_location
        res = registry.execute("save_location", self.context, {"name": "   "})
        self.assertEqual(res["status"], "error")
        self.assertIn("Validation failed", res["message"])
        
        # Empty/whitespace name for load_location
        res_load = registry.execute("load_location", self.context, {"name": ""})
        self.assertEqual(res_load["status"], "error")
        self.assertIn("Validation failed", res_load["message"])
        
        # Load location that doesn't exist
        res_missing = registry.execute("load_location", self.context, {"name": "nonexistent"})
        self.assertEqual(res_missing["status"], "error")
        self.assertEqual(res_missing["message"], "Location 'nonexistent' is not saved.")

    def test_memory_file_recreated_on_corruption(self):
        """Verify memory is reconstructed if memory.json file contains corrupted/invalid JSON."""
        os.makedirs(MEMORY_DIR, exist_ok=True)
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            f.write("{corrupt json ... [")
        
        data = load_memory()
        self.assertIn("locations", data)
        self.assertIn("notes", data)
        self.assertIn("preferences", data)

    def test_planner_outputs_expected_tool_calls(self):
        """Verify that the planner parses messages into expected ToolCall objects."""
        # save_location pattern
        calls = plan("remember this place as home", self.context)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].tool, "save_location")
        self.assertEqual(calls[0].arguments, {"name": "home"})
        
        # load_location pattern
        calls = plan("where is home", self.context)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].tool, "load_location")
        self.assertEqual(calls[0].arguments, {"name": "home"})
        
        # list_locations pattern
        calls = plan("list locations", self.context)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].tool, "list_locations")
        self.assertEqual(calls[0].arguments, {})
        
        # save_note pattern with space replacements
        calls = plan("remember my favorite block is spruce", self.context)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].tool, "save_note")
        self.assertEqual(calls[0].arguments, {"key": "favorite_block", "value": "spruce"})

        # Message with no tool match
        calls = plan("hello assistant", self.context)
        self.assertEqual(len(calls), 0)

    def test_registry_resolves_tools(self):
        """Verify the tool registry resolves existing tools and returns None for unknown tools."""
        self.assertIsNotNone(registry.get_tool("save_location"))
        self.assertIsNotNone(registry.get_tool("load_location"))
        self.assertIsNotNone(registry.get_tool("list_locations"))
        self.assertIsNotNone(registry.get_tool("save_note"))
        self.assertIsNone(registry.get_tool("nonexistent_tool"))

    def test_invalid_tool_calls_rejected(self):
        """Verify that invalid ToolCalls (unregistered tools or invalid arguments) are rejected."""
        # Call to a tool that is not in the registry
        res = registry.execute("nonexistent_tool", self.context, {})
        self.assertEqual(res["status"], "error")
        self.assertIn("not resolved in registry", res["message"])
        
        # Missing arguments for save_location
        res = registry.execute("save_location", self.context, {})
        self.assertEqual(res["status"], "error")
        self.assertIn("Validation failed", res["message"])

    def test_player_context_validation(self):
        """Verify that PlayerContext validates field types correctly."""
        # Check valid context compiles
        ctx = PlayerContext(
            name="Steve", x=100.0, y=64.0, z=-100.0, yaw=0.0, pitch=0.0,
            dimension="minecraft:the_nether", gamemode="creative",
            health=20.0, food=20, world_time=5000, biome="minecraft:nether_wastes"
        )
        self.assertEqual(ctx.name, "Steve")
        self.assertEqual(ctx.food, 20)
        
        # Check invalid field type throws validation error
        with self.assertRaises(Exception):
            PlayerContext(
                name="Steve", x="not_a_float", y=64.0, z=-100.0, yaw=0.0, pitch=0.0,
                dimension="minecraft:the_nether", gamemode="creative",
                health=20.0, food=20, world_time=5000, biome="minecraft:nether_wastes"
            )

if __name__ == "__main__":
    unittest.main()
