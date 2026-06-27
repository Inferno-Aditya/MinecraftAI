from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Type, List, Optional
from .base import BaseTool, ToolResult

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

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> ToolResult:
        target = arguments["target_type"].strip().lower()
        
        info = getattr(context, "player_info", None)
        px = getattr(info, "x", 0.0) if info else 0.0
        py = getattr(info, "y", 64.0) if info else 64.0
        pz = getattr(info, "z", 0.0) if info else 0.0
        
        # 1. Search blocks
        closest_block = None
        closest_block_dist = float('inf')
        
        # Scan blocks with max radius 64
        nearby_blocks = get_blocks_in_radius(context, 64)
        for nb in nearby_blocks:
            # Match target against block ID
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
            e_type = getattr(e, "type", "").lower()
            e_name = getattr(e, "name", "").lower()
            e_cat = getattr(e, "category", "").lower()
            e_dist = getattr(e, "distance", 999.0)
            
            if (target in e_type) or (target in e_name) or (target in e_cat):
                if e_dist < closest_entity_dist:
                    closest_entity_dist = e_dist
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
            tx = getattr(closest_entity, "x", 0.0)
            ty = getattr(closest_entity, "y", 64.0)
            tz = getattr(closest_entity, "z", 0.0)
            e_type = getattr(closest_entity, "type", "")
            e_name = getattr(closest_entity, "name", "")
            
            direction = calculate_direction(px, pz, py, tx, tz, ty)
            
            data = {
                "found": True,
                "type": "entity",
                "id": e_type,
                "name": e_name,
                "coordinates": [round(tx, 2), round(ty, 2), round(tz, 2)],
                "distance": round(closest_entity_dist, 1),
                "direction": direction,
                "confidence": 1.0
            }
            msg = f"Found nearest entity '{e_name}' ({e_type}) at coordinates {data['coordinates']} ({data['distance']} blocks away, direction: {direction})."
            
        else:
            data = {
                "found": False,
                "coordinates": None,
                "distance": None,
                "direction": None,
                "confidence": 0.0
            }
            msg = f"Could not find any block or entity matching '{target}' within a 64-block radius."

        return ToolResult(
            success=data.get("found", False),
            message=msg,
            data=data,
            tool_name=self.name
        )
