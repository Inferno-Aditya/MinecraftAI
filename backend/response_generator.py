import os
import json
import time

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


class ResponseGenerator:
    """
    Dedicated component responsible for synthesizing the final conversational response.
    Handles knowledge-only replies, tool result formatting, and hybrid reasoning.
    """
    def __init__(self, provider_name: str = None, model_name: str = None):
        config = load_config()
        self.provider_name = provider_name or config.get("provider", "gemini")
        self.model_name = model_name or config.get("model", "gemini-2.5-flash")

    def generate_response(self, strategy: ResponseStrategy, message: str, player_context: PlayerContext, tool_results: str, planner_reply: str) -> str:
        """
        Generates the final response according to the response strategy.
        """
        try:
            from main import log_message
        except ImportError:
            def log_message(level, msg):
                print(f"[{level}] {msg}")

        if strategy == ResponseStrategy.KNOWLEDGE:
            return planner_reply

        if strategy == ResponseStrategy.TOOLS:
            return tool_results

        if strategy == ResponseStrategy.HYBRID:
            log_message("INFO", f"Synthesizing hybrid response via provider '{self.provider_name}' using model '{self.model_name}'")

            system_prompt = (
                "You are a Minecraft expert and a helpful AI companion.\n"
                "Your task is to answer the player's question using their current game context and the results of the tools that were just executed.\n"
                "Combine your deep knowledge of Minecraft mechanics, recipes, combat, block behavior, and strategies with the live game data provided to give an accurate, expert, and conversational answer.\n"
                "Do not mention tool names or implementation details (like 'get_inventory returned...'). Just answer naturally as if you are observing the game.\n\n"
                "You must respond ONLY in valid JSON matching this schema:\n"
                "{\n"
                "  \"reply\": \"Your conversational answer combining the tool results and Minecraft knowledge here...\"\n"
                "}"
            )

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
                f"Player Question: {message}\n\n"
                f"Tool Execution Results:\n{tool_results}\n\n"
                "Based on the player's question, their status/context, and the tool results, provide your expert Minecraft advice/answer."
            )

            # Log prompts using the same logging helper if configuration allows
            config = load_config()
            if config.get("enable_prompt_logging", True):
                try:
                    base_dir = os.path.dirname(os.path.dirname(__file__))
                    prompts_dir = os.path.join(base_dir, "logs", "prompts")
                    os.makedirs(prompts_dir, exist_ok=True)
                    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
                    filepath = os.path.join(prompts_dir, f"synthesis_{timestamp}.txt")
                    content = (
                        f"=== SYSTEM PROMPT ===\n{system_prompt}\n\n"
                        f"=== USER PROMPT ===\n{user_prompt}\n"
                    )
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                except Exception:
                    pass

            try:
                response_text = execute_llm_request_with_rate_limits(
                    self.provider_name, self.model_name, system_prompt, user_prompt, request_type="synthesis"
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
                try:
                    data = json.loads(cleaned_response)
                    if isinstance(data, dict) and "reply" in data:
                        return data["reply"]
                except Exception:
                    pass
                return response_text.strip()
            except Exception as e:
                return f"I performed the checks but encountered an error synthesizing the final advice. Raw results:\n{tool_results}"

        return tool_results
