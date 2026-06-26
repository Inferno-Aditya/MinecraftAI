from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Type, List, Optional
from .base import BaseTool

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

try:
    from tools.helpers import get_blocks_in_radius, get_entities_in_radius, calculate_direction
except ImportError:
    from .helpers import get_blocks_in_radius, get_entities_in_radius, calculate_direction

class FindNearestInput(BaseModel):
    target_type: str = Field(..., description="The block type or entity type to find (e.g. 'minecraft:water', 'zombie', 'chest', 'sheep').")

    @field_validator('target_type')
    @classmethod
    def validate_target(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Target type cannot be empty.")
        return v_stripped

class FindNearestTool(BaseTool):
    @property
    def name(self) -> str:
        return "find_nearest"

    @property
    def description(self) -> str:
        return "Finds the coordinates, distance, and direction of the nearest occurrence of a specific block type or entity type within a 64-block radius."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return FindNearestInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "where is the closest water?",
            "find the nearest chest",
            "is there a zombie nearby?",
            "locate a sheep"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> Dict[str, Any]:
        target = arguments["target_type"].strip().lower()
        
        px, py, pz = context.player_info.x, context.player_info.y, context.player_info.z
        
        # 1. Search blocks
        closest_block = None
        closest_block_dist = float('inf')
        
        # Scan blocks with max radius 64
        nearby_blocks = get_blocks_in_radius(context, 64)
        for nb in nearby_blocks:
            # Match target against block ID (e.g. "minecraft:diamond_ore" contains "diamond")
            if target in nb.type.lower() and nb.nearest:
                tx, ty, tz = nb.nearest
                # Chebyshev distance relative to player
                dist = max(abs(tx - px), abs(ty - py), abs(tz - pz))
                if dist < closest_block_dist:
                    closest_block_dist = dist
                    closest_block = nb

        # 2. Search entities
        closest_entity = None
        closest_entity_dist = float('inf')
        
        nearby_entities = get_entities_in_radius(context, 64.0)
        for e in nearby_entities:
            # Match target against entity type, name or category
            if (target in e.type.lower()) or (target in e.name.lower()) or (target in e.category.lower()):
                if e.distance < closest_entity_dist:
                    closest_entity_dist = e.distance
                    closest_entity = e

        # 3. Compare block vs entity
        if closest_block and (closest_block_dist <= closest_entity_dist):
            tx, ty, tz = closest_block.nearest
            direction = calculate_direction(px, pz, py, tx, tz, ty)
            
            data = {
                "found": True,
                "type": "block",
                "id": closest_block.type,
                "coordinates": [tx, ty, tz],
                "distance": round(closest_block_dist, 1),
                "direction": direction,
                "confidence": 1.0
            }
            msg = f"Found nearest block '{closest_block.type}' at coordinates {data['coordinates']} ({data['distance']} blocks away, direction: {direction})."
            
        elif closest_entity:
            tx, ty, tz = closest_entity.x, closest_entity.y, closest_entity.z
            direction = calculate_direction(px, pz, py, tx, tz, ty)
            
            data = {
                "found": True,
                "type": "entity",
                "id": closest_entity.type,
                "name": closest_entity.name,
                "coordinates": [round(tx, 2), round(ty, 2), round(tz, 2)],
                "distance": round(closest_entity_dist, 1),
                "direction": direction,
                "confidence": 1.0
            }
            msg = f"Found nearest entity '{closest_entity.name}' ({closest_entity.type}) at coordinates {data['coordinates']} ({data['distance']} blocks away, direction: {direction})."
            
        else:
            data = {
                "found": False,
                "coordinates": None,
                "distance": None,
                "direction": None,
                "confidence": 0.0
            }
            msg = f"Could not find any block or entity matching '{target}' within a 64-block radius."

        return {
            "status": "success",
            "message": msg,
            "success": data.get("found", False),
            "data": data,
            "metadata": {
                "target_query": target,
                "scan_radius": 64
            }
        }
