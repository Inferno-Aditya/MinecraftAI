from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Dict, Any, Type, List

try:
    from context import PlayerContext
except ImportError:
    from ..context import PlayerContext

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
    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the tool with the provided player context and validated arguments.
        
        :param context: PlayerContext object containing current game and player state.
        :param arguments: Dictionary of arguments validated against input_schema.
        :return: A dictionary representing the structured success or error response.
                 Must contain 'status' (success/error), 'message' (str), and optional 'data'.
        """
        pass
