"""
Episodic Memory: Session history.

Episodic memory tracks what happened during a session:
- Messages exchanged
- Actions taken
- Decisions made
- Outcomes observed

Use cases:
- Providing conversation context to agents
- Debugging and auditing
- Learning from past interactions
- Detecting patterns and repeated errors
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class Episode:
    """
    A single episode (event) in memory.

    Episodes capture significant events:
    - Agent messages
    - Tool calls and results
    - Pattern transitions
    - Errors and recoveries
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: str = "message"  # message, tool_call, error, decision, etc.
    agent: str | None = None
    content: str = ""
    metadata: dict = field(default_factory=dict)

    # For importance-based retrieval (Generative Agents style)
    importance: float = 0.5  # 0.0 to 1.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "agent": self.agent,
            "content": self.content,
            "metadata": self.metadata,
            "importance": self.importance,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Episode":
        return cls(
            id=data.get("id", str(uuid4())),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
            event_type=data.get("event_type", "message"),
            agent=data.get("agent"),
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
            importance=data.get("importance", 0.5),
        )


class EpisodicMemory:
    """
    Session history memory.

    Features:
    - Chronological event storage
    - Retrieval by recency, importance, or type
    - Summarization for long contexts
    - Persistence to disk
    """

    def __init__(self, max_episodes: int = 1000):
        self.episodes: list[Episode] = []
        self.max_episodes = max_episodes

    def add(
        self,
        content: str,
        event_type: str = "message",
        agent: str | None = None,
        importance: float = 0.5,
        **metadata,
    ) -> Episode:
        """
        Add an episode to memory.

        Args:
            content: The event content/description
            event_type: Type of event (message, tool_call, error, etc.)
            agent: Agent that generated this event
            importance: How important this event is (0-1)
            **metadata: Additional metadata
        """
        episode = Episode(
            event_type=event_type,
            agent=agent,
            content=content,
            metadata=metadata,
            importance=importance,
        )
        self.episodes.append(episode)

        # Trim if over limit
        if len(self.episodes) > self.max_episodes:
            self._trim()

        return episode

    def get_recent(self, n: int = 10) -> list[Episode]:
        """Get the n most recent episodes."""
        return self.episodes[-n:]

    def get_by_type(self, event_type: str, limit: int = 100) -> list[Episode]:
        """Get episodes of a specific type."""
        matching = [e for e in self.episodes if e.event_type == event_type]
        return matching[-limit:]

    def get_by_agent(self, agent: str, limit: int = 100) -> list[Episode]:
        """Get episodes from a specific agent."""
        matching = [e for e in self.episodes if e.agent == agent]
        return matching[-limit:]

    def get_important(self, threshold: float = 0.7, limit: int = 20) -> list[Episode]:
        """Get episodes above an importance threshold."""
        important = [e for e in self.episodes if e.importance >= threshold]
        # Sort by importance, then recency
        important.sort(key=lambda e: (e.importance, e.timestamp), reverse=True)
        return important[:limit]

    def search(self, query: str, limit: int = 10) -> list[Episode]:
        """
        Simple text search in episode content.

        For semantic search, use SemanticMemory instead.
        """
        query_lower = query.lower()
        matching = [
            e for e in self.episodes
            if query_lower in e.content.lower()
        ]
        return matching[-limit:]

    def get_context_window(
        self,
        max_tokens: int = 2000,
        include_types: list[str] | None = None,
    ) -> str:
        """
        Get a formatted context window for prompts.

        Prioritizes:
        1. Recent messages
        2. High-importance events
        3. Relevant event types
        """
        # Filter by type if specified
        episodes = self.episodes
        if include_types:
            episodes = [e for e in episodes if e.event_type in include_types]

        # Take recent, respecting token limit (rough estimate: 4 chars per token)
        char_limit = max_tokens * 4
        result_parts = []
        total_chars = 0

        for episode in reversed(episodes):
            part = f"[{episode.event_type}] {episode.agent or 'system'}: {episode.content}"
            if total_chars + len(part) > char_limit:
                break
            result_parts.append(part)
            total_chars += len(part)

        result_parts.reverse()
        return "\n".join(result_parts)

    def summarize(self, max_length: int = 500) -> str:
        """
        Create a summary of the session.

        This is a simple extractive summary. For better summaries,
        use an LLM-based summarizer.
        """
        if not self.episodes:
            return "No events recorded."

        # Get important episodes
        important = self.get_important(threshold=0.6, limit=5)

        # Get recent episodes
        recent = self.get_recent(5)

        # Combine unique episodes
        seen = set()
        combined = []
        for ep in important + recent:
            if ep.id not in seen:
                seen.add(ep.id)
                combined.append(ep)

        # Format summary
        lines = [f"Session with {len(self.episodes)} events:"]
        for ep in combined[:10]:
            preview = ep.content[:100] + "..." if len(ep.content) > 100 else ep.content
            lines.append(f"- [{ep.event_type}] {preview}")

        summary = "\n".join(lines)
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."

        return summary

    def _trim(self):
        """Trim memory to max_episodes, keeping important events."""
        if len(self.episodes) <= self.max_episodes:
            return

        # Keep most recent half
        keep_recent = self.max_episodes // 2
        recent = self.episodes[-keep_recent:]

        # From older episodes, keep high-importance ones
        older = self.episodes[:-keep_recent]
        keep_important = self.max_episodes - keep_recent
        important = sorted(older, key=lambda e: e.importance, reverse=True)[:keep_important]

        # Combine and sort by timestamp
        self.episodes = sorted(important + recent, key=lambda e: e.timestamp)

    def clear(self):
        """Clear all episodes."""
        self.episodes = []

    def save(self, path: str | Path):
        """Save episodes to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [e.to_dict() for e in self.episodes]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: str | Path):
        """Load episodes from a JSON file."""
        path = Path(path)
        if not path.exists():
            return
        with open(path) as f:
            data = json.load(f)
        self.episodes = [Episode.from_dict(e) for e in data]

    def __len__(self) -> int:
        return len(self.episodes)

    def __repr__(self) -> str:
        return f"EpisodicMemory({len(self.episodes)} episodes)"
