import os
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

# Load environment variables
load_dotenv()

app = FastAPI(title="AI Minecraft Assistant Backend")

# Setup CORS for the Dashboard to communicate
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Log file path relative to this backend file
LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "aiassistant.log")

def log_message(level: str, message: str) -> None:
    """
    Logs messages to console stdout and appends to logs/aiassistant.log
    in the standard Mod log format.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}\n"
    # Print to console stdout
    print(f"[Backend] {log_entry.strip()}")
    # Write to file
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Failed to write to backend log file: {e}")

# Request/Response schemas
class ChatRequest(BaseModel):
    message: str
    player: PlayerContext
    memory: dict = {}

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
        if "PLANNER SELECTED" in msg_upper or "TOOL EXECUTION" in msg_upper or "TOOL CALL" in msg_upper or any(t.upper() in msg_upper for t in ["SAVE_LOCATION", "LOAD_LOCATION", "LIST_LOCATIONS", "SAVE_NOTE", "GET_PLAYER_STATUS", "GET_HELD_ITEM", "GET_EQUIPMENT", "GET_INVENTORY", "GET_WEATHER", "GET_TIME", "GET_LIGHT_LEVEL", "GET_NEARBY_BLOCKS", "SCAN_AREA", "FIND_NEAREST", "GET_NEARBY_ENTITIES", "GET_BIOME"]):
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

# Endpoints
@app.get("/health")
def health_check():
    resource_manager.record_launcher_heartbeat()
    return {"status": "healthy"}

@app.get("/api/resources/stats")
def get_resource_stats():
    return resource_manager.get_stats()

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

@app.get("/api/providers")
def get_providers():
    config = load_config()
    providers_list = []
    
    gemini_avail = bool(os.getenv("GEMINI_API_KEY"))
    providers_list.append({
        "id": "gemini",
        "name": "Google Gemini",
        "available": gemini_avail,
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash", "gemini-1.5-pro"],
        "default_model": "gemini-2.5-flash"
    })
    
    providers_list.append({
        "id": "mock",
        "name": "Mock Provider (Testing)",
        "available": True,
        "models": ["mock-model"],
        "default_model": "mock-model"
    })
    
    return providers_list

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


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    message = request.message
    player = request.player

    # 1. Planner decision
    try:
        planned_result = plan(message, player)
    except Exception as e:
        log_message("ERROR", f"Planner exception: {str(e)}")
        return ChatResponse(
            reply=f"[Backend Error: Planner failed: {str(e)}]",
            tool_calls=[]
        )
    
    # 2. Execution Engine
    generator = ResponseGenerator()
    if planned_result.tool_calls:
        # Execute every ToolCall in order
        replies = []
        for tool_call in planned_result.tool_calls:
            log_message("INFO", f"Planner selected {tool_call.tool.upper()}")
            
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
            log_message("INFO", log_exec_str)
            
            # Execute tool via the registry
            result = registry.execute(tool_call.tool, player, tool_call.arguments)
            
            if result["status"] == "error":
                log_message("ERROR", f"Tool execution failed: {result['message']}")
                
            replies.append(result["message"])
            
        combined_reply = "\n".join(replies)
        final_reply = generator.generate_response(
            planned_result.response_strategy,
            message,
            player,
            combined_reply,
            planned_result.reply
        )
        return ChatResponse(
            reply=final_reply,
            tool_calls=planned_result.tool_calls
        )

    # 3. Conversational Response
    final_reply = generator.generate_response(
        planned_result.response_strategy,
        message,
        player,
        "",
        planned_result.reply
    )
    return ChatResponse(
        reply=final_reply,
        tool_calls=[]
    )

# Mount static files for React Dashboard if build exists
dashboard_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dashboard", "dist"))
if os.path.exists(dashboard_dist):
    app.mount("/dashboard", StaticFiles(directory=dashboard_dist, html=True), name="dashboard")
    
    @app.get("/")
    def redirect_to_dashboard():
        return RedirectResponse(url="/dashboard/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
