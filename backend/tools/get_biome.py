from pydantic import BaseModel
from typing import Dict, Any, Type, List
from .base import BaseTool

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

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> Dict[str, Any]:
        biome = context.environment.biome
        msg = (
            f"You are currently in the biome '{biome.name}' "
            f"(Category: {biome.category}, Temperature: {biome.temperature:.2f}, Rainfall: {biome.rainfall:.2f})."
        )

        return {
            "status": "success",
            "message": msg,
            "success": True,
            "data": {
                "name": biome.name,
                "category": biome.category,
                "temperature": biome.temperature,
                "rainfall": biome.rainfall
            },
            "metadata": {}
        }
