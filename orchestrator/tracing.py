"""
Tracing and observability for multi-agent orchestration.

Traces capture the full execution history of a workflow,
enabling debugging, performance analysis, and cost tracking.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass
class TraceEvent:
    """
    A single event in a trace.

    Events capture:
    - Agent executions
    - Pattern transitions
    - Tool calls
    - Errors
    """
    name: str
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: int | None = None
    parent_id: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "parent_id": self.parent_id,
        }


@dataclass
class TraceSpan:
    """
    A span represents a unit of work within a trace.

    Spans have:
    - Start and end times
    - Nested child spans
    - Associated events
    """
    name: str
    id: str = field(default_factory=lambda: str(uuid4()))
    parent_id: str | None = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None
    events: list[TraceEvent] = field(default_factory=list)
    children: list["TraceSpan"] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    status: str = "running"  # running, completed, failed

    def end(self, status: str = "completed"):
        """End this span."""
        self.end_time = datetime.now()
        self.status = status

    def add_event(self, event: TraceEvent):
        """Add an event to this span."""
        event.parent_id = self.id
        self.events.append(event)

    def create_child(self, name: str) -> "TraceSpan":
        """Create a child span."""
        child = TraceSpan(name=name, parent_id=self.id)
        self.children.append(child)
        return child

    @property
    def duration_ms(self) -> int | None:
        """Calculate duration in milliseconds."""
        if self.end_time is None:
            return None
        delta = self.end_time - self.start_time
        return int(delta.total_seconds() * 1000)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "events": [e.to_dict() for e in self.events],
            "children": [c.to_dict() for c in self.children],
            "metadata": self.metadata,
        }


@dataclass
class Trace:
    """
    A complete trace of a workflow execution.

    Traces contain:
    - Root span with nested child spans
    - All events that occurred
    - Execution metadata (costs, tokens, timing)
    """
    execution_id: str
    workflow_name: str
    root_span: TraceSpan | None = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.root_span is None:
            self.root_span = TraceSpan(name=self.workflow_name)

    def add_event(self, event: TraceEvent):
        """Add an event to the root span."""
        self.root_span.add_event(event)

    def start_span(self, name: str) -> TraceSpan:
        """Start a new span as child of root."""
        return self.root_span.create_child(name)

    def end(self):
        """End the trace."""
        self.end_time = datetime.now()
        if self.root_span:
            self.root_span.end()

    @property
    def duration_ms(self) -> int | None:
        """Calculate total duration in milliseconds."""
        if self.end_time is None:
            return None
        delta = self.end_time - self.start_time
        return int(delta.total_seconds() * 1000)

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "workflow_name": self.workflow_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "root_span": self.root_span.to_dict() if self.root_span else None,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize trace to JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    def print_summary(self):
        """Print a human-readable summary of the trace."""
        print(f"\n{'='*60}")
        print(f"Workflow: {self.workflow_name}")
        print(f"Execution ID: {self.execution_id}")
        print(f"Duration: {self.duration_ms}ms")
        print(f"Tokens: {self.total_tokens}")
        print(f"Cost: ${self.total_cost_usd:.4f}")
        print(f"{'='*60}")

        if self.root_span:
            self._print_span(self.root_span, indent=0)

    def _print_span(self, span: TraceSpan, indent: int):
        """Recursively print span tree."""
        prefix = "  " * indent
        status_icon = "✓" if span.status == "completed" else "✗" if span.status == "failed" else "⋯"
        duration = f" ({span.duration_ms}ms)" if span.duration_ms else ""
        print(f"{prefix}{status_icon} {span.name}{duration}")

        for event in span.events:
            print(f"{prefix}  → {event.name}")

        for child in span.children:
            self._print_span(child, indent + 1)


class Tracer:
    """
    Factory for creating and managing traces.
    """

    def __init__(self):
        self.traces: dict[str, Trace] = {}

    def start_trace(self, execution_id: str, workflow_name: str) -> Trace:
        """Start a new trace."""
        trace = Trace(execution_id=execution_id, workflow_name=workflow_name)
        self.traces[execution_id] = trace
        return trace

    def get_trace(self, execution_id: str) -> Trace | None:
        """Get a trace by execution ID."""
        return self.traces.get(execution_id)

    def end_trace(self, execution_id: str) -> Trace | None:
        """End a trace and return it."""
        trace = self.traces.get(execution_id)
        if trace:
            trace.end()
        return trace

    def export_traces(self, path: str):
        """Export all traces to a JSON file."""
        data = {
            "traces": [t.to_dict() for t in self.traces.values()]
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def clear(self):
        """Clear all traces."""
        self.traces.clear()
