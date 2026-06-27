# Changelog

All notable changes to the **MinecraftAI** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [v0.4.8] - 2026-06-27

### Added (v0.4.8 Release)
- **Intelligent Intent Classifier**: Configuration-driven routing using `intent_classifier_config.json`, confidence thresholds, regular plurals matching, and synonym resolution.
- **Planner Routing Validation**: Added a validation layer inside `planner.py` to prevent silent overrides and check strategy/tool consistency.
- **Decision Reasoning Diagnostics**: Added detailed explainability metrics (`strategy_source`, `strategy_validation`, `override_applied`, and `decision_reason`) to `RequestContext` and debug logging.
- **Regression Protection Framework**: Developed `run_validation_report.py` to execute a 100% offline regression test suite and write detailed summaries.
- **Launcher & Dashboard Lifecycle Improvements**: Integrates automatic backend management, health monitoring, and manual controls.

---

## [v0.4.3] - 2026-06-26

### Added (Phase 4A.3 Release)
- **AI Resource Manager**: Developed a provider-agnostic core manager supporting token accounting, moving-average query latency tracking, and request diagnostics.
- **Proactive & Reactive Rate Limiting**: Implemented RPM, TPM, and RPD verification with auto-sleep queueing and exponential backoff retry cycles (2s, 4s, 8s) on HTTP 429 rate limit exceptions.
- **FastAPI REST API Server**: Setup CORS policies and added dedicated endpoints for remote statistics telemetry, masked environment configuration, available providers, tool schemas, database memory CRUD, and streamed console logging.
- **React Visual Dashboard**: Created a dark-themed visual SPA dashboard served directly from the backend server using custom Minecraft stone elements, Creeper green accents, responsive grids, and SVG metrics charts.
- **Dynamic Configuration Updates**: Re-evaluates `.env` settings dynamically via `load_dotenv(override=True)` upon key updates, bypassing backend restart requirements.
- **Unit & Integration Tests**: Implemented `test_resource_manager.py` verifying request stats persistence to `usage_stats.json` and correct rate-limit retry policies.

---

## [v0.4.2] - 2026-06-26

### Added (Phase 4A.2 Release)
- **Automatic Companion Launcher**: Developed a standalone C# WinForms background utility (`MinecraftAICompanion.exe`) that automatically manages the Python backend server lifecycle.
- **Robust Process Detection**: Detects Minecraft Java process (`javaw.exe`/`java.exe`) using WMI command-line filters (`--gameDir`, `net.minecraft.client.main.Main`) to isolate the active game from other launcher applications.
- **Smart Attach-to-Existing**: Queries `/health` to connect to pre-existing manual backend server instances, preventing duplicate server execution.
- **Orphan Process Cleanup**: Integrates native Windows Job Objects to ensure all Python process trees are cleaned up automatically when the launcher exits.
- **Uptime & Metrics Dashboard**: Includes a dark-themed visual window to monitor Minecraft status, backend PID, launcher/backend uptimes, and retry logs, along with manual force-restart actions.
- **Flexible Configuration**: Provides `launcher_config.json` with configuration parameters for directories, executables, intervals, retry limits, and an `AutoStartBackend` toggle.

---

## [v0.4.1] - 2026-06-26

### Added (Phase 4A.1 Patch)
- **Hybrid Knowledge & Tool-Based Reasoning**: Refactored the planner engine to act as a knowledgeable Minecraft assistant, using three request strategies:
  - `KNOWLEDGE`: Answering Minecraft mechanics, recipes, villagers, redstone, and combat questions directly using LLM knowledge without calling tools.
  - `TOOLS`: Standard world/player lookups that run tool calls directly.
  - `HYBRID`: Queries requiring both live game state and Minecraft domain knowledge (e.g. craftability checks, survival assessments) that execute tools and then synthesize a final response.
- **Dedicated Response Generator**: Introduced a separate `ResponseGenerator` component in `backend/response_generator.py` responsible for synthesizing final conversational responses, keeping the planner focused strictly on classification and tool call planning.
- **Strongly Typed ResponseStrategy**: Replaced previous boolean indicators with a strongly typed `ResponseStrategy` enum (`KNOWLEDGE`, `TOOLS`, `HYBRID`) in `backend/planner.py` to improve architecture readability and future agent/reflection extension.
- **Comprehensive Integration Tests**: Added test cases for strategy classification, `ResponseGenerator` logic, and FastAPI `/chat` integration in `test_phase4a.py`.

---

## [v0.4.0] - 2026-06-26

### Added (Phase 4A)
- **Environment & Player Perception**: The AI can now observe player coordinates, health, level, saturation, experience progress, inventory, equipped gear, weather, time, light level, biome, nearby blocks, and nearby entities.
- **12 Environmental Tools**:
  - `get_player_status` - Returns coordinate and health status.
  - `get_held_item` - Returns details of the currently held item.
  - `get_equipment` - Returns helmet, chestplate, leggings, boots, and offhand slots.
  - `get_inventory` - Returns items and summary; supports searching by name.
  - `get_weather` - Returns rain, thunder, clear states and duration.
  - `get_time` - Returns ticks, day/night status, and moon phase name.
  - `get_light_level` - Returns block, sky, and combined light levels.
  - `get_nearby_blocks` - Lists surrounding blocks (radius 1-64).
  - `scan_area` - Summarises trees, water, stone, building blocks, ores, and terrain height variance.
  - `find_nearest` - Locates closest block or entity with relative direction angle.
  - `get_nearby_entities` - Returns list of mobs, players, villagers, projectiles, and vehicles with health and distance.
  - `get_biome` - Returns name, temperature, rainfall, and category.
- **Short-Lived Scan Caching**: A request-scoped cache that reuses scan results (blocks/entities) during a single planning pipeline, ensuring zero-lag observations.
- **Chunk-Safe Scanning**: Scans are restricted to loaded chunks to prevent generating new terrain or causing server lag.
- **Compact Block Serialization**: Split scanning data into filler block summaries (count & nearest) and interesting block lists (capped at 500 coordinates) to maintain small JSON payloads.
- **Pydantic Model Validation**: Refactored `PlayerContext` into Pydantic models for `PlayerInfo` and `EnvironmentSnapshot` with custom properties and `model_copy` to ensure 100% backward compatibility with Phase 3 tests.
- **Test Suite Expansion**: Added `test_phase4a.py` with 18 comprehensive tests covering perception models, scanning calculations, direction math, caching, and planning intents.

---

## [v0.3.0] - 2026-06-26

### Added (Phase 3)
- **Gemini Planner Engine**: Integrated dynamic prompt construction and LLM planning using the Google Gemini SDK.
- **Dynamic Tool Schema Injection**: Serialises tool names, descriptions, and Pydantic argument schemas directly into the LLM system prompt from the Tool Registry.
- **JSON Mode & Retry Logic**: Configured Gemini JSON output mode and implemented retry logic with auto-correction prompts for malformed JSON or validation errors.
- **Validation Failure Fallback**: Handles persistent schema validation failures by returning a friendly conversational error reply.
- **Integration Test Suite**: Added `test_phase3.py` containing 10 integration tests using `fastapi.testclient` and a deterministic mock provider.
- **Prompt Debug Logs**: Generates request-specific prompt logs under `logs/prompts/` showing the exact inputs sent to the LLM.

---

## [v0.2.0] - 2026-06-26

### Added (Phase 2)
- **Tool Registry**: Introduced `ToolRegistry` and `BaseTool` class for modular tool implementation.
- **Memory Tools**: Implemented `save_location`, `load_location`, `list_locations`, and `save_note` tools.
- **Persistent Storage**: Created atomic file write logic for `memory.json` using temp files to prevent data corruption.
- **Memory Prompt Injection**: Automatically formats and injects memory summaries (saved locations and notes) into LLM prompts.
- **Pydantic Validation**: Validates all tool arguments using Pydantic schemas.
- **Unit Tests**: Added `test_phase2.py` with 9 unit tests verifying memory recovery, location overriding, and validation errors.

---

## [v0.1.0] - 2026-06-26

### Added (Phase 1)
- **Fabric Mod Command**: Registered the `/ai <message>` in-game command.
- **Player Context Collection**: Mod gathers player position, dimension, health, and world time on command trigger.
- **FastAPI Backend Abstraction**: Created a local web server (localhost:8000) exposing `/chat` and `/health` endpoints.
- **Unified Dual Logging**: Appends all network logs, tool selections, and errors to `logs/aiassistant.log` from both Java and Python sides.
- **Error Handling**: Friendly in-game messages for offline server, request timeouts, and backend errors.
