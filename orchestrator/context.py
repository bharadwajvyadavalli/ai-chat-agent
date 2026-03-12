"""
Context management for multi-agent orchestration.

Context is the shared state that flows through the orchestration pipeline.
It contains working memory, conversation history, and access to tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .message import Message, MessageRole

if TYPE_CHECKING:
    from .tools.registry import ToolRegistry


@dataclass
class WorkflowState:
    """
    Tracks the current state of a workflow execution.
    """
    workflow_id: str
    workflow_name: str
    current_step: int = 0
    total_steps: int = 0
    status: str = "running"  # running, completed, failed, paused
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    error: str | None = None

    def mark_completed(self):
        self.status = "completed"
        self.completed_at = datetime.now()

    def mark_failed(self, error: str):
        self.status = "failed"
        self.error = error
        self.completed_at = datetime.now()


@dataclass
class Context:
    """
    Shared state for multi-agent orchestration.

    Context flows through the pipeline and provides:
    - working_memory: Key-value store for current task state
    - history: Conversation/execution history
    - tools: Access to tool registry
    - workflow_state: Current workflow execution state
    """

    # Current task state (agent-writable)
    working_memory: dict[str, Any] = field(default_factory=dict)

    # Conversation history
    history: list[Message] = field(default_factory=list)

    # Tool access (set by runtime)
    tools: "ToolRegistry | None" = None

    # Workflow tracking
    workflow_state: WorkflowState | None = None

    # Execution metadata
    execution_id: str | None = None
    parent_context_id: str | None = None  # for nested workflows

    # Cost tracking (aggregated)
    total_tokens: int = 0
    total_latency_ms: int = 0
    total_cost_usd: float = 0.0

    def set(self, key: str, value: Any) -> None:
        """Set a value in working memory."""
        self.working_memory[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from working memory."""
        return self.working_memory.get(key, default)

    def add_message(self, message: Message) -> None:
        """Add a message to history and update cost tracking."""
        self.history.append(message)
        if message.tokens_used:
            self.total_tokens += message.tokens_used
        if message.latency_ms:
            self.total_latency_ms += message.latency_ms

    def get_history_for_prompt(self, max_messages: int = 10) -> list[dict]:
        """
        Get recent history formatted for LLM prompts.

        Returns list of {"role": ..., "content": ...} dicts.
        """
        recent = self.history[-max_messages:] if max_messages else self.history
        return [
            {
                "role": "assistant" if m.role == MessageRole.AGENT else m.role.value,
                "content": m.content,
            }
            for m in recent
        ]

    def get_agent_outputs(self, agent_name: str) -> list[Message]:
        """Get all outputs from a specific agent."""
        return [m for m in self.history if m.source_agent == agent_name]

    def get_last_output(self, agent_name: str | None = None) -> Message | None:
        """Get the last output, optionally filtered by agent."""
        if agent_name:
            outputs = self.get_agent_outputs(agent_name)
            return outputs[-1] if outputs else None
        return self.history[-1] if self.history else None

    def fork(self, execution_id: str | None = None) -> "Context":
        """
        Create a child context for nested execution.

        Child inherits working_memory (copy) and tools,
        but has its own history and workflow_state.
        """
        return Context(
            working_memory=self.working_memory.copy(),
            history=[],
            tools=self.tools,
            workflow_state=None,
            execution_id=execution_id,
            parent_context_id=self.execution_id,
        )

    def merge_costs(self, child: "Context") -> None:
        """Merge cost tracking from a child context."""
        self.total_tokens += child.total_tokens
        self.total_latency_ms += child.total_latency_ms
        self.total_cost_usd += child.total_cost_usd

    def to_dict(self) -> dict:
        """Serialize context for persistence/debugging."""
        return {
            "execution_id": self.execution_id,
            "working_memory": self.working_memory,
            "history": [m.to_dict() for m in self.history],
            "workflow_state": {
                "workflow_id": self.workflow_state.workflow_id,
                "workflow_name": self.workflow_state.workflow_name,
                "current_step": self.workflow_state.current_step,
                "total_steps": self.workflow_state.total_steps,
                "status": self.workflow_state.status,
            } if self.workflow_state else None,
            "total_tokens": self.total_tokens,
            "total_latency_ms": self.total_latency_ms,
            "total_cost_usd": self.total_cost_usd,
        }
