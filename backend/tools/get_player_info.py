from pydantic import BaseModel
from typing import Dict, Any, Type, List
from .base import BaseTool, ToolResult

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

class GetPlayerInfoInput(BaseModel):
    pass

class GetPlayerInfoTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_player_info"

    @property
    def description(self) -> str:
        return "Returns player coordinates, gamemode, and dimension."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return GetPlayerInfoInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "get player info",
            "where am i?",
            "what is my dimension and coordinates?"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> ToolResult:
        info = context.player_info
        data = {
            "name": info.name,
            "uuid": info.uuid,
            "coordinates": {
                "x": round(info.x, 2),
                "y": round(info.y, 2),
                "z": round(info.z, 2)
            },
            "gamemode": info.gamemode,
            "dimension": info.dimension
        }
        
        msg = f"Player Info: Name={info.name}, Dimension={info.dimension}, Gamemode={info.gamemode} at X={info.x:.1f}, Y={info.y:.1f}, Z={info.z:.1f}."
        
        return ToolResult(
            success=True,
            message=msg,
            data=data,
            tool_name=self.name
        )
