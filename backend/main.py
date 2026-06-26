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
    from planner import plan, ToolCall
except ImportError:
    from .planner import plan, ToolCall

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
    planned_calls = plan(message, player)
    
    if planned_calls:
        # We have a tool call planned
        tool_call = planned_calls[0]  # Regex planner returns at most 1 tool call
        
        # Log planner decision separately
        log_message("INFO", f"Planner selected {tool_call.tool.upper()}")
        
        # Format logging for tool execution
        if tool_call.tool in ["save_location", "load_location"]:
            log_arg = tool_call.arguments.get("name", "")
        elif tool_call.tool == "save_note":
            log_arg = tool_call.arguments.get("key", "")
        elif tool_call.tool == "list_locations":
            log_arg = ""
        else:
            log_arg = str(tool_call.arguments)
            
        log_exec_str = f"{tool_call.tool.upper()}({log_arg})"
        # Log every tool execution
        log_message("INFO", log_exec_str)
        
        # Execute tool via the registry
        result = registry.execute(tool_call.tool, player, tool_call.arguments)
        
        if result["status"] == "error":
            log_message("ERROR", f"Tool execution failed: {result['message']}")
            
        return ChatResponse(
            reply=result["message"],
            tool_calls=planned_calls
        )

    # 2. LLM Provider or Mock fallback if no tool is planned
    provider = os.getenv("AI_PROVIDER", "").lower()
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    reply_text = ""

    # Gemini Integration
    if provider == "gemini" and gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            
            system_prompt = (
                f"You are a helpful AI assistant inside Minecraft playing with {player.name}. "
                f"Here is the player's context:\n"
                f"- Position: X={player.x:.1f}, Y={player.y:.1f}, Z={player.z:.1f}\n"
                f"- Dimension: {player.dimension}\n"
                f"- Gamemode: {player.gamemode}\n"
                f"- Health: {player.health}/20\n"
                f"- Food Level: {player.food}/20\n"
                f"- Biome: {player.biome}\n"
                f"- World Time: {player.world_time}\n"
                f"Answer the player's message in a short, friendly, conversational tone (Minecraft chat format)."
            )
            response = model.generate_content([system_prompt, message])
            reply_text = response.text.strip()
        except Exception as e:
            reply_text = f"[Backend Error: Gemini API failed: {str(e)}]"

    # OpenAI Integration
    elif provider == "openai" and openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            
            system_prompt = (
                f"You are a helpful AI assistant inside Minecraft playing with {player.name}. "
                f"Here is the player's context:\n"
                f"- Position: X={player.x:.1f}, Y={player.y:.1f}, Z={player.z:.1f}\n"
                f"- Dimension: {player.dimension}\n"
                f"- Gamemode: {player.gamemode}\n"
                f"- Health: {player.health}/20\n"
                f"- Food Level: {player.food}/20\n"
                f"- Biome: {player.biome}\n"
                f"- World Time: {player.world_time}\n"
                f"Answer the player's message in a short, friendly, conversational tone."
            )
            
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ]
            )
            reply_text = completion.choices[0].message.content.strip()
        except Exception as e:
            reply_text = f"[Backend Error: OpenAI API failed: {str(e)}]"

    # Mock Fallback
    else:
        reply_text = (
            f"Hello, {player.name}! This is the local backend. I received your message: '{message}'.\n"
            f"Context: Location: {player.x:.1f}, {player.y:.1f}, {player.z:.1f} in {player.dimension} "
            f"({player.biome} biome), Health: {player.health:.1f}/20.0, Gamemode: {player.gamemode}."
        )

    return ChatResponse(
        reply=reply_text,
        tool_calls=[]
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
