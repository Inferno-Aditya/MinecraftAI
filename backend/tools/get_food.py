from pydantic import BaseModel
from typing import Dict, Any, Type, List
from .base import BaseTool, ToolResult

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

class GetFoodInput(BaseModel):
    pass

class GetFoodTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_food"

    @property
    def description(self) -> str:
        return "Returns the player's current food level and saturation."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return GetFoodInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "am i hungry?",
            "check my food level",
            "what is my hunger and saturation?"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> ToolResult:
        info = context.player_info
        data = {
            "food": info.food,
            "saturation": round(info.saturation, 2)
        }
        
        msg = f"Food Level: {info.food}/20 (Saturation: {info.saturation:.1f})."
        if info.food <= 6:
            msg += " WARNING: You are hungry! You should eat."
            
        return ToolResult(
            success=True,
            message=msg,
            data=data,
            tool_name=self.name
        )
