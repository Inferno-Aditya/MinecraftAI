import datetime
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Type, List
from .base import BaseTool, ToolResult
# ... (rest unchanged until execute)

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

try:
    from memory import load_memory, save_memory
except ImportError:
    from ..memory import load_memory, save_memory

class SaveLocationInput(BaseModel):
    name: str = Field(..., description="The name of the location to save.")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Location name cannot be empty or only whitespace.")
        return v_stripped

class SaveLocationTool(BaseTool):
    @property
    def name(self) -> str:
        return "save_location"

    @property
    def description(self) -> str:
        return "Saves the player's current location (coordinates, dimension, biome) to memory."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return SaveLocationInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "remember this place as home",
            "save this location as base",
            "remember this location as mine"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Saves the location context.
        Duplicates overwrite the previous entry. Invalid/empty names are handled by input schema.
        """
        name = arguments["name"].strip()
        name_lower = name.lower()
        
        # Load memory and update location entry
        memory = load_memory()
        
        # Overwrite any existing entry matching case-insensitively
        matched_key = None
        for key in list(memory.get("locations", {}).keys()):
            if key.lower() == name_lower:
                matched_key = key
                break
                
        if matched_key is not None:
            del memory["locations"][matched_key]
        
        # Generate current timestamp (UTC ISO format)
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        location_entry = {
            "x": context.x,
            "y": context.y,
            "z": context.z,
            "dimension": context.dimension,
            "biome": context.biome,
            "timestamp": timestamp
        }
        
        memory["locations"][name] = location_entry
        save_memory(memory)
        
        return ToolResult(
            success=True,
            message=f"Saved location '{name}' at coordinates x={context.x:.1f}, y={context.y:.1f}, z={context.z:.1f} in {context.dimension}.",
            data=location_entry,
            tool_name=self.name
        )

