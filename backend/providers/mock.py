import re
import json
from .base import BaseLLMProvider

class MockProvider(BaseLLMProvider):
    """
    Mock LLM provider for unit tests and offline/mock mode.
    Simulates a planning LLM by returning structured JSON tool calls or conversational replies.
    """
    def __init__(self, model_name: str = "mock-model"):
        self.model_name = model_name

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        # Check if the system prompt is for synthesis (ResponseGenerator)
        if "companion" in system_prompt.lower():
            if "shield" in user_prompt.lower():
                return json.dumps({"reply": "Yes, you can craft a shield. You have 16 oak logs which is enough for planks, but you need 1 iron ingot."})
            elif "survive the night" in user_prompt.lower():
                return json.dumps({"reply": "You have decent gear, but there is a zombie nearby. Watch out!"})
            elif "nether" in user_prompt.lower():
                return json.dumps({"reply": "Your armor is okay, but you should get a chestplate before going to the Nether."})
            elif "upgrade my sword" in user_prompt.lower():
                return json.dumps({"reply": "You have a diamond sword with Sharpness V, so you don't need to upgrade it first."})
            return json.dumps({"reply": "Mock synthesis response based on tool results."})

        # Check if the user prompt is a correction prompt for validation failure specifically
        if "Validation failed for tool 'save_location'" in user_prompt:
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "save_location", "arguments": {"another_invalid_arg": 456}}],
                "reply": ""
            })

        # Check if the user prompt is a general correction prompt (failed parsing/validation)
        if "failed parsing/validation" in user_prompt:
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "save_location", "arguments": {"name": "home"}}],
                "reply": ""
            })
            
        # Match user_prompt (user message) using regex patterns
        message = user_prompt
        for line in user_prompt.splitlines():
            if line.startswith("User Message:"):
                message = line.replace("User Message:", "").strip()
                break

        msg = message.strip()
        
        # Test simulations
        if msg == "simulate malformed JSON":
            return '{"tool_calls": [{"tool": "save_location", "arguments": {"name": "home"'
            
        if msg == "simulate validation failure":
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "save_location", "arguments": {"invalid_arg": 123}}],
                "reply": ""
            })
            
        if msg == "simulate timeout":
            raise Exception("Gemini request timed out.")
            
        if msg == "simulate rate limiting":
            raise Exception("429 Too Many Requests / Rate limit exceeded")

        # --- Phase 4A.1 New Knowledge-Only Queries ---
        if re.search(r"critical hits", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "KNOWLEDGE",
                "reply": "Critical hits are dealt when a player attacks while falling. They deal 150% of the weapon's base damage.",
                "tool_calls": []
            })
        if re.search(r"strongest weapon", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "KNOWLEDGE",
                "reply": "A Netherite Sword/Axe is the strongest weapon.",
                "tool_calls": []
            })
        if re.search(r"villagers breed", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "KNOWLEDGE",
                "reply": "Villagers breed when they have enough beds and food.",
                "tool_calls": []
            })
        if re.search(r"fortune work", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "KNOWLEDGE",
                "reply": "Fortune increases block drops.",
                "tool_calls": []
            })
        if re.search(r"nether portals work", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "KNOWLEDGE",
                "reply": "Nether portals are made of obsidian and lit with fire.",
                "tool_calls": []
            })

        # --- Phase 4A.1 New Hybrid Queries ---
        if re.search(r"survive the night", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "HYBRID",
                "reply": "",
                "tool_calls": [
                    {"tool": "get_time", "arguments": {}},
                    {"tool": "get_equipment", "arguments": {}},
                    {"tool": "get_nearby_entities", "arguments": {}}
                ]
            })
        if re.search(r"craft.*shield", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "HYBRID",
                "reply": "",
                "tool_calls": [{"tool": "get_inventory", "arguments": {}}]
            })
        if re.search(r"armor.*Nether", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "HYBRID",
                "reply": "",
                "tool_calls": [{"tool": "get_equipment", "arguments": {}}]
            })
        if re.search(r"upgrade.*sword", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "HYBRID",
                "reply": "",
                "tool_calls": [
                    {"tool": "get_held_item", "arguments": {}},
                    {"tool": "get_inventory", "arguments": {}}
                ]
            })
            
        # Check save_location intent
        save_match = re.search(r"(?:remember|save) this (?:place|location) as\s+(.+)$", msg, re.IGNORECASE)
        if save_match:
            name = save_match.group(1).strip()
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "save_location", "arguments": {"name": name}}],
                "reply": ""
            })
            
        # Check load_location intent
        load_match = re.search(r"(?:where is|load location|get location)\s+(.+)$", msg, re.IGNORECASE)
        if load_match and "closest" not in msg and "nearest" not in msg:
            name = load_match.group(1).strip()
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "load_location", "arguments": {"name": name}}],
                "reply": ""
            })
            
        # Check list_locations intent
        if re.search(r"^(?:list|show) locations|what locations are saved$", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "list_locations", "arguments": {}}],
                "reply": ""
            })
            
        # Check save_note intent
        note_match = re.search(r"remember (?:my|that)\s+(.+?)\s+is\s+(.+)$", msg, re.IGNORECASE)
        if not note_match:
            note_match = re.search(r"save note\s+(.+?)\s+as\s+(.+)$", msg, re.IGNORECASE)
        if note_match:
            key = note_match.group(1).strip().replace(" ", "_")
            value = note_match.group(2).strip()
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "save_note", "arguments": {"key": key, "value": value}}],
                "reply": ""
            })

        # --- Phase 4A Environmental Perception Intents ---

        # get_player_status
        if re.search(r"status|health and coordinates|where am i", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "get_player_status", "arguments": {}}],
                "reply": ""
            })

        # get_held_item
        if re.search(r"holding|held item|what is in my hand", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "get_held_item", "arguments": {}}],
                "reply": ""
            })

        # get_equipment
        if re.search(r"armor|equipment|gear", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "get_equipment", "arguments": {}}],
                "reply": ""
            })

        # get_inventory
        if re.search(r"inventory|do i have enough|do i have.*wood|do i have.*cobblestone|do i have.*torch", msg, re.IGNORECASE):
            # Extract item search query if search matches pattern like "do i have wood"
            search_item = None
            if "wood" in msg:
                search_item = "wood"
            elif "cobblestone" in msg:
                search_item = "cobblestone"
            elif "torch" in msg:
                search_item = "torch"
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "get_inventory", "arguments": {"search": search_item} if search_item else {}}],
                "reply": ""
            })

        # get_weather
        if re.search(r"weather|raining|thundering", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "get_weather", "arguments": {}}],
                "reply": ""
            })

        # get_time
        if re.search(r"time|day or night|ticks|moon phase", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "get_time", "arguments": {}}],
                "reply": ""
            })

        # get_light_level
        if re.search(r"bright|light level", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "get_light_level", "arguments": {}}],
                "reply": ""
            })

        # find_nearest
        nearest_match = re.search(r"(?:closest|nearest|find nearest|where is the closest|where is the nearest)\s+(.+)$", msg, re.IGNORECASE)
        if nearest_match:
            target = nearest_match.group(1).strip().strip("?").lower()
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "find_nearest", "arguments": {"target_type": target}}],
                "reply": ""
            })

        # get_nearby_entities
        if re.search(r"entities|monsters|mobs|zombie|players nearby", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "get_nearby_entities", "arguments": {}}],
                "reply": ""
            })

        # get_nearby_blocks
        if re.search(r"blocks around me|nearby blocks", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "get_nearby_blocks", "arguments": {"radius": 16}}],
                "reply": ""
            })

        # scan_area
        if re.search(r"scan|surroundings|lava nearby|resources around me", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "scan_area", "arguments": {"radius": 16}}],
                "reply": ""
            })

        # get_biome
        if re.search(r"biome", msg, re.IGNORECASE):
            return json.dumps({
                "response_strategy": "TOOLS",
                "tool_calls": [{"tool": "get_biome", "arguments": {}}],
                "reply": ""
            })

        # Default conversational reply
        return json.dumps({
            "response_strategy": "KNOWLEDGE",
            "tool_calls": [],
            "reply": f"Mock response for: {msg}"
        })
