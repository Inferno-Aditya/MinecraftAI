from pydantic import BaseModel
from typing import Dict, Any, Type, List
from .base import BaseTool, ToolResult

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

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> ToolResult:
        info = getattr(context, "player_info", None)
        held = getattr(info, "held_item", None) if info else None
        
        if not held or getattr(held, "item", "minecraft:air") == "minecraft:air" or getattr(held, "count", 0) == 0:
            return ToolResult(
                success=True,
                message="You are not holding any item.",
                data={
                    "item": "minecraft:air",
                    "count": 0,
                    "durability": 0,
                    "enchantments": {}
                },
                tool_name=self.name
            )
            
        data = {
            "item": held.item,
            "count": held.count,
            "durability": held.durability if held.durability is not None else 0,
            "enchantments": getattr(held, "enchantments", {}) or {}
        }

        ench_str = ""
        enchantments = data["enchantments"]
        if enchantments:
            ench_str = " (Enchantments: " + ", ".join(f"{k} {v}" for k, v in enchantments.items()) + ")"

        msg = f"Holding {data['count']}x {data['item']}{ench_str}."
        if data["durability"] > 0:
            msg += f" Durability: {data['durability']} remaining."

        return ToolResult(
            success=True,
            message=msg,
            data=data,
            tool_name=self.name
        )
