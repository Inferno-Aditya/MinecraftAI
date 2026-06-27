import time
import pprint
from context import PlayerContext
from planner import plan
from request_context import RequestContext
from intent_classifier import IntentClassifier

# Initialize player context with typical survival state
context_payload = {
    "player_info": {
        "name": "Steve",
        "uuid": "uuid-123",
        "x": 120.4,
        "y": 63.0,
        "z": -345.8,
        "yaw": 180.0,
        "pitch": 0.0,
        "health": 15.0,
        "food": 18,
        "saturation": 6.0,
        "experience": 0.5,
        "level": 5,
        "gamemode": "survival",
        "dimension": "minecraft:overworld",
        "inventory": [
            {"slot": 0, "item": "minecraft:iron_pickaxe", "count": 1, "durability": 180, "enchantments": {}, "nbt": ""},
            {"slot": 1, "item": "minecraft:oak_log", "count": 16, "durability": 0, "enchantments": {}, "nbt": ""},
            {"slot": 2, "item": "minecraft:bread", "count": 4, "durability": 0, "enchantments": {}, "nbt": ""}
        ],
        "equipment": {
            "helmet": {"item": "minecraft:iron_helmet", "count": 1, "durability": 120, "enchantments": {}},
            "chestplate": {"item": "minecraft:air", "count": 0, "durability": 0, "enchantments": {}},
            "leggings": {"item": "minecraft:air", "count": 0, "durability": 0, "enchantments": {}},
            "boots": {"item": "minecraft:air", "count": 0, "durability": 0, "enchantments": {}},
            "offhand": {"item": "minecraft:shield", "count": 1, "durability": 280, "enchantments": {}}
        },
        "held_item": {"item": "minecraft:diamond_sword", "count": 1, "durability": 1400, "enchantments": {"minecraft:sharpness": 1}}
    },
    "environment": {
        "weather": {"rain": False, "thunder": False, "clear": True, "time_remaining": 12000},
        "world_time": 1000,
        "is_day": True,
        "is_night": False,
        "moon_phase": 0,
        "light_level": {"block": 15, "sky": 15, "combined": 15},
        "biome": {"name": "minecraft:plains", "temperature": 0.8, "rainfall": 0.4, "category": "plains"},
        "nearby_blocks": {
            "filler_blocks": {},
            "interesting_blocks": [
                {"type": "minecraft:coal_ore", "x": 122, "y": 62, "z": -343},
                {"type": "minecraft:water", "x": 115, "y": 62, "z": -348}
            ]
        },
        "nearby_entities": [
            {"type": "minecraft:sheep", "name": "Sheep", "health": 8.0, "max_health": 8.0, "distance": 6.2, "x": 124.0, "y": 63.0, "z": -341.0, "category": "passive"}
        ]
    }
}

player_context = PlayerContext.model_validate(context_payload)

queries = [
    # Player queries (5)
    "What's my health and food level?",
    "Am I low on health?",
    "What am I holding in my hand?",
    "Check my inventory items.",
    "What armor do I have equipped?",

    # Environment queries (5)
    "What's the weather like right now?",
    "Is there any water nearby?",
    "Are there any hostile mobs close to me?",
    "Scan the area around me.",
    "What biome is this?",

    # Memory queries (3)
    "Remember this spot as outpost.",
    "Show my saved locations.",
    "Forget my base.",

    # Hybrid queries (2)
    "Can I craft a shield?",
    "Is it safe to sleep?"
]

print("=== STARTING END-TO-END MANUAL VALIDATION (GEMINI) ===")
for idx, query in enumerate(queries, 1):
    print(f"\n[{idx}/15] Query: '{query}'")
    ctx = RequestContext(user_message=query)
    
    # 1. Offline classification check
    classifier = IntentClassifier()
    classification = classifier.classify(query)
    print(f"   -> Classified Intent: {classification['intent']}")
    print(f"   -> Top 3 Tools: {classification['required_tools'][:3]}")
    
    # 2. Call Plan (this makes actual LLM call if configured to gemini)
    try:
        start_time = time.time()
        result = plan(query, player_context, ctx=ctx)
        elapsed = (time.time() - start_time) * 1000
        print(f"   -> Response Strategy: {result.response_strategy.value}")
        print(f"   -> Planned Tools: {[tc.tool for tc in result.tool_calls]}")
        if result.reply:
            print(f"   -> Reply: '{result.reply[:150]}...'")
        print(f"   -> Time: {elapsed:.1f}ms")
    except Exception as e:
        print(f"   -> E2E Execution Failed: {e}")
    
    # Small sleep to respect RPM limits
    time.sleep(2.0)

print("\n=== MANUAL VALIDATION COMPLETE ===")
