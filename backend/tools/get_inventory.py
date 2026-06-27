from pydantic import BaseModel, Field
from typing import Dict, Any, Type, List, Optional
from .base import BaseTool, ToolResult

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

class GetInventoryInput(BaseModel):
    search: Optional[str] = Field(None, description="Optional search term to filter inventory items (partial match on name/id).")

class GetInventoryTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_inventory"

    @property
    def description(self) -> str:
        return "Returns all player inventory items. Supports searching by item name or partial name."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return GetInventoryInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "what's in my inventory?",
            "check if i have wood",
            "do i have any cobblestone?",
            "search inventory for torch"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> ToolResult:
        search_query = arguments.get("search")
        if search_query:
            search_query = search_query.strip().lower()

        info = getattr(context, "player_info", None)
        inventory_list = getattr(info, "inventory", []) or []
        
        # 1. Classify/filter items and calculate counts
        filtered_slots = []
        summary_counts = {}

        for slot in inventory_list:
            if not slot or getattr(slot, "item", "minecraft:air") == "minecraft:air" or getattr(slot, "count", 0) <= 0:
                continue
                
            item_id = slot.item.lower()
            # If search query is specified, check both item id and its NBT custom display name
            matches = True
            if search_query:
                display_name = getattr(slot, "nbt", "").lower() if getattr(slot, "nbt", None) else ""
                matches = (search_query in item_id) or (search_query in display_name)
                
            if matches:
                filtered_slots.append(slot.model_dump())
                summary_counts[slot.item] = summary_counts.get(slot.item, 0) + slot.count

        # 2. Form organized summary
        summary_str_list = [f"{item}: {count}" for item, count in sorted(summary_counts.items())]
        if summary_str_list:
            summary_msg = "Inventory Summary:\n" + "\n".join(f"- {s}" for s in summary_str_list)
        else:
            summary_msg = "Inventory is empty" if not search_query else f"No items found matching '{search_query}'."

        return ToolResult(
            success=True,
            message=summary_msg,
            data={
                "slots": filtered_slots,
                "summary": summary_counts
            },
            tool_name=self.name
        )
