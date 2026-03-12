"""
Base class for orchestration patterns.

Patterns define how agents coordinate to solve a task.
Each pattern takes a list of agents and orchestrates their execution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..agent import Agent
from ..context import Context
from ..message import Message


@dataclass
class PatternConfig:
    """Configuration for a pattern."""
    name: str
    max_iterations: int = 10  # for iterative patterns
    timeout_seconds: float = 300.0  # 5 minutes default
    stop_on_error: bool = True
    metadata: dict = field(default_factory=dict)


@dataclass
class PatternResult:
    """
    Result of executing a pattern.

    Contains the final output plus execution metadata.
    """
    output: Message
    intermediate_outputs: list[Message] = field(default_factory=list)
    iterations: int = 1
    success: bool = True
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "output": self.output.to_dict(),
            "intermediate_outputs": [m.to_dict() for m in self.intermediate_outputs],
            "iterations": self.iterations,
            "success": self.success,
            "error": self.error,
        }


class Pattern(ABC):
    """
    Base class for orchestration patterns.

    A pattern defines how multiple agents work together:
    - Sequential: A → B → C
    - Parallel: A, B, C → combine
    - Hierarchical: Manager → Workers
    - Debate: A ↔ B → Judge
    - Reflexion: Act → Critique → Retry

    Subclasses must implement the `execute` method.
    """

    def __init__(self, config: PatternConfig | None = None):
        self.config = config or PatternConfig(name=self.__class__.__name__)

    @abstractmethod
    async def execute(
        self,
        agents: list[Agent],
        input_message: Message,
        context: Context,
    ) -> PatternResult:
        """
        Execute the pattern with the given agents.

        Args:
            agents: The agents to orchestrate
            input_message: The initial input
            context: Shared context

        Returns:
            PatternResult containing output and metadata
        """
        pass

    async def __call__(
        self,
        agents: list[Agent],
        input_message: Message,
        context: Context,
    ) -> PatternResult:
        """Execute the pattern (alias for execute)."""
        return await self.execute(agents, input_message, context)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(config={self.config.name})"


class PatternRegistry:
    """Registry for orchestration patterns."""

    def __init__(self):
        self._patterns: dict[str, type[Pattern]] = {}

    def register(self, name: str, pattern_class: type[Pattern]) -> None:
        """Register a pattern class."""
        self._patterns[name] = pattern_class

    def get(self, name: str) -> type[Pattern]:
        """Get a pattern class by name."""
        if name not in self._patterns:
            raise KeyError(f"Pattern '{name}' not found. Available: {list(self._patterns.keys())}")
        return self._patterns[name]

    def create(self, name: str, config: PatternConfig | None = None) -> Pattern:
        """Create a pattern instance by name."""
        pattern_class = self.get(name)
        return pattern_class(config)

    def list(self) -> list[str]:
        """List all registered pattern names."""
        return list(self._patterns.keys())


# Global pattern registry
pattern_registry = PatternRegistry()


def register_pattern(name: str):
    """Decorator to register a pattern class."""
    def decorator(cls: type[Pattern]) -> type[Pattern]:
        pattern_registry.register(name, cls)
        return cls
    return decorator
