import os
import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import List, Dict, Any

try:
    from context import PlayerContext
except ImportError:
    from .context import PlayerContext

try:
    from planner import plan, ToolCall, PlannerResult
except ImportError:
    from .planner import plan, ToolCall, PlannerResult

try:
    from tools import registry
except ImportError:
    from .tools import registry

# Load environment variables
load_dotenv()

app = FastAPI(title="AI Minecraft Assistant Backend")

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

@app.get("/health")
def health_check():
    return {"status": "healthy"}

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
        return ChatResponse(
            reply=combined_reply,
            tool_calls=planned_result.tool_calls
        )

    # 3. Conversational Response
    return ChatResponse(
        reply=planned_result.reply,
        tool_calls=[]
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
