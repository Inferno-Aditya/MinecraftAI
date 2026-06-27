from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import Dict, Any, Type, List, Optional

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

class ToolResult(BaseModel):
    """
    Standardized return format for all Minecraft tools.
    Supports dictionary emulation for backward compatibility.
    """
    success: bool = Field(..., description="True if the tool executed successfully, False otherwise.")
    message: str = Field(..., description="A friendly natural language message summarizing the result.")
    data: Dict[str, Any] = Field(default_factory=dict, description="Structured query results or context details.")
    error: Optional[str] = Field(None, description="The error message or exception details if success is False.")
    execution_time_ms: Optional[float] = Field(None, description="Time taken to execute the tool in milliseconds.")
    tool_name: str = Field(..., description="The canonical name of the tool.")

    def __getitem__(self, item: str) -> Any:
        # Backward compatibility translation: status maps to success boolean as "success" or "error"
        if item == "status":
            return "success" if self.success else "error"
        if hasattr(self, item):
            return getattr(self, item)
        # Transparent fallback to data dictionary keys
        if item in self.data:
            return self.data[item]
        raise KeyError(item)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

class BaseTool(ABC):
    """
    Abstract base class for all tools in the Minecraft AI Assistant tool registry.
    Each tool must implement these properties and the execute method.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """The unique name of the tool used by the planner and client."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """A brief description of what the tool does."""
        pass

    @property
    @abstractmethod
    def input_schema(self) -> Type[BaseModel]:
        """Pydantic model representing the expected arguments for the tool."""
        pass

    @property
    @abstractmethod
    def usage_examples(self) -> List[str]:
        """A list of typical natural language phrases that trigger this tool."""
        pass

    @abstractmethod
    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> ToolResult:
        """
        Executes the tool with the provided player context and validated arguments.
        
        :param context: PlayerContext object containing current game and player state.
        :param arguments: Dictionary of arguments validated against input_schema.
        :return: A ToolResult representing the standardized tool outcome.
        """
        pass
