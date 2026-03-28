"""Tool definitions for Claude API."""
from engine import get_registered_functions

# Type mapping from registry format to JSON Schema format
TYPE_MAPPING = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
}

SQL_EXECUTE_TOOL = {
    "name": "execute_sql",
    "description": "Execute a read-only SQL SELECT query against the WNBA statistics database. Use this when no engine function covers the question or when custom joins/aggregations are needed.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "A SELECT query to execute. Must be read-only. No INSERT/UPDATE/DELETE/DROP."
            },
            "chart_suggestion": {
                "type": "string",
                "description": "Optional: suggest a chart type for the results. One of: trend_line, heat_map, scatter, split_comparison, bar, table",
                "enum": ["trend_line", "heat_map", "scatter", "split_comparison", "bar", "table"]
            }
        },
        "required": ["sql"]
    }
}


def generate_tools_from_registry():
    """Convert engine registry functions to Claude API tool format."""
    functions = get_registered_functions()
    tools = []

    for func_dict in functions:
        name = func_dict["name"]
        description = func_dict["description"]
        params = func_dict.get("parameters", {})

        # Build JSON Schema properties and required list
        properties = {}
        required = []

        for param_name, param_info in params.items():
            param_type = param_info.get("type", "str")
            is_optional = param_info.get("optional", False)

            # Convert type to JSON Schema format
            json_type = TYPE_MAPPING.get(param_type, "string")

            property_def = {
                "type": json_type,
                "description": param_info.get("description", "")
            }

            # Handle list type with items
            if param_type == "list":
                property_def["items"] = {"type": "string"}

            properties[param_name] = property_def

            # Add to required if not optional
            if not is_optional:
                required.append(param_name)

        tool = {
            "name": name,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }

        tools.append(tool)

    return tools


def get_all_tools():
    """Return all available tools: engine functions + SQL execute."""
    return generate_tools_from_registry() + [SQL_EXECUTE_TOOL]
