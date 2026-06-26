import datetime
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Type
from .base import BaseTool

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

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Saves the location context.
        Duplicates overwrite the previous entry. Invalid/empty names are handled by input schema.
        """
        name = arguments["name"].strip()
        
        # Load memory and update location entry
        memory = load_memory()
        
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
        
        return {
            "status": "success",
            "message": f"Saved location '{name}' at coordinates x={context.x:.1f}, y={context.y:.1f}, z={context.z:.1f} in {context.dimension}.",
            "data": location_entry
        }
