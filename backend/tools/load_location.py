from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Type, List
from .base import BaseTool, ToolResult

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

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> ToolResult:
        """
        Loads the location context.
        If the location does not exist in memory, returns a structured error response.
        """
        name = arguments["name"].strip()
        name_lower = name.lower()
        
        memory = load_memory()
        
        matched_key = None
        for key in memory.get("locations", {}).keys():
            if key.lower() == name_lower:
                matched_key = key
                break
                
        if matched_key is None:
            return ToolResult(
                success=False,
                message=f"Location '{name}' is not saved.",
                error="Location not saved",
                tool_name=self.name
            )
            
        location_entry = memory["locations"][matched_key]
        return ToolResult(
            success=True,
            message=f"Loaded location '{matched_key}': coordinates are x={location_entry['x']:.1f}, y={location_entry['y']:.1f}, z={location_entry['z']:.1f} in {location_entry['dimension']}.",
            data=location_entry,
            tool_name=self.name
        )
