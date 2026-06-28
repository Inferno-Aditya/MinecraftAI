import os
import asyncio
import datetime
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import List, Dict, Any

try:
    from context import PlayerContext
except ImportError:
    from .context import PlayerContext

try:
    from planner import plan, ToolCall, PlannerResult, ResponseStrategy
except ImportError:
    from .planner import plan, ToolCall, PlannerResult, ResponseStrategy

try:
    from response_generator import ResponseGenerator
except ImportError:
    from .response_generator import ResponseGenerator

try:
    from tools import registry
except ImportError:
    from .tools import registry

try:
    from resource_manager import resource_manager
except ImportError:
    from .resource_manager import resource_manager

try:
    from config import load_config, save_config, save_api_key
except ImportError:
    from .config import load_config, save_config, save_api_key

try:
    from memory import load_memory, save_memory
except ImportError:
    from .memory import load_memory, save_memory

try:
    from personality import load_personality, save_personality, restore_default_personality, get_personality_meta
except ImportError:
    from .personality import load_personality, save_personality, restore_default_personality, get_personality_meta

try:
    from request_context import RequestContext, FailureCategory, RequestState
except ImportError:
    from .request_context import RequestContext

from tools.base import ToolResult
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from fastapi.concurrency import run_in_threadpool

# Load environment variables
load_dotenv()

app = FastAPI(title="AI Minecraft Assistant Backend")

# Setup CORS for the Dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers for request validation to ensure HTTP 200 ChatResponses
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    error_msg = f"Request validation failed: {str(exc)}"
    log_message("ERROR", error_msg)
    if "/chat" in request.url.path:
        return JSONResponse(
            status_code=200,
            content={
                "reply": f"Validation error: the request payload was invalid or missing required fields. Details: {str(exc.errors())}",
                "tool_calls": []
            }
        )
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )

@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request, exc):
    error_msg = f"Pydantic validation failed: {str(exc)}"
    log_message("ERROR", error_msg)
    if "/chat" in request.url.path:
        return JSONResponse(
            status_code=200,
            content={
                "reply": f"Validation error: Pydantic parsing failed. Details: {str(exc.errors())}",
                "tool_calls": []
            }
        )
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )

# Log file path
LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "aiassistant.log")


def log_message(level: str, message: str) -> None:
    """
    Logs messages to console stdout and appends to logs/aiassistant.log.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}\n"
    print(f"[Backend] {log_entry.strip()}")
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Failed to write to backend log file: {e}")


# ─────────────────────────────────────────────────────────────
# Request/Response schemas
# ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    player: PlayerContext
    memory: dict = {}
    screenshot: str = ""

class ChatResponse(BaseModel):
    reply: str
    tool_calls: List[ToolCall] = []

class ConfigUpdateRequest(BaseModel):
    provider: str
    model: str
    temperature: float
    max_tokens: int
    timeout: float
    rate_limits: Dict[str, Dict[str, int]] = {}
    gemini_api_key: str = ""


# ─────────────────────────────────────────────────────────────
# Log parsing helper
# ─────────────────────────────────────────────────────────────

def parse_log_line(line: str, source: str) -> dict:
    line = line.strip()
    if not line.startswith("[") or "] [" not in line:
        return None
    try:
        ts_end = line.find("]")
        timestamp = line[1:ts_end]
        level_start = line.find("[", ts_end + 1)
        level_end = line.find("]", level_start + 1)
        if level_start == -1 or level_end == -1:
            return None
        level = line[level_start + 1:level_end]
        message = line[level_end + 1:].strip()

        msg_upper = message.upper()
        if "PLANNER SELECTED" in msg_upper or "TOOL EXECUTION" in msg_upper or "TOOL CALL" in msg_upper or any(
            t.upper() in msg_upper for t in [
                "SAVE_LOCATION", "LOAD_LOCATION", "LIST_LOCATIONS", "SAVE_NOTE",
                "GET_PLAYER_STATUS", "GET_HELD_ITEM", "GET_EQUIPMENT", "GET_INVENTORY",
                "GET_WEATHER", "GET_TIME", "GET_LIGHT_LEVEL", "GET_NEARBY_BLOCKS",
                "SCAN_AREA", "FIND_NEAREST", "GET_NEARBY_ENTITIES", "GET_BIOME"
            ]
        ):
            category = "Tool Execution"
        elif level.upper() in ["ERROR", "WARNING"] or "FAILED" in msg_upper or "EXCEPTION" in msg_upper:
            category = "Error"
        else:
            category = "General"

        return {
            "timestamp": timestamp,
            "level": level,
            "source": source,
            "message": message,
            "category": category
        }
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# Endpoints – Health & Stats
# ─────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    resource_manager.record_launcher_heartbeat()
    return {"status": "healthy"}

@app.get("/api/resources/stats")
def get_resource_stats():
    return resource_manager.get_stats()


# ─────────────────────────────────────────────────────────────
# Endpoints – Config
# ─────────────────────────────────────────────────────────────

@app.get("/api/config")
def get_config():
    config = load_config()
    gemini_key = os.getenv("GEMINI_API_KEY")
    config["gemini_api_key"] = "********" if gemini_key else ""
    return config

@app.post("/api/config")
def update_config(req: ConfigUpdateRequest):
    try:
        if req.gemini_api_key and req.gemini_api_key != "********":
            save_api_key(req.gemini_api_key)

        config_data = {
            "provider": req.provider,
            "model": req.model,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "timeout": req.timeout,
            "providers": {
                req.provider: {
                    "rate_limits": req.rate_limits.get(req.provider, {})
                }
            }
        }
        for p_name, p_val in req.rate_limits.items():
            if p_name != req.provider:
                if "providers" not in config_data:
                    config_data["providers"] = {}
                config_data["providers"][p_name] = {"rate_limits": p_val}

        save_config(config_data)
        return {"status": "success", "message": "Configuration updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# Endpoints – Models
# ─────────────────────────────────────────────────────────────

class ActiveModelRequest(BaseModel):
    model_id: str

def _serialize_model(m_id: str, m) -> dict:
    return {
        "name": m.name,
        "provider": m.provider,
        "description": m.description,
        "rpm": m.rpm,
        "rpd": m.rpd,
        "context_window": m.context_window,
        "output_token_limit": m.output_token_limit,
        "recommended_usage": m.recommended_usage,
        "supports_chat": m.supports_chat,
        "supports_tools": m.supports_tools,
        "supports_json_mode": m.supports_json_mode,
        "recommended": m.recommended,
        "badge": m.badge,
        "icon": m.icon,
        "is_hidden": m.is_hidden,
        "discovery_source": m.discovery_source,
    }

@app.get("/api/models")
def get_models():
    from model_manager import model_manager
    # Expose ALL models (including hidden) so the dashboard can
    # choose which to show.  The `is_hidden` flag drives UI filtering.
    return {
        "active_model": model_manager.get_active_model(),
        "active_provider": model_manager.get_active_provider(),
        "default_model": model_manager.get_default_model_id(),
        "last_sync_time": model_manager.last_sync_time,
        "discovery_source": model_manager.discovery_source,
        "warning": model_manager.sync_warning,
        "supported_models": {
            m_id: _serialize_model(m_id, m)
            for m_id, m in model_manager.get_supported_models().items()
        }
    }

@app.post("/api/models/refresh")
def refresh_models():
    from model_manager import model_manager
    sync_result = model_manager.discover_models(force=True)
    return {
        "status": "success",
        "active_model_changed": sync_result.get("active_model_changed", False),
        "warning": sync_result.get("warning"),
        "last_sync_time": sync_result.get("last_sync_time"),
        "discovery_source": sync_result.get("discovery_source"),
        "active_model": model_manager.get_active_model(),
        "active_provider": model_manager.get_active_provider(),
        "supported_models": {
            m_id: _serialize_model(m_id, m)
            for m_id, m in model_manager.get_supported_models().items()
        }
    }

@app.post("/api/models/active")
def set_active_model(req: ActiveModelRequest):
    from model_manager import model_manager
    success = model_manager.set_active_model(req.model_id)
    if not success:
        raise HTTPException(status_code=400, detail=f"Model '{req.model_id}' is not supported.")
    return {"status": "success", "active_model": model_manager.get_active_model()}


# ─────────────────────────────────────────────────────────────
# Endpoints – Providers
# ─────────────────────────────────────────────────────────────

@app.get("/api/providers")
def get_providers():
    from model_manager import model_manager
    supported = model_manager.get_supported_models()

    # Only expose selectable (chat) models in provider model lists
    selectable = model_manager.get_selectable_models()
    gemini_models = [m_id for m_id, m in selectable.items() if m.provider == "gemini"]
    mock_models = [m_id for m_id, m in selectable.items() if m.provider == "mock"]

    gemini_avail = bool(os.getenv("GEMINI_API_KEY"))
    return [
        {
            "id": "gemini",
            "name": "Google Gemini",
            "available": gemini_avail,
            "models": gemini_models if gemini_models else ["gemini-2.5-flash"],
            "default_model": gemini_models[0] if gemini_models else "gemini-2.5-flash"
        },
        {
            "id": "mock",
            "name": "Mock Provider (Testing)",
            "available": True,
            "models": mock_models if mock_models else ["mock-model"],
            "default_model": mock_models[0] if mock_models else "mock-model"
        }
    ]


# ─────────────────────────────────────────────────────────────
# Endpoints – Tools / Memory / Logs
# ─────────────────────────────────────────────────────────────

@app.get("/api/tools")
def get_tools_metadata():
    tools = registry.list_tools()
    result = []
    for name, tool in tools.items():
        if name.startswith("save_") or name.startswith("load_") or name.startswith("list_") or "location" in name or "note" in name:
            category = "Memory"
        else:
            category = "Perception"
        result.append({
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema.model_json_schema(),
            "examples": tool.usage_examples,
            "category": category
        })
    return result

class PersonalityUpdate(BaseModel):
    content: str

@app.get("/api/personality")
def get_personality():
    return get_personality_meta()

@app.post("/api/personality")
def update_personality(data: PersonalityUpdate):
    success = save_personality(data.content)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to save personality (cannot be empty)")
    return {"status": "success"}

@app.post("/api/personality/reset")
def reset_personality_route():
    content = restore_default_personality()
    return {"status": "success", "content": content}

@app.get("/api/memory")
def get_all_memory():
    return load_memory()

@app.put("/api/memory/locations/{name}")
def update_memory_location(name: str, data: dict):
    mem = load_memory()
    mem["locations"][name] = data
    save_memory(mem)
    return {"status": "success"}

@app.delete("/api/memory/locations/{name}")
def delete_memory_location(name: str):
    mem = load_memory()
    if name in mem["locations"]:
        del mem["locations"][name]
        save_memory(mem)
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Location not found")

@app.put("/api/memory/notes/{key}")
def update_memory_note(key: str, data: dict):
    mem = load_memory()
    val = data.get("value", "")
    mem["notes"][key] = val
    save_memory(mem)
    return {"status": "success"}

@app.delete("/api/memory/notes/{key}")
def delete_memory_note(key: str):
    mem = load_memory()
    if key in mem["notes"]:
        del mem["notes"][key]
        save_memory(mem)
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Note not found")

@app.put("/api/memory/preferences/{key}")
def update_memory_preference(key: str, data: dict):
    mem = load_memory()
    val = data.get("value", "")
    mem["preferences"][key] = val
    save_memory(mem)
    return {"status": "success"}

@app.delete("/api/memory/preferences/{key}")
def delete_memory_preference(key: str):
    mem = load_memory()
    if key in mem["preferences"]:
        del mem["preferences"][key]
        save_memory(mem)
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Preference not found")

@app.get("/api/logs")
def get_logs(
    source: str = None,
    level: str = None,
    category: str = None,
    query: str = None,
    limit: int = 150
):
    backend_log_path = LOG_FILE
    launcher_log_path = os.path.join(os.path.dirname(LOG_FILE), "launcher.log")

    parsed_entries = []

    if (not source or source == "backend") and os.path.exists(backend_log_path):
        try:
            with open(backend_log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[-1000:]:
                    entry = parse_log_line(line, "backend")
                    if entry:
                        parsed_entries.append(entry)
        except Exception:
            pass

    if (not source or source == "launcher") and os.path.exists(launcher_log_path):
        try:
            with open(launcher_log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[-1000:]:
                    entry = parse_log_line(line, "launcher")
                    if entry:
                        parsed_entries.append(entry)
        except Exception:
            pass

    filtered = parsed_entries

    if level:
        filtered = [e for e in filtered if e["level"].upper() == level.upper()]
    if category:
        filtered = [e for e in filtered if e["category"].upper() == category.upper()]
    if query:
        q = query.lower()
        filtered = [e for e in filtered if q in e["message"].lower() or q in e["timestamp"].lower()]

    filtered.sort(key=lambda x: x["timestamp"], reverse=True)
    return filtered[:limit]


# ─────────────────────────────────────────────────────────────
# Endpoint – Developer Diagnostics
# ─────────────────────────────────────────────────────────────

@app.get("/api/diagnostics")
def get_diagnostics():
    """
    Returns the last request's full diagnostic context:
    - Request ID, provider, model, strategy
    - Per-stage timing breakdown
    - Last exception (if any)
    - Sanitized provider request payload
    - Discovery source
    - Model capability flags
    """
    from model_manager import model_manager

    active_profile = model_manager.get_active_model_profile()
    model_caps = {
        "supports_chat": active_profile.supports_chat,
        "supports_tools": active_profile.supports_tools,
        "supports_json_mode": active_profile.supports_json_mode,
        "context_window": active_profile.context_window,
        "output_token_limit": active_profile.output_token_limit,
    }

    last_ctx = resource_manager.last_request_context_dict or {}

    return {
        "active_provider": model_manager.get_active_provider(),
        "active_model": model_manager.get_active_model(),
        "model_capabilities": model_caps,
        "discovery_source": model_manager.discovery_source,
        "last_sync_time": model_manager.last_sync_time,
        # Last request details
        "last_request_id": last_ctx.get("request_id"),
        "last_request_message": last_ctx.get("user_message"),
        "last_request_strategy": last_ctx.get("plan_strategy"),
        "last_request_tools": last_ctx.get("tool_calls_made", []),
        "last_response_status": last_ctx.get("response_status"),
        "last_response_time_ms": last_ctx.get("response_time_ms"),
        "last_input_tokens": last_ctx.get("input_tokens"),
        "last_output_tokens": last_ctx.get("output_tokens"),
        "last_exception": resource_manager.last_exception_message,
        "last_exception_type": last_ctx.get("last_exception_type"),
        "failure_category": last_ctx.get("failure_category", "NONE"),
        "current_state": last_ctx.get("current_state", "UNKNOWN"),
        "last_successful_request_id": resource_manager.last_successful_request_id,
        "last_provider_payload": last_ctx.get("last_payload", {}),
        "stage_timings": last_ctx.get("stage_timings", []),
        # Tool execution details
        "last_executed_tool": last_ctx.get("last_executed_tool"),
        "tool_execution_time_ms": last_ctx.get("tool_execution_time_ms"),
        "tool_status": last_ctx.get("tool_status"),
        "tool_output": last_ctx.get("tool_output"),
        "tool_exception": last_ctx.get("tool_exception"),
    }


@app.get("/api/tools/health")
def get_tools_health():
    """
    Enumerates all registered tools, runs self-validation checks, and reports readiness.
    """
    from tools.registry import registry
    try:
        registry.validate_all()
        status = "healthy"
        error_details = None
    except Exception as e:
        status = "unhealthy"
        error_details = str(e)

    tools_summary = {}
    for name, tool in registry.list_tools().items():
        tools_summary[name] = {
            "name": name,
            "description": tool.description,
            "input_schema": tool.input_schema.__name__,
            "examples_count": len(tool.usage_examples),
            "healthy": True
        }

    return {
        "status": status,
        "error": error_details,
        "tools": tools_summary
    }


# ─────────────────────────────────────────────────────────────
# Chat endpoint – main pipeline
# ─────────────────────────────────────────────────────────────

# Overall backend timeout – must be less than the Minecraft mod's HTTP timeout
# (AIAssistantMod.java REQUEST_TIMEOUT_SECONDS = 45). Set to 43 to give a
# 2-second margin for serialization and network delivery.
_CHAT_PIPELINE_TIMEOUT_S = 43.0

def log_planner_debug(ctx: RequestContext, planned_result: PlannerResult) -> None:
    """
    Logs structured detailed planner diagnostics for routing verification.
    """
    try:
        log_message("INFO", "=== PLANNER DEBUG LOG ===")
        
        # 1. Intent Explainability Section
        log_message("INFO", "--- Intent Explainability ---")
        detected_mobs = getattr(ctx, "detected_mobs", [])
        detected_structures = getattr(ctx, "detected_structures", [])
        detected_blocks = getattr(ctx, "detected_blocks", [])
        detected_items = getattr(ctx, "detected_items", [])
        detected_spatial = getattr(ctx, "detected_spatial_keywords", [])
        detected_verbs = getattr(ctx, "detected_action_verbs", [])
        
        if detected_spatial:
            log_message("INFO", f"Spatial Keyword: {', '.join(detected_spatial)}")
        if detected_structures:
            log_message("INFO", f"Structure: {', '.join(detected_structures)}")
        if detected_mobs:
            log_message("INFO", f"Mob: {', '.join(detected_mobs)}")
        if detected_blocks:
            log_message("INFO", f"Block: {', '.join(detected_blocks)}")
        if detected_items:
            log_message("INFO", f"Item: {', '.join(detected_items)}")
        if detected_verbs:
            log_message("INFO", f"Action Verb: {', '.join(detected_verbs)}")
            
        intent_scores = getattr(ctx, "intent_confidence_scores", {})
        intent_scores_str = ", ".join(f"{k}: {v:.2f}" for k, v in intent_scores.items() if k != "WORLD_SEARCH")
        log_message("INFO", f"Intent Confidence Scores: {intent_scores_str}")
        
        is_uncertain = getattr(ctx, "is_uncertain", False)
        if is_uncertain:
            log_message("INFO", f"Uncertainty Detected: Highest score below threshold. Falling back from '{getattr(ctx, 'original_intent')}' to '{getattr(ctx, 'intent')}'")
        
        log_message("INFO", f"Final Intent: {getattr(ctx, 'intent', 'N/A')} ({intent_scores.get(getattr(ctx, 'intent', ''), 0.0):.2f})")
        log_message("INFO", "-----------------------------")
        
        # 1.5. Decision Reasoning
        log_message("INFO", "--- Decision Reasoning ---")
        reasoning = getattr(ctx, "decision_reasoning", {})
        if reasoning:
            log_message("INFO", f"Strategy Source: {reasoning.get('strategy_source', 'N/A')}")
            log_message("INFO", f"Strategy Validation: {reasoning.get('strategy_validation', 'N/A')}")
            log_message("INFO", f"Override Applied: {reasoning.get('override_applied', 'N/A')}")
            log_message("INFO", f"Decision Reason: {reasoning.get('decision_reason', 'N/A')}")
            
        override = getattr(ctx, "planner_override", {})
        if override:
            log_message("INFO", f"[Override Details] Fallback applied from '{override.get('original_intent')}' with confidence {override.get('original_confidence', 0.0):.2f}")
            
        warnings = getattr(ctx, "dev_warnings", [])
        if warnings:
            log_message("INFO", f"[Dev Warnings] Contradiction warnings: {warnings}")
        log_message("INFO", "--------------------------")
        
        # 2. Final Planner Decision
        log_message("INFO", f"Selected Strategy: {planned_result.response_strategy.value if hasattr(planned_result.response_strategy, 'value') else planned_result.response_strategy}")
        
        # Candidate Tools with confidence scores (from Candidate Tool Ranking)
        cand_ranking = getattr(ctx, "candidate_tool_ranking", [])
        cand_with_conf = [f"{t} ({score:.2f})" for t, score in cand_ranking]
        log_message("INFO", f"Candidate Tool Ranking: {cand_with_conf}")
        
        # Chosen & Rejected Tools
        chosen_tools = getattr(ctx, "chosen_tools", [])
        rejected_tools = getattr(ctx, "rejected_tools", [])
        log_message("INFO", f"Final Planner Decision (Chosen Tools): {chosen_tools}")
        log_message("INFO", f"Rejected Tools: {rejected_tools}")
        
        # Rejection Reasons
        rejection_reasons = getattr(ctx, "rejection_reasons", {})
        if rejected_tools:
            rejections_str = ", ".join(f"{t}: {rejection_reasons.get(t, 'Not selected')}" for t in rejected_tools)
            log_message("INFO", f"Reason for rejection: {rejections_str}")
        else:
            log_message("INFO", "Reason for rejection: N/A")
            
        # Tool Execution verification status and results
        exec_verification = getattr(ctx, "execution_verification", {})
        tool_results_log = getattr(ctx, "tool_execution_results", [])
        if tool_results_log:
            log_message("INFO", f"Tool execution result: {'; '.join(tool_results_log)}")
        elif planned_result.tool_calls:
            log_message("INFO", "Tool execution result: (Executed but no results recorded)")
        else:
            log_message("INFO", "Tool execution result: N/A (No tools executed)")
            
        # Prompt Injection Summary
        injected = getattr(ctx, "prompt_sections_injected", {})
        injected_list = [k for k, v in injected.items() if v]
        log_message("INFO", f"Prompt sections injected: {injected_list}")
        
        # Detailed Execution Verification Stage
        if exec_verification:
            status = exec_verification.get("verification_status", "pending")
            reason = exec_verification.get("failure_reason")
            log_message("INFO", f"Execution Verification Status: {status.upper()}")
            if reason:
                log_message("INFO", f"Execution Verification Failure Reason: {reason}")
            log_message("INFO", f"  - Tool Executed Successfully: {exec_verification.get('tool_execution_success', {})}")
            log_message("INFO", f"  - Valid ToolResult Returned: {exec_verification.get('valid_tool_result', {})}")
            log_message("INFO", f"  - Accepted by Prompt Builder: {exec_verification.get('accepted_by_prompt_builder')}")
            log_message("INFO", f"  - Prompt Section Generated: {exec_verification.get('prompt_section_generated')}")
            log_message("INFO", f"  - Provider Received Section: {exec_verification.get('provider_received_section')}")
        
        log_message("INFO", "=========================")
    except Exception as e:
        log_message("ERROR", f"Error printing planner debug log: {e}")

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    message = request.message
    player = request.player

    # Create a unique RequestContext for this request
    ctx = RequestContext(user_message=message)
    ctx.set_state(RequestState.QUEUED)
    log_message("INFO", f"{ctx.prefix()} Chat request received: '{message[:80]}{'...' if len(message) > 80 else ''}'")

    final_reply_str = None
    try:
        reply = await asyncio.wait_for(
            _run_chat_pipeline(message, player, ctx),
            timeout=_CHAT_PIPELINE_TIMEOUT_S,
        )
        final_reply_str = reply.reply
        return reply
    except asyncio.TimeoutError:
        # The pipeline exceeded the overall budget – finalize the context and
        # return a graceful HTTP 200 response so the Minecraft mod displays a
        # user-friendly message rather than "AI server unavailable."
        try:
            from request_context import FailureCategory
            ctx.set_failure(FailureCategory.REQUEST_BUDGET_EXCEEDED)
        except Exception:
            pass
        ctx.set_state(RequestState.FAILED)
        ctx.finalize(status="timeout")
        resource_manager.update_diagnostics(ctx)
        log_message("ERROR", (
            f"{ctx.prefix()} [REQUEST_BUDGET_EXCEEDED] Chat pipeline exceeded "
            f"{_CHAT_PIPELINE_TIMEOUT_S}s overall timeout. "
            f"Elapsed: {ctx.response_time_ms}ms."
        ))
        fallback_reply = "I'm taking too long to respond right now. Please try again in a moment."
        final_reply_str = fallback_reply
        return ChatResponse(
            reply=fallback_reply,
            tool_calls=[],
        )
    except Exception as unhandled:
        # Safety net: any unhandled exception must not crash the backend.
        try:
            from request_context import FailureCategory
            ctx.record_exception(unhandled, failure_category=FailureCategory.UNKNOWN_PROVIDER_EXCEPTION)
        except Exception:
            pass
        ctx.set_state(RequestState.FAILED)
        ctx.finalize(status="error")
        resource_manager.update_diagnostics(ctx)
        log_message("ERROR", (
            f"{ctx.prefix()} [UNHANDLED_EXCEPTION] Unexpected error in chat pipeline: "
            f"{type(unhandled).__name__}: {unhandled}"
        ))
        fallback_reply = "An unexpected internal error occurred. Please try again."
        final_reply_str = fallback_reply
        return ChatResponse(
            reply=fallback_reply,
            tool_calls=[],
        )
    finally:
        try:
            from eval_recorder import record_evaluation
            player_dict = player.model_dump() if hasattr(player, "model_dump") else (player.dict() if hasattr(player, "dict") else {})
            record_evaluation(ctx, player_dict, request.screenshot, final_reply_str)
        except Exception as eval_err:
            log_message("ERROR", f"Failed to record evaluation: {eval_err}")


async def _run_chat_pipeline(
    message: str,
    player,
    ctx: RequestContext,
) -> ChatResponse:
    """
    The actual chat pipeline, extracted so that chat_endpoint can wrap it
    in asyncio.wait_for() without nesting try/except logic.
    """
    # ── Stage 1: Planning ────────────────────────────────────
    ctx.set_state(RequestState.PLANNING)
    ctx.begin_stage("pipeline:planner")
    planned_result: PlannerResult
    try:
        planned_result = await run_in_threadpool(plan, message, player, ctx=ctx)
        ctx.end_stage()
    except Exception as e:
        try:
            from request_context import FailureCategory
            category = FailureCategory.PLANNER_TIMEOUT if isinstance(e, TimeoutError) else FailureCategory.UNKNOWN_PROVIDER_EXCEPTION
            ctx.end_stage(error=str(e), failure_category=category)
            ctx.record_exception(e, failure_category=category)
        except Exception:
            ctx.end_stage(error=str(e))
            ctx.record_exception(e)
        ctx.set_state(RequestState.FAILED)
        ctx.finalize(status="error")
        resource_manager.update_diagnostics(ctx)
        log_message("ERROR", f"{ctx.prefix()} Planner exception: {type(e).__name__}: {e}")
        return ChatResponse(
            reply=f"Sorry, my planning engine encountered an error: {type(e).__name__}. Please try again.",
            tool_calls=[]
        )

    # Instantiate response generator (reads active model profile)
    generator = ResponseGenerator()

    # ── Stage 2: Tool Execution ──────────────────────────────
    if planned_result.tool_calls:
        ctx.set_state(RequestState.EXECUTING_TOOLS)
        ctx.begin_stage("pipeline:tool_execution")
        replies = []
        for tool_call in planned_result.tool_calls:
            log_message("INFO", f"{ctx.prefix()} Planner selected {tool_call.tool.upper()}")
            ctx.tool_calls_made.append(tool_call.tool)

            # Format argument description for logging
            if tool_call.tool in ["save_location", "load_location"]:
                log_arg = tool_call.arguments.get("name", "")
            elif tool_call.tool == "save_note":
                log_arg = tool_call.arguments.get("key", "")
            elif tool_call.tool == "list_locations":
                log_arg = ""
            else:
                log_arg = str(tool_call.arguments)

            log_exec_str = f"{tool_call.tool.upper()}({log_arg})"
            log_message("INFO", f"{ctx.prefix()} {log_exec_str}")

            tool_start = time.time()
            tool_exc_val = None
            try:
                result = await run_in_threadpool(registry.execute, tool_call.tool, player, tool_call.arguments)
                tool_success = result.success
            except Exception as tool_exc:
                log_message("ERROR", f"{ctx.prefix()} Tool execution exception for '{tool_call.tool}': {tool_exc}")
                result = ToolResult(
                    success=False,
                    message=f"Tool '{tool_call.tool}' raised an exception: {tool_exc}",
                    error=str(tool_exc),
                    tool_name=tool_call.tool
                )
                tool_success = False
                tool_exc_val = str(tool_exc)

            tool_duration = round((time.time() - tool_start) * 1000, 2)

            # Record last executed tool details on request context
            ctx.last_executed_tool = tool_call.tool
            ctx.tool_execution_time_ms = tool_duration
            ctx.tool_status = "success" if tool_success else "failure"
            ctx.tool_output = result.message
            ctx.tool_exception = tool_exc_val

            # Record execution verification details
            is_valid_result = isinstance(result, ToolResult) and hasattr(result, "success") and hasattr(result, "message")
            if hasattr(ctx, "execution_verification") and isinstance(ctx.execution_verification, dict):
                ctx.execution_verification["tool_execution_success"][tool_call.tool] = tool_success
                ctx.execution_verification["valid_tool_result"][tool_call.tool] = is_valid_result

            # Record tool result message
            if not hasattr(ctx, "tool_execution_results"):
                ctx.tool_execution_results = []
            ctx.tool_execution_results.append(f"{tool_call.tool}: {'Success' if tool_success else 'Failed'} ({result.message[:60]})")

            try:
                resource_manager.record_tool_execution(generator.model_name, success=tool_success)
            except Exception:
                pass

            if not tool_success:
                log_message("ERROR", f"{ctx.prefix()} Tool execution failed: {result.message}")

            replies.append(result.message)

        ctx.end_stage()
        combined_reply = "\n".join(replies)

        # ── Stage 3: Response Generation ────────────────────
        ctx.set_state(RequestState.GENERATING_RESPONSE)
        ctx.begin_stage("pipeline:response_generation")
        final_reply = await run_in_threadpool(
            generator.generate_response,
            planned_result.response_strategy,
            message,
            player,
            combined_reply,
            planned_result.reply,
            ctx=ctx
        )
        ctx.end_stage()

        ctx.set_state(RequestState.SENDING_RESPONSE)
        ctx.finalize(status="success")
        resource_manager.update_diagnostics(ctx)

        # Log the detailed planner log block
        log_planner_debug(ctx, planned_result)

        ctx.set_state(RequestState.COMPLETED)
        log_message("INFO", f"{ctx.prefix()} Request complete – strategy={planned_result.response_strategy} tools={ctx.tool_calls_made} time={ctx.response_time_ms}ms")
        log_message("INFO", ctx.get_timeline_summary())

        return ChatResponse(reply=final_reply, tool_calls=planned_result.tool_calls)

    # ── Stage 3: Conversational Response (no tools) ──────────
    ctx.set_state(RequestState.GENERATING_RESPONSE)
    ctx.begin_stage("pipeline:response_generation")
    final_reply = await run_in_threadpool(
        generator.generate_response,
        planned_result.response_strategy,
        message,
        player,
        "",
        planned_result.reply,
        ctx=ctx
    )
    ctx.end_stage()

    ctx.set_state(RequestState.SENDING_RESPONSE)
    ctx.finalize(status="success")
    resource_manager.update_diagnostics(ctx)

    # Direct verify: no tools were needed, so verification status is success
    if hasattr(ctx, "execution_verification") and isinstance(ctx.execution_verification, dict):
        ctx.execution_verification["verification_status"] = "success"

    # Log the detailed planner log block
    log_planner_debug(ctx, planned_result)

    ctx.set_state(RequestState.COMPLETED)
    log_message("INFO", f"{ctx.prefix()} Request complete – strategy={planned_result.response_strategy} time={ctx.response_time_ms}ms")
    log_message("INFO", ctx.get_timeline_summary())

    return ChatResponse(reply=final_reply, tool_calls=[])



# ─────────────────────────────────────────────────────────────
# Static Dashboard mount
# ─────────────────────────────────────────────────────────────

dashboard_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dashboard", "dist"))
if os.path.exists(dashboard_dist):
    app.mount("/dashboard", StaticFiles(directory=dashboard_dist, html=True), name="dashboard")

    @app.get("/")
    def redirect_to_dashboard():
        return RedirectResponse(url="/dashboard/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
