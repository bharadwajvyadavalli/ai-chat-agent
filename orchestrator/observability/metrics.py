"""
Metrics Collection: Track and expose application metrics.

Collects:
- Request counts and latencies
- Tool usage statistics
- Token consumption
- Error rates
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class ToolMetrics:
    """Metrics for a single tool."""
    name: str
    call_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    last_called: datetime | None = None
    last_error: str | None = None

    @property
    def avg_latency_ms(self) -> float:
        if self.call_count == 0:
            return 0.0
        return self.total_latency_ms / self.call_count

    @property
    def success_rate(self) -> float:
        if self.call_count == 0:
            return 1.0
        return self.success_count / self.call_count

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "call_count": self.call_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": round(self.success_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "min_latency_ms": round(self.min_latency_ms, 2) if self.min_latency_ms != float('inf') else 0,
            "max_latency_ms": round(self.max_latency_ms, 2),
            "last_called": self.last_called.isoformat() if self.last_called else None,
            "last_error": self.last_error,
        }


@dataclass
class Metrics:
    """Application-wide metrics."""
    # Request metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0

    # Token metrics
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0

    # Memory metrics
    total_memories_retrieved: int = 0
    total_memories_stored: int = 0

    # Tool metrics
    tools: dict[str, ToolMetrics] = field(default_factory=dict)

    # Time tracking
    started_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def avg_latency_ms(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens

    @property
    def uptime_seconds(self) -> float:
        return (datetime.utcnow() - self.started_at).total_seconds()

    def to_dict(self) -> dict:
        return {
            "requests": {
                "total": self.total_requests,
                "successful": self.successful_requests,
                "failed": self.failed_requests,
                "success_rate": round(self.success_rate, 4),
                "avg_latency_ms": round(self.avg_latency_ms, 2),
            },
            "tokens": {
                "prompt": self.total_prompt_tokens,
                "completion": self.total_completion_tokens,
                "total": self.total_tokens,
            },
            "memory": {
                "retrieved": self.total_memories_retrieved,
                "stored": self.total_memories_stored,
            },
            "tools": {
                name: tool.to_dict()
                for name, tool in self.tools.items()
            },
            "uptime": {
                "started_at": self.started_at.isoformat() + "Z",
                "uptime_seconds": round(self.uptime_seconds, 2),
            },
        }


class MetricsCollector:
    """
    Thread-safe metrics collector.

    Usage:
        collector = MetricsCollector()

        # Record a request
        collector.record_request(latency_ms=150, success=True)

        # Record tool usage
        collector.record_tool_call("web_search", latency_ms=450, success=True)

        # Record LLM usage
        collector.record_tokens(prompt=100, completion=50)

        # Get metrics
        metrics = collector.get_metrics()
    """

    def __init__(self):
        self._metrics = Metrics()
        self._lock = threading.Lock()

    def record_request(
        self,
        latency_ms: float,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Record a request."""
        with self._lock:
            self._metrics.total_requests += 1
            self._metrics.total_latency_ms += latency_ms

            if success:
                self._metrics.successful_requests += 1
            else:
                self._metrics.failed_requests += 1

    def record_tool_call(
        self,
        tool_name: str,
        latency_ms: float,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Record a tool call."""
        with self._lock:
            if tool_name not in self._metrics.tools:
                self._metrics.tools[tool_name] = ToolMetrics(name=tool_name)

            tool = self._metrics.tools[tool_name]
            tool.call_count += 1
            tool.total_latency_ms += latency_ms
            tool.min_latency_ms = min(tool.min_latency_ms, latency_ms)
            tool.max_latency_ms = max(tool.max_latency_ms, latency_ms)
            tool.last_called = datetime.utcnow()

            if success:
                tool.success_count += 1
            else:
                tool.error_count += 1
                tool.last_error = error

    def record_tokens(
        self,
        prompt: int = 0,
        completion: int = 0,
    ) -> None:
        """Record token usage."""
        with self._lock:
            self._metrics.total_prompt_tokens += prompt
            self._metrics.total_completion_tokens += completion

    def record_memory_retrieval(self, count: int) -> None:
        """Record memories retrieved."""
        with self._lock:
            self._metrics.total_memories_retrieved += count

    def record_memory_storage(self, count: int = 1) -> None:
        """Record memories stored."""
        with self._lock:
            self._metrics.total_memories_stored += count

    def get_metrics(self) -> Metrics:
        """Get a copy of current metrics."""
        with self._lock:
            return Metrics(
                total_requests=self._metrics.total_requests,
                successful_requests=self._metrics.successful_requests,
                failed_requests=self._metrics.failed_requests,
                total_latency_ms=self._metrics.total_latency_ms,
                total_prompt_tokens=self._metrics.total_prompt_tokens,
                total_completion_tokens=self._metrics.total_completion_tokens,
                total_memories_retrieved=self._metrics.total_memories_retrieved,
                total_memories_stored=self._metrics.total_memories_stored,
                tools=dict(self._metrics.tools),
                started_at=self._metrics.started_at,
            )

    def get_metrics_dict(self) -> dict:
        """Get metrics as dictionary."""
        return self.get_metrics().to_dict()

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._metrics = Metrics()


# Global metrics instance
_global_metrics: MetricsCollector | None = None


def get_metrics() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = MetricsCollector()
    return _global_metrics
