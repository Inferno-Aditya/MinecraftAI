import os
import json
import base64
import time
from typing import Optional
from config import load_config
from request_context import RequestContext

def record_evaluation(
    ctx: RequestContext,
    player_state: dict,
    screenshot_b64: Optional[str],
    response_reply: Optional[str]
) -> None:
    """
    Main entry point to record a complete snapshot of an AI chat request.
    This runs completely inside a try-catch block to ensure it never interferes
    with the main gameplay or request pipeline if it fails.
    """
    try:
        # 1. Check configuration flag
        config = load_config()
        if not config.get("enable_eval_recorder", True):
            return

        # 2. Determine evals directory (workspace root / evals)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        evals_dir = os.path.join(base_dir, "evals")
        
        # Format timestamp using ctx.created_at
        local_time = time.localtime(ctx.created_at)
        formatted_time = time.strftime("%Y-%m-%d_%H-%M-%S", local_time)
        
        # Folder format: evals/YYYY-MM-DD_HH-MM-SS_REQ-XXXXXXXX/
        req_folder_name = f"{formatted_time}_REQ-{ctx.request_id}"
        req_dir = os.path.join(evals_dir, req_folder_name)
        os.makedirs(req_dir, exist_ok=True)

        # 3. question.txt
        with open(os.path.join(req_dir, "question.txt"), "w", encoding="utf-8") as f:
            f.write(ctx.user_message)

        # 4. answer.txt
        final_answer = response_reply or ""
        with open(os.path.join(req_dir, "answer.txt"), "w", encoding="utf-8") as f:
            f.write(final_answer)

        # 5. player_state.json
        with open(os.path.join(req_dir, "player_state.json"), "w", encoding="utf-8") as f:
            json.dump(player_state, f, indent=4, ensure_ascii=False)

        # 6. planner.json
        planner_data = {
            "system_prompt": getattr(ctx, "planner_system_prompt", None),
            "user_prompt": getattr(ctx, "planner_user_prompt", None),
            "raw_response": getattr(ctx, "planner_raw_response", None),
            "intent_classification": getattr(ctx, "intent", None),
            "intent_confidence_scores": getattr(ctx, "intent_confidence_scores", {}),
            "planner_override": getattr(ctx, "planner_override", None),
            "dev_warnings": getattr(ctx, "dev_warnings", []),
            "decision_reasoning": getattr(ctx, "decision_reasoning", None)
        }
        with open(os.path.join(req_dir, "planner.json"), "w", encoding="utf-8") as f:
            json.dump(planner_data, f, indent=4, ensure_ascii=False)

        # 7. tools.json
        tools_data = {
            "candidate_tools": getattr(ctx, "candidate_tools", []),
            "chosen_tools": getattr(ctx, "chosen_tools", []),
            "tool_calls_made": getattr(ctx, "tool_calls_made", []),
            "last_executed_tool": getattr(ctx, "last_executed_tool", None),
            "tool_execution_time_ms": getattr(ctx, "tool_execution_time_ms", None),
            "tool_status": getattr(ctx, "tool_status", None),
            "tool_output": getattr(ctx, "tool_output", None),
            "tool_exception": getattr(ctx, "tool_exception", None),
            "tool_execution_results": getattr(ctx, "tool_execution_results", [])
        }
        with open(os.path.join(req_dir, "tools.json"), "w", encoding="utf-8") as f:
            json.dump(tools_data, f, indent=4, ensure_ascii=False)

        # 8. timings.json
        timings_data = {
            "total_response_time_ms": ctx.response_time_ms,
            "stage_timings": ctx.get_stage_timings()
        }
        with open(os.path.join(req_dir, "timings.json"), "w", encoding="utf-8") as f:
            json.dump(timings_data, f, indent=4, ensure_ascii=False)

        # 9. raw_llm_response.json
        raw_llm_data = {
            "planner_raw_response": getattr(ctx, "planner_raw_response", None),
            "generator_raw_response": getattr(ctx, "generator_raw_response", None)
        }
        with open(os.path.join(req_dir, "raw_llm_response.json"), "w", encoding="utf-8") as f:
            json.dump(raw_llm_data, f, indent=4, ensure_ascii=False)

        # 10. request.json
        request_data = {
            "request_id": ctx.request_id,
            "timestamp": ctx.created_at,
            "timestamp_formatted": formatted_time,
            "provider": ctx.provider_name,
            "model": ctx.model_name,
            "response_strategy": ctx.plan_strategy,
            "response_status": ctx.response_status,
            "last_exception": ctx.last_exception,
            "last_exception_type": ctx.last_exception_type,
            "failure_category": ctx.failure_category
        }
        with open(os.path.join(req_dir, "request.json"), "w", encoding="utf-8") as f:
            json.dump(request_data, f, indent=4, ensure_ascii=False)

        # 11. screenshot.png
        if screenshot_b64:
            try:
                # Remove header/prefix if present (e.g. data:image/png;base64,)
                if "," in screenshot_b64:
                    screenshot_b64 = screenshot_b64.split(",")[1]
                img_data = base64.b64decode(screenshot_b64)
                with open(os.path.join(req_dir, "screenshot.png"), "wb") as f:
                    f.write(img_data)
            except Exception as e:
                # Catch screenshot write errors independently so they don't break other files
                print(f"[EVAL RECORDER ERROR] Failed to save screenshot: {e}")

        # 12. README.md
        detected_intent = ctx.intent if getattr(ctx, "intent", None) else "N/A"
        tools_called_str = ", ".join(ctx.tool_calls_made) if ctx.tool_calls_made else "None"
        
        readme_content = f"""# AI Evaluation: REQ-{ctx.request_id}

* **Question**: {ctx.user_message}
* **Final Answer**: {final_answer}
* **Expected Intent**: N/A
* **Detected Intent**: {detected_intent}
* **Strategy Used**: {ctx.plan_strategy}
* **Tools Called**: {tools_called_str}
* **Time Taken**: {ctx.response_time_ms} ms
* **Provider**: {ctx.provider_name}
* **Model**: {ctx.model_name}
* **Request ID**: {ctx.request_id}
"""
        with open(os.path.join(req_dir, "README.md"), "w", encoding="utf-8") as f:
            f.write(readme_content)

    except Exception as e:
        # Completely independent, catch all and print warning
        print(f"[EVAL RECORDER ERROR] General evaluation recorder exception: {e}")
