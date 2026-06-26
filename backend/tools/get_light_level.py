from pydantic import BaseModel
from typing import Dict, Any, Type, List
from .base import BaseTool

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

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> Dict[str, Any]:
        light = context.environment.light_level
        msg = f"Light Level: Combined={light.combined}/15 (Block Light={light.block}/15, Sky Light={light.sky}/15)."
        
        # Add warning about mobs spawning (light level <= 0 is spawning threshold for general mobs in newer Minecraft)
        if light.combined <= 0:
            msg += " WARNING: It is dark enough for monsters to spawn!"

        return {
            "status": "success",
            "message": msg,
            "success": True,
            "data": {
                "block_light": light.block,
                "sky_light": light.sky,
                "combined_light": light.combined
            },
            "metadata": {}
        }
