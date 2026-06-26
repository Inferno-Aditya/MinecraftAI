import unittest
import os
import json
from unittest.mock import patch

from context import (
    PlayerContext, PlayerInfo, EnvironmentSnapshot, InventorySlot, 
    EquipmentItem, EquipmentSlots, HeldItem, WeatherInfo, LightInfo, BiomeInfo
)
from tools.registry import registry
from tools.helpers import get_blocks_in_radius, get_entities_in_radius, calculate_direction
from planner import plan, get_tool_definitions

class TestPhase4A(unittest.TestCase):
    def setUp(self):
        # Create a rich nested PlayerContext payload for testing
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
                    {"slot": 0, "item": "minecraft:iron_pickaxe", "count": 1, "durability": 200, "enchantments": {"minecraft:efficiency": 3}, "nbt": "My Lucky Pick"},
                    {"slot": 1, "item": "minecraft:oak_log", "count": 16, "durability": 0, "enchantments": {}, "nbt": ""},
                    {"slot": 2, "item": "minecraft:coal", "count": 8, "durability": 0, "enchantments": {}, "nbt": ""}
                ],
                "equipment": {
                    "helmet": {"item": "minecraft:iron_helmet", "count": 1, "durability": 150, "enchantments": {"minecraft:protection": 1}},
                    "chestplate": {"item": "minecraft:air", "count": 0, "durability": 0, "enchantments": {}},
                    "leggings": {"item": "minecraft:air", "count": 0, "durability": 0, "enchantments": {}},
                    "boots": {"item": "minecraft:air", "count": 0, "durability": 0, "enchantments": {}},
                    "offhand": {"item": "minecraft:shield", "count": 1, "durability": 300, "enchantments": {}}
                },
                "held_item": {"item": "minecraft:diamond_sword", "count": 1, "durability": 1500, "enchantments": {"minecraft:sharpness": 5}}
            },
            "environment": {
                "weather": {
                    "rain": True,
                    "thunder": False,
                    "clear": False,
                    "time_remaining": 6000
                },
                "world_time": 13000, # Night time
                "is_day": False,
                "is_night": True,
                "moon_phase": 4, # New Moon
                "light_level": {
                    "block": 5,
                    "sky": 0,
                    "combined": 5
                },
                "biome": {
                    "name": "minecraft:forest",
                    "temperature": 0.7,
                    "rainfall": 0.8,
                    "category": "forest"
                },
                "nearby_blocks": {
                    "filler_blocks": {
                        "minecraft:stone": {
                            "nearest": [0, -1, 0],
                            "counts": {"8": 150, "16": 1200, "32": 8000, "64": 8000}
                        },
                        "minecraft:dirt": {
                            "nearest": [0, 0, 1],
                            "counts": {"8": 50, "16": 300, "32": 1500, "64": 1500}
                        },
                        "minecraft:water": {
                            "nearest": [5, -1, 5],
                            "counts": {"8": 2, "16": 15, "32": 100, "64": 100}
                        }
                    },
                    "interesting_blocks": [
                        {"type": "minecraft:diamond_ore", "x": 3, "y": -5, "z": -2},
                        {"type": "minecraft:coal_ore", "x": 2, "y": -2, "z": 1},
                        {"type": "minecraft:coal_ore", "x": 10, "y": -4, "z": 8}, # outside radius 8, inside 16
                        {"type": "minecraft:chest", "x": -1, "y": 0, "z": -1}
                    ]
                },
                "nearby_entities": [
                    {"type": "minecraft:zombie", "name": "Zombie", "health": 20.0, "max_health": 20.0, "distance": 4.5, "x": 103.0, "y": 64.0, "z": -197.0, "category": "hostile"},
                    {"type": "minecraft:cow", "name": "Cow", "health": 10.0, "max_health": 10.0, "distance": 12.2, "x": 90.0, "y": 64.0, "z": -205.0, "category": "passive"},
                    {"type": "minecraft:villager", "name": "Librarian", "health": 20.0, "max_health": 20.0, "distance": 8.0, "x": 105.0, "y": 64.0, "z": -205.0, "category": "villager"}
                ]
            }
        }
        
        self.context = PlayerContext.model_validate(self.context_data)
        
        # Patch config for planning tests
        self.config_patcher = patch("planner.load_config", return_value={
            "provider": "mock",
            "model": "mock-model",
            "enable_prompt_logging": False
        })
        self.config_patcher.start()

    def tearDown(self):
        self.config_patcher.stop()

    def test_backward_compatibility_flat_context(self):
        """Verify that PlayerContext model validator correctly parses flat Phase 3 context."""
        flat_data = {
            "name": "Steve",
            "x": 10.0,
            "y": 64.0,
            "z": -20.0,
            "yaw": 0.0,
            "pitch": 0.0,
            "dimension": "minecraft:overworld",
            "gamemode": "survival",
            "health": 20.0,
            "food": 20,
            "world_time": 1000,
            "biome": "minecraft:plains"
        }
        ctx = PlayerContext.model_validate(flat_data)
        self.assertEqual(ctx.name, "Steve")
        self.assertEqual(ctx.x, 10.0)
        self.assertEqual(ctx.world_time, 1000)
        self.assertEqual(ctx.biome, "minecraft:plains")
        # Verify sub-objects were populated with defaults
        self.assertEqual(ctx.player_info.saturation, 0.0)
        self.assertEqual(ctx.environment.weather.clear, True)

    def test_get_player_status_tool(self):
        """Verify get_player_status returns correct health, coordinates, level, and dimensions."""
        res = registry.execute("get_player_status", self.context, {})
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["health"], 18.5)
        self.assertEqual(res["data"]["level"], 12)
        self.assertEqual(res["data"]["coordinates"]["x"], 100.5)

    def test_get_held_item_tool(self):
        """Verify get_held_item returns details of the currently held item."""
        res = registry.execute("get_held_item", self.context, {})
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["item"], "minecraft:diamond_sword")
        self.assertEqual(res["data"]["enchantments"]["minecraft:sharpness"], 5)

        # Test empty hand fallback
        empty_ctx_data = self.context_data.copy()
        empty_ctx_data["player_info"]["held_item"] = {"item": "minecraft:air", "count": 0, "durability": 0, "enchantments": {}}
        empty_ctx = PlayerContext.model_validate(empty_ctx_data)
        res_empty = registry.execute("get_held_item", empty_ctx, {})
        self.assertEqual(res_empty["data"]["item"], "minecraft:air")
        self.assertIn("not holding any item", res_empty["message"])

    def test_get_equipment_tool(self):
        """Verify get_equipment returns equipped gear and handles empty slots."""
        res = registry.execute("get_equipment", self.context, {})
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["helmet"]["item"], "minecraft:iron_helmet")
        self.assertEqual(res["data"]["helmet"]["enchantments"]["minecraft:protection"], 1)
        self.assertEqual(res["data"]["chestplate"]["item"], "minecraft:air")
        self.assertEqual(res["data"]["offhand"]["item"], "minecraft:shield")

    def test_get_inventory_tool_and_search(self):
        """Verify get_inventory supports list summary and filters correctly based on search terms."""
        # Unfiltered list
        res = registry.execute("get_inventory", self.context, {})
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["success"])
        self.assertIn("minecraft:iron_pickaxe", res["data"]["summary"])
        self.assertEqual(res["data"]["summary"]["minecraft:oak_log"], 16)
        
        # Filtered list: match by ID
        res_search_log = registry.execute("get_inventory", self.context, {"search": "log"})
        self.assertEqual(len(res_search_log["data"]["slots"]), 1)
        self.assertEqual(res_search_log["data"]["slots"][0]["item"], "minecraft:oak_log")

        # Filtered list: match by custom name (NBT)
        res_search_nbt = registry.execute("get_inventory", self.context, {"search": "lucky"})
        self.assertEqual(len(res_search_nbt["data"]["slots"]), 1)
        self.assertEqual(res_search_nbt["data"]["slots"][0]["item"], "minecraft:iron_pickaxe")

        # Filtered list: no match
        res_search_none = registry.execute("get_inventory", self.context, {"search": "diamond"})
        self.assertEqual(len(res_search_none["data"]["slots"]), 0)

    def test_get_weather_tool(self):
        """Verify get_weather returns correct states and duration."""
        res = registry.execute("get_weather", self.context, {})
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["rain"], True)
        self.assertEqual(res["data"]["thunder"], False)
        self.assertEqual(res["data"]["time_remaining_ticks"], 6000)

    def test_get_time_tool(self):
        """Verify get_time returns ticks, day/night, and moon phase name."""
        res = registry.execute("get_time", self.context, {})
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["world_ticks"], 13000)
        self.assertEqual(res["data"]["is_night"], True)
        self.assertEqual(res["data"]["moon_phase_name"], "New Moon")

    def test_get_light_level_tool(self):
        """Verify get_light_level returns block, sky, and combined light levels."""
        res = registry.execute("get_light_level", self.context, {})
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["block_light"], 5)
        self.assertEqual(res["data"]["sky_light"], 0)
        self.assertEqual(res["data"]["combined_light"], 5)

    def test_get_nearby_blocks_radius_filtering(self):
        """Verify get_nearby_blocks filters correctly using Chebyshev distance and supports radius clamp."""
        # Radius 8 scan
        res_8 = registry.execute("get_nearby_blocks", self.context, {"radius": 8})
        self.assertEqual(res_8["status"], "success")
        # Check that diamond_ore (dist 5: dx=3, dy=-5, dz=-2) is inside radius 8
        self.assertTrue(any(b["type"] == "minecraft:diamond_ore" for b in res_8["data"]["blocks"]))
        # Check that coal_ore at x=10, y=-4, z=8 (dist 10) is NOT inside radius 8
        coal_ore_counts = [b["count"] for b in res_8["data"]["blocks"] if b["type"] == "minecraft:coal_ore"]
        # Only one coal_ore (at dist 2) should be in radius 8
        self.assertEqual(coal_ore_counts[0], 1)

        # Radius 16 scan (should include both coal_ores)
        res_16 = registry.execute("get_nearby_blocks", self.context, {"radius": 16})
        coal_ore_counts_16 = [b["count"] for b in res_16["data"]["blocks"] if b["type"] == "minecraft:coal_ore"]
        self.assertEqual(coal_ore_counts_16[0], 2)

        # Verify radius clamping
        res_clamp = registry.execute("get_nearby_blocks", self.context, {"radius": 100})
        self.assertEqual(res_clamp["metadata"]["effective_radius"], 64)

    def test_scan_area_tool(self):
        """Verify scan_area aggregates counts and correctly builds TerrainStatistics."""
        res = registry.execute("scan_area", self.context, {"radius": 16})
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["success"])
        
        # Check counts
        self.assertEqual(res["data"]["stone_count"], 1200)
        self.assertEqual(res["data"]["water_count"], 15)
        # Check ores aggregated
        self.assertEqual(res["data"]["ore_counts"]["diamond"], 1)
        self.assertEqual(res["data"]["ore_counts"]["coal"], 2)
        # Check height variation stats
        # known Y values: player (64), stone (63), dirt (64), water (63), diamond (59), coal1 (62), coal2 (60), chest (64)
        # min_y = 59, max_y = 64, variation = 5
        self.assertEqual(res["data"]["terrain_statistics"]["min_y"], 59)
        self.assertEqual(res["data"]["terrain_statistics"]["max_y"], 64)
        self.assertEqual(res["data"]["terrain_statistics"]["height_variation"], 5)

    def test_find_nearest_block_and_entity(self):
        """Verify find_nearest returns coordinates, distance, and direction for matching block or entity."""
        # Find nearest block: diamond
        res_block = registry.execute("find_nearest", self.context, {"target_type": "diamond"})
        self.assertEqual(res_block["status"], "success")
        self.assertTrue(res_block["success"])
        self.assertEqual(res_block["data"]["type"], "block")
        self.assertEqual(res_block["data"]["id"], "minecraft:diamond_ore")
        self.assertEqual(res_block["data"]["distance"], 5.0) # Chebyshev: max(3, 5, 2) = 5
        # Player is at 100.5, 64, -200.5; diamond is relative 3, -5, -2 -> absolute 103.5, 59.0, -202.5
        # Direction: dx=3, dz=-2 -> angle is ~-33 deg -> East
        self.assertEqual(res_block["data"]["direction"], "East")

        # Find nearest entity: zombie
        res_ent = registry.execute("find_nearest", self.context, {"target_type": "zombie"})
        self.assertEqual(res_ent["status"], "success")
        self.assertTrue(res_ent["success"])
        self.assertEqual(res_ent["data"]["type"], "entity")
        self.assertEqual(res_ent["data"]["distance"], 4.5)
        # Zombie at 103, 64, -197 -> absolute distance 4.5
        # Player is at 100.5, 64, -200.5; zombie is at 103, 64, -197 -> dx=2.5, dz=3.5 -> South-East -> South
        self.assertEqual(res_ent["data"]["direction"], "South")

        # Find nearest: nothing found
        res_none = registry.execute("find_nearest", self.context, {"target_type": "creeper"})
        self.assertFalse(res_none["success"])
        self.assertIn("Could not find any block or entity", res_none["message"])

    def test_get_nearby_entities_tool(self):
        """Verify get_nearby_entities returns details of surrounding players, villagers, and mobs."""
        res = registry.execute("get_nearby_entities", self.context, {"radius": 64})
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["success"])
        self.assertEqual(len(res["data"]["entities"]), 3)
        self.assertTrue(any(e["type"] == "minecraft:zombie" for e in res["data"]["entities"]))

        # Check radius filtering: cow is at 12.2m, librarian at 8.0m, zombie at 4.5m
        # Radius 6 scan should only return zombie
        res_6 = registry.execute("get_nearby_entities", self.context, {"radius": 6})
        self.assertEqual(len(res_6["data"]["entities"]), 1)
        self.assertEqual(res_6["data"]["entities"][0]["type"], "minecraft:zombie")

    def test_get_biome_tool(self):
        """Verify get_biome returns correct temperature, category, and name."""
        res = registry.execute("get_biome", self.context, {})
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["name"], "minecraft:forest")
        self.assertEqual(res["data"]["category"], "forest")
        self.assertEqual(res["data"]["temperature"], 0.7)

    def test_caching_behavior(self):
        """Verify that get_blocks_in_radius and get_entities_in_radius reuse cached lists."""
        # Clear cache first
        self.context._cache.clear()

        # 1. First block scan
        nearby_blocks_1 = get_blocks_in_radius(self.context, 16)
        self.assertEqual(self.context._cache.get("cache_misses", 0), 1)
        self.assertEqual(self.context._cache.get("cache_hits", 0), 0)

        # 2. Second block scan with same radius (should hit cache)
        nearby_blocks_2 = get_blocks_in_radius(self.context, 16)
        self.assertEqual(self.context._cache.get("cache_misses", 0), 1)
        self.assertEqual(self.context._cache.get("cache_hits", 0), 1)
        self.assertEqual(len(nearby_blocks_1), len(nearby_blocks_2))

        # 3. Entity scan (first call - miss)
        entities_1 = get_entities_in_radius(self.context, 64.0)
        self.assertEqual(self.context._cache.get("cache_misses", 0), 2)
        
        # 4. Entity scan (second call - hit)
        entities_2 = get_entities_in_radius(self.context, 64.0)
        self.assertEqual(self.context._cache.get("cache_misses", 0), 2)
        self.assertEqual(self.context._cache.get("cache_hits", 0), 2)
        self.assertEqual(len(entities_1), len(entities_2))

    def test_planner_tool_injection_definitions_contains_new_tools(self):
        """Verify that newly registered tools automatically appear in get_tool_definitions()."""
        defs = get_tool_definitions()
        self.assertIn("get_player_status", defs)
        self.assertIn("get_held_item", defs)
        self.assertIn("get_equipment", defs)
        self.assertIn("get_inventory", defs)
        self.assertIn("get_weather", defs)
        self.assertIn("get_time", defs)
        self.assertIn("get_light_level", defs)
        self.assertIn("get_nearby_blocks", defs)
        self.assertIn("scan_area", defs)
        self.assertIn("find_nearest", defs)
        self.assertIn("get_nearby_entities", defs)
        self.assertIn("get_biome", defs)

    def test_planner_planning_intents(self):
        """Verify that the planner maps player environment questions to correct tool calls."""
        # Biome check
        res = plan("what biome am i in?", self.context)
        self.assertEqual(len(res.tool_calls), 1)
        self.assertEqual(res.tool_calls[0].tool, "get_biome")

        # Held item check
        res = plan("what am i holding in my hand?", self.context)
        self.assertEqual(len(res.tool_calls), 1)
        self.assertEqual(res.tool_calls[0].tool, "get_held_item")

        # Weather check
        res = plan("is it thundering outside?", self.context)
        self.assertEqual(len(res.tool_calls), 1)
        self.assertEqual(res.tool_calls[0].tool, "get_weather")

        # Nearest check
        res = plan("where is the closest water?", self.context)
        self.assertEqual(len(res.tool_calls), 1)
        self.assertEqual(res.tool_calls[0].tool, "find_nearest")
        self.assertEqual(res.tool_calls[0].arguments["target_type"], "water")

if __name__ == "__main__":
    unittest.main()
