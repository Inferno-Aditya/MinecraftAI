from pydantic import BaseModel
from typing import Dict, Any, Type, List
from .base import BaseTool

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

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> Dict[str, Any]:
        env = context.environment
        ticks = env.world_time
        day_night = "Day" if env.is_day else "Night"
        phase_name = MOON_PHASES.get(env.moon_phase, f"Unknown ({env.moon_phase})")
        
        # Calculate in-game clock time: 0 is 06:00 (sunrise), 6000 is 12:00 (noon), 18000 is 00:00 (midnight)
        time_in_day = ticks % 24000
        hour = (int(time_in_day / 1000) + 6) % 24
        minute = int((time_in_day % 1000) * 60 / 1000)
        formatted_time = f"{hour:02d}:{minute:02d}"

        msg = f"World Time: {ticks} ticks (Clock: {formatted_time}, State: {day_night}). Moon phase is {phase_name}."

        return {
            "status": "success",
            "message": msg,
            "success": True,
            "data": {
                "world_ticks": ticks,
                "is_day": env.is_day,
                "is_night": env.is_night,
                "moon_phase": env.moon_phase,
                "moon_phase_name": phase_name,
                "clock_time": formatted_time
            },
            "metadata": {}
        }
