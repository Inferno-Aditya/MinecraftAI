from typing import Dict, Any, Optional, Type
from pydantic import ValidationError, BaseModel
from .base import BaseTool
from .save_location import SaveLocationTool
from .load_location import LoadLocationTool
from .list_locations import ListLocationsTool
from .save_note import SaveNoteTool

# Phase 4A perception tools
from .get_player_status import GetPlayerStatusTool
from .get_held_item import GetHeldItemTool
from .get_equipment import GetEquipmentTool
from .get_inventory import GetInventoryTool
from .get_weather import GetWeatherTool
from .get_time import GetTimeTool
from .get_light_level import GetLightLevelTool
from .get_nearby_blocks import GetNearbyBlocksTool
from .scan_area import ScanAreaTool
from .find_nearest import FindNearestTool
from .get_nearby_entities import GetNearbyEntitiesTool
from .get_biome import GetBiomeTool

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

class ToolRegistry:
    """
    Registry for managing and executing tools.
    Encapsulates tool lookup, parameter validation using tool Pydantic input schemas,
    and tool execution using player context.
    """
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Registers a tool in the registry."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Resolves a tool by its name."""
        return self._tools.get(name)

    def list_tools(self) -> Dict[str, BaseTool]:
        """Returns all registered tools."""
        return self._tools

    def execute(self, tool_name: str, context: PlayerContext, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a registered tool.
        
        1. Resolves the tool name.
        2. Validates arguments using the tool's input_schema.
        3. Invokes the tool's execute() method with context and validated arguments.
        
        Returns a structured success/error response dictionary.
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return {
                "status": "error",
                "message": f"Tool '{tool_name}' not resolved in registry."
            }
        
        try:
            # Validate input arguments against tool's Pydantic model
            validated_args = tool.input_schema(**arguments)
            # Use model_dump() for Pydantic V2 compatibility
            args_dict = validated_args.model_dump()
            return tool.execute(context, args_dict)
        except ValidationError as e:
            # Format ValidationError messages to return clean error details
            error_details = []
            for err in e.errors():
                loc = " -> ".join(str(l) for l in err["loc"])
                error_details.append(f"{loc}: {err['msg']}")
            return {
                "status": "error",
                "message": f"Validation failed for tool '{tool_name}': {'; '.join(error_details)}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Execution error in tool '{tool_name}': {str(e)}"
            }

# Instantiate global registry and register Phase 2 & Phase 4A tools
registry = ToolRegistry()

# Phase 2 Memory Tools
registry.register(SaveLocationTool())
registry.register(LoadLocationTool())
registry.register(ListLocationsTool())
registry.register(SaveNoteTool())

# Phase 4A Environment Perception Tools
registry.register(GetPlayerStatusTool())
registry.register(GetHeldItemTool())
registry.register(GetEquipmentTool())
registry.register(GetInventoryTool())
registry.register(GetWeatherTool())
registry.register(GetTimeTool())
registry.register(GetLightLevelTool())
registry.register(GetNearbyBlocksTool())
registry.register(ScanAreaTool())
registry.register(FindNearestTool())
registry.register(GetNearbyEntitiesTool())
registry.register(GetBiomeTool())
