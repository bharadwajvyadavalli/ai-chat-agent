"""
Structured Logging: JSON-formatted logging with request context.

Features:
- JSON output format for machine parsing
- Request-scoped context
- Performance timing
- Correlation IDs
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any

# Log levels
class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class JSONFormatter(logging.Formatter):
    """Format log records as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class StructuredLogger(logging.Logger):
    """Logger with structured context support."""

    def __init__(self, name: str, level: int = logging.NOTSET):
        super().__init__(name, level)
        self._context: dict = {}

    def set_context(self, **kwargs) -> None:
        """Set context fields for all subsequent logs."""
        self._context.update(kwargs)

    def clear_context(self) -> None:
        """Clear all context fields."""
        self._context.clear()

    def _log_with_context(
        self,
        level: int,
        msg: str,
        args: tuple,
        exc_info=None,
        extra: dict | None = None,
        **kwargs
    ) -> None:
        """Log with context merged."""
        extra = extra or {}
        extra["extra_data"] = {**self._context, **kwargs}
        super()._log(level, msg, args, exc_info=exc_info, extra=extra)

    def debug(self, msg: str, *args, **kwargs) -> None:
        self._log_with_context(logging.DEBUG, msg, args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        self._log_with_context(logging.INFO, msg, args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        self._log_with_context(logging.WARNING, msg, args, **kwargs)

    def error(self, msg: str, *args, exc_info=None, **kwargs) -> None:
        self._log_with_context(logging.ERROR, msg, args, exc_info=exc_info, **kwargs)

    def critical(self, msg: str, *args, exc_info=None, **kwargs) -> None:
        self._log_with_context(logging.CRITICAL, msg, args, exc_info=exc_info, **kwargs)


def configure_logging(
    level: str | LogLevel = "INFO",
    json_format: bool = True,
    log_file: str | None = None,
) -> None:
    """
    Configure global logging.

    Args:
        level: Log level
        json_format: Use JSON output format
        log_file: Optional file to write logs to
    """
    # Set custom logger class
    logging.setLoggerClass(StructuredLogger)

    # Get root logger
    root = logging.getLogger()

    # Set level
    if isinstance(level, LogLevel):
        level = level.value
    root.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root.handlers.clear()

    # Create formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger."""
    logging.setLoggerClass(StructuredLogger)
    return logging.getLogger(name)


@dataclass
class RequestLog:
    """Structured log for a single request."""
    request_id: str
    timestamp: str
    query: str
    route_decision: str = ""
    tools_called: list[dict] = field(default_factory=list)
    memories_retrieved: int = 0
    llm_tokens: dict = field(default_factory=dict)
    total_latency_ms: float = 0.0
    success: bool = True
    error: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class RequestLogger:
    """
    Per-request logger with automatic timing and context.

    Usage:
        with RequestLogger(query="What is the weather?") as log:
            log.record_tool("web_search", latency_ms=450, success=True)
            log.record_llm_usage(prompt_tokens=100, completion_tokens=50)
        # Automatically logs when context exits
    """

    def __init__(
        self,
        query: str,
        request_id: str | None = None,
        logger: StructuredLogger | None = None,
    ):
        self.request_id = request_id or str(uuid.uuid4())[:8]
        self.query = query
        self._logger = logger or get_logger("request")
        self._start_time = None
        self._log = RequestLog(
            request_id=self.request_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            query=query,
        )

    def __enter__(self) -> RequestLogger:
        self._start_time = time.time()
        self._logger.info(
            "Request started",
            request_id=self.request_id,
            query=self.query[:100],
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._log.total_latency_ms = (time.time() - self._start_time) * 1000

        if exc_type:
            self._log.success = False
            self._log.error = str(exc_val)

        # Log the complete request
        self._logger.info(
            "Request completed",
            **self._log.to_dict(),
        )

    def record_route(self, decision: str) -> None:
        """Record routing decision."""
        self._log.route_decision = decision

    def record_tool(
        self,
        name: str,
        latency_ms: float,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Record a tool call."""
        self._log.tools_called.append({
            "name": name,
            "latency_ms": latency_ms,
            "success": success,
            "error": error,
        })

    def record_llm_usage(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        model: str = "",
    ) -> None:
        """Record LLM token usage."""
        self._log.llm_tokens = {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": prompt_tokens + completion_tokens,
            "model": model,
        }

    def record_memories(self, count: int) -> None:
        """Record number of memories retrieved."""
        self._log.memories_retrieved = count

    def add_metadata(self, **kwargs) -> None:
        """Add arbitrary metadata."""
        self._log.metadata.update(kwargs)

    def mark_error(self, error: str) -> None:
        """Mark request as failed."""
        self._log.success = False
        self._log.error = error

    @property
    def log(self) -> RequestLog:
        """Get the current log state."""
        return self._log


# Auto-configure from environment on import
_configured = False
if not _configured:
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_format = os.getenv("LOG_FORMAT", "json").lower() == "json"
    log_file = os.getenv("LOG_FILE")
    configure_logging(level=log_level, json_format=log_format, log_file=log_file)
    _configured = True
