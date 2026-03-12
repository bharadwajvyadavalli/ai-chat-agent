"""
Message primitives for multi-agent communication.

Messages are the unit of communication between agents. They carry content,
metadata about the source/confidence, and optional artifacts (files, code, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class MessageRole(Enum):
    """Role of the message sender."""
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    TOOL = "tool"


class ArtifactType(Enum):
    """Type of artifact attached to a message."""
    CODE = "code"
    FILE = "file"
    JSON = "json"
    IMAGE = "image"
    TABLE = "table"


@dataclass
class Artifact:
    """
    An artifact attached to a message.

    Artifacts represent structured data produced by agents:
    code snippets, files, JSON data, etc.
    """
    type: ArtifactType
    content: Any
    name: str | None = None
    language: str | None = None  # for code artifacts
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.type == ArtifactType.CODE and not self.language:
            self.language = "python"  # default


@dataclass
class Message:
    """
    The unit of communication between agents.

    Messages flow through the orchestration pipeline, carrying:
    - content: The main text content
    - role: Who sent this message
    - metadata: Source, confidence, token usage, timing
    - artifacts: Structured data attachments
    """
    content: str
    role: MessageRole = MessageRole.AGENT

    # Identity
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)

    # Source tracking
    source_agent: str | None = None
    parent_message_id: str | None = None

    # Quality signals
    confidence: float | None = None  # 0.0 to 1.0

    # Cost tracking
    tokens_used: int | None = None
    latency_ms: int | None = None
    model: str | None = None

    # Attachments
    artifacts: list[Artifact] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def add_artifact(self, artifact: Artifact) -> "Message":
        """Add an artifact to this message. Returns self for chaining."""
        self.artifacts.append(artifact)
        return self

    def with_metadata(self, **kwargs) -> "Message":
        """Add metadata to this message. Returns self for chaining."""
        self.metadata.update(kwargs)
        return self

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "role": self.role.value,
            "timestamp": self.timestamp.isoformat(),
            "source_agent": self.source_agent,
            "parent_message_id": self.parent_message_id,
            "confidence": self.confidence,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "model": self.model,
            "artifacts": [
                {
                    "type": a.type.value,
                    "content": a.content,
                    "name": a.name,
                    "language": a.language,
                    "metadata": a.metadata,
                }
                for a in self.artifacts
            ],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """Create a Message from a dictionary."""
        artifacts = [
            Artifact(
                type=ArtifactType(a["type"]),
                content=a["content"],
                name=a.get("name"),
                language=a.get("language"),
                metadata=a.get("metadata", {}),
            )
            for a in data.get("artifacts", [])
        ]
        return cls(
            id=data.get("id", str(uuid4())),
            content=data["content"],
            role=MessageRole(data.get("role", "agent")),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
            source_agent=data.get("source_agent"),
            parent_message_id=data.get("parent_message_id"),
            confidence=data.get("confidence"),
            tokens_used=data.get("tokens_used"),
            latency_ms=data.get("latency_ms"),
            model=data.get("model"),
            artifacts=artifacts,
            metadata=data.get("metadata", {}),
        )

    def __str__(self) -> str:
        preview = self.content[:100] + "..." if len(self.content) > 100 else self.content
        return f"Message({self.role.value}, {self.source_agent or 'unknown'}): {preview}"
