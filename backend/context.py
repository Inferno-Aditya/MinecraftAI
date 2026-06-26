from pydantic import BaseModel, Field

class PlayerContext(BaseModel):
    """
    Model representing the player's context in Minecraft.
    This model captures information sent by the Fabric mod, such as player position,
    dimension, biome, health, food, and other game state attributes.
    """
    name: str = Field(..., description="The username of the player.")
    x: float = Field(..., description="The X coordinate of the player.")
    y: float = Field(..., description="The Y coordinate of the player.")
    z: float = Field(..., description="The Z coordinate of the player.")
    yaw: float = Field(..., description="The horizontal orientation/rotation (yaw) of the player.")
    pitch: float = Field(..., description="The vertical orientation/rotation (pitch) of the player.")
    dimension: str = Field(..., description="The dimension name (e.g. minecraft:overworld).")
    gamemode: str = Field(..., description="The player's game mode (e.g. survival, creative).")
    health: float = Field(..., description="The player's current health (max 20.0).")
    food: int = Field(..., description="The player's current food level (max 20).")
    world_time: int = Field(..., description="The current world time in ticks.")
    biome: str = Field("unknown", description="The biome where the player is currently located.")
