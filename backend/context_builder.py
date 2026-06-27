from typing import Dict, Any, List
try:
    from context import PlayerContext
except ImportError:
    from .context import PlayerContext

def build_context(player_context: PlayerContext, required_components: List[str]) -> str:
    """
    Assembles the requested context text components.
    """
    sections = []
    
    if "player_context" in required_components:
        sections.append(
            f"Player Name: {player_context.name}\n"
            f"Current Location: X={player_context.x:.1f}, Y={player_context.y:.1f}, Z={player_context.z:.1f}\n"
            f"Dimension: {player_context.dimension}\n"
            f"Gamemode: {player_context.gamemode}\n"
            f"Health: {player_context.health}/20\n"
            f"Food Level: {player_context.food}/20\n"
            f"Biome: {player_context.biome}\n"
            f"World Time: {player_context.world_time} ticks"
        )
        
    if "environment_snapshot" in required_components:
        env = player_context.environment
        weather_str = f"Weather: rain={env.weather.rain}, thunder={env.weather.thunder}, clear={env.weather.clear} (time_remaining={env.weather.time_remaining})"
        light_str = f"Light Level: block={env.light_level.block}, sky={env.light_level.sky}, combined={env.light_level.combined}"
        
        entity_counts = {}
        for ent in env.nearby_entities:
            entity_counts[ent.type] = entity_counts.get(ent.type, 0) + 1
        entities_summary = ", ".join(f"{k} x{v}" for k, v in entity_counts.items()) if entity_counts else "None"
        entities_str = f"Nearby Entities: {entities_summary}"
        
        filler_counts = {}
        for b_type, summary in env.nearby_blocks.filler_blocks.items():
            count_8 = summary.counts.get("8", 0)
            if count_8 > 0:
                filler_counts[b_type] = count_8
        interesting_counts = {}
        for b in env.nearby_blocks.interesting_blocks:
            interesting_counts[b.type] = interesting_counts.get(b.type, 0) + 1
        blocks_summary = []
        if filler_counts:
            blocks_summary.append("Filler: " + ", ".join(f"{k} ({v})" for k, v in filler_counts.items()))
        if interesting_counts:
            blocks_summary.append("Interesting: " + ", ".join(f"{k} x{v}" for k, v in interesting_counts.items()))
        blocks_str = f"Nearby Blocks:\n  " + "\n  ".join(blocks_summary) if blocks_summary else "Nearby Blocks: None"
        
        sections.append(
            f"Environment Details:\n"
            f"- {weather_str}\n"
            f"- {light_str}\n"
            f"- {entities_str}\n"
            f"- {blocks_str}"
        )
        
    return "\n\n".join(sections) if sections else ""
