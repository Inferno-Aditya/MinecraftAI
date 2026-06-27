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

class GetTimeInput(BaseModel):
    pass

class GetTimeTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_time"

    @property
    def description(self) -> str:
        return "Returns current world time: total world ticks, day/night status, and current moon phase."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return GetTimeInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "what time is it?",
            "is it day or night?",
            "show the time and moon phase"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> ToolResult:
        env = getattr(context, "environment", None)
        ticks = getattr(env, "world_time", 0) if env else 0
        is_day = getattr(env, "is_day", True) if env else True
        is_night = getattr(env, "is_night", False) if env else False
        moon_phase = getattr(env, "moon_phase", 0) if env else 0
        
        day_night = "Day" if is_day else "Night"
        phase_name = MOON_PHASES.get(moon_phase, f"Unknown ({moon_phase})")
        
        # Calculate in-game clock time: 0 is 06:00 (sunrise), 6000 is 12:00 (noon), 18000 is 00:00 (midnight)
        time_in_day = ticks % 24000
        hour = (int(time_in_day / 1000) + 6) % 24
        minute = int((time_in_day % 1000) * 60 / 1000)
        formatted_time = f"{hour:02d}:{minute:02d}"

        msg = f"World Time: {ticks} ticks (Clock: {formatted_time}, State: {day_night}). Moon phase is {phase_name}."

        return ToolResult(
            success=True,
            message=msg,
            data={
                "world_ticks": ticks,
                "is_day": is_day,
                "is_night": is_night,
                "moon_phase": moon_phase,
                "moon_phase_name": phase_name,
                "clock_time": formatted_time
            },
            tool_name=self.name
        )
