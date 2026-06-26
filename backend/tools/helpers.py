import time
from typing import List, Dict, Any, Optional
from context import PlayerContext, NearbyBlock, FillerBlockSummary, InterestingBlock

def get_blocks_in_radius(context: PlayerContext, radius: int) -> List[NearbyBlock]:
    """
    Combines filler blocks and interesting blocks, filtering by Chebyshev radius.
    Caches results within the PlayerContext request lifecycle.
    """
    # Clamp radius between 1 and 64
    radius = max(1, min(64, radius))
    
    cache_key = f"blocks_in_radius_{radius}"
    if cache_key in context._cache:
        # Increment cache hit
        context._cache["cache_hits"] = context._cache.get("cache_hits", 0) + 1
        return context._cache[cache_key]
    
    # Increment cache miss
    context._cache["cache_misses"] = context._cache.get("cache_misses", 0) + 1
    start_time = time.time()

    # Determine which tier key to use for filler blocks ("8", "16", "32", "64")
    if radius <= 8:
        tier_key = "8"
    elif radius <= 16:
        tier_key = "16"
    elif radius <= 32:
        tier_key = "32"
    else:
        tier_key = "64"

    blocks_map = {}

    # 1. Process filler blocks
    for b_type, summary in context.environment.nearby_blocks.filler_blocks.items():
        count = summary.counts.get(tier_key, 0)
        if count > 0:
            nearest_coord = None
            if summary.nearest:
                nearest_coord = [
                    int(context.player_info.x + summary.nearest[0]),
                    int(context.player_info.y + summary.nearest[1]),
                    int(context.player_info.z + summary.nearest[2])
                ]
            blocks_map[b_type] = NearbyBlock(
                type=b_type,
                count=count,
                nearest=nearest_coord
            )

    # 2. Process interesting blocks (filter exactly using Chebyshev distance)
    for b in context.environment.nearby_blocks.interesting_blocks:
        dx, dy, dz = b.x, b.y, b.z
        dist = max(abs(dx), abs(dy), abs(dz))
        if dist <= radius:
            abs_coord = [
                int(context.player_info.x + dx),
                int(context.player_info.y + dy),
                int(context.player_info.z + dz)
            ]
            if b.type not in blocks_map:
                blocks_map[b.type] = NearbyBlock(
                    type=b.type,
                    count=1,
                    nearest=abs_coord
                )
            else:
                blocks_map[b.type].count += 1
                curr_nearest = blocks_map[b.type].nearest
                if curr_nearest:
                    curr_dx = curr_nearest[0] - context.player_info.x
                    curr_dy = curr_nearest[1] - context.player_info.y
                    curr_dz = curr_nearest[2] - context.player_info.z
                    curr_dist = max(abs(curr_dx), abs(curr_dy), abs(curr_dz))
                    if dist < curr_dist:
                        blocks_map[b.type].nearest = abs_coord
                else:
                    blocks_map[b.type].nearest = abs_coord

    results = list(blocks_map.values())
    context._cache[cache_key] = results
    
    # Store performance profiling metrics
    duration = time.time() - start_time
    context._cache[f"duration_{cache_key}"] = duration
    context._cache["blocks_analyzed"] = context._cache.get("blocks_analyzed", 0) + len(results)
    
    return results

def get_entities_in_radius(context: PlayerContext, radius: float) -> List[Any]:
    """
    Filters nearby entities by distance and caches the list.
    """
    cache_key = f"entities_in_radius_{radius}"
    if cache_key in context._cache:
        context._cache["cache_hits"] = context._cache.get("cache_hits", 0) + 1
        return context._cache[cache_key]
    
    context._cache["cache_misses"] = context._cache.get("cache_misses", 0) + 1
    start_time = time.time()

    filtered_entities = [
        e for e in context.environment.nearby_entities
        if e.distance <= radius
    ]
    
    context._cache[cache_key] = filtered_entities
    
    duration = time.time() - start_time
    context._cache[f"duration_{cache_key}"] = duration
    context._cache["entities_analyzed"] = context._cache.get("entities_analyzed", 0) + len(filtered_entities)
    
    return filtered_entities

def calculate_direction(px: float, pz: float, py: float, tx: float, tz: float, ty: float) -> str:
    """
    Calculates a human-readable direction (e.g. North, South, East, West, Up, Down) 
    from player coordinates (px, py, pz) to target coordinates (tx, ty, tz).
    """
    dx = tx - px
    dy = ty - py
    dz = tz - pz
    
    if abs(dy) > max(abs(dx), abs(dz)) * 2:
        return "Up" if dy > 0 else "Down"
        
    # Calculate yaw angle
    import math
    # In Minecraft, positive Z is South, negative Z is North, positive X is East, negative X is West
    angle = math.atan2(dz, dx) * 180 / math.pi
    # map angle to directions
    if -135 <= angle < -45:
        return "North"
    elif -45 <= angle < 45:
        return "East"
    elif 45 <= angle < 135:
        return "South"
    else:
        return "West"
