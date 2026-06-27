from pydantic import BaseModel
from typing import Dict, Any, Type, List
from .base import BaseTool, ToolResult

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

class GetPlayerStatusInput(BaseModel):
    pass

class GetPlayerStatusTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_player_status"

    @property
    def description(self) -> str:
        return "Returns the player's status: health, hunger, saturation, experience level, coordinates, rotation, gamemode, and dimension."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return GetPlayerStatusInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "what is my status?",
            "check player status",
            "show my health and coordinates"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> ToolResult:
        info = getattr(context, "player_info", None)
        if not info:
            return ToolResult(
                success=False,
                message="Error: Player state is not available.",
                error="Missing player_info",
                tool_name=self.name
            )
            
        data = {
            "name": getattr(info, "name", "Player"),
            "uuid": getattr(info, "uuid", ""),
            "coordinates": {
                "x": round(getattr(info, "x", 0.0), 2),
                "y": round(getattr(info, "y", 64.0), 2),
                "z": round(getattr(info, "z", 0.0), 2)
            },
            "rotation": {
                "yaw": round(getattr(info, "yaw", 0.0), 2),
                "pitch": round(getattr(info, "pitch", 0.0), 2)
            },
            "health": round(getattr(info, "health", 20.0), 2),
            "hunger": getattr(info, "food", 20),
            "saturation": round(getattr(info, "saturation", 5.0), 2),
            "experience": round(getattr(info, "experience", 0.0), 2),
            "level": getattr(info, "level", 0),
            "gamemode": getattr(info, "gamemode", "survival"),
            "dimension": getattr(info, "dimension", "minecraft:overworld")
        }
        
        status_msg = (
            f"Player {data['name']} status: Health {data['health']:.1f}/20, Hunger {data['hunger']}/20, "
            f"Level {data['level']}, Gamemode {data['gamemode']}, Dimension {data['dimension']} "
            f"at X={data['coordinates']['x']:.1f}, Y={data['coordinates']['y']:.1f}, Z={data['coordinates']['z']:.1f}."
        )

        return ToolResult(
            success=True,
            message=status_msg,
            data=data,
            tool_name=self.name
        )
