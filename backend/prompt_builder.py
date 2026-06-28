from pydantic import BaseModel, Field
from typing import Dict, Any, List

class PromptProfile(BaseModel):
    """
    Model encapsulating prompt composition token metrics.
    """
    system_prompt_tokens: int = Field(default=0, description="Tokens used by system instructions.")
    context_tokens: int = Field(default=0, description="Tokens used by player context and tool results.")
    memory_tokens: int = Field(default=0, description="Tokens used by retrieved memory.")
    tool_tokens: int = Field(default=0, description="Tokens used by tool definitions.")
    user_message_tokens: int = Field(default=0, description="Tokens used by user message.")
    total_prompt_tokens: int = Field(default=0, description="Total actual prompt tokens.")
    baseline_tokens: int = Field(default=0, description="Baseline unoptimized prompt tokens.")

    @classmethod
    def calculate(
        cls,
        system_instructions: str,
        context_text: str,
        memory_text: str,
        tool_defs: str,
        user_message: str,
        actual_system_prompt: str,
        actual_user_prompt: str,
        baseline_tokens: int
    ) -> "PromptProfile":
        try:
            from resource_manager import estimate_tokens
        except ImportError:
            from .resource_manager import estimate_tokens

        actual_total = estimate_tokens(actual_system_prompt) + estimate_tokens(actual_user_prompt)
        return cls(
            system_prompt_tokens=estimate_tokens(system_instructions),
            context_tokens=estimate_tokens(context_text),
            memory_tokens=estimate_tokens(memory_text),
            tool_tokens=estimate_tokens(tool_defs),
            user_message_tokens=estimate_tokens(user_message),
            total_prompt_tokens=actual_total,
            baseline_tokens=baseline_tokens
        )


class PromptBuilder:
    """
    Dedicated builder component responsible for constructing final prompt representations.
    """
    @staticmethod
    def build_planner_prompt(
        system_instructions: str,
        context_text: str,
        memory_text: str,
        tool_definitions: str,
        user_message: str
    ) -> tuple[str, str]:
        """
        Combines system components and user components into a system_prompt and user_prompt.
        """
        # Build System Prompt
        try:
            from personality import load_personality
        except ImportError:
            from .personality import load_personality
            
        personality = load_personality()
        
        system_prompt_parts = [system_instructions]
        if personality:
            system_prompt_parts.append(f"Personality:\n{personality}")
            
        if tool_definitions:
            system_prompt_parts.append(f"Available Tools:\n{tool_definitions}")
        else:
            system_prompt_parts.append("Available Tools:\nNone (You are in knowledge-only mode. Set 'response_strategy' to 'KNOWLEDGE' and reply directly.)")
            
        system_prompt = "\n\n".join(system_prompt_parts)
        
        # Build User Prompt
        user_prompt_parts = []
        if context_text:
            user_prompt_parts.append(context_text)
        if memory_text:
            user_prompt_parts.append(f"Memory Summary:\n{memory_text}")
        user_prompt_parts.append(f"User Message: {user_message}")
        
        user_prompt = "\n\n".join(user_prompt_parts)
        
        return system_prompt, user_prompt

    @staticmethod
    def build_synthesis_prompt(
        system_instructions: str,
        context_text: str,
        memory_text: str,
        user_message: str,
        tool_results: str
    ) -> tuple[str, str]:
        """
        Combines components for the response synthesis step.
        """
        try:
            from personality import load_personality
        except ImportError:
            from .personality import load_personality
            
        personality = load_personality()
        
        system_prompt_parts = [system_instructions]
        if personality:
            system_prompt_parts.append(f"Personality:\n{personality}")
            
        system_prompt = "\n\n".join(system_prompt_parts)
        
        user_prompt_parts = []
        if context_text:
            user_prompt_parts.append(context_text)
        if memory_text:
            user_prompt_parts.append(f"Memory Summary:\n{memory_text}")
        user_prompt_parts.append(f"Player Question: {user_message}")
        user_prompt_parts.append(f"Tool Execution Results:\n{tool_results}")
        user_prompt_parts.append("Based on the player's question, their status/context, and the tool results, provide your expert Minecraft advice/answer.")
        
        user_prompt = "\n\n".join(user_prompt_parts)
        
        return system_prompt, user_prompt
