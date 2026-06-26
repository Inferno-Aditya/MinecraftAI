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
        # Check if the user prompt is a correction prompt for validation failure specifically
        if "Validation failed for tool 'save_location'" in user_prompt:
            return json.dumps({
                "tool_calls": [{"tool": "save_location", "arguments": {"another_invalid_arg": 456}}],
                "reply": ""
            })

        # Check if the user prompt is a general correction prompt (failed parsing/validation)
        if "failed parsing/validation" in user_prompt:
            return json.dumps({
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
                "tool_calls": [{"tool": "save_location", "arguments": {"invalid_arg": 123}}],
                "reply": ""
            })
            
        if msg == "simulate timeout":
            raise Exception("Gemini request timed out.")
            
        if msg == "simulate rate limiting":
            raise Exception("429 Too Many Requests / Rate limit exceeded")
            
        # Check save_location intent
        save_match = re.search(r"(?:remember|save) this (?:place|location) as\s+(.+)$", msg, re.IGNORECASE)
        if save_match:
            name = save_match.group(1).strip()
            return json.dumps({
                "tool_calls": [{"tool": "save_location", "arguments": {"name": name}}],
                "reply": ""
            })
            
        # Check load_location intent
        load_match = re.search(r"(?:where is|load location|get location)\s+(.+)$", msg, re.IGNORECASE)
        # Avoid matching "where is the closest..." or "where is the nearest..." as load_location
        if load_match and "closest" not in msg and "nearest" not in msg:
            name = load_match.group(1).strip()
            return json.dumps({
                "tool_calls": [{"tool": "load_location", "arguments": {"name": name}}],
                "reply": ""
            })
            
        # Check list_locations intent
        if re.search(r"^(?:list|show) locations|what locations are saved$", msg, re.IGNORECASE):
            return json.dumps({
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
                "tool_calls": [{"tool": "save_note", "arguments": {"key": key, "value": value}}],
                "reply": ""
            })

        # --- Phase 4A Environmental Perception Intents ---

        # get_player_status
        if re.search(r"status|health and coordinates|where am i", msg, re.IGNORECASE):
            return json.dumps({
                "tool_calls": [{"tool": "get_player_status", "arguments": {}}],
                "reply": ""
            })

        # get_held_item
        if re.search(r"holding|held item|what is in my hand", msg, re.IGNORECASE):
            return json.dumps({
                "tool_calls": [{"tool": "get_held_item", "arguments": {}}],
                "reply": ""
            })

        # get_equipment
        if re.search(r"armor|equipment|gear", msg, re.IGNORECASE):
            return json.dumps({
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
                "tool_calls": [{"tool": "get_inventory", "arguments": {"search": search_item} if search_item else {}}],
                "reply": ""
            })

        # get_weather
        if re.search(r"weather|raining|thundering", msg, re.IGNORECASE):
            return json.dumps({
                "tool_calls": [{"tool": "get_weather", "arguments": {}}],
                "reply": ""
            })

        # get_time
        if re.search(r"time|day or night|ticks|moon phase", msg, re.IGNORECASE):
            return json.dumps({
                "tool_calls": [{"tool": "get_time", "arguments": {}}],
                "reply": ""
            })

        # get_light_level
        if re.search(r"bright|light level", msg, re.IGNORECASE):
            return json.dumps({
                "tool_calls": [{"tool": "get_light_level", "arguments": {}}],
                "reply": ""
            })

        # find_nearest
        nearest_match = re.search(r"(?:closest|nearest|find nearest|where is the closest|where is the nearest)\s+(.+)$", msg, re.IGNORECASE)
        if nearest_match:
            target = nearest_match.group(1).strip().strip("?").lower()
            return json.dumps({
                "tool_calls": [{"tool": "find_nearest", "arguments": {"target_type": target}}],
                "reply": ""
            })

        # get_nearby_entities
        if re.search(r"entities|monsters|mobs|zombie|players nearby", msg, re.IGNORECASE):
            return json.dumps({
                "tool_calls": [{"tool": "get_nearby_entities", "arguments": {}}],
                "reply": ""
            })

        # get_nearby_blocks
        if re.search(r"blocks around me|nearby blocks", msg, re.IGNORECASE):
            return json.dumps({
                "tool_calls": [{"tool": "get_nearby_blocks", "arguments": {"radius": 16}}],
                "reply": ""
            })

        # scan_area
        if re.search(r"scan|surroundings|lava nearby|resources around me", msg, re.IGNORECASE):
            return json.dumps({
                "tool_calls": [{"tool": "scan_area", "arguments": {"radius": 16}}],
                "reply": ""
            })

        # get_biome
        if re.search(r"biome", msg, re.IGNORECASE):
            return json.dumps({
                "tool_calls": [{"tool": "get_biome", "arguments": {}}],
                "reply": ""
            })

        # Default conversational reply
        return json.dumps({
            "tool_calls": [],
            "reply": f"Mock response for: {msg}"
        })
