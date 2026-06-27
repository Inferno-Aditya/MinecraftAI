from pydantic import BaseModel
from typing import Dict, Any, Type, List
from .base import BaseTool, ToolResult

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

class GetDimensionInput(BaseModel):
    pass

class GetDimensionTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_dimension"

    @property
    def description(self) -> str:
        return "Returns the player's current dimension."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return GetDimensionInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "what dimension am i in?",
            "check dimension",
            "am i in the overworld or nether?"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> ToolResult:
        info = context.player_info
        data = {
            "dimension": info.dimension
        }
        
        msg = f"You are currently in the dimension: {info.dimension}."
        return ToolResult(
            success=True,
            message=msg,
            data=data,
            tool_name=self.name
        )
