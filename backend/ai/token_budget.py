from typing import List, Dict, Any, Tuple
from backend.resource_manager import estimate_tokens

def enforce_token_budget(
    system_instructions: str,
    player_question: str,
    tool_results: str,
    live_context: str,
    personality: str,
    relevant_memories: List[Dict[str, Any]],
    max_budget: int = 8192
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Enforces a strict token limit on the assembled prompt based on the priority order:
    1. System Instructions (Highest)
    2. Player Question
    3. Tool Results
    4. Live Minecraft Context
    5. Highest Ranked Memories (Top 3)
    6. Personality
    7. Remaining Memories (Lowest)
    
    Returns:
      - A dict containing the accepted text sections:
        {
          "system_instructions": str,
          "player_question": str,
          "tool_results": str,
          "live_context": str,
          "personality": str,
          "top_memories": List[dict],
          "remaining_memories": List[dict]
        }
      - The list of memories with updated utilization statuses ("injected" vs "pruned").
    """
    # Initialize utilization status for all candidate memories
    updated_memories = [dict(m) for m in relevant_memories]
    for m in updated_memories:
        m["utilization_status"] = "injected"
        
    # Split memories into top 3 (Priority 5) and remaining (Priority 7)
    top_candidates = updated_memories[:3]
    remaining_candidates = updated_memories[3:]
    
    # Calculate baseline token costs for permanent parts
    system_ins_tokens = estimate_tokens(system_instructions)
    question_tokens = estimate_tokens(player_question)
    tool_res_tokens = estimate_tokens(tool_results)
    live_ctx_tokens = estimate_tokens(live_context)
    personality_tokens = estimate_tokens(personality)
    
    # Helper to calculate current total tokens
    def get_total_tokens(
        tr: str, lc: str, pers: str,
        tc: List[dict], rc: List[dict]
    ) -> int:
        from backend.ai.memory_formatter import format_memory_entry
        total = system_ins_tokens + question_tokens + estimate_tokens(tr) + estimate_tokens(lc) + estimate_tokens(pers)
        
        # Add memory tokens
        for m in tc + rc:
            total += estimate_tokens(format_memory_entry(m))
        return total

    # 1. Prune remaining memories (Priority 7) first
    while remaining_candidates and get_total_tokens(tool_results, live_context, personality, top_candidates, remaining_candidates) > max_budget:
        discarded = remaining_candidates.pop() # Discard from lowest rank first (end of list)
        # Update its utilization status to pruned
        for m in updated_memories:
            if m["memory_uuid"] == discarded["memory_uuid"]:
                m["utilization_status"] = "pruned"
                
    # 2. Prune personality (Priority 6) next
    current_personality = personality
    if get_total_tokens(tool_results, live_context, current_personality, top_candidates, remaining_candidates) > max_budget:
        current_personality = ""
        
    # 3. Prune top memories (Priority 5) next
    while top_candidates and get_total_tokens(tool_results, live_context, current_personality, top_candidates, remaining_candidates) > max_budget:
        discarded = top_candidates.pop() # Discard from lowest rank first
        # Update its utilization status to pruned
        for m in updated_memories:
            if m["memory_uuid"] == discarded["memory_uuid"]:
                m["utilization_status"] = "pruned"
                
    # 4. Prune live context (Priority 4) next
    current_live_context = live_context
    if get_total_tokens(tool_results, current_live_context, current_personality, top_candidates, remaining_candidates) > max_budget:
        current_live_context = ""
        
    # 5. Prune tool results (Priority 3) next
    current_tool_results = tool_results
    if get_total_tokens(current_tool_results, current_live_context, current_personality, top_candidates, remaining_candidates) > max_budget:
        current_tool_results = ""
        
    accepted_sections = {
        "system_instructions": system_instructions,
        "player_question": player_question,
        "tool_results": current_tool_results,
        "live_context": current_live_context,
        "personality": current_personality,
        "top_memories": top_candidates,
        "remaining_memories": remaining_candidates
    }
    
    return accepted_sections, updated_memories
