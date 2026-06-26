from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Type, List
from .base import BaseTool

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

try:
    from memory import load_memory
except ImportError:
    from ..memory import load_memory

class LoadLocationInput(BaseModel):
    name: str = Field(..., description="The name of the location to load.")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Location name cannot be empty or only whitespace.")
        return v_stripped

class LoadLocationTool(BaseTool):
    @property
    def name(self) -> str:
        return "load_location"

    @property
    def description(self) -> str:
        return "Retrieves the saved coordinates and dimension for a given location name."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return LoadLocationInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "where is home",
            "load location base",
            "get location mine"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Loads the location context.
        If the location does not exist in memory, returns a structured error response.
        """
        name = arguments["name"].strip()
        
        memory = load_memory()
        
        if name not in memory["locations"]:
            return {
                "status": "error",
                "message": f"Location '{name}' is not saved."
            }
            
        location_entry = memory["locations"][name]
        return {
            "status": "success",
            "message": f"Loaded location '{name}': coordinates are x={location_entry['x']:.1f}, y={location_entry['y']:.1f}, z={location_entry['z']:.1f} in {location_entry['dimension']}.",
            "data": location_entry
        }
