from pydantic import BaseModel
from typing import Dict, Any, Type, List
from .base import BaseTool, ToolResult

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

class GetLightLevelInput(BaseModel):
    pass

class GetLightLevelTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_light_level"

    @property
    def description(self) -> str:
        return "Returns light level at the player's current position: block light, sky light, and combined light levels."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return GetLightLevelInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "how bright is it here?",
            "what is the light level?",
            "check light level"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> ToolResult:
        env = getattr(context, "environment", None)
        light = getattr(env, "light_level", None) if env else None
        
        if not light:
            return ToolResult(
                success=True,
                message="Light Level: Combined=15/15 (Default).",
                data={
                    "block_light": 0,
                    "sky_light": 15,
                    "combined_light": 15
                },
                tool_name=self.name
            )
            
        combined = getattr(light, "combined", 15)
        block = getattr(light, "block", 0)
        sky = getattr(light, "sky", 15)
        
        msg = f"Light Level: Combined={combined}/15 (Block Light={block}/15, Sky Light={sky}/15)."
        
        # Add warning about mobs spawning
        if combined <= 0:
            msg += " WARNING: It is dark enough for monsters to spawn!"

        return ToolResult(
            success=True,
            message=msg,
            data={
                "block_light": block,
                "sky_light": sky,
                "combined_light": combined
            },
            tool_name=self.name
        )
