# src/tools/factory.py
import json
import inspect
from typing import Any, Optional
from src.upstream.manager import UpstreamManager

def create_upstream_tool_wrapper(
    upstream: UpstreamManager,
    server_name: str,
    tool_name: str,
    input_schema: dict[str, Any]
) -> Any:
    """Factory function to create tool wrappers with proper signatures"""

    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])

    params: list[inspect.Parameter] = []
    annotations: dict[str, Any] = {}

    type_mapping = {
        "string": str,
        "number": float,
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    # ✅ FIXED: Add required parameters FIRST (without defaults)
    for param_name in required:
        if param_name in properties:
            param_info = properties[param_name]
            param_type = param_info.get("type", "string")
            python_type = type_mapping.get(param_type, Any)
            annotations[param_name] = python_type

            params.append(inspect.Parameter(
                param_name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=python_type
            ))

    # ✅ FIXED: Add optional parameters SECOND (with defaults)
    for param_name, param_info in properties.items():
        if param_name not in required:  # Skip already-added required params
            param_type = param_info.get("type", "string")
            python_type = type_mapping.get(param_type, Any)
            annotations[param_name] = Optional[python_type]

            params.append(inspect.Parameter(
                param_name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=None,
                annotation=Optional[python_type]
            ))

    async def upstream_tool_wrapper(**kwargs: Any) -> str:
        """Wrapper for upstream tool"""
        try:
            arguments = {k: v for k, v in kwargs.items() if v is not None}
            result = await upstream.call_tool(server_name, tool_name, arguments)

            if result is None:
                return json.dumps({"error": "No result returned from upstream"})
            elif isinstance(result, str):
                return result
            elif hasattr(result, '__dict__'):
                return json.dumps(result.__dict__)
            else:
                try:
                    return json.dumps(result)
                except (TypeError, ValueError):
                    return str(result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return json.dumps({"error": str(e)})

    sig = inspect.Signature(
        parameters=params,
        return_annotation=str
    )
    upstream_tool_wrapper.__signature__ = sig  # type: ignore
    upstream_tool_wrapper.__annotations__ = {**annotations, 'return': str}

    return upstream_tool_wrapper