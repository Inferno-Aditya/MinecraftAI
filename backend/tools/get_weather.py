from pydantic import BaseModel
from typing import Dict, Any, Type, List
from .base import BaseTool, ToolResult

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

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> ToolResult:
        env = getattr(context, "environment", None)
        weather = getattr(env, "weather", None) if env else None
        
        if not weather:
            return ToolResult(
                success=True,
                message="Weather status: Clear (Default).",
                data={
                    "rain": False,
                    "thunder": False,
                    "clear": True,
                    "time_remaining_ticks": 0,
                    "time_remaining_seconds": 0.0
                },
                tool_name=self.name
            )
            
        status_parts = []
        if getattr(weather, "thunder", False):
            status_parts.append("Thundering")
        if getattr(weather, "rain", False):
            status_parts.append("Raining")
        if getattr(weather, "clear", True) and not status_parts:
            status_parts.append("Clear")
            
        weather_desc = " and ".join(status_parts) if status_parts else "Clear"
        time_rem_ticks = getattr(weather, "time_remaining", 0)
        time_rem_sec = round(time_rem_ticks / 20.0, 1)
        
        msg = f"Weather is currently: {weather_desc}. Approximately {time_rem_sec} seconds remaining."

        return ToolResult(
            success=True,
            message=msg,
            data={
                "rain": getattr(weather, "rain", False),
                "thunder": getattr(weather, "thunder", False),
                "clear": getattr(weather, "clear", True),
                "time_remaining_ticks": time_rem_ticks,
                "time_remaining_seconds": time_rem_sec
            },
            tool_name=self.name
        )
