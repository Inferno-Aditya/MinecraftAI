from pydantic import BaseModel
from typing import Dict, Any, Type, List
from .base import BaseTool

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

class GetWeatherInput(BaseModel):
    pass

class GetWeatherTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_weather"

    @property
    def description(self) -> str:
        return "Returns current weather status in the Minecraft world: rain, thunder, clear, and duration remaining."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return GetWeatherInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "what's the weather like?",
            "is it raining?",
            "check weather"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> Dict[str, Any]:
        weather = context.environment.weather
        
        status_parts = []
        if weather.thunder:
            status_parts.append("Thundering")
        if weather.rain:
            status_parts.append("Raining")
        if weather.clear:
            status_parts.append("Clear")
            
        weather_desc = " and ".join(status_parts)
        time_rem_ticks = weather.time_remaining
        time_rem_sec = round(time_rem_ticks / 20.0, 1)
        
        msg = f"Weather is currently: {weather_desc}. Approximately {time_rem_sec} seconds remaining."

        return {
            "status": "success",
            "message": msg,
            "success": True,
            "data": {
                "rain": weather.rain,
                "thunder": weather.thunder,
                "clear": weather.clear,
                "time_remaining_ticks": weather.time_remaining,
                "time_remaining_seconds": time_rem_sec
            },
            "metadata": {}
        }
