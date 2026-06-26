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

### Phase 4A – Environment Awareness & World Perception

The AI assistant gains the ability to observe, inspect, and reason about the Minecraft world without modifying it. This phase focuses entirely on collecting information through read-only tools so the assistant can make informed decisions before taking actions in later phases. The AI should be able to query nearby blocks, entities, inventory contents, held items, equipped armor, player status, weather, world time, light levels, and scan surrounding areas. Example capabilities include answering questions such as "What resources are around me?", "Do I have enough wood to build a house?", "Are there any hostile mobs nearby?", or "Where is the nearest village?". No tool introduced in this phase may alter the game world, execute commands, place blocks, or change player state. The objective is to establish complete environmental awareness and contextual reasoning while maintaining a strictly read-only interaction model.


### Phase 4B – World Interaction & Intelligent Actions

Building upon the environmental awareness developed in Phase 4A, the AI assistant gains the ability to safely interact with and modify the Minecraft world through validated tools. This includes placing and breaking blocks, filling or replacing regions, executing approved Minecraft commands, summoning entities, generating structures, laying foundations, interacting with inventories, and performing other controlled world modifications. All actions must be executed through the existing Tool Registry with strict argument validation, safety checks, logging, and error handling—never through arbitrary code execution. The AI should reason about the current environment before acting, enabling natural requests such as "Lay down a 10×10 stone foundation here", "Summon a zombie wearing diamond armor", "Place a diamond ore vein beneath me", or "Build the outline of a small wooden house." This phase marks the transition from an intelligent observer to an intelligent actor while preserving the project's modular architecture, safety-first design, and provider-independent planning system.


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
