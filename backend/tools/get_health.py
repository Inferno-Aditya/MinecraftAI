from pydantic import BaseModel
from typing import Dict, Any, Type, List
from .base import BaseTool, ToolResult

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

class GetHealthInput(BaseModel):
    pass

class GetHealthTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_health"

    @property
    def description(self) -> str:
        return "Returns the player's current health."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return GetHealthInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "what is my health?",
            "check my health",
            "how much HP do i have?"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> ToolResult:
        info = context.player_info
        data = {
            "health": round(info.health, 2)
        }
        
        msg = f"Current Health: {info.health:.1f}/20 HP."
        if info.health <= 6.0:
            msg += " WARNING: Your health is low!"
        
        return ToolResult(
            success=True,
            message=msg,
            data=data,
            tool_name=self.name
        )
