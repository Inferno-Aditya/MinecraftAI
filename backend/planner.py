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


def validate_and_reason_decision(
    result: PlannerResult,
    intent: str,
    classification: dict,
    ctx,
    query: str,
    strategy_source: str = "LLM"
) -> None:
    try:
        from main import log_message
    except ImportError:
        def log_message(level, msg):
            print(f"[{level}] {msg}")

    selected_strategy = result.response_strategy
    chosen_tools = [tc.tool for tc in result.tool_calls]
    req_tools = classification.get("required_tools", [])
    
    # 1. Decision Reasoning
    reason_map = {
        "ENVIRONMENT": "Environment query with nearby-entity, block, or biome detection.",
        "PLAYER": "Player query to inspect stats, equipment, offhand, or inventory.",
        "MEMORY": "Memory query to save/retrieve waypoints or coordinates.",
        "HYBRID": "Hybrid query requiring both environment context and knowledge synthesis.",
        "KNOWLEDGE": "Knowledge query answered using expert Minecraft knowledge.",
        "TOOL": "Direct tool execution request."
    }
    decision_reason = reason_map.get(intent, "General query handling.")
    
    # 2. Strategy Consistency Validation
    intent_to_expected_strategy = {
        "ENVIRONMENT": [ResponseStrategy.TOOLS, ResponseStrategy.HYBRID],
        "PLAYER": [ResponseStrategy.TOOLS],
        "MEMORY": [ResponseStrategy.TOOLS],
        "HYBRID": [ResponseStrategy.HYBRID],
        "KNOWLEDGE": [ResponseStrategy.KNOWLEDGE],
        "TOOL": [ResponseStrategy.TOOLS, ResponseStrategy.HYBRID]
    }
    
    expected_strategies = intent_to_expected_strategy.get(intent, [])
    is_override = False
    override_reason = ""
    strategy_validation = "Passed"
    
    if expected_strategies and selected_strategy not in expected_strategies:
        is_override = True
        strategy_validation = "Failed"
        override_reason = (
            f"LLM ResponseStrategy '{selected_strategy.value}' deviated from classified Intent '{intent}' "
            f"(expected one of {[s.value for s in expected_strategies]})"
        )
        
        # Log override
        log_message("WARNING", "=== PLANNER OVERRIDE DETECTED ===")
        log_message("WARNING", f"Query: '{query}'")
        log_message("WARNING", f"Original Intent: {intent}")
        highest_score = classification.get("diagnostics", {}).get("intent_confidence_scores", {}).get(intent, 0.0)
        log_message("WARNING", f"Original Confidence: {highest_score:.2f}")
        log_message("WARNING", f"Selected Strategy: {selected_strategy.value}")
        log_message("WARNING", f"Override Reason: {override_reason}")
        log_message("WARNING", "=================================")

    # 3. Decision Reasoning logging
    reasoning_payload = {
        "strategy_source": strategy_source,
        "strategy_validation": strategy_validation,
        "override_applied": "Yes" if is_override else "No",
        "decision_reason": decision_reason
    }

    # 4. Planner Decision Validation Layer / Consistency Checks
    dev_warnings = []
    
    # Check 1: ENVIRONMENT intent -> KNOWLEDGE strategy
    if intent == "ENVIRONMENT" and selected_strategy == ResponseStrategy.KNOWLEDGE:
        dev_warnings.append("ENVIRONMENT intent resolved to KNOWLEDGE strategy")
        
    # Check 2: PLAYER intent -> KNOWLEDGE strategy
    if intent == "PLAYER" and selected_strategy == ResponseStrategy.KNOWLEDGE:
        dev_warnings.append("PLAYER intent resolved to KNOWLEDGE strategy")
        
    # Check 3: Candidate tools exist but none selected by the planner
    if req_tools and len(result.tool_calls) == 0:
        dev_warnings.append("Candidate tools exist but none were selected by the planner")
        
    # Check 4: High confidence intent with zero execution
    highest_score = classification.get("diagnostics", {}).get("intent_confidence_scores", {}).get(intent, 0.0)
    if highest_score >= 0.70 and intent != "KNOWLEDGE" and len(result.tool_calls) == 0:
        dev_warnings.append("High confidence intent with zero tool execution")
        
    # Check 5: Tool ranking exists but planner rejects every tool
    if req_tools and not any(t in req_tools for t in chosen_tools):
        dev_warnings.append("Tool ranking exists but planner rejected every candidate tool")

    # Contradiction warning check before tool execution
    if is_override or dev_warnings:
        log_message("WARNING", f"[Planner Decision Validation Layer] Contradiction warning emitted before execution for query: '{query}'")
        for warning in dev_warnings:
            log_message("WARNING", f"  - Warning: {warning}")

    if ctx:
        ctx.decision_reasoning = reasoning_payload
        if is_override:
            ctx.planner_override = {
                "original_intent": intent,
                "original_confidence": highest_score,
                "selected_strategy": selected_strategy.value,
                "override_reason": override_reason
            }
        ctx.dev_warnings = dev_warnings


def plan(message: str, player_context: PlayerContext, ctx=None) -> PlannerResult:
    """
    Decides which tool(s) should run based on the user's message, player context, and memory.
    Uses the configured LLM provider to return a PlannerResult.

    Args:
        message:        The user's chat message.
        player_context: The player's current game state.
        ctx:            Optional RequestContext for end-to-end tracing.
    """
    try:
        from model_manager import model_manager
    except ImportError:
        from .model_manager import model_manager

    config = load_config()
    model_profile = model_manager.get_active_model_profile()
    provider_name = model_profile.provider
    model_name = model_profile.model_id

    try:
        from main import log_message
    except ImportError:
        def log_message(level, msg):
            print(f"[{level}] {msg}")

    req_id = ctx.prefix() if ctx else ""

    # Update context with resolved provider/model
    if ctx:
        ctx.provider_name = provider_name
        ctx.model_name = model_name

    # 1. Baseline calculations
    baseline_system = build_system_prompt()
    baseline_user = build_user_prompt(message, player_context)
    from resource_manager import estimate_tokens
    baseline_tokens = estimate_tokens(baseline_system) + estimate_tokens(baseline_user)

    # 2. Optimized Pipeline
    try:
        from intent_classifier import IntentClassifier
        from context_builder import build_context
        from memory_retriever import retrieve_relevant_memory
        from tool_selector import select_tool_definitions
        from prompt_builder import PromptBuilder, PromptProfile
    except ImportError:
        from .intent_classifier import IntentClassifier
        from .context_builder import build_context
        from .memory_retriever import retrieve_relevant_memory
        from .tool_selector import select_tool_definitions
        from .prompt_builder import PromptBuilder, PromptProfile

    # Step A: Classify Intent
    if ctx:
        ctx.begin_stage("planner:classify_intent")
    classifier = IntentClassifier()
    classification = classifier.classify(message)
    intent = classification["intent"]
    req_context = classification["required_context"]
    req_memory = classification["required_memory"]
    req_tools = classification["required_tools"]
    if ctx:
        ctx.end_stage()
        
    # Store classification details in RequestContext
    if ctx:
        ctx.intent = intent
        ctx.candidate_tools = req_tools
        ctx.tool_confidences = classification.get("tool_confidences", {})
        
        diagnostics = classification.get("diagnostics", {})
        ctx.detected_mobs = diagnostics.get("detected_mobs", [])
        ctx.detected_structures = diagnostics.get("detected_structures", [])
        ctx.detected_blocks = diagnostics.get("detected_blocks", [])
        ctx.detected_items = diagnostics.get("detected_items", [])
        ctx.detected_spatial_keywords = diagnostics.get("detected_spatial_keywords", [])
        ctx.detected_action_verbs = diagnostics.get("detected_action_verbs", [])
        ctx.intent_confidence_scores = diagnostics.get("intent_confidence_scores", {})
        ctx.candidate_tool_ranking = diagnostics.get("candidate_tool_ranking", [])
        ctx.is_uncertain = diagnostics.get("is_uncertain", False)
        ctx.original_intent = diagnostics.get("original_intent")
        ctx.contributing_factors = diagnostics.get("contributing_factors", {})
        
        # Populate Prompt Injection Summary based on classifications (before final synthesis)
        ctx.prompt_sections_injected = {
            "Player Context": "player_context" in req_context,
            "World Context": "environment_snapshot" in req_context,
            "Nearby Entities": "environment_snapshot" in req_context and len(getattr(getattr(player_context, "environment", None), "nearby_entities", [])) > 0,
            "Nearby Blocks": "environment_snapshot" in req_context,
            "Memory": bool(req_memory),
            "Tool Definitions": bool(req_tools),
            "Tool Results": False
        }
        
        # Initialize execution verification defaults
        ctx.execution_verification = {
            "tool_execution_success": {},
            "valid_tool_result": {},
            "accepted_by_prompt_builder": "N/A",
            "prompt_section_generated": "N/A",
            "provider_received_section": "N/A",
            "verification_status": "pending",
            "failure_reason": None
        }

    # Step B: Build Context
    if ctx:
        ctx.begin_stage("planner:build_context")
    context_text = build_context(player_context, req_context)
    if ctx:
        ctx.end_stage()

    # Step C: Retrieve Memory
    if ctx:
        ctx.begin_stage("planner:retrieve_memory")
    memory_text = retrieve_relevant_memory(message, req_memory)
    if ctx:
        ctx.end_stage()

    # Step D: Select Tool Definitions
    if ctx:
        ctx.begin_stage("planner:select_tools")
    tool_defs = select_tool_definitions(req_tools)
    if ctx:
        ctx.end_stage()

    # Step E: Construct Optimized System & User Prompts
    system_instructions = (
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
        "  }\n"
    )

    if ctx:
        ctx.begin_stage("planner:build_prompt")
    system_prompt, user_prompt = PromptBuilder.build_planner_prompt(
        system_instructions, context_text, memory_text, tool_defs, message
    )

    # Step F: Generate Prompt Profile
    prompt_profile = PromptProfile.calculate(
        system_instructions=system_instructions,
        context_text=context_text,
        memory_text=memory_text,
        tool_defs=tool_defs,
        user_message=message,
        actual_system_prompt=system_prompt,
        actual_user_prompt=user_prompt,
        baseline_tokens=baseline_tokens
    )
    if ctx:
        ctx.end_stage()
    
    if config.get("enable_prompt_logging", True):
        log_prompt_debug(system_prompt, user_prompt)

    log_message("INFO", f"{req_id} Planning via provider='{provider_name}' model='{model_name}' intent={intent} elapsed={round(ctx.elapsed_seconds() * 1000) if ctx else 0}ms")

    if ctx:
        ctx.begin_stage("planner:llm_call")
    try:
        response_text = execute_llm_request_with_rate_limits(
            provider_name, model_name, system_prompt, user_prompt,
            request_type="plan", prompt_profile=prompt_profile,
            model_profile=model_profile, ctx=ctx
        )
    except Exception as e:
        if ctx:
            ctx.end_stage(error=str(e))
            ctx.chosen_tools = []
            ctx.rejected_tools = list(ctx.candidate_tools) if hasattr(ctx, "candidate_tools") else []
            ctx.rejection_reasons = {t: f"Planner execution failed with exception: {type(e).__name__}" for t in ctx.rejected_tools}
        result = PlannerResult(
            reply=f"I couldn't reach my planner engine. Error: {type(e).__name__}: {e}",
            tool_calls=[]
        )
        validate_and_reason_decision(result, intent, classification, ctx, message, "Fallback")
        return result
    if ctx:
        ctx.end_stage()

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
    log_message("DEBUG", f"{req_id} LLM raw cleaned response: {cleaned_response[:300]}{'...' if len(cleaned_response) > 300 else ''}")

    if ctx:
        ctx.begin_stage("planner:parse_validate")
    try:
        result = parse_and_validate(cleaned_response)
        if ctx:
            ctx.end_stage()
            ctx.plan_strategy = result.response_strategy.value
            ctx.chosen_tools = [tc.tool for tc in result.tool_calls]
            ctx.rejected_tools = [t for t in ctx.candidate_tools if t not in ctx.chosen_tools]
            ctx.rejection_reasons = {t: "Not selected by the planner for this query." for t in ctx.rejected_tools}
        validate_and_reason_decision(result, intent, classification, ctx, message, "LLM")
        return result
    except Exception as parse_err:
        if ctx:
            ctx.end_stage(error=str(parse_err))
        log_message("WARNING", f"{req_id} Initial LLM response parsing/validation failed: {str(parse_err)}")

        # Retry exactly once with correction prompt – only if we still have time budget
        correction_user_prompt = (
            f"Your previous response failed parsing/validation with error:\n{str(parse_err)}\n\n"
            f"Here is your previous response:\n{response_text}\n\n"
            f"Please correct it and return ONLY valid JSON matching the schema."
        )

        # Time-budget guard: skip retry if the overall request is already close to its deadline.
        # This prevents the correction retry from pushing total latency past the 43s backend
        # timeout, which would cause the Minecraft client to see "AI server unavailable."
        elapsed_s = ctx.elapsed_seconds() if ctx else 0.0
        if elapsed_s > 35.0:
            log_message("WARNING", (
                f"{req_id} Skipping correction retry – request already elapsed "
                f"{elapsed_s:.1f}s (> 35s budget). Returning knowledge fallback."
            ))
            if ctx:
                try:
                    from request_context import FailureCategory
                    ctx.set_failure(FailureCategory.JSON_PARSE_ERROR)
                except Exception:
                    pass
            result = PlannerResult(
                reply="I had trouble formatting a response. Please rephrase your question.",
                tool_calls=[],
                response_strategy=ResponseStrategy.KNOWLEDGE,
            )
            validate_and_reason_decision(result, intent, classification, ctx, message, "Fallback (Time Budget)")
            return result
        log_message("INFO", f"{req_id} Retrying LLM generation with auto-correction prompt...")
        if ctx:
            ctx.begin_stage("planner:llm_correction_retry")
        try:
            retry_response = execute_llm_request_with_rate_limits(
                provider_name, model_name, system_prompt, correction_user_prompt,
                request_type="plan", prompt_profile=prompt_profile,
                model_profile=model_profile, ctx=ctx
            )
            if ctx:
                ctx.end_stage()
            cleaned_retry = clean_markdown_json(retry_response)
            log_message("DEBUG", f"{req_id} Cleaned retry response: {cleaned_retry[:300]}{'...' if len(cleaned_retry) > 300 else ''}")

            result = parse_and_validate(cleaned_retry)
            if ctx:
                ctx.plan_strategy = result.response_strategy.value
                ctx.chosen_tools = [tc.tool for tc in result.tool_calls]
                ctx.rejected_tools = [t for t in ctx.candidate_tools if t not in ctx.chosen_tools]
                ctx.rejection_reasons = {t: "Not selected by the planner for this query." for t in ctx.rejected_tools}
            validate_and_reason_decision(result, intent, classification, ctx, message, "LLM (Retry)")
            return result
        except Exception as retry_err:
            if ctx:
                ctx.end_stage(error=str(retry_err))
                ctx.record_exception(retry_err)
                ctx.chosen_tools = []
                ctx.rejected_tools = list(ctx.candidate_tools) if hasattr(ctx, "candidate_tools") else []
                ctx.rejection_reasons = {t: f"Planner retry failed: {type(retry_err).__name__}" for t in ctx.rejected_tools}
            log_message("ERROR", f"{req_id} Correction retry failed: {type(retry_err).__name__}: {retry_err}")
            result = PlannerResult(
                reply="I couldn't understand the planner response.",
                tool_calls=[]
            )
            validate_and_reason_decision(result, intent, classification, ctx, message, "Fallback (Retry)")
            return result
