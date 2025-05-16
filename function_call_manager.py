import json
from typing import Any, Dict
from tools.verification_tool import verification_tool
from tools.create_case import create_case
from tools.get_case import get_case
from tools.classification import classify_email
from tools.sentiment import analyze_sentiment_email
from tools.ai_summary import generate_case_summary
from tools.update_case import update_case
from tools.hangup_call import hangup_call


class FunctionCallManager:
    """
    Maps function names to implementations and executes them with JSON arguments.
    Handles errors and formats results for OpenAI Realtime API function calling.
    """

    def __init__(self):
        self.function_map = {
            "verification_tool": verification_tool,
            "create_case": create_case,
            "get_case": get_case,
            "classify_email": classify_email,
            "analyze_sentiment_email": analyze_sentiment_email,
            "generate_case_summary": generate_case_summary,
            "update_case": update_case,
            "hangup_call": hangup_call,
        }

    async def call_function(self, name: str, arguments: str) -> Dict[str, Any]:
        if name not in self.function_map:
            return {"error": f"Function '{name}' not found."}
        func = self.function_map[name]
        try:
            args = json.loads(arguments) if arguments else {}
        except Exception as e:
            return {"error": f"Invalid arguments JSON: {str(e)}"}
        try:
            # Support both sync and async functions
            if hasattr(func, "__call__"):
                if hasattr(func, "__await__") or hasattr(func, "__aiter__"):
                    result = await func(**args)
                else:
                    result = func(**args)
            else:
                return {"error": f"Function '{name}' is not callable."}
            return {"result": result}
        except Exception as e:
            return {"error": f"Function '{name}' raised: {str(e)}"}

    def tool_defs(self):
        return [
            {
                "type": "function",
                "name": name,
                "description": func.__doc__ or "",
                "parameters": {
                    "type": "object",
                    "properties": self.get_params(func),
                },
            }
            for name, func in self.function_map.items()
        ]

    def get_params(self, func):
        """
        Returns a dictionary describing the parameters of the given function,
        suitable for OpenAPI/JSON schema (name, type, required, etc).
        """
        import inspect
        from typing import get_type_hints

        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
        params = {}
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            param_type = type_hints.get(name, str)
            # Map Python types to JSON Schema types
            if param_type == int:
                json_type = "integer"
            elif param_type == float:
                json_type = "number"
            elif param_type == bool:
                json_type = "boolean"
            else:
                json_type = "string"
            params[name] = {
                "type": json_type,
                "description": "",
            }
            if param.default is not inspect.Parameter.empty:
                params[name]["default"] = param.default
        return params