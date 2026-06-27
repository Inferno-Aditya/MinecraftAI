import json
from typing import List, Dict, Any

try:
    from tools.registry import registry
except ImportError:
    from .tools.registry import registry

def select_tool_definitions(required_tools: List[str]) -> str:
    """
    Formats only the required tool definitions in schema format.
    """
    if not required_tools:
        return ""
        
    defs = []
    for tool_name in required_tools:
        tool = registry.get_tool(tool_name)
        if not tool:
            continue
            
        schema = tool.input_schema.model_json_schema()
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        clean_props = {}
        for prop_name, prop_info in properties.items():
            clean_props[prop_name] = {
                "type": prop_info.get("type", "unknown"),
                "description": prop_info.get("description", "")
            }

        examples_str = "\n".join(f"  - \"{ex}\"" for ex in tool.usage_examples)

        tool_def = (
            f"Tool: {tool.name}\n"
            f"Description: {tool.description}\n"
            f"Arguments Schema:\n{json.dumps(clean_props, indent=2)}\n"
            f"Required Arguments: {required}\n"
            f"Usage Examples:\n{examples_str}"
        )
        defs.append(tool_def)

    return "\n\n---\n\n".join(defs) if defs else ""
