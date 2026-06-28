# Final Validation Report – Planner Routing & Intent Validation

This report provides a formal evaluation of the Minecraft AI Planner Pipeline correctness.

## Accuracy Metrics

- **Classification Accuracy**: 100.0%
- **Strategy Accuracy**: 100.0%
- **Tool Selection Accuracy**: 100.0%
- **Tool Execution Accuracy**: 100.0%
- **Planner Override Count**: 0
- **Consistency Warnings Emitted**: 0
- **Regression Pass Rate**: 100.0%

## Pipeline Stage Summary

| Query | Intent Classification | Strategy Selection | Candidate Tool Ranking | Final Tool Selection | Tool Execution | Response Generation | Passed |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| "How am I doing?" | PASS | PASS | PASS | PASS | PASS | PASS | ✅ PASS |
| "What am I holding?" | PASS | PASS | PASS | PASS | PASS | PASS | ✅ PASS |
| "Are there any hostile mobs nearby?" | PASS | PASS | PASS | PASS | PASS | PASS | ✅ PASS |
| "What biome am I in?" | PASS | PASS | PASS | PASS | PASS | PASS | ✅ PASS |
| "Find the nearest village." | PASS | PASS | PASS | PASS | PASS | PASS | ✅ PASS |
| "Is it safe to sleep?" | PASS | PASS | PASS | PASS | PASS | PASS | ✅ PASS |
| "Should I fight these mobs?" | PASS | PASS | PASS | PASS | PASS | PASS | ✅ PASS |
| "Save this location as Home." | PASS | PASS | PASS | PASS | PASS | PASS | ✅ PASS |
| "Where is Home?" | PASS | PASS | PASS | PASS | PASS | PASS | ✅ PASS |
| "How do I craft a Brewing Stand?" | PASS | PASS | PASS | PASS | PASS | PASS | ✅ PASS |

## Detailed Routing Traces

### Query: "How am I doing?"
- **Intent**: Expected `PLAYER`, Got `PLAYER`
- **Strategy**: Expected `TOOLS`, Got `TOOLS`
- **Tools**: Expected `['get_health', 'get_food']`, Got `['get_health', 'get_food']`
- **Decision Reasoning**:
  - Strategy Source: `LLM`
  - Strategy Validation: `Passed`
  - Override Applied: `No`
  - Decision Reason: Player query to inspect stats, equipment, offhand, or inventory.

### Query: "What am I holding?"
- **Intent**: Expected `PLAYER`, Got `PLAYER`
- **Strategy**: Expected `TOOLS`, Got `TOOLS`
- **Tools**: Expected `['get_held_item']`, Got `['get_held_item']`
- **Decision Reasoning**:
  - Strategy Source: `LLM`
  - Strategy Validation: `Passed`
  - Override Applied: `No`
  - Decision Reason: Player query to inspect stats, equipment, offhand, or inventory.

### Query: "Are there any hostile mobs nearby?"
- **Intent**: Expected `ENVIRONMENT`, Got `ENVIRONMENT`
- **Strategy**: Expected `TOOLS`, Got `TOOLS`
- **Tools**: Expected `['get_nearby_entities']`, Got `['get_nearby_entities']`
- **Decision Reasoning**:
  - Strategy Source: `LLM`
  - Strategy Validation: `Passed`
  - Override Applied: `No`
  - Decision Reason: Environment query with nearby-entity, block, or biome detection.

### Query: "What biome am I in?"
- **Intent**: Expected `ENVIRONMENT`, Got `ENVIRONMENT`
- **Strategy**: Expected `TOOLS`, Got `TOOLS`
- **Tools**: Expected `['get_biome']`, Got `['get_biome']`
- **Decision Reasoning**:
  - Strategy Source: `LLM`
  - Strategy Validation: `Passed`
  - Override Applied: `No`
  - Decision Reason: Environment query with nearby-entity, block, or biome detection.

### Query: "Find the nearest village."
- **Intent**: Expected `ENVIRONMENT`, Got `ENVIRONMENT`
- **Strategy**: Expected `TOOLS`, Got `TOOLS`
- **Tools**: Expected `['find_nearest']`, Got `['find_nearest']`
- **Decision Reasoning**:
  - Strategy Source: `LLM`
  - Strategy Validation: `Passed`
  - Override Applied: `No`
  - Decision Reason: Environment query with nearby-entity, block, or biome detection.

### Query: "Is it safe to sleep?"
- **Intent**: Expected `HYBRID`, Got `HYBRID`
- **Strategy**: Expected `HYBRID`, Got `HYBRID`
- **Tools**: Expected `['get_time', 'get_nearby_entities']`, Got `['get_time', 'get_nearby_entities']`
- **Decision Reasoning**:
  - Strategy Source: `LLM`
  - Strategy Validation: `Passed`
  - Override Applied: `No`
  - Decision Reason: Hybrid query requiring both environment context and knowledge synthesis.

### Query: "Should I fight these mobs?"
- **Intent**: Expected `HYBRID`, Got `HYBRID`
- **Strategy**: Expected `HYBRID`, Got `HYBRID`
- **Tools**: Expected `['get_health', 'get_food', 'get_nearby_entities']`, Got `['get_health', 'get_food', 'get_nearby_entities']`
- **Decision Reasoning**:
  - Strategy Source: `LLM`
  - Strategy Validation: `Passed`
  - Override Applied: `No`
  - Decision Reason: Hybrid query requiring both environment context and knowledge synthesis.

### Query: "Save this location as Home."
- **Intent**: Expected `MEMORY`, Got `MEMORY`
- **Strategy**: Expected `TOOLS`, Got `TOOLS`
- **Tools**: Expected `['save_location']`, Got `['save_location']`
- **Decision Reasoning**:
  - Strategy Source: `LLM`
  - Strategy Validation: `Passed`
  - Override Applied: `No`
  - Decision Reason: Memory query to save/retrieve waypoints or coordinates.

### Query: "Where is Home?"
- **Intent**: Expected `MEMORY`, Got `MEMORY`
- **Strategy**: Expected `TOOLS`, Got `TOOLS`
- **Tools**: Expected `['load_location']`, Got `['load_location']`
- **Decision Reasoning**:
  - Strategy Source: `LLM`
  - Strategy Validation: `Passed`
  - Override Applied: `No`
  - Decision Reason: Memory query to save/retrieve waypoints or coordinates.

### Query: "How do I craft a Brewing Stand?"
- **Intent**: Expected `KNOWLEDGE`, Got `KNOWLEDGE`
- **Strategy**: Expected `KNOWLEDGE`, Got `KNOWLEDGE`
- **Tools**: Expected `[]`, Got `[]`
- **Decision Reasoning**:
  - Strategy Source: `LLM`
  - Strategy Validation: `Passed`
  - Override Applied: `No`
  - Decision Reason: Knowledge query answered using expert Minecraft knowledge.

