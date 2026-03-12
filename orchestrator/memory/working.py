"""
Working Memory: Short-term task state.

Working memory is a key-value store for the current task context.
It persists for the duration of a workflow execution and can be
accessed/modified by agents.

Use cases:
- Passing data between agents
- Tracking intermediate results
- Storing parsed/extracted information
- Maintaining state across pattern iterations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class WorkingMemoryEntry:
    """A single entry in working memory."""
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: str | None = None  # agent name
    access_count: int = 0


class WorkingMemory:
    """
    Short-term key-value memory for task execution.

    Features:
    - Type-safe get/set with defaults
    - Access tracking
    - Namespaced keys (e.g., "agent_name:key")
    - Expiration (optional)
    """

    def __init__(self):
        self._store: dict[str, WorkingMemoryEntry] = {}

    def set(
        self,
        key: str,
        value: Any,
        agent: str | None = None,
        namespace: str | None = None,
    ) -> None:
        """
        Set a value in working memory.

        Args:
            key: The key to set
            value: The value to store
            agent: Optional agent name that set this value
            namespace: Optional namespace prefix
        """
        full_key = f"{namespace}:{key}" if namespace else key

        if full_key in self._store:
            entry = self._store[full_key]
            entry.value = value
            entry.updated_at = datetime.now()
        else:
            self._store[full_key] = WorkingMemoryEntry(
                key=full_key,
                value=value,
                created_by=agent,
            )

    def get(
        self,
        key: str,
        default: Any = None,
        namespace: str | None = None,
    ) -> Any:
        """
        Get a value from working memory.

        Args:
            key: The key to retrieve
            default: Value to return if key not found
            namespace: Optional namespace prefix
        """
        full_key = f"{namespace}:{key}" if namespace else key

        if full_key in self._store:
            entry = self._store[full_key]
            entry.access_count += 1
            return entry.value
        return default

    def has(self, key: str, namespace: str | None = None) -> bool:
        """Check if a key exists."""
        full_key = f"{namespace}:{key}" if namespace else key
        return full_key in self._store

    def delete(self, key: str, namespace: str | None = None) -> bool:
        """Delete a key. Returns True if key existed."""
        full_key = f"{namespace}:{key}" if namespace else key
        if full_key in self._store:
            del self._store[full_key]
            return True
        return False

    def keys(self, namespace: str | None = None) -> list[str]:
        """List all keys, optionally filtered by namespace."""
        if namespace:
            prefix = f"{namespace}:"
            return [k for k in self._store.keys() if k.startswith(prefix)]
        return list(self._store.keys())

    def get_namespace(self, namespace: str) -> dict[str, Any]:
        """Get all key-value pairs in a namespace."""
        prefix = f"{namespace}:"
        return {
            k[len(prefix):]: v.value
            for k, v in self._store.items()
            if k.startswith(prefix)
        }

    def clear(self, namespace: str | None = None) -> None:
        """Clear all entries, optionally only in a namespace."""
        if namespace:
            prefix = f"{namespace}:"
            self._store = {
                k: v for k, v in self._store.items()
                if not k.startswith(prefix)
            }
        else:
            self._store.clear()

    def to_dict(self) -> dict[str, Any]:
        """Export all values as a dictionary."""
        return {k: v.value for k, v in self._store.items()}

    def from_dict(self, data: dict[str, Any], agent: str | None = None) -> None:
        """Import values from a dictionary."""
        for key, value in data.items():
            self.set(key, value, agent=agent)

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: str) -> bool:
        return key in self._store

    def __repr__(self) -> str:
        return f"WorkingMemory({len(self._store)} entries)"
