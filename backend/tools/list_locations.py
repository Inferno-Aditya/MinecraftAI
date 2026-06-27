from pydantic import BaseModel
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

class ListLocationsInput(BaseModel):
    """Empty schema as list_locations requires no parameters."""
    pass

class ListLocationsTool(BaseTool):
    @property
    def name(self) -> str:
        return "list_locations"

    @property
    def description(self) -> str:
        return "Lists all saved location names."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return ListLocationsInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "list locations",
            "show locations",
            "what locations are saved"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> ToolResult:
        """
        Lists all saved location names in memory.
        """
        memory = load_memory()
        locations = list(memory["locations"].keys())
        
        if not locations:
            return ToolResult(
                success=True,
                message="No locations saved yet.",
                data={"locations": []},
                tool_name=self.name
            )
            
        locations_str = ", ".join(locations)
        return ToolResult(
            success=True,
            message=f"Saved locations: {locations_str}.",
            data={"locations": locations},
            tool_name=self.name
        )
