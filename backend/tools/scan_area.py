from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Type, List
from .base import BaseTool

try:
    from context import PlayerContext, AreaSummary, TerrainStatistics
except ImportError:
    from ..context import PlayerContext, AreaSummary, TerrainStatistics

try:
    from tools.helpers import get_blocks_in_radius
except ImportError:
    from .helpers import get_blocks_in_radius

class ScanAreaInput(BaseModel):
    radius: int = Field(16, description="The scan radius (Chebyshev distance).")

    @field_validator('radius')
    @classmethod
    def clamp_radius(cls, v: int) -> int:
        return max(1, min(64, v))

class ScanAreaTool(BaseTool):
    @property
    def name(self) -> str:
        return "scan_area"

    @property
    def description(self) -> str:
        return "Scans the surroundings and returns a structured high-level summary of the area (biome, terrain, ores, liquids, trees, buildings, etc.)."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return ScanAreaInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "scan this area",
            "is there any lava or ore nearby?",
            "what does the surrounding terrain look like?"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> Dict[str, Any]:
        radius = arguments.get("radius", 16)
        
        nearby_blocks = get_blocks_in_radius(context, radius)
        
        # Categorized counts
        stone_count = 0
        water_count = 0
        lava_count = 0
        air_count = 0
        tree_count = 0
        flower_count = 0
        building_count = 0
        ore_counts = {}

        # Coordinate tracking for terrain statistics
        known_ys = [int(context.player_info.y)]

        for nb in nearby_blocks:
            b_type = nb.type.lower()
            
            # Track coordinates if available for height statistics
            if nb.nearest:
                known_ys.append(nb.nearest[1])

            # Classify
            if "stone" in b_type or "deepslate" in b_type or b_type == "minecraft:tuff":
                stone_count += nb.count
            elif "water" in b_type:
                water_count += nb.count
            elif "lava" in b_type:
                lava_count += nb.count
            elif "air" in b_type:
                air_count += nb.count
            elif "log" in b_type or "leaves" in b_type or "wood" in b_type:
                tree_count += nb.count
            elif any(x in b_type for x in ["flower", "dandelion", "poppy", "orchid", "allium", "tulip", "daisy", "cornflower", "lily", "rose", "sunflower", "lilac", "peony", "grass", "fern"]):
                flower_count += nb.count
            elif any(x in b_type for x in ["planks", "brick", "concrete", "terracotta", "wool", "cobblestone"]):
                building_count += nb.count
            
            # Ores
            if "ore" in b_type or "debris" in b_type:
                ore_name = b_type.split(":")[-1].replace("deepslate_", "").replace("_ore", "")
                ore_counts[ore_name] = ore_counts.get(ore_name, 0) + nb.count

        min_y = min(known_ys)
        max_y = max(known_ys)
        avg_y = sum(known_ys) / len(known_ys)
        height_var = max_y - min_y

        terrain_stats = TerrainStatistics(
            min_y=min_y,
            max_y=max_y,
            average_y=round(avg_y, 2),
            height_variation=height_var
        )

        summary = AreaSummary(
            biome=context.environment.biome.name,
            height_variation=height_var,
            stone_count=stone_count,
            water_count=water_count,
            lava_count=lava_count,
            ore_counts=ore_counts,
            tree_count=tree_count,
            flower_count=flower_count,
            building_blocks_count=building_count,
            air_count=air_count,
            terrain_statistics=terrain_stats
        )

        # Build clean natural message
        ores_found = ", ".join(f"{k} ({v})" for k, v in ore_counts.items()) if ore_counts else "None"
        msg = (
            f"Area Scan Report (Radius {radius} in Biome: {summary.biome}):\n"
            f"- Terrain Y Range: {min_y} to {max_y} (Variation: {height_var} blocks)\n"
            f"- Blocks: Stone={stone_count}, Trees/Leaves={tree_count}, Buildings={building_count}\n"
            f"- Liquids: Water={water_count}, Lava={lava_count}\n"
            f"- Ores Detected: {ores_found}\n"
            f"- Vegetation/Flowers: {flower_count}\n"
            f"- Air: {air_count}"
        )

        return {
            "status": "success",
            "message": msg,
            "success": True,
            "data": summary.model_dump(),
            "metadata": {
                "requested_radius": radius,
                "effective_radius": radius,
                "blocks_analyzed": len(nearby_blocks)
            }
        }
