import os
import json
import time
from typing import Optional, TYPE_CHECKING

try:
    from planner import ResponseStrategy
except ImportError:
    from .planner import ResponseStrategy

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

if TYPE_CHECKING:
    from request_context import RequestContext


class ResponseGenerator:
    """
    Dedicated component responsible for synthesizing the final conversational response.

    Handles three response strategies:
      - KNOWLEDGE: Returns the planner's pre-computed reply directly.
      - TOOLS:     Returns the raw tool result string.
      - HYBRID:    Runs a full LLM synthesis pass to weave tool results with Minecraft knowledge.

    The generate_response() method is guaranteed to never raise — it always returns a
    valid string so that the upstream chat_endpoint always has a reply to serialize.
    """

    def __init__(self, provider_name: str = None, model_name: str = None):
        try:
            from model_manager import model_manager
        except ImportError:
            from .model_manager import model_manager

        self.model_profile = model_manager.get_active_model_profile()
        self.provider_name = provider_name or self.model_profile.provider
        self.model_name = model_name or self.model_profile.model_id

    def generate_response(
        self,
        strategy: ResponseStrategy,
        message: str,
        player_context: PlayerContext,
        tool_results: str,
        planner_reply: str,
        ctx: Optional["RequestContext"] = None
    ) -> str:
        """
        Generates the final response according to the response strategy.

        This method is guaranteed to never raise an exception — all failures are
        caught and converted to a user-visible fallback string.
        """
        try:
            from main import log_message
        except ImportError:
            def log_message(level, msg):
                print(f"[{level}] {msg}")

        req_id = ctx.prefix() if ctx else ""

        # ----------------------------------------------------------------
        # KNOWLEDGE – planner already answered, return directly
        # ----------------------------------------------------------------
        if strategy == ResponseStrategy.KNOWLEDGE:
            if ctx:
                ctx.begin_stage("generator:knowledge_passthrough")
                ctx.end_stage()
            return planner_reply

        # ----------------------------------------------------------------
        # TOOLS – raw tool result, return directly
        # ----------------------------------------------------------------
        if strategy == ResponseStrategy.TOOLS:
            if ctx:
                ctx.begin_stage("generator:tools_passthrough")
                ctx.end_stage()
                # Run direct TOOLS strategy verification
                if hasattr(ctx, "execution_verification") and isinstance(ctx.execution_verification, dict):
                    ctx.execution_verification["accepted_by_prompt_builder"] = "N/A (TOOLS strategy passthrough)"
                    ctx.execution_verification["prompt_section_generated"] = "N/A (TOOLS strategy passthrough)"
                    ctx.execution_verification["provider_received_section"] = "N/A (TOOLS strategy passthrough)"
                    
                    tool_exec_success = all(ctx.execution_verification["tool_execution_success"].values())
                    tool_result_valid = all(ctx.execution_verification["valid_tool_result"].values())
                    
                    if not tool_exec_success:
                        ctx.execution_verification["verification_status"] = "failed"
                        failed_tools = [t for t, succ in ctx.execution_verification["tool_execution_success"].items() if not succ]
                        ctx.execution_verification["failure_reason"] = f"Tool(s) failed execution: {', '.join(failed_tools)}"
                    elif not tool_result_valid:
                        ctx.execution_verification["verification_status"] = "failed"
                        invalid_tools = [t for t, valid in ctx.execution_verification["valid_tool_result"].items() if not valid]
                        ctx.execution_verification["failure_reason"] = f"Tool(s) returned invalid ToolResult: {', '.join(invalid_tools)}"
                    else:
                        ctx.execution_verification["verification_status"] = "success"
            return tool_results

        # ----------------------------------------------------------------
        # HYBRID – LLM synthesis pass
        # ----------------------------------------------------------------
        if strategy == ResponseStrategy.HYBRID:
            log_message("INFO", f"{req_id} [Generator] Synthesizing hybrid response via provider='{self.provider_name}' model='{self.model_name}'")

            system_instructions = (
                "You are a Minecraft expert and a helpful AI companion.\n"
                "Your task is to answer the player's question using their current game context and the results of the tools that were just executed.\n"
                "Combine your deep knowledge of Minecraft mechanics, recipes, combat, block behavior, and strategies with the live game data provided to give an accurate, expert, and conversational answer.\n"
                "Do not mention tool names or implementation details (like 'get_inventory returned...'). Just answer naturally as if you are observing the game.\n\n"
                "You must respond ONLY in valid JSON matching this schema:\n"
                "{\n"
                "  \"reply\": \"Your conversational answer combining the tool results and Minecraft knowledge here...\"\n"
                "}"
            )

            # Stage A: Classify Intent
            if ctx:
                ctx.begin_stage("generator:classify_intent")
            try:
                from intent_classifier import IntentClassifier
                from context_builder import build_context
                from memory_retriever import retrieve_relevant_memory
                from prompt_builder import PromptBuilder, PromptProfile
            except ImportError:
                from .intent_classifier import IntentClassifier
                from .context_builder import build_context
                from .memory_retriever import retrieve_relevant_memory
                from .prompt_builder import PromptBuilder, PromptProfile

            classifier = IntentClassifier()
            classification = classifier.classify(message)
            req_context = classification["required_context"]
            req_memory = classification["required_memory"]
            if ctx:
                ctx.end_stage()

            # Stage B: Build Context
            if ctx:
                ctx.begin_stage("generator:build_context")
            context_text = build_context(player_context, req_context)
            if ctx:
                ctx.end_stage()

            # Stage C: Retrieve Memory
            if ctx:
                ctx.begin_stage("generator:retrieve_memory")
            memory_text = retrieve_relevant_memory(message, req_memory)
            if ctx:
                ctx.end_stage()

            # Stage D: Build Prompts
            if ctx:
                ctx.begin_stage("generator:build_prompt")
            try:
                from resource_manager import estimate_tokens
            except ImportError:
                from .resource_manager import estimate_tokens

            baseline_memory_summary = get_memory_summary()
            baseline_user_prompt = (
                f"Player Name: {player_context.name}\n"
                f"Current Location: X={player_context.x:.1f}, Y={player_context.y:.1f}, Z={player_context.z:.1f}\n"
                f"Dimension: {player_context.dimension}\n"
                f"Gamemode: {player_context.gamemode}\n"
                f"Health: {player_context.health}/20\n"
                f"Food Level: {player_context.food}/20\n"
                f"Biome: {player_context.biome}\n"
                f"World Time: {player_context.world_time} ticks\n\n"
                f"Memory Summary:\n{baseline_memory_summary}\n\n"
                f"Player Question: {message}\n\n"
                f"Tool Execution Results:\n{tool_results}\n\n"
                "Based on the player's question, their status/context, and the tool results, provide your expert Minecraft advice/answer."
            )
            baseline_tokens = estimate_tokens(system_instructions) + estimate_tokens(baseline_user_prompt)

            system_prompt, user_prompt = PromptBuilder.build_synthesis_prompt(
                system_instructions, context_text, memory_text, message, tool_results
            )

            # Execution Verification check for Prompt builder/section generation/provider payload
            if ctx and hasattr(ctx, "execution_verification") and isinstance(ctx.execution_verification, dict):
                ctx.execution_verification["accepted_by_prompt_builder"] = True
                
                section_text = f"Tool Execution Results:\n{tool_results}"
                has_section = section_text in user_prompt
                ctx.execution_verification["prompt_section_generated"] = has_section
                ctx.execution_verification["provider_received_section"] = has_section
                
                # Check if any errors occurred during tool execution
                tool_exec_success = all(ctx.execution_verification["tool_execution_success"].values()) if ctx.execution_verification["tool_execution_success"] else False
                tool_result_valid = all(ctx.execution_verification["valid_tool_result"].values()) if ctx.execution_verification["valid_tool_result"] else False
                
                if not tool_exec_success:
                    ctx.execution_verification["verification_status"] = "failed"
                    failed_tools = [t for t, succ in ctx.execution_verification["tool_execution_success"].items() if not succ]
                    ctx.execution_verification["failure_reason"] = f"Tool(s) failed execution: {', '.join(failed_tools)}"
                elif not tool_result_valid:
                    ctx.execution_verification["verification_status"] = "failed"
                    invalid_tools = [t for t, valid in ctx.execution_verification["valid_tool_result"].items() if not valid]
                    ctx.execution_verification["failure_reason"] = f"Tool(s) returned invalid ToolResult: {', '.join(invalid_tools)}"
                elif not has_section:
                    ctx.execution_verification["verification_status"] = "failed"
                    ctx.execution_verification["failure_reason"] = "Prompt Builder did not generate the Tool Results section."
                else:
                    ctx.execution_verification["verification_status"] = "success"
                
                # Also mark Tool Results as injected in the Prompt Injection Summary
                if hasattr(ctx, "prompt_sections_injected") and isinstance(ctx.prompt_sections_injected, dict):
                    ctx.prompt_sections_injected["Tool Results"] = True

            prompt_profile = PromptProfile.calculate(
                system_instructions=system_instructions,
                context_text=context_text + "\n\nTool Execution Results:\n" + tool_results,
                memory_text=memory_text,
                tool_defs="",
                user_message=message,
                actual_system_prompt=system_prompt,
                actual_user_prompt=user_prompt,
                baseline_tokens=baseline_tokens
            )
            if ctx:
                ctx.end_stage()

            # Optional prompt logging
            config = load_config()
            if config.get("enable_prompt_logging", True):
                try:
                    base_dir = os.path.dirname(os.path.dirname(__file__))
                    prompts_dir = os.path.join(base_dir, "logs", "prompts")
                    os.makedirs(prompts_dir, exist_ok=True)
                    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
                    filepath = os.path.join(prompts_dir, f"synthesis_{timestamp}.txt")
                    content = (
                        f"=== REQUEST ID: {ctx.request_id if ctx else 'N/A'} ===\n"
                        f"=== SYSTEM PROMPT ===\n{system_prompt}\n\n"
                        f"=== USER PROMPT ===\n{user_prompt}\n"
                    )
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                except Exception:
                    pass

            # Stage E: LLM Call – time-budget guarded
            if ctx:
                ctx.begin_stage("generator:llm_call")

            # Time-budget guard: if the request is already close to its overall
            # deadline, skip the second LLM call and return the tool results directly
            # rather than adding another 20-35s and triggering a client timeout.
            elapsed_s = ctx.elapsed_seconds() if ctx else 0.0
            if elapsed_s > 38.0:
                if ctx:
                    ctx.end_stage(
                        error=f"Time budget exceeded ({elapsed_s:.1f}s > 38s); skipping generator LLM call",
                        failure_category="GENERATOR_TIMEOUT",
                    )
                    try:
                        from request_context import FailureCategory
                        ctx.set_failure(FailureCategory.GENERATOR_TIMEOUT)
                    except Exception:
                        pass
                log_message("WARNING", (
                    f"{req_id} [GENERATOR_TIMEOUT] Skipping HYBRID generator LLM call – "
                    f"request already at {elapsed_s:.1f}s (> 38s budget). "
                    "Returning tool results directly."
                ))
                return (
                    "I successfully gathered the requested game information, but ran out of "
                    "time synthesizing a detailed response. Here's the raw data:\n"
                    + tool_results
                )

            try:
                response_text = execute_llm_request_with_rate_limits(
                    self.provider_name, self.model_name,
                    system_prompt, user_prompt,
                    request_type="synthesis",
                    prompt_profile=prompt_profile,
                    model_profile=self.model_profile,
                    ctx=ctx
                )
                if ctx:
                    ctx.end_stage()
            except Exception as llm_err:
                if ctx:
                    try:
                        from request_context import FailureCategory
                        cat = FailureCategory.GENERATOR_TIMEOUT if isinstance(llm_err, TimeoutError) else FailureCategory.UNKNOWN_PROVIDER_EXCEPTION
                        ctx.end_stage(error=str(llm_err), failure_category=cat)
                        ctx.record_exception(llm_err, failure_category=cat)
                    except Exception:
                        ctx.end_stage(error=str(llm_err))
                        ctx.record_exception(llm_err)
                log_message("ERROR", (
                    f"{req_id} [Generator] LLM synthesis call failed: "
                    f"{type(llm_err).__name__}: {llm_err}"
                ))
                return (
                    "I successfully gathered the requested game information, "
                    "but encountered an internal error while generating a conversational response. "
                    "Here's the raw data:\n"
                    + tool_results
                )

            # Stage F: Parse Response
            if ctx:
                ctx.begin_stage("generator:parse_response")

            # Log raw response before parsing so failures are diagnosable
            log_message("INFO", (
                f"{req_id} [Generator] Raw synthesis response "
                f"(chars={len(response_text)}): "
                f"{response_text[:300].replace(chr(10), ' ')!r}"
            ))

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
            try:
                data = json.loads(cleaned_response)
                if isinstance(data, dict) and "reply" in data:
                    if ctx:
                        ctx.end_stage()
                    return data["reply"]
            except Exception as parse_err:
                log_message("WARNING", (
                    f"{req_id} [Generator] JSON parse failed on synthesis response: "
                    f"{parse_err}. Raw: {cleaned_response[:200]!r}"
                ))
                if ctx:
                    try:
                        from request_context import FailureCategory
                        ctx.end_stage(
                            error=str(parse_err),
                            failure_category=FailureCategory.JSON_PARSE_ERROR,
                        )
                    except Exception:
                        ctx.end_stage(error=str(parse_err))
                # Fallback: return plain text if JSON parse fails (Gemma / non-JSON mode)
                if ctx:
                    ctx.begin_stage("generator:parse_response")

            if ctx:
                ctx.end_stage()
            # Fallback: return raw text if JSON parsing fails
            return response_text.strip()

        # Unknown strategy – safe fallback
        return tool_results
