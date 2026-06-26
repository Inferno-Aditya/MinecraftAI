# Changelog

All notable changes to the **MinecraftAI** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
