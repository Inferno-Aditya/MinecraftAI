import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="AI Minecraft Assistant Backend")

# Request/Response schemas
class PlayerContext(BaseModel):
    name: str
    x: float
    y: float
    z: float
    yaw: float
    pitch: float
    dimension: str
    gamemode: str
    health: float
    food: int
    world_time: int
    biome: str = "unknown"

class ChatRequest(BaseModel):
    message: str
    player: PlayerContext
    memory: dict = {}

class ChatResponse(BaseModel):
    reply: str
    tool_calls: list = []

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    message = request.message
    player = request.player

    # Get configuration from env
    provider = os.getenv("AI_PROVIDER", "").lower()
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    reply_text = ""

    # 1. Gemini Integration
    if provider == "gemini" and gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            
            # Formulate prompt with player context
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

    # 2. OpenAI Integration
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

    # 3. Mock Fallback
    else:
        # Generate an informative mock response illustrating successful parsing of request context
        time_formatted = f"{player.world_time} ticks"
        reply_text = (
            f"Hello, {player.name}! This is the local backend. I received your message: '{message}'.\n"
            f"Context: Location: {player.x:.1f}, {player.y:.1f}, {player.z:.1f} in {player.dimension} "
            f"({player.biome} biome), Health: {player.health:.1f}/20.0, Gamemode: {player.gamemode}."
        )

    return ChatResponse(
        reply=reply_text,
        tool_calls=[] # Tool calls are Phase 2 functionality
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
