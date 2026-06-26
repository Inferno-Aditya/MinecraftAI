from pydantic import BaseModel
from typing import Dict, Any, Type, List
from .base import BaseTool

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

class GetHeldItemInput(BaseModel):
    pass

class GetHeldItemTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_held_item"

    @property
    def description(self) -> str:
        return "Returns details of the item currently held in the player's main hand: item type, count, durability, and enchantments."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return GetHeldItemInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "what am i holding?",
            "check my held item",
            "what is in my hand?"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> Dict[str, Any]:
        held = context.player_info.held_item
        if not held or held.item == "minecraft:air" or held.count == 0:
            return {
                "status": "success",
                "message": "You are not holding any item.",
                "success": True,
                "data": {
                    "item": "minecraft:air",
                    "count": 0,
                    "durability": 0,
                    "enchantments": {}
                },
                "metadata": {}
            }
            
        data = {
            "item": held.item,
            "count": held.count,
            "durability": held.durability if held.durability is not None else 0,
            "enchantments": held.enchantments
        }

        ench_str = ""
        if held.enchantments:
            ench_str = " (Enchantments: " + ", ".join(f"{k} {v}" for k, v in held.enchantments.items()) + ")"

        msg = f"Holding {held.count}x {held.item}{ench_str}."
        if held.durability is not None and held.durability > 0:
            msg += f" Durability: {held.durability} remaining."

        return {
            "status": "success",
            "message": msg,
            "success": True,
            "data": data,
            "metadata": {}
        }
