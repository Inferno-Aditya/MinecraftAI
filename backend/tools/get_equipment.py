from pydantic import BaseModel
from typing import Dict, Any, Type, List
from .base import BaseTool

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

class GetEquipmentInput(BaseModel):
    pass

class GetEquipmentTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_equipment"

    @property
    def description(self) -> str:
        return "Returns details of the player's equipped armor and offhand item: helmet, chestplate, leggings, boots, and offhand item."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return GetEquipmentInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "what armor am i wearing?",
            "check my equipment",
            "show my gear"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> Dict[str, Any]:
        eq = context.player_info.equipment
        slots = ["helmet", "chestplate", "leggings", "boots", "offhand"]
        
        data = {}
        msg_parts = []
        for slot in slots:
            item_val = getattr(eq, slot, None)
            if item_val and item_val.item != "minecraft:air" and item_val.count > 0:
                data[slot] = {
                    "item": item_val.item,
                    "count": item_val.count,
                    "durability": item_val.durability if item_val.durability is not None else 0,
                    "enchantments": item_val.enchantments
                }
                ench_str = ""
                if item_val.enchantments:
                    ench_str = " (" + ", ".join(f"{k} {v}" for k, v in item_val.enchantments.items()) + ")"
                msg_parts.append(f"{slot.capitalize()}: {item_val.item}{ench_str}")
            else:
                data[slot] = {
                    "item": "minecraft:air",
                    "count": 0,
                    "durability": 0,
                    "enchantments": {}
                }
                msg_parts.append(f"{slot.capitalize()}: None")

        msg = "Equipped Gear:\n" + "\n".join(msg_parts)

        return {
            "status": "success",
            "message": msg,
            "success": True,
            "data": data,
            "metadata": {}
        }
