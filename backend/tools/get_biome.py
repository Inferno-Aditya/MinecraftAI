from pydantic import BaseModel
from typing import Dict, Any, Type, List
from .base import BaseTool, ToolResult

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

class GetBiomeInput(BaseModel):
    pass

class GetBiomeTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_biome"

    @property
    def description(self) -> str:
        return "Returns details of the biome where the player is currently located: biome name, temperature, rainfall, and category."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return GetBiomeInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "what biome am i in?",
            "check biome info",
            "what is the temperature and biome?"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> ToolResult:
        env = getattr(context, "environment", None)
        biome = getattr(env, "biome", None) if env else None
        
        if not biome:
            return ToolResult(
                success=True,
                message="You are currently in an unknown biome.",
                data={
                    "name": "unknown",
                    "category": "unknown",
                    "temperature": 0.0,
                    "rainfall": 0.0
                },
                tool_name=self.name
            )
            
        b_name = getattr(biome, "name", "unknown")
        b_cat = getattr(biome, "category", "unknown")
        b_temp = getattr(biome, "temperature", 0.0)
        b_rain = getattr(biome, "rainfall", 0.0)
        
        msg = (
            f"You are currently in the biome '{b_name}' "
            f"(Category: {b_cat}, Temperature: {b_temp:.2f}, Rainfall: {b_rain:.2f})."
        )

        return ToolResult(
            success=True,
            message=msg,
            data={
                "name": b_name,
                "category": b_cat,
                "temperature": b_temp,
                "rainfall": b_rain
            },
            tool_name=self.name
        )
