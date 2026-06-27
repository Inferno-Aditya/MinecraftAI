from pydantic import BaseModel
from typing import Dict, Any, Type, List
from .base import BaseTool, ToolResult

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

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> ToolResult:
        info = getattr(context, "player_info", None)
        eq = getattr(info, "equipment", None) if info else None
        slots = ["helmet", "chestplate", "leggings", "boots", "offhand"]
        
        data = {}
        msg_parts = []
        for slot in slots:
            item_val = getattr(eq, slot, None) if eq else None
            if item_val and getattr(item_val, "item", "minecraft:air") != "minecraft:air" and getattr(item_val, "count", 0) > 0:
                data[slot] = {
                    "item": item_val.item,
                    "count": item_val.count,
                    "durability": item_val.durability if item_val.durability is not None else 0,
                    "enchantments": getattr(item_val, "enchantments", {}) or {}
                }
                ench_str = ""
                ench = data[slot]["enchantments"]
                if ench:
                    ench_str = " (" + ", ".join(f"{k} {v}" for k, v in ench.items()) + ")"
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

        return ToolResult(
            success=True,
            message=msg,
            data=data,
            tool_name=self.name
        )
