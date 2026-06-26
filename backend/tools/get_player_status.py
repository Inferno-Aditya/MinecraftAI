from pydantic import BaseModel
from typing import Dict, Any, Type, List
from .base import BaseTool

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

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> Dict[str, Any]:
        info = context.player_info
        data = {
            "name": info.name,
            "uuid": info.uuid,
            "coordinates": {
                "x": round(info.x, 2),
                "y": round(info.y, 2),
                "z": round(info.z, 2)
            },
            "rotation": {
                "yaw": round(info.yaw, 2),
                "pitch": round(info.pitch, 2)
            },
            "health": round(info.health, 2),
            "hunger": info.food,
            "saturation": round(info.saturation, 2),
            "experience": round(info.experience, 2),
            "level": info.level,
            "gamemode": info.gamemode,
            "dimension": info.dimension
        }
        
        status_msg = (
            f"Player {info.name} status: Health {info.health:.1f}/20, Hunger {info.food}/20, "
            f"Level {info.level}, Gamemode {info.gamemode}, Dimension {info.dimension} "
            f"at X={info.x:.1f}, Y={info.y:.1f}, Z={info.z:.1f}."
        )

        return {
            "status": "success",
            "message": status_msg,
            "success": True,
            "data": data,
            "metadata": {}
        }
