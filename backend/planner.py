import os
import json
import datetime
from pydantic import BaseModel, Field
from typing import List
from enum import Enum

try:
    from context import PlayerContext
except ImportError:
    from .context import PlayerContext

try:
    from config import load_config
except ImportError:
    from .config import load_config

try:
    from resource_manager import execute_llm_request_with_rate_limits
except ImportError:
    from .resource_manager import execute_llm_request_with_rate_limits

try:
    from memory import get_memory_summary
except ImportError:
    from .memory import get_memory_summary


class ResponseStrategy(str, Enum):
    KNOWLEDGE = "KNOWLEDGE"
    TOOLS = "TOOLS"
    HYBRID = "HYBRID"


class ToolCall(BaseModel):
    """
    Model representing a planned tool execution call.
    """
    tool: str = Field(..., description="The name of the tool to be executed.")
    arguments: dict = Field(..., description="The dictionary of arguments to pass to the tool.")


class PlannerResult(BaseModel):
    """
    Result returned by the LLM Planner.
    Encapsulates either a conversational reply or a list of tool calls to execute.
    """
    reply: str = Field(default="", description="Conversational reply when no tools are planned.")
    tool_calls: List[ToolCall] = Field(default_factory=list, description="List of tool calls to execute.")
    response_strategy: ResponseStrategy = Field(
        default=ResponseStrategy.TOOLS,
        description="The strategy to handle this query (KNOWLEDGE, TOOLS, or HYBRID)."
    )

    # Backwards compatibility methods to allow treating PlannerResult as a list of ToolCalls
    def __len__(self) -> int:
        return len(self.tool_calls)

    def __getitem__(self, index):
        return self.tool_calls[index]

    def __iter__(self):
        return iter(self.tool_calls)


def get_tool_definitions() -> str:
    """
    Iterates over all registered tools in the ToolRegistry and
    serializes their names, descriptions, input schemas, and usage examples.
    """
    try:
        from tools.registry import registry
    except ImportError:
        from .tools.registry import registry

    tools = registry.list_tools()
    defs = []
    for tool_name, tool in tools.items():
        # Extract the JSON schema for validation and prompt injection
        schema = tool.input_schema.model_json_schema()
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        # Format properties cleanly for LLM readability
        clean_props = {}
        for prop_name, prop_info in properties.items():
            clean_props[prop_name] = {
                "type": prop_info.get("type", "unknown"),
                "description": prop_info.get("description", "")
            }

        examples_str = "\n".join(f"  - \"{ex}\"" for ex in tool.usage_examples)

        tool_def = (
            f"Tool: {tool.name}\n"
            f"Description: {tool.description}\n"
            f"Arguments Schema:\n{json.dumps(clean_props, indent=2)}\n"
            f"Required Arguments: {required}\n"
            f"Usage Examples:\n{examples_str}"
        )
        defs.append(tool_def)

    return "\n\n---\n\n".join(defs)


def build_system_prompt() -> str:
    """
    Builds the structured system prompt dynamically injecting available tools.
    """
    tool_defs = get_tool_definitions()
    system_prompt = (
        "You are both a Minecraft expert and a planning engine for an AI Minecraft assistant.\n"
        "Your role is to classify every user query into one of three response strategies and plan tool calls if necessary.\n"
        "Only return valid JSON.\n"
        "Never refuse a question or say you are 'only a planning engine'. Answer knowledge questions directly using your extensive Minecraft expertise.\n\n"
        "Response JSON Schema:\n"
        "{\n"
        "  \"response_strategy\": \"KNOWLEDGE | TOOLS | HYBRID\",\n"
        "  \"reply\": \"conversational message to the player (required for KNOWLEDGE; empty string for TOOLS and HYBRID)\",\n"
        "  \"tool_calls\": [\n"
        "    {\n"
        "      \"tool\": \"tool_name\",\n"
        "      \"arguments\": { ... }\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Instructions:\n"
        "1. Classify the user query into one of these strategies:\n"
        "   - \"KNOWLEDGE\": The question can be answered entirely using your Minecraft knowledge (e.g., combat mechanics, critical hits, crafting recipes, redstone, brewing, enchantments, game rules, updates). Set 'tool_calls' to [] and write the full expert answer directly in the 'reply' field.\n"
        "   - \"TOOLS\": The question is a direct query about the player's current world state (e.g., coordinates, health, inventory lookup, searching blocks/entities). Set 'tool_calls' to the required tool(s) in order of execution, set 'reply' to \"\", and set 'response_strategy' to \"TOOLS\".\n"
        "   - \"HYBRID\": The question requires both current game context and Minecraft knowledge synthesis (e.g., 'Can I craft a shield?', 'Can I survive the night?', 'Is my sword worth enchanting?'). Set 'tool_calls' to the required tool(s) to gather current state, set 'reply' to \"\", and set 'response_strategy' to \"HYBRID\".\n"
        "2. Do not invent tools. Only use tools listed in the 'Available Tools' section.\n"
        "3. Validate that arguments match the tool's schema exactly.\n\n"
        "Classification Examples:\n"
        "Example 1 (KNOWLEDGE):\n"
        "  User: 'How do critical hits work?'\n"
        "  JSON:\n"
        "  {\n"
        "    \"response_strategy\": \"KNOWLEDGE\",\n"
        "    \"reply\": \"Critical hits are dealt when a player attacks while falling. They deal 150% of the weapon's base damage...\",\n"
        "    \"tool_calls\": []\n"
        "  }\n\n"
        "Example 2 (TOOLS):\n"
        "  User: 'What biome am I in?'\n"
        "  JSON:\n"
        "  {\n"
        "    \"response_strategy\": \"TOOLS\",\n"
        "    \"reply\": \"\",\n"
        "    \"tool_calls\": [{\"tool\": \"get_biome\", \"arguments\": {}}]\n"
        "  }\n\n"
        "Example 3 (HYBRID):\n"
        "  User: 'Can I craft a shield?'\n"
        "  JSON:\n"
        "  {\n"
        "    \"response_strategy\": \"HYBRID\",\n"
        "    \"reply\": \"\",\n"
        "    \"tool_calls\": [{\"tool\": \"get_inventory\", \"arguments\": {}}]\n"
        "  }\n\n"
        "Available Tools:\n"
        f"{tool_defs}"
    )
    return system_prompt


def build_user_prompt(message: str, player_context: PlayerContext) -> str:
    """
    Builds the user prompt injecting PlayerContext and memory summaries.
    """
    memory_summary = get_memory_summary()
    user_prompt = (
        f"Player Name: {player_context.name}\n"
        f"Current Location: X={player_context.x:.1f}, Y={player_context.y:.1f}, Z={player_context.z:.1f}\n"
        f"Dimension: {player_context.dimension}\n"
        f"Gamemode: {player_context.gamemode}\n"
        f"Health: {player_context.health}/20\n"
        f"Food Level: {player_context.food}/20\n"
        f"Biome: {player_context.biome}\n"
        f"World Time: {player_context.world_time} ticks\n\n"
        f"Memory Summary:\n{memory_summary}\n\n"
        f"User Message: {message}"
    )
    return user_prompt


def log_prompt_debug(system_prompt: str, user_prompt: str) -> None:
    """
    Logs the generated prompts to logs/prompts/ for debug inspection.
    """
    try:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        prompts_dir = os.path.join(base_dir, "logs", "prompts")
        os.makedirs(prompts_dir, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = os.path.join(prompts_dir, f"{timestamp}.txt")
        
        content = (
            f"=== SYSTEM PROMPT ===\n{system_prompt}\n\n"
            f"=== USER PROMPT ===\n{user_prompt}\n"
        )
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        pass  # Gracefully ignore any logging IO issues to prevent crashes


def parse_and_validate(cleaned_text: str) -> PlannerResult:
    """
    Parses a cleaned LLM JSON response and validates all tool names and schemas.
    """
    try:
        data = json.loads(cleaned_text)
    except Exception as e:
        raise ValueError(f"Invalid JSON syntax: {str(e)}")

    if not isinstance(data, dict):
        raise ValueError("Root of JSON response must be an object.")

    reply = data.get("reply", "")
    if not isinstance(reply, str):
        raise ValueError("field 'reply' must be a string.")

    tool_calls_raw = data.get("tool_calls", [])
    if not isinstance(tool_calls_raw, list):
        raise ValueError("field 'tool_calls' must be a list.")

    response_strategy_str = data.get("response_strategy", None)
    if response_strategy_str is None:
        if tool_calls_raw:
            response_strategy = ResponseStrategy.TOOLS
        else:
            response_strategy = ResponseStrategy.KNOWLEDGE
    else:
        if not isinstance(response_strategy_str, str):
            raise ValueError("field 'response_strategy' must be a string.")
        try:
            response_strategy = ResponseStrategy(response_strategy_str.upper())
        except ValueError:
            raise ValueError(f"field 'response_strategy' must be one of: KNOWLEDGE, TOOLS, HYBRID. Got: '{response_strategy_str}'")

    validated_calls = []
    try:
        from tools.registry import registry
    except ImportError:
        from .tools.registry import registry

    for idx, tc in enumerate(tool_calls_raw):
        if not isinstance(tc, dict):
            raise ValueError(f"tool_calls[{idx}] must be a JSON object.")
        if "tool" not in tc or "arguments" not in tc:
            raise ValueError(f"tool_calls[{idx}] must contain 'tool' and 'arguments' keys.")
        
        tool_name = tc["tool"]
        arguments = tc["arguments"]
        
        if not isinstance(tool_name, str):
            raise ValueError(f"tool_calls[{idx}].tool must be a string.")
        if not isinstance(arguments, dict):
            raise ValueError(f"tool_calls[{idx}].arguments must be a JSON object.")

        # Resolve tool
        tool = registry.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' is not registered in the registry.")

        # Validate arguments
        try:
            tool.input_schema(**arguments)
        except Exception as schema_err:
            raise ValueError(f"Validation failed for tool '{tool_name}' arguments: {str(schema_err)}")

        validated_calls.append(ToolCall(tool=tool_name, arguments=arguments))

    return PlannerResult(reply=reply, tool_calls=validated_calls, response_strategy=response_strategy)


def plan(message: str, player_context: PlayerContext) -> PlannerResult:
    """
    Decides which tool(s) should run based on the user's message, player context, and memory.
    Uses the configured LLM provider to return a PlannerResult.
    """
    config = load_config()
    provider_name = config.get("provider", "gemini")
    model_name = config.get("model", "gemini-2.5-flash")
    
    try:
        from main import log_message
    except ImportError:
        def log_message(level, msg):
            print(f"[{level}] {msg}")

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(message, player_context)
    
    if config.get("enable_prompt_logging", True):
        log_prompt_debug(system_prompt, user_prompt)

    log_message("INFO", f"Planning via provider '{provider_name}' using model '{model_name}'")
    
    try:
        response_text = execute_llm_request_with_rate_limits(
            provider_name, model_name, system_prompt, user_prompt, request_type="plan"
        )
    except Exception as e:
        return PlannerResult(
            reply=f"I couldn't reach my planner engine. Error: {str(e)}",
            tool_calls=[]
        )

    # Clean markdown block markers if any
    def clean_markdown_json(text: str) -> str:
        t = text.strip()
        if t.startswith("```json"):
            t = t[7:]
        elif t.startswith("```"):
            t = t[3:]
        if t.endswith("```"):
            t = t[:-3]
        return t.strip()

    cleaned_response = clean_markdown_json(response_text)
    log_message("DEBUG", f"LLM Raw cleaned response: {cleaned_response}")

    try:
        return parse_and_validate(cleaned_response)
    except Exception as parse_err:
        log_message("WARNING", f"Initial LLM response parsing/validation failed: {str(parse_err)}")
        
        # Retry exactly once with correction prompt
        correction_user_prompt = (
            f"Your previous response failed parsing/validation with error:\n{str(parse_err)}\n\n"
            f"Here is your previous response:\n{response_text}\n\n"
            f"Please correct it and return ONLY valid JSON matching the schema."
        )
        
        log_message("INFO", "Retrying LLM generation with auto-correction prompt...")
        try:
            retry_response = execute_llm_request_with_rate_limits(
                provider_name, model_name, system_prompt, correction_user_prompt, request_type="plan"
            )
            cleaned_retry = clean_markdown_json(retry_response)
            log_message("DEBUG", f"Cleaned retry response: {cleaned_retry}")
            
            return parse_and_validate(cleaned_retry)
        except Exception as retry_err:
            log_message("ERROR", f"Correction retry failed or timed out: {str(retry_err)}")
            return PlannerResult(
                reply="I couldn't understand the planner response.",
                tool_calls=[]
            )
