import time
from typing import List, Dict, Any, Optional

try:
    from context import PlayerContext, NearbyBlock, FillerBlockSummary, InterestingBlock
except ImportError:
    from ..context import PlayerContext, NearbyBlock, FillerBlockSummary, InterestingBlock

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

    # Extract nested context properties with graceful fallbacks
    env = getattr(context, "environment", None)
    nb_snapshot = getattr(env, "nearby_blocks", None) if env else None
    
    # 1. Process filler blocks
    filler_blocks = getattr(nb_snapshot, "filler_blocks", {}) or {}
    if isinstance(filler_blocks, dict):
        for b_type, summary in filler_blocks.items():
            if not summary:
                continue
            counts = getattr(summary, "counts", {}) or {}
            count = counts.get(tier_key, 0)
            if count > 0:
                nearest_coord = None
                nearest_rel = getattr(summary, "nearest", None)
                if nearest_rel and len(nearest_rel) >= 3:
                    px = getattr(context.player_info, "x", 0.0)
                    py = getattr(context.player_info, "y", 64.0)
                    pz = getattr(context.player_info, "z", 0.0)
                    nearest_coord = [
                        int(px + nearest_rel[0]),
                        int(py + nearest_rel[1]),
                        int(pz + nearest_rel[2])
                    ]
                blocks_map[b_type] = NearbyBlock(
                    type=b_type,
                    count=count,
                    nearest=nearest_coord
                )

    # 2. Process interesting blocks (filter exactly using Chebyshev distance)
    interesting_blocks = getattr(nb_snapshot, "interesting_blocks", []) or []
    if isinstance(interesting_blocks, list):
        for b in interesting_blocks:
            if not b:
                continue
            dx = getattr(b, "x", 0)
            dy = getattr(b, "y", 0)
            dz = getattr(b, "z", 0)
            b_type = getattr(b, "type", "minecraft:air")
            
            dist = max(abs(dx), abs(dy), abs(dz))
            if dist <= radius:
                px = getattr(context.player_info, "x", 0.0)
                py = getattr(context.player_info, "y", 64.0)
                pz = getattr(context.player_info, "z", 0.0)
                abs_coord = [
                    int(px + dx),
                    int(py + dy),
                    int(pz + dz)
                ]
                if b_type not in blocks_map:
                    blocks_map[b_type] = NearbyBlock(
                        type=b_type,
                        count=1,
                        nearest=abs_coord
                    )
                else:
                    blocks_map[b_type].count += 1
                    curr_nearest = blocks_map[b_type].nearest
                    if curr_nearest:
                        curr_dx = curr_nearest[0] - px
                        curr_dy = curr_nearest[1] - py
                        curr_dz = curr_nearest[2] - pz
                        curr_dist = max(abs(curr_dx), abs(curr_dy), abs(curr_dz))
                        if dist < curr_dist:
                            blocks_map[b_type].nearest = abs_coord
                    else:
                        blocks_map[b_type].nearest = abs_coord

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

    env = getattr(context, "environment", None)
    entities = getattr(env, "nearby_entities", []) or []
    
    filtered_entities = []
    if isinstance(entities, list):
        for e in entities:
            if not e:
                continue
            dist = getattr(e, "distance", 999.0)
            if dist <= radius:
                filtered_entities.append(e)
    
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
    # In Minecraft, Z+ is South, Z- is North, X+ is East, X- is West
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
