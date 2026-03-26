"""
Tool subsystem for multi-agent orchestration.

Tools are capabilities that agents can use:
- External APIs
- Code execution
- File operations
- Database queries
- Web search
- SQL queries
"""

from .registry import Tool, ToolRegistry, tool
from .sandbox import Sandbox, SandboxConfig
from .base import BaseTool, ToolResult
from .web_search import WebSearchTool
from .sql_query import SQLQueryTool

__all__ = [
    # Core
    "Tool",
    "ToolRegistry",
    "tool",
    "Sandbox",
    "SandboxConfig",
    # Base classes
    "BaseTool",
    "ToolResult",
    # Concrete tools
    "WebSearchTool",
    "SQLQueryTool",
]
