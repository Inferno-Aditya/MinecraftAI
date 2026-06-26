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
            # Return another invalid argument on retry to simulate persistent validation failure
            return json.dumps({
                "tool_calls": [{"tool": "save_location", "arguments": {"another_invalid_arg": 456}}],
                "reply": ""
            })

        # Check if the user prompt is a general correction prompt (failed parsing/validation)
        if "failed parsing/validation" in user_prompt:
            # Return the correct JSON on retry
            return json.dumps({
                "tool_calls": [{"tool": "save_location", "arguments": {"name": "home"}}],
                "reply": ""
            })
            
        # Match user_prompt (user message) using regex patterns similar to Phase 2
        message = user_prompt
        for line in user_prompt.splitlines():
            if line.startswith("User Message:"):
                message = line.replace("User Message:", "").strip()
                break

        msg = message.strip()
        
        # Test simulations
        if msg == "simulate malformed JSON":
            # Missing closing brackets/braces to force parsing failure
            return '{"tool_calls": [{"tool": "save_location", "arguments": {"name": "home"'
            
        if msg == "simulate validation failure":
            # Invalid argument name to trigger input schema validation failure
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
        if load_match:
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
            
        # Default conversational reply
        return json.dumps({
            "tool_calls": [],
            "reply": f"Mock response for: {msg}"
        })
