from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Type, List
from .base import BaseTool

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

try:
    from memory import load_memory, save_memory
except ImportError:
    from ..memory import load_memory, save_memory

class SaveNoteInput(BaseModel):
    key: str = Field(..., description="The key or topic of the note.")
    value: str = Field(..., description="The text content to store.")

    @field_validator('key')
    @classmethod
    def validate_key(cls, v: str) -> str:
        # Normalize the key by replacing spaces with underscores and stripping whitespace
        v_normalized = v.strip().replace(" ", "_")
        if not v_normalized:
            raise ValueError("Note key cannot be empty or only whitespace.")
        return v_normalized

    @field_validator('value')
    @classmethod
    def validate_value(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Note value cannot be empty or only whitespace.")
        return v_stripped

class SaveNoteTool(BaseTool):
    @property
    def name(self) -> str:
        return "save_note"

    @property
    def description(self) -> str:
        return "Stores an arbitrary note under a key in the persistent notes memory."

    @property
    def input_schema(self) -> Type[BaseModel]:
        return SaveNoteInput

    @property
    def usage_examples(self) -> List[str]:
        return [
            "remember my favorite block is spruce",
            "remember that my dog is named buddy",
            "save note favorite_color as blue"
        ]

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stores the note.
        Replaces any existing note with the same key. Key is normalized (spaces replaced by underscores).
        """
        key = arguments["key"]
        value = arguments["value"]
        
        memory = load_memory()
        memory["notes"][key] = value
        save_memory(memory)
        
        return {
            "status": "success",
            "message": f"Saved note for '{key}': '{value}'.",
            "data": {"key": key, "value": value}
        }
