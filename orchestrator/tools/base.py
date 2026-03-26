"""
Base Tool Interface: Abstract base class for all tools.

Provides a consistent interface for tool execution with:
- Structured results (success/failure, data, error, latency)
- Timeout handling
- Async execution
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """
    Structured result from tool execution.

    Attributes:
        success: Whether the tool executed successfully
        data: The result data (if successful)
        error: Error message (if failed)
        latency_ms: Execution time in milliseconds
        tool_name: Name of the tool that produced this result
        metadata: Additional context about the execution
    """
    success: bool
    data: Any
    error: str | None = None
    latency_ms: float = 0.0
    tool_name: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "tool_name": self.tool_name,
            "metadata": self.metadata,
        }

    @classmethod
    def ok(cls, data: Any, tool_name: str = "", latency_ms: float = 0.0, **metadata) -> ToolResult:
        """Create a successful result."""
        return cls(
            success=True,
            data=data,
            error=None,
            latency_ms=latency_ms,
            tool_name=tool_name,
            metadata=metadata,
        )

    @classmethod
    def fail(cls, error: str, tool_name: str = "", latency_ms: float = 0.0, **metadata) -> ToolResult:
        """Create a failed result."""
        return cls(
            success=False,
            data=None,
            error=error,
            latency_ms=latency_ms,
            tool_name=tool_name,
            metadata=metadata,
        )


class BaseTool(ABC):
    """
    Abstract base class for tools.

    All tools should extend this class and implement:
    - name: Unique identifier for the tool
    - description: Human-readable description for LLM
    - execute: The actual tool implementation

    Optional overrides:
    - parameters_schema: JSON schema for parameters
    - validate: Custom validation logic
    """

    def __init__(self, timeout_seconds: float = 10.0):
        """
        Initialize the tool.

        Args:
            timeout_seconds: Default timeout for tool execution
        """
        self._timeout = timeout_seconds
        self._call_count = 0
        self._total_latency_ms = 0.0
        self._error_count = 0
        self._last_error: str | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for the tool."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Description for LLM to understand what this tool does."""
        ...

    @property
    def parameters_schema(self) -> dict:
        """
        JSON schema for tool parameters.

        Override this to define expected parameters.
        Default returns empty schema (no parameters).
        """
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with given parameters.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult with success/failure status and data
        """
        ...

    def validate(self, **kwargs) -> tuple[bool, str | None]:
        """
        Validate parameters before execution.

        Override to add custom validation logic.

        Returns:
            (is_valid, error_message)
        """
        return True, None

    async def run(self, timeout: float | None = None, **kwargs) -> ToolResult:
        """
        Run the tool with timeout and error handling.

        This is the main entry point for tool execution.
        It wraps execute() with:
        - Parameter validation
        - Timeout handling
        - Error catching
        - Latency tracking

        Args:
            timeout: Override default timeout (seconds)
            **kwargs: Tool parameters

        Returns:
            ToolResult with execution outcome
        """
        start_time = time.time()
        timeout_sec = timeout or self._timeout

        # Validate parameters
        is_valid, error = self.validate(**kwargs)
        if not is_valid:
            return ToolResult.fail(
                error=error or "Invalid parameters",
                tool_name=self.name,
                latency_ms=(time.time() - start_time) * 1000,
            )

        try:
            # Execute with timeout
            self._call_count += 1
            result = await asyncio.wait_for(
                self.execute(**kwargs),
                timeout=timeout_sec,
            )

            latency_ms = (time.time() - start_time) * 1000
            self._total_latency_ms += latency_ms

            # Ensure result has correct metadata
            result.tool_name = self.name
            result.latency_ms = latency_ms

            return result

        except asyncio.TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            self._error_count += 1
            self._last_error = f"Timeout after {timeout_sec}s"
            return ToolResult.fail(
                error=f"Tool '{self.name}' timed out after {timeout_sec} seconds",
                tool_name=self.name,
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._error_count += 1
            self._last_error = str(e)
            return ToolResult.fail(
                error=f"Tool '{self.name}' failed: {str(e)}",
                tool_name=self.name,
                latency_ms=latency_ms,
            )

    def get_stats(self) -> dict:
        """Get execution statistics for this tool."""
        return {
            "name": self.name,
            "call_count": self._call_count,
            "total_latency_ms": self._total_latency_ms,
            "avg_latency_ms": (
                self._total_latency_ms / self._call_count
                if self._call_count > 0 else 0
            ),
            "error_count": self._error_count,
            "error_rate": (
                self._error_count / self._call_count
                if self._call_count > 0 else 0
            ),
            "last_error": self._last_error,
        }

    def to_openai_schema(self) -> dict:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
