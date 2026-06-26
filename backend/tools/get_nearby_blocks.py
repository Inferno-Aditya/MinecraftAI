from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Type, List
from .base import BaseTool

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

try:
    from tools.helpers import get_blocks_in_radius
except ImportError:
    from .helpers import get_blocks_in_radius

class GetNearbyBlocksInput(BaseModel):
    radius: int = Field(16, description="Scan radius in blocks (Chebyshev distance).")

    @field_validator('radius')
    @classmethod
    def clamp_radius(cls, v: int) -> int:
        return max(1, min(64, v))

class GetNearbyBlocksTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_nearby_blocks"

    @property
    def description(self) -> str:
        return "Returns all block types, counts, and nearest coordinates within the specified radius (1 to 64 blocks, default 16)."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return GetNearbyBlocksInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "what blocks are around me?",
            "check blocks within a radius of 10",
            "show nearby blocks"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> Dict[str, Any]:
        radius = arguments.get("radius", 16)
        
        # Call scanning helper
        nearby_blocks = get_blocks_in_radius(context, radius)
        
        # Format response data
        data_list = []
        msg_parts = []
        for nb in sorted(nearby_blocks, key=lambda x: x.count, reverse=True):
            data_list.append({
                "type": nb.type,
                "count": nb.count,
                "nearest": nb.nearest
            })
            coord_str = f" at {nb.nearest}" if nb.nearest else ""
            msg_parts.append(f"- {nb.type}: {nb.count} occurrences{coord_str}")

        msg = f"Blocks within radius {radius}:\n" + "\n".join(msg_parts) if msg_parts else f"No blocks detected in radius {radius}."
        
        # Extract metadata from cache
        hits = context._cache.get("cache_hits", 0)
        misses = context._cache.get("cache_misses", 0)
        cache_status = "hit" if hits > 0 else "miss"

        metadata = {
            "requested_radius": radius,
            "effective_radius": radius,
            "blocks_scanned": len(nearby_blocks),
            "cache": cache_status
        }

        return {
            "status": "success",
            "message": msg,
            "success": True,
            "data": {
                "blocks": data_list
            },
            "metadata": metadata
        }
