from pydantic import BaseModel
from typing import Dict, Any, Type, List
from .base import BaseTool, ToolResult

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

MOON_PHASES = {
    0: "Full Moon",
    1: "Waning Gibbous",
    2: "Third Quarter",
    3: "Waning Crescent",
    4: "New Moon",
    5: "Waxing Crescent",
    6: "First Quarter",
    7: "Waxing Gibbous"
}

class GetWorldTimeInput(BaseModel):
    pass

class GetWorldTimeTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_world_time"

    @property
    def description(self) -> str:
        return "Returns current world time: total ticks, formatted clock time, is_day/is_night, and moon phase."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return GetWorldTimeInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "what is the world time?",
            "check world time",
            "show ticks and clock time"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> ToolResult:
        env = context.environment
        ticks = env.world_time
        day_night = "Day" if env.is_day else "Night"
        phase_name = MOON_PHASES.get(env.moon_phase, f"Unknown ({env.moon_phase})")
        
        # Calculate in-game clock time
        time_in_day = ticks % 24000
        hour = (int(time_in_day / 1000) + 6) % 24
        minute = int((time_in_day % 1000) * 60 / 1000)
        formatted_time = f"{hour:02d}:{minute:02d}"

        msg = f"World Time: {ticks} ticks (Clock: {formatted_time}, State: {day_night}). Moon phase: {phase_name}."
        
        data = {
            "world_ticks": ticks,
            "is_day": env.is_day,
            "is_night": env.is_night,
            "moon_phase": env.moon_phase,
            "moon_phase_name": phase_name,
            "clock_time": formatted_time
        }
        
        return ToolResult(
            success=True,
            message=msg,
            data=data,
            tool_name=self.name
        )
