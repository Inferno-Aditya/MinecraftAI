# 🧱 MinecraftAI — In-Game AI Assistant

> A Fabric mod + Python backend that brings a context-aware, memory-persistent AI assistant directly into Minecraft Java Edition — powered by Google Gemini.

---

![Minecraft](https://img.shields.io/badge/Minecraft-1.21.1-green?logo=minecraft&logoColor=white)
![Fabric](https://img.shields.io/badge/Fabric_Loader-0.16.5-blue)
![Java](https://img.shields.io/badge/Java-21-orange?logo=openjdk)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-teal?logo=fastapi)
![Gemini](https://img.shields.io/badge/Gemini-3.5--flash-purple?logo=google)
![Version](https://img.shields.io/badge/Version-v0.4.0-blue?logo=github)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

<!-- BANNER: A future banner image showing the Minecraft game window with an AI chat reply visible in the chat box would be ideal here. -->

---

## Overview

**MinecraftAI** bridges Minecraft Java Edition and a large language model through a clean, local HTTP API. When a player types `/ai <message>`, the Fabric mod collects their full game context — position, inventory, equipment, nearby blocks, nearby entities, weather, world time, light level, and biome details — and sends it as structured JSON to a FastAPI backend running on `localhost:8000`. The backend passes the data through an LLM-powered **Planner**, which decides whether to:

1. **Execute a tool** (e.g., query player status, search inventory, scan the surrounding block layout, locate the nearest entity, or write to memory), or
2. **Return a conversational reply** (e.g., answer a question, respond to a joke).

The result is sent back to the mod, which displays it in the Minecraft chat. Crucially, the LLM **never executes tools itself** — it only decides *which* tools to call and *with what arguments*. All actual execution happens in validated Python code on the backend.

The system is designed around three principles: **provider abstraction** (swap Gemini for any other LLM by changing one config line), **tool extensibility** (add new capabilities by implementing a single abstract class), and **persistent memory** (locations and notes survive server restarts via `memory.json`).

---

## Features

### ✅ Current Features

- **`/ai <message>` Fabric command** — triggers the AI assistant in-game from any player message.
- **Environment & Player Perception** — automatically collects player position, health, hunger, saturation, experience progress/level, gamemode, dimension, inventory items, equipped gear, weather, time, light level, biome, nearby entities, and surrounding block data.
- **Short-Lived Scan Caching** — scans are cached within a single request context. Repeated queries for blocks or entities during a single planning pipeline reuse scan results to maintain zero lag.
- **Smart Block Scanning** — scans a 32-block cube without generating chunks. Distinguishes between filler blocks (stone, dirt, grass, sand, water, lava, etc.) and interesting blocks (ores, chests, wood, crops), capping coords to maintain low JSON payload sizes.
- **Entity Awareness** — captures nearby players, villagers, passive/hostile mobs, projectiles, and vehicles within a 64-block radius, including distance, health, and location.
- **Inventory Search & Filter** — supports partial-name queries and summaries for inventory checking (e.g. "Do I have enough wood?").
- **LLM Planner** — sends structured system + user prompts to Gemini and parses the structured JSON response.
- **Tool execution engine** — validates and dispatches LLM-selected tools in sequence.
- **Built-in tools:**
  - **Memory:** `save_location`, `load_location`, `list_locations`, `save_note`.
  - **Player Perception:** `get_player_status`, `get_held_item`, `get_equipment`, `get_inventory`.
  - **World Perception:** `get_weather`, `get_time`, `get_light_level`, `get_biome`.
  - **Environment Perception:** `get_nearby_blocks`, `scan_area`, `find_nearest`, `get_nearby_entities`.
- **Persistent memory** — `memory.json` survives server restarts; writes use atomic temp-file replacement to prevent corruption.
- **Memory injection into prompts** — known locations and notes are summarised and injected into every LLM call so the AI is always context-aware.
- **Automatic retry logic** — if the LLM returns malformed JSON or fails schema validation, the planner sends a correction prompt and retries once.
- **Provider abstraction** — `BaseLLMProvider` ABC lets you swap Gemini for any future provider without touching business logic.
- **Mock provider** — a fully deterministic rule-based `MockProvider` for offline development and unit testing.
- **Structured output enforcement** — Gemini is called with `response_mime_type: "application/json"` to minimise markdown wrapping.
- **Pydantic validation everywhere** — all tool arguments, player context, and API schemas are validated with Pydantic v2.
- **Dual logging** — all requests, responses, tool executions, and errors are logged to `logs/aiassistant.log` by both the mod (Java) and backend (Python).
- **Prompt debug logging** — every generated system + user prompt pair is saved to `logs/prompts/<timestamp>.txt` for inspection.
- **Graceful error handling** — backend offline, timeout, rate limiting, and malformed responses all result in a clean, friendly in-game message rather than a crash.
- **Health endpoint** — `GET /health` returns `{"status": "healthy"}` for uptime monitoring.
- **Unit test suite** — 37 tests across three test files covering memory, planner, tools, providers, retry logic, perception models, scanning calculations, and the full HTTP request/response cycle.

### 🔲 Planned Features (Phase 4B+)

- **Safe block placement and breaking tools** — allow the AI to construct or destroy blocks in defined, safe areas.
- **Whitelisted Minecraft commands** — AI-selected commands dispatched through the server console.
- **Multi-tool chaining with result passing** — allow a tool's output to feed the next tool's input.
- **Datapack generation** — generate and apply custom datapacks from natural language descriptions.
- **Multi-agent architecture** — multiple AI agents for different concerns (builder, advisor, memory manager).
- **Natural language world editing** — describe a structure in plain English and have it built.

---

## Demo

> Screenshots and recordings to be added once the project has a public release.

| Type | Placeholder |
|---|---|
| Screenshot | `docs/screenshot_chat.png` — AI reply displayed in Minecraft chat |
| GIF | `docs/demo.gif` — typing `/ai remember this place as home` and getting a confirmation |
| Video | `docs/demo.mp4` — full walkthrough: backend startup to in-game command to memory recall |

---

## Architecture

### System Flow
```mermaid
graph TD
    A["Player: /ai message"]
    B["Fabric Mod: AIAssistantMod.java"]
    C["FastAPI Backend: main.py (localhost:8000)"]
    D["Planner: planner.py"]
    E["Provider Factory: providers/__init__.py"]
    F["GeminiProvider: providers/gemini.py"]
    G["MockProvider: providers/mock.py"]
    H["Tool Registry: tools/registry.py"]
    I["Environment & Memory Tools"]
    M["memory.json: backend/memory/"]
    N["Prompt Logs: logs/prompts/"]
    O["aiassistant.log: logs/"]

    A -- "HTTP POST /chat (JSON)" --> B
    B -- "Async HTTP POST" --> C
    C --> D
    D -- "build_system_prompt" --> N
    D --> E
    E -- "provider=gemini" --> F
    E -- "provider=mock" --> G
    D -- "parse and validate JSON" --> H
    H --> I
    I -- "read/write" --> M
    C -- "ChatResponse reply + tool_calls" --> B
    B -- "Minecraft chat message" --> A
    C --> O
    B --> O
```

### Environment Awareness Scan Flow
```mermaid
graph TD
    A["Mod: handleAICommand"]
    B["Scan loaded chunks (radius 32)"]
    C["Separate filler vs interesting blocks"]
    D["Filter entities in radius 64"]
    E["Serialize to JSON & POST to backend"]
    F["Backend: PlayerContext model validation"]
    G["Tool execution: get_blocks_in_radius()"]
    H["Cache hit?"]
    I["Return cached results"]
    J["Perform filter & cache results"]
    
    A --> B
    B --> C
    A --> D
    C --> E
    D --> E
    E --> F
    F --> G
    G --> H
    H -- "Yes" --> I
    H -- "No" --> J
```

### Planner Pipeline
```mermaid
graph TD
    A["POST /chat request"]
    B["get_tool_definitions() from Registry"]
    C["get_memory_summary() from Memory"]
    D["build_system_prompt() with schemas"]
    E["build_user_prompt() with player context"]
    F["LLM Provider call (Gemini/Mock)"]
    G["parse_and_validate() JSON & schemas"]
    H["Parsing/Validation Success?"]
    I["Return PlannerResult"]
    J["Retry once with correction prompt"]
    K["Success?"]
    L["Fallback to friendly error reply"]
    
    A --> B
    A --> C
    B --> D
    C --> E
    D --> F
    E --> F
    F --> G
    G --> H
    H -- "Yes" --> I
    H -- "No" --> J
    J --> K
    K -- "Yes" --> I
    K -- "No" --> L
```

### Tool Execution Engine
```mermaid
graph TD
    A["PlannerResult with tool_calls"]
    B["For each ToolCall in sequence"]
    C["Resolve tool in Registry"]
    D["Validate arguments via Pydantic input_schema"]
    E["Execute tool with context & args"]
    F["Log execution to aiassistant.log"]
    G["Collect message & data response"]
    H["Combine replies and return ChatResponse"]

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    E --> G
    G --> H
```

### Component Descriptions

| Component | Location | Responsibility |
|---|---|---|
| **Fabric Mod** | `fabric-mod/.../AIAssistantMod.java` | Registers `/ai` command, scans chunks and entities, packages JSON context, displays replies in chat |
| **FastAPI Backend** | `backend/main.py` | Exposes `/chat` and `/health` endpoints, orchestrates planner and sequential tool execution |
| **PlayerContext** | `backend/context.py` | Pydantic model refactored into `PlayerInfo` and `EnvironmentSnapshot` with full backward compatibility |
| **Planner** | `backend/planner.py` | Builds prompts, calls LLM provider, parses/validates response structure, manages retry logic |
| **Provider Factory** | `backend/providers/__init__.py` | Factory function retrieving the configured `BaseLLMProvider` |
| **GeminiProvider** | `backend/providers/gemini.py` | Calls Google Gemini API with JSON mode and timeout configuration |
| **MockProvider** | `backend/providers/mock.py` | Rule-based LLM simulator supporting all Phase 2 and Phase 4A intents for offline tests |
| **Tool Registry** | `backend/tools/registry.py` | Manages tool registration, resolving, and argument validation |
| **BaseTool** | `backend/tools/base.py` | Abstract Base Class specifying tool properties (`name`, `description`, `input_schema`, `execute`) |
| **Memory Manager** | `backend/memory.py` | Persistent JSON memory storage using safe temp-file replacement |
| **Config Loader** | `backend/config.py` | Handles runtime configurations loaded on each request |

---

## PlayerContext Hierarchy

`PlayerContext` encapsulates all data gathered by the Fabric Mod and sent to the backend. It consists of two logical structures:

```mermaid
graph TD
    PlayerContext --> PlayerInfo
    PlayerContext --> EnvironmentSnapshot
    
    PlayerInfo --> name["name: str"]
    PlayerInfo --> uuid["uuid: str"]
    PlayerInfo --> pos["x, y, z, yaw, pitch: float"]
    PlayerInfo --> stats["health, food, saturation, experience, level, gamemode, dimension"]
    PlayerInfo --> inventory["inventory: List[InventorySlot]"]
    PlayerInfo --> equipment["equipment: EquipmentSlots"]
    PlayerInfo --> held_item["held_item: HeldItem"]
    
    EnvironmentSnapshot --> weather["weather: WeatherInfo"]
    EnvironmentSnapshot --> time_info["world_time: int, is_day, is_night, moon_phase"]
    EnvironmentSnapshot --> light["light_level: LightInfo"]
    EnvironmentSnapshot --> biome["biome: BiomeInfo"]
    EnvironmentSnapshot --> blocks["nearby_blocks: NearbyBlocksSnapshot"]
    EnvironmentSnapshot --> entities["nearby_entities: List[NearbyEntity]"]
```

### Pydantic Models Overview

- **`PlayerInfo`**: Represents the current player status (coordinates, health, level, inventory slots, equipped slots, held item details).
- **`EnvironmentSnapshot`**: Represents the state of the surrounding Minecraft world (weather, time, light level, biome details, nearby block counts, nearby entities).
- **`InventorySlot`**: Contains slot index, item ID, stack count, durability, custom display name, and enchantments.
- **`EquipmentSlots`**: Helmet, chestplate, leggings, boots, and offhand slots.
- **`WeatherInfo`**: Boolean flags for clear/rain/thunder, and ticks remaining.
- **`LightInfo`**: Sky light, block light, and combined light levels.
- **`BiomeInfo`**: Biome registry ID, temperature, rainfall, and inferred category.
- **`NearbyEntity`**: Entity ID, display name, category (hostile/passive/villager/etc.), distance, health, and absolute coordinates.
- **`NearbyBlocksSnapshot`**: Split into `filler_blocks` (stone, dirt, grass, etc. - count and nearest occurrence) and `interesting_blocks` (exact coordinates of chests, ores, etc.).

---

## Project Structure

```
minecraft/
├── README.md
├── Parameters.md               # Original project specification and vision
├── CHANGELOG.md                # Project changelog tracking versioned releases
├── .gitignore
│
├── backend/                    # Python FastAPI backend
│   ├── main.py                 # FastAPI app, /chat and /health endpoints, execution engine
│   ├── planner.py              # LLM planner: prompt generation, provider calls, retry logic
│   ├── context.py              # PlayerContext and perception Pydantic models
│   ├── memory.py               # Persistent memory: load, save, atomic write, summary
│   ├── config.py               # config.json loader with defaults
│   ├── config.json             # Runtime config: provider name and model
│   ├── .env                    # Secret keys (git-ignored)
│   ├── .env.example            # Template for .env
│   ├── requirements.txt        # Python dependencies
│   ├── test_phase2.py          # Unit tests: memory, tools, planner, player context
│   ├── test_phase3.py          # Integration tests: HTTP endpoints, retry, providers, config
│   ├── test_phase4a.py         # Perception tests: environment scanning, weather, entities, tools, cache
│   │
│   ├── providers/              # LLM provider abstraction layer
│   │   ├── __init__.py         # get_provider() factory function
│   │   ├── base.py             # BaseLLMProvider ABC
│   │   ├── gemini.py           # Google Gemini implementation
│   │   └── mock.py             # Deterministic mock for offline testing
│   │
│   ├── tools/                  # Tool registry and implementations
│   │   ├── __init__.py         # Re-exports registry singleton
│   │   ├── base.py             # BaseTool ABC
│   │   ├── registry.py         # ToolRegistry: register, resolve, validate, execute
│   │   ├── helpers.py          # Short-lived caching, Chebyshev scanning, direction math
│   │   ├── save_location.py    # Saves player coordinates to memory
│   │   ├── load_location.py    # Retrieves named coordinates from memory
│   │   ├── list_locations.py   # Lists all saved location names
│   │   ├── save_note.py        # Stores arbitrary key/value notes
│   │   ├── get_player_status.py # Queries player coordinates, health, level
│   │   ├── get_held_item.py    # Queries hand stack count and enchantments
│   │   ├── get_equipment.py   # Queries helmet, chestplate, boots, offhand
│   │   ├── get_inventory.py    # Lists inventory with optional search filters
│   │   ├── get_weather.py      # Queries clear/rain/thunder and remaining ticks
│   │   ├── get_time.py         # Queries world ticks and moon phases
│   │   ├── get_light_level.py  # Queries block, sky, and combined light levels
│   │   ├── get_nearby_blocks.py # Filters nearby blocks by Chebyshev radius
│   │   ├── scan_area.py        # Summarises ores, trees, liquids, and terrain Y variation
│   │   ├── find_nearest.py     # Locates nearest block/entity with direction angle
│   │   ├── get_nearby_entities.py # Lists nearby players, villagers, and mobs
│   │   └── get_biome.py        # Queries current biome, temp, rainfall
│   │
│   └── memory/
│       └── memory.json         # Persistent memory store (git-ignored)
│
├── fabric-mod/                 # Minecraft Fabric mod (Java)
│   ├── build.gradle            # Gradle build: Fabric Loom 1.7.4, Java 21
│   ├── gradle.properties       # Minecraft 1.21.1, Fabric Loader 0.16.5, mod version v0.4.0
│   ├── settings.gradle
│   ├── gradlew / gradlew.bat
│   └── src/main/
│       ├── java/net/example/aiassistant/
│       │   └── AIAssistantMod.java   # Mod entry point, /ai command, chunk scan, entity scan
│       └── resources/
│           └── fabric.mod.json       # Mod manifest: id, name, version, dependencies
│
└── logs/                       # Runtime logs (git-ignored)
    ├── aiassistant.log         # Unified request/response/error log
    └── prompts/                # Per-request prompt debug dumps
```

---

## Technology Stack

| Category | Technology | Version |
|---|---|---|
| **Minecraft** | Java Edition | 1.21.1 |
| **Mod Loader** | Fabric Loader | 0.16.5 |
| **Fabric API** | fabric-api | 0.102.0+1.21.1 |
| **Fabric Loom** | Build tooling | 1.7.4 |
| **Yarn Mappings** | Deobfuscation | 1.21.1+build.3 |
| **Java** | OpenJDK | 21 |
| **Python** | CPython | 3.10+ |
| **Web Framework** | FastAPI | >= 0.100.0 |
| **ASGI Server** | Uvicorn | >= 0.22.0 |
| **Data Validation** | Pydantic | >= 2.0.0 |
| **LLM (default)** | Google Gemini | Gemini 3.5 Flash |
| **Gemini SDK** | google-generativeai | >= 0.3.0 |
| **Env config** | python-dotenv | >= 1.0.0 |
| **HTTP (mod side)** | Java `java.net.http.HttpClient` | JDK 21 built-in |
| **JSON (mod side)** | Gson (via Fabric) | bundled |
| **Testing** | Python `unittest` + `fastapi.testclient` | stdlib |
| **Memory storage** | JSON file | — |

---

## Installation

### Prerequisites

- **Java 21** (JDK). The repo includes a bundled JDK at `fabric-mod/.java-21/` for the Gradle build.
- **Python 3.10+**
- **Minecraft Java Edition 1.21.1** with Fabric Loader 0.16.5 installed.
- A **Google Gemini API key** (free tier available at [aistudio.google.com](https://aistudio.google.com)).

---

### 1. Clone the Repository

```bash
git clone https://github.com/<your-username>/MinecraftAI.git
cd MinecraftAI
```

---

### 2. Set Up the Python Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

### 3. Configure the Backend

**Step 1 — Create your `.env` file:**

```bash
cp .env.example .env
```

Edit `.env` and replace with your actual key:

```env
GEMINI_API_KEY=your_actual_api_key_here
```

**Step 2 — Review `config.json`:**

```json
{
    "provider": "gemini",
    "model": "gemini-2.5-flash"
}
```

This selects the LLM provider and model. Currently supported providers: `gemini`, `mock`.

---

### 4. Start the Backend Server

```bash
# From inside the backend/ directory, with venv active
uvicorn main:app --host 127.0.0.1 --port 8000
```

Verify it is running:

```bash
curl http://127.0.0.1:8000/health
# → {"status":"healthy"}
```

The backend must be running before you launch Minecraft.

---

### 5. Build the Fabric Mod

```bash
cd ../fabric-mod

# Windows
gradlew.bat build

# macOS / Linux
./gradlew build
```

The compiled `.jar` will be at:

```
fabric-mod/build/libs/aiassistant-1.0.0.jar
```

---

### 6. Install the Mod and Launch Minecraft

1. Copy `aiassistant-1.0.0.jar` into your Minecraft `mods/` folder.
2. Ensure Fabric Loader **0.16.5** and **Fabric API** are installed.
3. Launch Minecraft 1.21.1 with the Fabric profile.
4. Join a world (singleplayer or server).
5. Type `/ai hello` in chat.

---

## Configuration

### `backend/config.json`

Runtime configuration for the backend. Loaded on every request; no server restart required.

| Field | Type | Default | Description |
|---|---|---|---|
| `provider` | `string` | `"gemini"` | LLM provider to use. Currently supports `"gemini"` or `"mock"`. |
| `model` | `string` | `"gemini-2.5-flash"` | Model name passed to the provider. For Gemini: any valid Gemini model ID. |
| `enable_prompt_logging` | `boolean` | `true` | If `true`, each LLM call writes a `logs/prompts/<timestamp>.txt` debug file. |

**Example — switch to mock provider for local testing:**

```json
{
    "provider": "mock",
    "model": "mock-model"
}
```

---

### `backend/.env`

Secret keys. Never committed to version control (listed in `.gitignore`).

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes (for Gemini) | Your Google Gemini API key. Get one at [aistudio.google.com](https://aistudio.google.com). |

---

### `backend/.env.example`

Checked-in template:

```env
# Secret Keys Configuration
# Replace with your actual Gemini API Key
GEMINI_API_KEY=YOUR_API_KEY
```

---

## Usage

All commands are entered in the Minecraft in-game chat. The `/ai` command accepts a free-form natural language message.

### Conversational Chat

```
/ai hello
```
> The AI responds with a friendly conversational reply. No tools are executed.

---

### Perception Queries (Phase 4A)

```
/ai check my status
```
> **Response:** `Player Steve status: Health 20.0/20, Hunger 20/20, Level 5, Gamemode survival, Dimension minecraft:overworld at X=120.4, Y=64.0, Z=-350.2.`

```
/ai what am i holding?
```
> **Response:** `Holding 1x minecraft:diamond_pickaxe (Enchantments: minecraft:efficiency 4). Durability: 1540 remaining.`

```
/ai what armor am i wearing?
```
> **Response:** `Equipped Gear: Helmet: minecraft:iron_helmet (minecraft:protection 1), Chestplate: minecraft:air, Leggings: minecraft:air, Boots: minecraft:air, Offhand: minecraft:shield.`

```
/ai do i have enough wood for a crafting table?
```
> **Response:** `Inventory Summary: - minecraft:oak_log: 12 - minecraft:torch: 4.` (Gemini will reason: "Yes, you have 12 oak logs, which is enough to make a crafting table.")

```
/ai is there lava nearby?
```
> **Response:** `Area Scan Report (Radius 16 in Biome: minecraft:plains): Terrain Y Range: 60 to 72, Blocks: Stone=2400, Trees/Leaves=0, liquids: Water=12, Lava=0.`

```
/ai where is the closest water?
```
> **Response:** `Found nearest block 'minecraft:water' at coordinates [124, 63, -345] (4.5 blocks away, direction: North).`

```
/ai are there monsters close to me?
```
> **Response:** `Nearby entities in radius 64m: - Hostile Mobs: Zombie (12.4m), Creeper (24.1m).`

```
/ai what biome am i in?
```
> **Response:** `You are currently in the biome 'minecraft:plains' (Category: plains, Temperature: 0.80, Rainfall: 0.40).`

---

### Memory & Notes

```
/ai remember this place as home
```
> **Response:** `Saved location 'home' at coordinates x=-109.6, y=71.0, z=-85.3 in minecraft:overworld.`

```
/ai where is home
```
> **Response:** `Loaded location 'home': coordinates are x=-109.6, y=71.0, z=-85.3 in minecraft:overworld.`

```
/ai list locations
```
> **Response:** `Saved locations: base, home.`

```
/ai remember that my dog is named buddy
```
> **Response:** `Saved note for 'dog_name': 'buddy'.`

---

## Tool System

Every tool must subclass `BaseTool` (`backend/tools/base.py`) and implement four abstract properties and one method:

```python
class BaseTool(ABC):
    name: str           # Unique identifier used by the planner and registry
    description: str    # Injected verbatim into the system prompt
    input_schema: Type[BaseModel]   # Pydantic model; JSON schema is serialised into the system prompt
    usage_examples: List[str]       # Natural language examples injected into the system prompt

    def execute(self, context: PlayerContext, arguments: Dict[str, Any]) -> Dict[str, Any]:
        # Must return {"status": "success"|"error", "message": str, "success": bool, "data": ..., "metadata": ...}
```

### Registered Tools

| Category | Tool Name | Arguments Schema | Description |
|---|---|---|---|
| **Memory** | `save_location` | `name: str` | Saves player's current coordinate context to persistent storage |
| **Memory** | `load_location` | `name: str` | Retrieves coordinate context for a saved name |
| **Memory** | `list_locations` | *(none)* | Returns all saved location names in memory |
| **Memory** | `save_note` | `key: str`, `value: str` | Saves a persistent note key/value pair |
| **Player** | `get_player_status` | *(none)* | Queries health, hunger, coordinates, rotation, level, dimension |
| **Player** | `get_held_item` | *(none)* | Queries held item in main hand (name, count, durability, enchantments) |
| **Player** | `get_equipment` | *(none)* | Queries helmet, chestplate, leggings, boots, offhand slots |
| **Player** | `get_inventory` | `search: Optional[str]` | Lists inventory items with optional partial name filter |
| **World** | `get_weather` | *(none)* | Queries rain, thunder, clear weather state, and time remaining |
| **World** | `get_time` | *(none)* | Queries world ticks, day/night status, and moon phase name |
| **World** | `get_light_level` | *(none)* | Queries block light, sky light, and combined light levels |
| **World** | `get_biome` | *(none)* | Queries current biome ID, temperature, rainfall, and category |
| **Environment** | `get_nearby_blocks` | `radius: int = 16` | Lists block types, counts, and nearest coordinates (radius 1-64) |
| **Environment** | `scan_area` | `radius: int = 16` | Returns structured high-level summary of surroundings and Y variation |
| **Environment** | `find_nearest` | `target_type: str` | Locates nearest block or entity matching query with relative direction |
| **Entities** | `get_nearby_entities` | `radius: int = 64` | Lists nearby players, villagers, passive/hostile mobs with distance |

### Execution Flow

```
POST /chat
  → plan(message, player_context)
      → build_system_prompt()        # inject tool schemas dynamically from registry
      → build_user_prompt()          # inject player context + memory summary
      → provider.generate()          # call LLM
      → parse_and_validate()         # validate JSON + tool args via Pydantic
      → PlannerResult
  → for tool_call in planned_result.tool_calls:
      → registry.execute(tool_name, player, arguments)
          → tool.input_schema(**arguments)  # Pydantic validation
          → tool.execute(context, args)     # business logic with cache lookup
          → {"status", "message", "success", "data", "metadata"}
  → ChatResponse(reply, tool_calls)
```

---

## Testing

The project uses Python's built-in `unittest` framework with `fastapi.testclient` for integration tests.

### Running Tests

```bash
cd backend

# Run Phase 2 tests (memory, tools, planner)
python -m unittest test_phase2.py

# Run Phase 3 tests (endpoints, retry, providers, config)
python -m unittest test_phase3.py

# Run Phase 4A tests (perception, scanning, caching, tools)
python -m unittest test_phase4a.py

# Run all tests
python -m unittest discover -s .
```

---

## Logging

### `logs/aiassistant.log`

A unified append-only log written by both the Fabric mod (Java) and the FastAPI backend (Python) using the same format:

```
[2026-06-26 18:52:02] [INFO] Planning via provider 'gemini' using model 'gemini-2.5-flash'
[2026-06-26 18:52:03] [INFO] LLM responded in 0.94s
[2026-06-26 18:52:03] [INFO] Planner selected GET_PLAYER_STATUS
[2026-06-26 18:52:03] [INFO] GET_PLAYER_STATUS()
```

### Prompt Debug Logging

Every generated system + user prompt pair is saved to `logs/prompts/<timestamp>.txt` for debugging unexpected planner behavior. Can be disabled by setting `"enable_prompt_logging": false` in `config.json`.

---

## Roadmap

```
Phase 1 — Foundation                                     [COMPLETE]
  Fabric mod loads and registers /ai command
  Player context collection (XYZ, dimension, biome, health, food, gamemode, world time)
  Async HTTP POST to local FastAPI backend
  Gemini LLM integration
  Formatted reply displayed in Minecraft chat
  Graceful error handling (offline, timeout, bad JSON)
  Unified dual logging (mod + backend)

Phase 2 — Memory and Tools                               [COMPLETE]
  Persistent memory.json with atomic writes and corruption recovery
  save_location / load_location / list_locations / save_note tools
  Pydantic validation on all tool arguments
  Tool registry with structured success/error responses
  Memory summary injection into LLM prompts
  Unit test suite (9 tests)

Phase 3 — Planner Hardening and Integration Testing      [COMPLETE]
  Dynamic tool definition injection into system prompt
  Provider abstraction (BaseLLMProvider, factory pattern)
  MockProvider for offline/test mode
  Structured JSON output enforcement (Gemini JSON mode)
  Malformed JSON retry with correction prompt
  Validation failure fallback to friendly error reply
  Prompt debug logging to logs/prompts/
  Full integration test suite via FastAPI TestClient (10 tests)
  LLM latency measurement and logging

Phase 4A — Environment Awareness & World Perception      [COMPLETE]
  Refactored PlayerContext into PlayerInfo & EnvironmentSnapshot
  Loaded chunk-safe scanning & entity distance filtering
  Radius configuration, validation & clamping (1-64)
  Optimized filler block aggregation & interesting block coord listing
  Short-lived cache for single-request performance optimization
  12 new tools for player, world, environment, and entity awareness
  Comprehensive tests for perception models & calculations (18 tests)

Phase 4B — World Interaction & Intelligent Actions       [PLANNED]
  Safe block placement & breaking tools
  Consolidation of server whitelisted command dispatches
  Chaining results across multiple tool dispatches
  Natural language structure generation blueprints

Phase 5 — Advanced Capabilities                          [PLANNED]
  Datapack generation from natural language
  Custom item definitions
  Structure blueprints

Phase 6 — Multi-Agent and Ecosystem                      [PLANNED]
  Multi-agent architecture (builder, advisor, memory manager)
  Additional LLM providers (OpenAI, Ollama, OpenRouter)
  Natural language world editing
```

---

## Contributing

Contributions are welcome. Please follow the conventions already established in the codebase.

### Coding Style

- **Python**: Follow PEP 8. All public functions and classes must have docstrings. Use Pydantic v2 models for all data validation.
- **Java**: Follow standard Java conventions. Keep code clean and async where possible.
- **Commit messages**: Use imperative present tense (`Add save_note tool`, not `Added save_note tool`).

### Architecture Philosophy

- **Observe before acting.** Environment perception must be complete and read-only before any interaction tools are created.
- **The LLM is a planner, not an executor.** The AI decides *what* to do but never *does* it. This prevents prompt injection, runaway tool calls, and hallucinated operations from affecting game state. Every tool call is validated against a Pydantic schema before it reaches any business logic.
- **Extensibility is structural, not accidental.** Adding a new tool, a new LLM provider, or a new memory category does not require modifying existing files — only adding new ones and registering them in the registry.
- **Fail gracefully, always.** Every network call, file operation, JSON parse, and schema validation is wrapped to return a user-visible message rather than crash the game or the server.
- **Offline-first testing.** The `MockProvider` and test isolation mean the entire backend can be developed and tested without a Minecraft instance or an API key.

---

## Acknowledgements

- **[Fabric](https://fabricmc.net/)** — the lightweight, modular Minecraft mod loader.
- **[FastAPI](https://fastapi.tiangolo.com/)** — the high-performance Python web framework with first-class Pydantic integration.
- **[Pydantic](https://docs.pydantic.dev/)** — for robust, readable data validation across the entire backend.
- **[Google Gemini](https://ai.google.dev/)** — the LLM powering the planning engine.
- **[Gson](https://github.com/google/gson)** — JSON serialisation in the Fabric mod.
- **[python-dotenv](https://github.com/theskumar/python-dotenv)** — clean secret management.

---

## License

This project is licensed under the **MIT License** — see `fabric.mod.json` which declares `"license": "MIT"`.

```
MIT License

Copyright (c) 2026 MinecraftAI Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
