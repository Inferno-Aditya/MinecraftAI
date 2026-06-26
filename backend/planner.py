import re
from pydantic import BaseModel, Field
from typing import List

try:
    from context import PlayerContext
except ImportError:
    from .context import PlayerContext

class ToolCall(BaseModel):
    """
    Model representing a planned tool execution call.
    """
    tool: str = Field(..., description="The name of the tool to be executed.")
    arguments: dict = Field(..., description="The dictionary of arguments to pass to the tool.")

# Regex patterns for lightweight intent detection
SAVE_LOCATION_PATTERNS = [
    re.compile(r"^remember this place as\s+(.+)$", re.IGNORECASE),
    re.compile(r"^save this place as\s+(.+)$", re.IGNORECASE),
    re.compile(r"^remember this location as\s+(.+)$", re.IGNORECASE),
    re.compile(r"^save this location as\s+(.+)$", re.IGNORECASE),
]

LOAD_LOCATION_PATTERNS = [
    re.compile(r"^where is\s+(.+)$", re.IGNORECASE),
    re.compile(r"^load location\s+(.+)$", re.IGNORECASE),
    re.compile(r"^get location\s+(.+)$", re.IGNORECASE),
]

LIST_LOCATIONS_PATTERNS = [
    re.compile(r"^list locations$", re.IGNORECASE),
    re.compile(r"^show locations$", re.IGNORECASE),
    re.compile(r"^what locations are saved$", re.IGNORECASE),
]

SAVE_NOTE_PATTERNS = [
    re.compile(r"^remember my\s+(.+?)\s+is\s+(.+)$", re.IGNORECASE),
    re.compile(r"^remember that\s+(.+?)\s+is\s+(.+)$", re.IGNORECASE),
    re.compile(r"^save note\s+(.+?)\s+as\s+(.+)$", re.IGNORECASE),
]

def plan(message: str, player_context: PlayerContext) -> List[ToolCall]:
    """
    Decides which tool(s) should run based on the user's message and player context.
    Returns a list of ToolCall objects. Returns an empty list if no tool intent is detected.
    Does not execute tools.
    """
    msg = message.strip()
    
    # Check save_location intent
    for pattern in SAVE_LOCATION_PATTERNS:
        match = pattern.match(msg)
        if match:
            name = match.group(1).strip()
            return [ToolCall(tool="save_location", arguments={"name": name})]
            
    # Check load_location intent
    for pattern in LOAD_LOCATION_PATTERNS:
        match = pattern.match(msg)
        if match:
            name = match.group(1).strip()
            return [ToolCall(tool="load_location", arguments={"name": name})]
            
    # Check list_locations intent
    for pattern in LIST_LOCATIONS_PATTERNS:
        match = pattern.match(msg)
        if match:
            return [ToolCall(tool="list_locations", arguments={})]
            
    # Check save_note intent
    for pattern in SAVE_NOTE_PATTERNS:
        match = pattern.match(msg)
        if match:
            # We replace spaces in the key with underscores to ensure clean key indexing (e.g. favorite block -> favorite_block)
            key = match.group(1).strip().replace(" ", "_")
            value = match.group(2).strip()
            return [ToolCall(tool="save_note", arguments={"key": key, "value": value})]
            
    return []
