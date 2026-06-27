from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Type, List, Optional
from .base import BaseTool, ToolResult

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

try:
    from tools.helpers import get_entities_in_radius
except ImportError:
    from .helpers import get_entities_in_radius

class GetNearbyEntitiesInput(BaseModel):
    radius: int = Field(64, description="Maximum distance to filter entities (1 to 64 blocks).")

    @field_validator('radius')
    @classmethod
    def clamp_radius(cls, v: int) -> int:
        return max(1, min(64, v))

class GetNearbyEntitiesTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_nearby_entities"

    @property
    def description(self) -> str:
        return "Returns a list of all entities near the player (players, passive mobs, hostile mobs, villagers, animals, vehicles, projectiles) within the specified radius (default 64)."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return GetNearbyEntitiesInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "are there monsters close to me?",
            "check nearby entities",
            "are there any players or villagers nearby?",
            "list entities in radius 20"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> ToolResult:
        radius = arguments.get("radius", 64)
        
        entities = get_entities_in_radius(context, radius)
        
        # Categorized lists for the organized summary
        players = []
        hostile = []
        passive = []
        villagers = []
        vehicles = []
        projectiles = []
        other = []
        
        serialized_entities = []

        for e in entities:
            e_type = getattr(e, "type", "")
            e_name = getattr(e, "name", "")
            e_health = getattr(e, "health", 20.0)
            e_max_health = getattr(e, "max_health", 20.0)
            e_dist = getattr(e, "distance", 0.0)
            e_cat = getattr(e, "category", "other")
            e_x = getattr(e, "x", 0.0)
            e_y = getattr(e, "y", 64.0)
            e_z = getattr(e, "z", 0.0)

            e_data = {
                "type": e_type,
                "name": e_name,
                "health": round(e_health, 1),
                "max_health": round(e_max_health, 1),
                "distance": round(e_dist, 1),
                "category": e_cat,
                "coordinates": [round(e_x, 2), round(e_y, 2), round(e_z, 2)]
            }
            serialized_entities.append(e_data)
            
            summary_desc = f"{e_name} ({round(e_dist, 1)}m)"
            if e_cat == "player":
                players.append(summary_desc)
            elif e_cat == "hostile":
                hostile.append(summary_desc)
            elif e_cat == "villager":
                villagers.append(summary_desc)
            elif e_cat == "passive":
                passive.append(summary_desc)
            elif e_cat == "projectile":
                projectiles.append(summary_desc)
            elif e_cat == "vehicle":
                vehicles.append(summary_desc)
            else:
                other.append(summary_desc)

        # Build natural summary response message
        msg_parts = []
        if players:
            msg_parts.append("Players: " + ", ".join(players))
        if hostile:
            msg_parts.append("Hostile Mobs: " + ", ".join(hostile))
        if villagers:
            msg_parts.append("Villagers: " + ", ".join(villagers))
        if passive:
            msg_parts.append("Passive/Animals: " + ", ".join(passive))
        if vehicles:
            msg_parts.append("Vehicles: " + ", ".join(vehicles))
        if projectiles:
            msg_parts.append("Projectiles: " + ", ".join(projectiles))
        if other:
            msg_parts.append("Other: " + ", ".join(other))
            
        if msg_parts:
            msg = f"Nearby entities in radius {radius}m:\n" + "\n".join(f"- {p}" for p in msg_parts)
        else:
            msg = f"No entities detected within {radius} blocks of the player."

        return ToolResult(
            success=True,
            message=msg,
            data={
                "entities": serialized_entities
            },
            tool_name=self.name
        )
