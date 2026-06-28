# 🧱 MinecraftAI — Context-Aware In-Game AI Companion

> A modular Fabric mod and Python FastAPI backend system that brings a context-aware, memory-persistent, and rate-guarded AI assistant directly into Minecraft Java Edition — powered by Google Gemini.

---

[![Minecraft](https://img.shields.io/badge/Minecraft-1.21.1-green?logo=minecraft&logoColor=white)](https://www.minecraft.net/)
[![Fabric](https://img.shields.io/badge/Fabric-1.21.1-blue)](https://fabricmc.net/)
[![Java](https://img.shields.io/badge/Java-21-orange?logo=openjdk)](https://openjdk.org/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-teal?logo=fastapi)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 📖 Overview

**MinecraftAI** bridges Minecraft Java Edition with large language models (LLMs) through a local FastAPI gateway. When you type `/ai <message>` in game, the Fabric mod packages your real-time context (position, inventory, health, time, light levels, biomes, nearby blocks, and entities) and posts it to the backend. The backend processes the request via an intelligent **Intent Classifier** and **Planner Pipeline** to respond or call tools.

The companion supports three execution strategies:
1. **KNOWLEDGE**: Answer general gameplay, brewing, redstone, and recipe questions immediately using LLM knowledge without executing tools.
2. **TOOLS**: Directly execute perceptions (status check, inventory query, block scan) and output raw results.
3. **HYBRID**: Call perceptions first, then synthesize live game state with expert Minecraft knowledge to generate a conversational advice reply (e.g., *"Can I craft a shield?"*).

---

## 🏗️ System Architecture

The MinecraftAI core architecture is separated into a Java client side, a Windows background service manager, and a Python decision-making gateway:

```
                  ┌──────────────────────────────────────────────┐
                  │            Minecraft Client (Java)           │
                  │   [Fabric Mod] ──► /ai Command Trigger       │
                  │   [Context Collector] ──► Chunk/Entity Scan  │
                  └──────────────────────┬───────────────────────┘
                                         │ Async HTTP POST
                                         ▼
   ┌──────────────────────────────────────────────────────────────────────────┐
   │                         FastAPI Backend (Python)                         │
   │                                                                          │
   │   ┌─────────────────────┐   ┌───────────────────┐   ┌────────────────┐   │
   │   │  Intent Classifier  │──►│ Routing Validator │──►│ Prompt Builder │   │
   │   │ (Synonyms/Plurals)  │   │  (Contradictions) │   │ (Token Budget) │   │
   │   └─────────────────────┘   └───────────────────┘   └────────┬───────┘   │
   │                                                              │           │
   │   ┌─────────────────────┐   ┌───────────────────┐            │           │
   │   │   SQLite Database   │◄──│  Semantic Memory  │◄───────────┘           │
   │   │ (Facts & Episodes)  │   │ (Embeddings/L2)   │                        │
   │   └─────────────────────┘   └───────────────────┘                        │
   │                                                                          │
   │   ┌─────────────────────┐   ┌───────────────────┐   ┌────────────────┐   │
   │   │    Tool Registry    │◄──│  Response Synth   │◄──│ LLM Resource   │   │
   │   │ (21 validated tools)│   │(ResponseGenerator)│   │   Manager      │   │
   │   └─────────────────────┘   └───────────────────┘   └────────┬───────┘   │
   └──────────────────────────────────────────────────────────────┼───────────┘
                                                                  │ Rate-Guarded API
                                                                  ▼
                                                       ┌─────────────────────┐
                                                       │  Google Gemini API  │
                                                       └─────────────────────┘
```

### Core Subsystems

* **Intelligent Intent Classifier (`intent_classifier.py`)**: A rule-driven router utilizing regular expression plurals matching, synonym alias dictionaries, and spatial/entity tags to classify requests into `KNOWLEDGE`, `PLAYER`, `ENVIRONMENT`, `MEMORY`, `TOOL`, or `HYBRID` intents and assign confidence scores.
* **Planner Routing & Validation Layer (`planner.py`)**: Assesses planner decisions against classified intents, warning developers of overrides, and validating tool schemas before dispatching.
* **Prompt Token Budgeter (`ai/prompt_builder.py`, `ai/token_budget.py`)**: A priority-based prompt compiler that retrieves semantic memories, evaluates prompt sizes, and enforces a hard token budget to prevent context window overflow.
* **SQLite Semantic Memory (`memory/`)**: Stores episodic memories and extracted gameplay facts in a SQLite database (`memory.db`). Features SentenceTransformer embedding extraction and L2 cosine similarity search.
* **AI Resource Manager (`resource_manager.py`)**: Handles RPM/TPD/TPM rate limits, queues delayed requests, processes exponential backoffs (2s, 4s, 8s) on HTTP 429 errors, and persists token usage statistics to `usage_stats.json`.
* **React SPA Dashboard (`dashboard/`)**: A Minecraft-themed responsive web client served natively by FastAPI for memory editing, configuration mapping, log streaming, and live telemetry tracking.
* **Companion Windows Launcher (`MinecraftAICompanion.exe`)**: A C# WinForms background process that monitors Minecraft client lifecycles via WMI command filters, automatically launching or shutting down the FastAPI backend and preventing duplicate server instances.

---

## 🛠️ Implemented Perceptions & Tools

MinecraftAI comes equipped with **21 validated perception tools** across five core categories:

| Category | Tool Name | Arguments | Description |
| :--- | :--- | :--- | :--- |
| 💾 **Memory** | `save_location` | `name: str` | Saves the player's current coordinate and dimension context. |
| 💾 **Memory** | `load_location` | `name: str` | Retrieves coordinate context for a saved name. |
| 💾 **Memory** | `list_locations` | *(None)* | Lists all saved location names in memory. |
| 💾 **Memory** | `save_note` | `key: str`, `value: str` | Saves a persistent note key/value pair. |
| 👤 **Player** | `get_player_status` | *(None)* | Returns player coordinates, health, level, food, and dimension. |
| 👤 **Player** | `get_player_info` | *(None)* | Returns simplified coordinate and position summary. |
| 👤 **Player** | `get_health` | *(None)* | Returns detailed player health (HP). |
| 👤 **Player** | `get_food` | *(None)* | Returns player hunger, saturation, and food level. |
| 👤 **Player** | `get_held_item` | *(None)* | Queries active hand item details, count, durability, and enchantments. |
| 👤 **Player** | `get_equipment` | *(None)* | Queries helmet, chestplate, leggings, boots, and offhand slots. |
| 👤 **Player** | `get_inventory` | `search: str = ""` | Lists inventory contents with optional partial name matching. |
| 🌍 **World** | `get_weather` | *(None)* | Queries clear, rain, or thunder states and remaining ticks. |
| 🌍 **World** | `get_time` | *(None)* | Queries current world time, day/night phases, and moon phase. |
| 🌍 **World** | `get_world_time` | *(None)* | Queries the raw game world age in ticks. |
| 🌍 **World** | `get_light_level` | *(None)* | Queries block light, sky light, and combined light levels. |
| 🌍 **World** | `get_biome` | *(None)* | Queries current biome ID, temperature, rainfall, and category. |
| 🌍 **World** | `get_dimension` | *(None)* | Returns active dimension (`overworld`, `the_nether`, `the_end`). |
| 🌲 **Environment** | `get_nearby_blocks` | `radius: int = 16` | Lists block types, counts, and nearest coordinates (radius 1–64). |
| 🌲 **Environment** | `scan_area` | `radius: int = 16` | Returns aggregated terrain variation, tree, liquid, and ore summaries. |
| 🌲 **Environment** | `find_nearest` | `target_type: str` | Locates nearest block or entity matching query with direction angle. |
| 👾 **Entities** | `get_nearby_entities`| `radius: int = 64` | Lists mobs, passive animals, villagers, and players with distances. |

---

## 🚀 Getting Started

### Prerequisites
* **Java 21 (JDK)**
* **Python 3.10+**
* **Minecraft Java 1.21.1** with Fabric Loader **0.16.5**
* A **Google Gemini API Key** (obtainable via [Google AI Studio](https://aistudio.google.com/))

### 1. Backend Setup
```bash
# Navigate to the backend directory
cd backend

# Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Backend Configuration
Copy the `.env` template and set your API key:
```bash
cp .env.example .env
```
Open `.env` and fill in:
```env
GEMINI_API_KEY=AIzaSy...
```
*(Optional)* Review `config.json` to customize default providers (`gemini` or `mock` for offline runs):
```json
{
    "provider": "gemini",
    "model": "gemini-3.1-flash-lite",
    "temperature": 0.7,
    "max_tokens": 2048,
    "timeout": 15.0,
    "enable_eval_recorder": true
}
```

### 3. Start the Backend Gateway
You can choose lifecycle automation or direct execution:
* **Option A: Companion Launcher (Recommended on Windows)**
  Go to `backend-launcher/publish` and run `MinecraftAICompanion.exe`. It automatically starts the FastAPI server when Minecraft starts and terminates it upon game exit.
* **Option B: Manual CLI Execution**
  Run the server manually using:
  ```bash
  # Inside backend/ with venv activated
  uvicorn main:app --host 127.0.0.1 --port 8000
  ```
  Verify by visiting `http://127.0.0.1:8000/health` (should return `{"status":"healthy"}`). Access the React Web Dashboard at `http://127.0.0.1:8000/dashboard/`.

### 4. Build and Install the Fabric Mod
```bash
cd fabric-mod

# Build the mod JAR
# Windows:
gradlew.bat build
# macOS/Linux:
./gradlew build
```
Copy the compiled JAR file from `fabric-mod/build/libs/aiassistant-1.0.0.jar` into your local Minecraft `mods/` directory.

---

## 🧪 Testing & Validation

### Running Unit & Integration Tests
Run the comprehensive test suite (94 tests covering token budgeting, rate limit backoffs, semantic search vector stores, and planner strategies):
```bash
cd backend
$env:PYTHONPATH=".."  # Windows PowerShell
python -m unittest discover -s . -p "test_*.py"
```

### Running the Offline Regression Suite
To test routing pipelines, classifier accuracies, and tool selections across 10 benchmark queries completely offline:
```bash
# Executing from workspace root
.\backend\venv\Scripts\python.exe backend/run_validation_report.py
```
This generates a markdown results sheet at `docs/validation_report.md`.

---

## 🗺️ Engineering Roadmap

```
Phase 1 — Foundation                                      [COMPLETE]
  Fabric mod registers /ai command & async HTTP context posts
  Google Gemini LLM pipeline integration
  Unified Dual Logging & basic error fallbacks

Phase 2 — Memory and Perceptions                         [COMPLETE]
  Atomic persistent memory.json waypoints & notes
  Pydantic argument validation schemas
  Registry module with 9 core tools

Phase 3 — Robust JSON Parsing & Mocking                   [COMPLETE]
  LLM JSON Mode enforcement & malformed response auto-correction
  BaseLLMProvider factory with deterministic MockProvider for offline dev
  Request-specific prompts logged to file

Phase 4A — World & Entity Awareness                       [COMPLETE]
  Perception models split: PlayerInfo vs EnvironmentSnapshot
  Chebyshev scans, chunk-safe scanning, and compact lists
  12 new tools for detailed entity and block perceptions

Phase 4A.1 — Hybrid Reasoning                             [COMPLETE]
  ResponseStrategy routing (KNOWLEDGE, TOOLS, HYBRID)
  ResponseGenerator decoupling response synthesis from planning
  Integration testing covering 43 mock evaluation suites

Phase 4A.2 — Companion Win Launcher                       [COMPLETE]
  C# tray client; WMI process monitoring & child process job objects
  Attached manual instances & custom launcher_config.json

Phase 4A.3 — Telemetry & React Dashboard                   [COMPLETE]
  AI Resource Manager rate limiting (RPM/TPD/TPM) and stats charts
  FastAPI streamed log logs and Memory CRUD editing React grid

Phase 4A.8 — Semantic Episodic Memory                     [COMPLETE]
  SQLite DB models (episodes, facts, sessions, embeddings)
  SentenceTransformer vector store (L2 distance lookup)
  Prioritized Prompt Budgeting & routing override checks

Phase 4B — World Interaction                              [PLANNED]
  Safe block placement & block breaking tools
  Console command validation dispatching
  Multi-tool chaining pipeline results passing
```

---

## 📄 License

This project is licensed under the **MIT License** — see the `fabric.mod.json` declaration.
