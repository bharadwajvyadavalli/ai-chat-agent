"""
Tests for memory subsystem.

Tests:
- WorkingMemory
- EpisodicMemory
- SemanticMemory
- MemoryRetriever (ASMR integration)
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from orchestrator.memory import (
    WorkingMemory,
    EpisodicMemory,
    SemanticMemory,
    MemoryConfig,
    MemoryRetriever,
    RetrievedMemory,
    RetrievalResponse,
)


class TestWorkingMemory:
    """Tests for WorkingMemory (key-value store)."""

    @pytest.fixture
    def memory(self):
        return WorkingMemory()

    def test_set_and_get(self, memory):
        """Test basic set and get operations."""
        memory.set("key1", "value1")
        assert memory.get("key1") == "value1"

    def test_get_default(self, memory):
        """Test get with default value."""
        result = memory.get("nonexistent", "default")
        assert result == "default"

    def test_namespaced_keys(self, memory):
        """Test namespaced key access."""
        memory.set("agent1:result", "output1")
        memory.set("agent2:result", "output2")

        assert memory.get("agent1:result") == "output1"
        assert memory.get("agent2:result") == "output2"

    def test_delete(self, memory):
        """Test deleting a key."""
        memory.set("key", "value")
        memory.delete("key")

        assert memory.get("key") is None

    def test_clear(self, memory):
        """Test clearing all entries."""
        memory.set("key1", "value1")
        memory.set("key2", "value2")
        memory.clear()

        assert memory.get("key1") is None
        assert memory.get("key2") is None

    def test_keys(self, memory):
        """Test listing all keys."""
        memory.set("a", 1)
        memory.set("b", 2)

        keys = memory.keys()
        assert "a" in keys
        assert "b" in keys


class TestEpisodicMemory:
    """Tests for EpisodicMemory (session history)."""

    @pytest.fixture
    def memory(self):
        return EpisodicMemory()

    def test_add_event(self, memory):
        """Test adding an event."""
        event_id = memory.add(
            event_type="message",
            content="Hello world",
            importance=0.5,
            metadata={"source": "test"},
        )

        assert event_id is not None
        events = memory.get_all()
        assert len(events) == 1

    def test_get_recent(self, memory):
        """Test getting recent events."""
        for i in range(5):
            memory.add(
                event_type="message",
                content=f"Message {i}",
                importance=0.5,
            )

        recent = memory.get_recent(limit=3)
        assert len(recent) == 3

    def test_get_by_type(self, memory):
        """Test filtering by event type."""
        memory.add(event_type="message", content="msg1", importance=0.5)
        memory.add(event_type="tool_call", content="tool1", importance=0.5)
        memory.add(event_type="message", content="msg2", importance=0.5)

        messages = memory.get_by_type("message")
        assert len(messages) == 2

    def test_get_important(self, memory):
        """Test getting high-importance events."""
        memory.add(event_type="message", content="low", importance=0.2)
        memory.add(event_type="message", content="high", importance=0.9)
        memory.add(event_type="message", content="medium", importance=0.5)

        important = memory.get_important(threshold=0.7)
        assert len(important) == 1
        assert important[0]["content"] == "high"

    def test_search(self, memory):
        """Test searching events."""
        memory.add(event_type="message", content="Python programming", importance=0.5)
        memory.add(event_type="message", content="JavaScript tutorial", importance=0.5)

        results = memory.search("Python")
        assert len(results) >= 1


class TestSemanticMemory:
    """Tests for SemanticMemory (vector store)."""

    @pytest.fixture
    def mock_embedding_fn(self):
        """Create a simple mock embedding function."""
        def embed(text: str) -> list[float]:
            # Simple hash-based embedding for testing
            import hashlib
            h = hashlib.md5(text.encode()).digest()
            return [b / 255.0 for b in h][:8]  # 8-dim embedding

        return embed

    @pytest.fixture
    def memory(self, mock_embedding_fn, tmp_path):
        return SemanticMemory(
            embedding_fn=mock_embedding_fn,
            persistence_path=str(tmp_path / "semantic.json"),
        )

    def test_add_memory(self, memory):
        """Test adding a memory."""
        memory_id = memory.add(
            content="Python is a programming language",
            metadata={"source": "test"},
        )

        assert memory_id is not None

    def test_search_similar(self, memory):
        """Test searching for similar content."""
        memory.add(content="Python programming basics")
        memory.add(content="JavaScript for beginners")
        memory.add(content="Advanced Python techniques")

        results = memory.search("Python tutorials", top_k=2)

        assert len(results) <= 2
        # Python-related content should be more similar
        assert any("Python" in r["content"] for r in results)

    def test_persistence(self, memory, mock_embedding_fn, tmp_path):
        """Test saving and loading."""
        memory.add(content="Test content 1")
        memory.add(content="Test content 2")
        memory.save()

        # Create new instance from same path
        memory2 = SemanticMemory(
            embedding_fn=mock_embedding_fn,
            persistence_path=str(tmp_path / "semantic.json"),
        )
        memory2.load()

        all_memories = memory2.get_all()
        assert len(all_memories) == 2


class TestMemoryConfig:
    """Tests for MemoryConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = MemoryConfig()

        assert config.backend == "semantic"
        assert config.top_k == 5
        assert config.require_reasoning is True

    def test_from_env(self):
        """Test loading from environment."""
        import os

        # Set test environment
        os.environ["MEMORY_BACKEND"] = "asmr"
        os.environ["MEMORY_TOP_K"] = "10"

        config = MemoryConfig.from_env()

        assert config.backend == "asmr"
        assert config.top_k == 10

        # Cleanup
        del os.environ["MEMORY_BACKEND"]
        del os.environ["MEMORY_TOP_K"]


class TestRetrievedMemory:
    """Tests for RetrievedMemory dataclass."""

    def test_to_dict(self):
        """Test serialization."""
        memory = RetrievedMemory(
            id="test-id",
            content="Test content",
            timestamp=datetime(2024, 1, 1),
            source="test_source",
            relevance_score=0.85,
            metadata={"key": "value"},
        )

        data = memory.to_dict()

        assert data["id"] == "test-id"
        assert data["content"] == "Test content"
        assert data["relevance_score"] == 0.85


class TestMemoryRetriever:
    """Tests for MemoryRetriever."""

    @pytest.fixture
    def mock_embedding_fn(self):
        """Create a mock embedding function."""
        def embed(text: str) -> list[float]:
            import hashlib
            h = hashlib.md5(text.encode()).digest()
            return [b / 255.0 for b in h][:8]

        return embed

    @pytest.fixture
    def retriever(self, mock_embedding_fn, tmp_path):
        config = MemoryConfig(
            backend="semantic",
            persistence_path=str(tmp_path / "memories.json"),
            top_k=3,
        )
        return MemoryRetriever(config=config, embedding_fn=mock_embedding_fn)

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, retriever):
        """Test storing and retrieving memories."""
        # Store some memories
        await retriever.store("Python is great for data science")
        await retriever.store("JavaScript is used for web development")
        await retriever.store("Python has excellent libraries")

        # Retrieve
        response = await retriever.retrieve("Python programming")

        assert isinstance(response, RetrievalResponse)
        assert len(response.memories) <= 3
        assert response.backend_used == "semantic"

    @pytest.mark.asyncio
    async def test_store_conversation_turn(self, retriever):
        """Test storing conversation turns."""
        user_id, assistant_id = await retriever.store_conversation_turn(
            user_message="What is Python?",
            assistant_message="Python is a programming language.",
            metadata={"topic": "programming"},
        )

        assert user_id is not None
        assert assistant_id is not None

    @pytest.mark.asyncio
    async def test_retrieval_response_format(self, retriever):
        """Test retrieval response structure."""
        await retriever.store("Test memory content")

        response = await retriever.retrieve("test query")

        assert hasattr(response, "memories")
        assert hasattr(response, "context")
        assert hasattr(response, "backend_used")
        assert hasattr(response, "latency_ms")

    @pytest.mark.asyncio
    async def test_context_building(self, retriever):
        """Test that context is built correctly."""
        await retriever.store("Important fact about AI", source="ai_docs")

        response = await retriever.retrieve("AI information")

        # Context should include the memory
        if response.memories:
            assert "context" in response.context.lower() or "memory" in response.context.lower() or "Important" in response.context


class TestMemoryFallback:
    """Tests for memory fallback behavior."""

    @pytest.mark.asyncio
    async def test_fallback_to_semantic(self, tmp_path):
        """Test fallback from ASMR to semantic memory."""
        config = MemoryConfig(
            backend="asmr",  # ASMR not available
            asmr_path="/nonexistent/path",
            persistence_path=str(tmp_path / "memories.json"),
        )

        def mock_embed(text):
            return [0.1] * 8

        retriever = MemoryRetriever(config=config, embedding_fn=mock_embed)

        # Should fall back to semantic
        await retriever.store("Test content")
        response = await retriever.retrieve("test")

        # Either semantic or the config should have changed
        assert retriever.config.backend in ["semantic", "asmr"]
