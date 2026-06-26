# Parameters.md --- AI Minecraft Assistant (Phase 1)

## Vision

Build a Fabric mod for Minecraft Java that provides an AI assistant
inside the game. The assistant is triggered with `/ai <message>` and
can: - Chat with the player. - Read game context. - Remember information
across sessions. - Execute safe tools through a backend API.

## Scope (Phase 1 ONLY)

Goals: 1. Fabric mod loads successfully. 2. Register `/ai` command. 3.
Send prompt to local backend. 4. Receive AI response. 5. Print response
in Minecraft chat.

Do NOT implement block placement, world editing, or autonomous gameplay
yet.

------------------------------------------------------------------------

# Architecture

Minecraft (Fabric Mod) → HTTP Client → Local FastAPI Server
(localhost:8000) → LLM Provider → JSON Response → Minecraft Chat

The Fabric mod never calls the LLM directly except through the local
backend.

------------------------------------------------------------------------

# Tech Stack

Minecraft: Java Edition Mod Loader: Fabric Language (Mod): Java Backend:
Python + FastAPI Transport: HTTP (JSON) Memory: JSON files AI:
Configurable (OpenAI/Gemini/OpenRouter/etc.)

------------------------------------------------------------------------

# Commands

/ai `<message>`{=html}

Examples: - /ai hello - /ai where am i - /ai remember this place as home

Unknown commands should never crash the game.

------------------------------------------------------------------------

# Request JSON

{ "message": "remember this place as home", "player": { "name": "...",
"x": 0, "y": 64, "z": 0, "yaw": 0, "pitch": 0, "dimension":
"minecraft:overworld", "gamemode": "survival", "health": 20, "food": 20,
"world_time": 0 }, "memory": {} }

------------------------------------------------------------------------

# Response JSON

{ "reply": "Okay, I'll remember this location.", "tool_calls": \[ {
"tool": "save_location", "arguments": { "name": "home" } } \] }

The mod displays reply. The backend executes validated tool calls.

------------------------------------------------------------------------

# Memory

Store memory in: config/aiassistant/memory.json

Example:

{ "locations": { "home": { "dimension": "minecraft:overworld", "x": 100,
"y": 64, "z": -250 } } }

Memory categories: - Locations - Notes - Preferences - Future expansion

------------------------------------------------------------------------

# Available Context

Collect automatically: - Player name - XYZ - Rotation - Dimension -
Health - Hunger - Gamemode - World time - Biome (if easily available) -
F3-equivalent values where practical

Do not require player to type these.

------------------------------------------------------------------------

# Backend Endpoints

POST /chat GET /health

Future: POST /tools POST /memory/save POST /memory/load

------------------------------------------------------------------------

# Tool System

Never allow arbitrary AI code execution.

Supported tool interface:

save_location(name) load_location(name) execute_command(command)
get_player_info()

Every tool: - Validate arguments. - Return success/failure. - Never
crash.

------------------------------------------------------------------------

# Error Handling

If backend offline: "AI server unavailable."

If timeout: "AI request timed out."

If invalid JSON: Ignore tool calls and show safe error.

------------------------------------------------------------------------

# Logging

Create logs: logs/aiassistant.log

Log: - Requests - Responses - Errors - Tool executions

Never log API keys.

------------------------------------------------------------------------

# Folder Structure

fabric-mod/ backend/ memory/ logs/ config/

------------------------------------------------------------------------

# Future Roadmap (Not Phase 1)

Phase 2: - Persistent memory - Tool execution

Phase 3: - Place blocks - Build structures - Inventory awareness

Phase 4: - Generate datapacks - Custom items - Custom mobs

Phase 5: - AI-assisted mod generation - Multi-agent architecture -
Natural language world editing

------------------------------------------------------------------------

# Development Principles

-   Modular.
-   Safe tool execution.
-   Backend independent of AI provider.
-   Extensible tool registry.
-   Clear JSON contracts.
-   Fail gracefully.
-   Document public interfaces.
