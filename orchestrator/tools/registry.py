"""
Tool Registry: Manage and execute tools for agents.

Tools are functions that agents can call to interact with
external systems, execute code, or perform actions.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from typing import Any, Callable, get_type_hints


@dataclass
class ToolParameter:
    """Description of a tool parameter."""
    name: str
    type: str
    description: str = ""
    required: bool = True
    default: Any = None


@dataclass
class Tool:
    """
    A tool that agents can use.

    Tools have:
    - name: Unique identifier
    - description: What the tool does (for LLM to understand)
    - parameters: Input parameters
    - function: The actual implementation
    """
    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)
    function: Callable | None = None
    is_async: bool = False

    # Execution tracking
    call_count: int = 0
    total_time_ms: int = 0
    last_error: str | None = None

    def to_openai_schema(self) -> dict:
        """Convert to OpenAI function calling schema."""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = {
                "type": self._python_type_to_json(param.type),
                "description": param.description,
            }
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def _python_type_to_json(self, type_str: str) -> str:
        """Convert Python type to JSON schema type."""
        mapping = {
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "list": "array",
            "dict": "object",
        }
        return mapping.get(type_str, "string")

    async def execute(self, **kwargs) -> Any:
        """Execute the tool with given arguments."""
        if self.function is None:
            raise ValueError(f"Tool '{self.name}' has no function")

        start_time = time.time()
        self.call_count += 1

        try:
            if self.is_async:
                result = await self.function(**kwargs)
            else:
                result = await asyncio.to_thread(self.function, **kwargs)

            self.total_time_ms += int((time.time() - start_time) * 1000)
            return result

        except Exception as e:
            self.last_error = str(e)
            raise

    def __repr__(self) -> str:
        return f"Tool({self.name})"


class ToolRegistry:
    """
    Registry for managing tools.

    Features:
    - Register tools by name
    - Execute tools with validation
    - Generate schemas for LLM function calling
    - Track execution statistics
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def register_function(
        self,
        func: Callable,
        name: str | None = None,
        description: str | None = None,
    ) -> Tool:
        """
        Register a function as a tool.

        Automatically extracts parameters from function signature.
        """
        tool_name = name or func.__name__
        tool_description = description or func.__doc__ or f"Execute {tool_name}"

        # Extract parameters from signature
        sig = inspect.signature(func)
        hints = get_type_hints(func) if hasattr(func, "__annotations__") else {}

        parameters = []
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue

            param_type = hints.get(param_name, str).__name__
            has_default = param.default != inspect.Parameter.empty

            parameters.append(ToolParameter(
                name=param_name,
                type=param_type,
                required=not has_default,
                default=param.default if has_default else None,
            ))

        tool = Tool(
            name=tool_name,
            description=tool_description,
            parameters=parameters,
            function=func,
            is_async=asyncio.iscoroutinefunction(func),
        )

        self.register(tool)
        return tool

    def get(self, name: str) -> Tool:
        """Get a tool by name."""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found. Available: {list(self._tools.keys())}")
        return self._tools[name]

    def has(self, name: str) -> bool:
        """Check if a tool exists."""
        return name in self._tools

    def list(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def get_all(self) -> list[Tool]:
        """Get all registered tools."""
        return list(self._tools.values())

    async def execute(self, name: str, **kwargs) -> Any:
        """Execute a tool by name."""
        tool = self.get(name)
        return await tool.execute(**kwargs)

    def get_openai_schemas(self, tool_names: list[str] | None = None) -> list[dict]:
        """
        Get OpenAI function calling schemas for tools.

        Args:
            tool_names: Specific tools to include (None = all)
        """
        tools = self._tools.values()
        if tool_names:
            tools = [self._tools[n] for n in tool_names if n in self._tools]
        return [t.to_openai_schema() for t in tools]

    def get_descriptions(self, tool_names: list[str] | None = None) -> str:
        """
        Get human-readable descriptions of tools.

        Useful for including in system prompts.
        """
        tools = self._tools.values()
        if tool_names:
            tools = [self._tools[n] for n in tool_names if n in self._tools]

        lines = ["Available tools:"]
        for tool in tools:
            params = ", ".join(p.name for p in tool.parameters)
            lines.append(f"- {tool.name}({params}): {tool.description}")

        return "\n".join(lines)

    def get_stats(self) -> dict:
        """Get execution statistics for all tools."""
        return {
            name: {
                "call_count": tool.call_count,
                "total_time_ms": tool.total_time_ms,
                "avg_time_ms": tool.total_time_ms / tool.call_count if tool.call_count > 0 else 0,
                "last_error": tool.last_error,
            }
            for name, tool in self._tools.items()
        }

    def clear(self):
        """Remove all registered tools."""
        self._tools.clear()

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


# Global registry
_global_registry = ToolRegistry()


def tool(
    name: str | None = None,
    description: str | None = None,
):
    """
    Decorator to register a function as a tool.

    Usage:
        @tool(description="Search the web")
        def web_search(query: str) -> str:
            ...
    """
    def decorator(func: Callable) -> Callable:
        _global_registry.register_function(
            func,
            name=name,
            description=description,
        )
        return func
    return decorator


def get_tool(name: str) -> Tool:
    """Get a tool from the global registry."""
    return _global_registry.get(name)


def execute_tool(name: str, **kwargs) -> Any:
    """Execute a tool from the global registry."""
    return _global_registry.execute(name, **kwargs)


def list_tools() -> list[str]:
    """List all tools in the global registry."""
    return _global_registry.list()
