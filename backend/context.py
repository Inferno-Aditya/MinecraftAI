from pydantic import BaseModel, Field, PrivateAttr, model_validator
from typing import List, Dict, Any, Optional

class InventorySlot(BaseModel):
    slot: int = Field(..., description="The inventory slot index (0-35).")
    item: str = Field(..., description="The registry ID of the item.")
    count: int = Field(..., description="The quantity of the item.")
    durability: Optional[int] = Field(None, description="The remaining durability of the item, if damageable.")
    enchantments: Dict[str, int] = Field(default_factory=dict, description="Map of enchantment name to level.")
    nbt: str = Field("", description="NBT tags summary or custom name.")

class EquipmentItem(BaseModel):
    item: str = Field(..., description="The registry ID of the item.")
    count: int = Field(..., description="The quantity of the item.")
    durability: Optional[int] = Field(None, description="The remaining durability of the item, if damageable.")
    enchantments: Dict[str, int] = Field(default_factory=dict, description="Map of enchantment name to level.")

class EquipmentSlots(BaseModel):
    helmet: Optional[EquipmentItem] = Field(None, description="Helmet slot item.")
    chestplate: Optional[EquipmentItem] = Field(None, description="Chestplate slot item.")
    leggings: Optional[EquipmentItem] = Field(None, description="Leggings slot item.")
    boots: Optional[EquipmentItem] = Field(None, description="Boots slot item.")
    offhand: Optional[EquipmentItem] = Field(None, description="Offhand slot item.")

class HeldItem(BaseModel):
    item: str = Field(..., description="The registry ID of the held item.")
    count: int = Field(..., description="The quantity of the held item.")
    durability: Optional[int] = Field(None, description="The remaining durability of the held item.")
    enchantments: Dict[str, int] = Field(default_factory=dict, description="Map of enchantment name to level.")

class PlayerInfo(BaseModel):
    name: str = Field(..., description="The username of the player.")
    uuid: str = Field("", description="The unique ID of the player.")
    x: float = Field(..., description="The X coordinate of the player.")
    y: float = Field(..., description="The Y coordinate of the player.")
    z: float = Field(..., description="The Z coordinate of the player.")
    yaw: float = Field(..., description="The horizontal orientation/rotation (yaw) of the player.")
    pitch: float = Field(..., description="The vertical orientation/rotation (pitch) of the player.")
    health: float = Field(..., description="The player's current health (max 20.0).")
    food: int = Field(..., description="The player's current food level (max 20).")
    saturation: float = Field(0.0, description="The player's current saturation level.")
    experience: float = Field(0.0, description="The player's experience progress (0.0 to 1.0).")
    level: int = Field(0, description="The player's experience level.")
    gamemode: str = Field(..., description="The player's game mode.")
    dimension: str = Field(..., description="The dimension name.")
    inventory: List[InventorySlot] = Field(default_factory=list, description="The player's inventory contents.")
    equipment: EquipmentSlots = Field(default_factory=EquipmentSlots, description="The player's equipped armor and offhand item.")
    held_item: Optional[HeldItem] = Field(None, description="The item currently held in the player's main hand.")

class WeatherInfo(BaseModel):
    rain: bool = Field(..., description="True if it is raining.")
    thunder: bool = Field(..., description="True if it is thundering.")
    clear: bool = Field(..., description="True if the weather is clear.")
    time_remaining: int = Field(..., description="Ticks remaining for the current weather pattern.")

class LightInfo(BaseModel):
    block: int = Field(..., description="Block light level (0-15).")
    sky: int = Field(..., description="Sky light level (0-15).")
    combined: int = Field(..., description="Combined light level (0-15).")

class BiomeInfo(BaseModel):
    name: str = Field(..., description="The registry ID of the biome.")
    temperature: float = Field(0.0, description="Temperature of the biome.")
    rainfall: float = Field(0.0, description="Rainfall of the biome.")
    category: str = Field("unknown", description="Category of the biome (e.g. forest, plains, ocean).")

class NearbyEntity(BaseModel):
    type: str = Field(..., description="The entity type (e.g. minecraft:zombie).")
    name: str = Field(..., description="The display name or custom name of the entity.")
    health: float = Field(..., description="Current health of the entity.")
    max_health: float = Field(..., description="Maximum health of the entity.")
    distance: float = Field(..., description="Distance from the player in blocks.")
    x: float = Field(..., description="X coordinate of the entity.")
    y: float = Field(..., description="Y coordinate of the entity.")
    z: float = Field(..., description="Z coordinate of the entity.")
    category: str = Field(..., description="Category: player, villager, hostile, passive, projectile, vehicle, or other.")

class FillerBlockSummary(BaseModel):
    nearest: Optional[List[int]] = Field(None, description="Relative coordinate [dx, dy, dz] of the nearest occurrence.")
    counts: Dict[str, int] = Field(default_factory=dict, description="Counts at different radius tiers (e.g. '8', '16', '32').")

class InterestingBlock(BaseModel):
    type: str = Field(..., description="The block type registry ID.")
    x: int = Field(..., description="Relative block coordinate dx.")
    y: int = Field(..., description="Relative block coordinate dy.")
    z: int = Field(..., description="Relative block coordinate dz.")

class NearbyBlock(BaseModel):
    type: str = Field(..., description="The block type registry ID.")
    count: int = Field(..., description="Total count within the radius.")
    nearest: Optional[List[int]] = Field(None, description="Relative or absolute coordinates [x, y, z] of the nearest occurrence.")

class TerrainStatistics(BaseModel):
    min_y: int = Field(..., description="Minimum Y level in the scanned area.")
    max_y: int = Field(..., description="Maximum Y level in the scanned area.")
    average_y: float = Field(..., description="Average Y level of the surface in the scanned area.")
    height_variation: int = Field(..., description="Difference between max and min Y levels.")

class AreaSummary(BaseModel):
    biome: str = Field(..., description="The biome where the player is located.")
    height_variation: int = Field(..., description="Difference between highest and lowest blocks.")
    stone_count: int = Field(..., description="Number of stone/deepslate blocks.")
    water_count: int = Field(..., description="Number of water blocks.")
    lava_count: int = Field(..., description="Number of lava blocks.")
    ore_counts: Dict[str, int] = Field(default_factory=dict, description="Counts of different ores detected.")
    tree_count: int = Field(..., description="Number of wood logs/leaves detected.")
    flower_count: int = Field(..., description="Number of flowers/vegetation detected.")
    building_blocks_count: int = Field(..., description="Number of building blocks detected.")
    air_count: int = Field(..., description="Number of air blocks.")
    terrain_statistics: TerrainStatistics = Field(..., description="Detailed terrain statistics.")

class NearbyBlocksSnapshot(BaseModel):
    filler_blocks: Dict[str, FillerBlockSummary] = Field(default_factory=dict, description="Filler block summaries.")
    interesting_blocks: List[InterestingBlock] = Field(default_factory=list, description="Interesting block lists.")

class EnvironmentSnapshot(BaseModel):
    weather: WeatherInfo = Field(..., description="Current weather info.")
    world_time: int = Field(..., description="World ticks time.")
    is_day: bool = Field(..., description="True if it is day.")
    is_night: bool = Field(..., description="True if it is night.")
    moon_phase: int = Field(..., description="Moon phase (0-7).")
    light_level: LightInfo = Field(..., description="Light level info.")
    biome: BiomeInfo = Field(..., description="Current biome info.")
    nearby_blocks: NearbyBlocksSnapshot = Field(default_factory=NearbyBlocksSnapshot, description="Scanned nearby blocks.")
    nearby_entities: List[NearbyEntity] = Field(default_factory=list, description="List of nearby entities.")

class PlayerContext(BaseModel):
    """
    Model representing the player's context in Minecraft.
    Refactored to separate PlayerInfo and EnvironmentSnapshot.
    Provides backward-compatible properties for existing Phase 3 logic.
    """
    player_info: PlayerInfo
    environment: EnvironmentSnapshot
    _cache: dict = PrivateAttr(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def assemble_context(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "player_info" not in data and "environment" not in data:
                # Flat format to nested format conversion (backward compatibility)
                player_info_fields = ["name", "uuid", "x", "y", "z", "yaw", "pitch", "health", "food", "saturation", "experience", "level", "gamemode", "dimension", "inventory", "equipment", "held_item"]
                player_info_data = {}
                for f in player_info_fields:
                    if f in data:
                        player_info_data[f] = data[f]
                
                # Check for nested keys under environment
                env_fields = ["weather", "world_time", "is_day", "is_night", "moon_phase", "light_level", "biome", "nearby_blocks", "nearby_entities"]
                env_data = {}
                for f in env_fields:
                    if f in data:
                        env_data[f] = data[f]
                
                # Special mapping for biome if it was a flat string
                if "biome" in data and isinstance(data["biome"], str):
                    env_data["biome"] = {"name": data["biome"]}
                
                # Defaults for nested models if missing
                if "weather" not in env_data:
                    env_data["weather"] = {"rain": False, "thunder": False, "clear": True, "time_remaining": 0}
                if "world_time" not in env_data:
                    env_data["world_time"] = data.get("world_time", 0)
                if "is_day" not in env_data:
                    env_data["is_day"] = True
                if "is_night" not in env_data:
                    env_data["is_night"] = False
                if "moon_phase" not in env_data:
                    env_data["moon_phase"] = 0
                if "light_level" not in env_data:
                    env_data["light_level"] = {"block": 0, "sky": 0, "combined": 0}
                if "biome" not in env_data:
                    env_data["biome"] = {"name": "unknown", "temperature": 0.0, "rainfall": 0.0, "category": "unknown"}
                
                # Wrap it up
                data = {
                    "player_info": player_info_data,
                    "environment": env_data
                }
        return data

    @property
    def name(self) -> str:
        return self.player_info.name

    @property
    def x(self) -> float:
        return self.player_info.x

    @property
    def y(self) -> float:
        return self.player_info.y

    @property
    def z(self) -> float:
        return self.player_info.z

    @property
    def yaw(self) -> float:
        return self.player_info.yaw

    @property
    def pitch(self) -> float:
        return self.player_info.pitch

    @property
    def dimension(self) -> str:
        return self.player_info.dimension

    @property
    def gamemode(self) -> str:
        return self.player_info.gamemode

    @property
    def health(self) -> float:
        return self.player_info.health

    @property
    def food(self) -> int:
        return self.player_info.food

    @property
    def world_time(self) -> int:
        return self.environment.world_time

    @property
    def biome(self) -> str:
        return self.environment.biome.name

    def model_copy(self, *, update: Optional[Dict[str, Any]] = None, deep: bool = False) -> "PlayerContext":
        if update:
            player_info_fields = ["name", "uuid", "x", "y", "z", "yaw", "pitch", "health", "food", "saturation", "experience", "level", "gamemode", "dimension", "inventory", "equipment", "held_item"]
            player_update = {}
            env_update = {}
            # Work on a copy of keys to avoid modification during iteration
            for k, v in list(update.items()):
                if k in player_info_fields:
                    player_update[k] = v
                    del update[k]
                elif k in ["weather", "world_time", "is_day", "is_night", "moon_phase", "light_level", "biome", "nearby_blocks", "nearby_entities"]:
                    env_update[k] = v
                    del update[k]
                elif k == "biome" and isinstance(v, str):
                    env_update["biome"] = {"name": v}
                    del update[k]
            
            copied = super().model_copy(update=update, deep=deep)
            if player_update:
                copied.player_info = copied.player_info.model_copy(update=player_update, deep=deep)
            if env_update:
                copied.environment = copied.environment.model_copy(update=env_update, deep=deep)
            return copied
        return super().model_copy(deep=deep)

