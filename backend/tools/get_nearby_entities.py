from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Type, List, Optional
from .base import BaseTool

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

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> Dict[str, Any]:
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
            e_data = {
                "type": e.type,
                "name": e.name,
                "health": round(e.health, 1),
                "max_health": round(e.max_health, 1),
                "distance": round(e.distance, 1),
                "category": e.category,
                "coordinates": [round(e.x, 2), round(e.y, 2), round(e.z, 2)]
            }
            serialized_entities.append(e_data)
            
            summary_desc = f"{e.name} ({round(e.distance, 1)}m)"
            if e.category == "player":
                players.append(summary_desc)
            elif e.category == "hostile":
                hostile.append(summary_desc)
            elif e.category == "villager":
                villagers.append(summary_desc)
            elif e.category == "passive":
                passive.append(summary_desc)
            elif e.category == "projectile":
                projectiles.append(summary_desc)
            elif e.category == "vehicle":
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

        return {
            "status": "success",
            "message": msg,
            "success": True,
            "data": {
                "entities": serialized_entities
            },
            "metadata": {
                "requested_radius": radius,
                "effective_radius": radius,
                "entities_count": len(entities)
            }
        }
