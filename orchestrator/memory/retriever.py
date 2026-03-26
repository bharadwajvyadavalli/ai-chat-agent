"""
ASMR Integration Bridge: Connect the agent-memory-system to this framework.

This module provides:
- ASMR integration when available (multi-agent retrieval)
- Fallback to semantic memory when ASMR is unavailable
- Unified interface for memory storage and retrieval
- Context injection for LLM prompts
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class MemoryConfig:
    """Configuration for memory backend."""
    backend: str = "semantic"  # "asmr", "semantic", "sqlite"
    asmr_path: str | None = None  # Path to agent-memory-system
    persistence_path: str = "data/memories.json"
    embedding_model: str = "text-embedding-3-small"
    top_k: int = 5
    require_reasoning: bool = True  # For ASMR: use agent reasoning
    max_context_tokens: int = 2000

    @classmethod
    def from_env(cls) -> MemoryConfig:
        """Load configuration from environment variables."""
        return cls(
            backend=os.getenv("MEMORY_BACKEND", "semantic"),
            asmr_path=os.getenv("ASMR_PATH"),
            persistence_path=os.getenv("MEMORY_PERSISTENCE_PATH", "data/memories.json"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            top_k=int(os.getenv("MEMORY_TOP_K", "5")),
            require_reasoning=os.getenv("MEMORY_REASONING", "true").lower() == "true",
            max_context_tokens=int(os.getenv("MEMORY_MAX_TOKENS", "2000")),
        )


@dataclass
class RetrievedMemory:
    """A single retrieved memory."""
    id: str
    content: str
    timestamp: datetime | None = None
    source: str = ""
    relevance_score: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "source": self.source,
            "relevance_score": self.relevance_score,
            "metadata": self.metadata,
        }


@dataclass
class RetrievalResponse:
    """Response from memory retrieval."""
    memories: list[RetrievedMemory]
    context: str  # Formatted context for LLM
    backend_used: str  # Which backend was used
    latency_ms: float = 0.0
    metadata: dict = field(default_factory=dict)


class MemoryRetriever:
    """
    Unified memory retrieval interface.

    Supports multiple backends:
    - ASMR: Full multi-agent retrieval with reasoning
    - Semantic: Vector-based similarity search
    - SQLite: Basic conversation history (fallback)
    """

    def __init__(
        self,
        config: MemoryConfig | None = None,
        embedding_fn: Callable[[str], list[float]] | None = None,
    ):
        """
        Initialize memory retriever.

        Args:
            config: Memory configuration (loads from env if None)
            embedding_fn: Custom embedding function (uses OpenAI if None)
        """
        self.config = config or MemoryConfig.from_env()
        self._embedding_fn = embedding_fn
        self._asmr_pipeline = None
        self._semantic_memory = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of backends."""
        if self._initialized:
            return

        if self.config.backend == "asmr":
            self._init_asmr()
        elif self.config.backend == "semantic":
            self._init_semantic()
        # SQLite is always available as fallback

        self._initialized = True

    def _init_asmr(self) -> bool:
        """Initialize ASMR backend."""
        asmr_path = self.config.asmr_path or os.getenv("ASMR_PATH", "../agent-memory-system")
        asmr_path = Path(asmr_path).resolve()

        if not asmr_path.exists():
            logger.warning(f"ASMR path not found: {asmr_path}. Falling back to semantic memory.")
            self.config.backend = "semantic"
            return self._init_semantic()

        try:
            # Add ASMR to path
            if str(asmr_path) not in sys.path:
                sys.path.insert(0, str(asmr_path))

            from retrieval.pipeline import RetrievalPipeline
            from agents.orchestrator import Orchestrator
            from agents.relevance import RelevanceAgent
            from agents.recency import RecencyAgent
            from agents.conflict import ConflictAgent
            from agents.synthesis import SynthesisAgent

            # Configure agents (use OpenAI by default)
            orchestrator = Orchestrator(
                relevance_agent=RelevanceAgent(llm_provider="openai"),
                recency_agent=RecencyAgent(llm_provider="openai"),
                conflict_agent=ConflictAgent(llm_provider="openai"),
                synthesis_agent=SynthesisAgent(llm_provider="openai"),
                parallel_first_pass=True,
            )

            self._asmr_pipeline = RetrievalPipeline(orchestrator=orchestrator)
            logger.info("ASMR backend initialized successfully")
            return True

        except ImportError as e:
            logger.warning(f"Failed to import ASMR: {e}. Falling back to semantic memory.")
            self.config.backend = "semantic"
            return self._init_semantic()

        except Exception as e:
            logger.error(f"Error initializing ASMR: {e}. Falling back to semantic memory.")
            self.config.backend = "semantic"
            return self._init_semantic()

    def _init_semantic(self) -> bool:
        """Initialize semantic memory backend."""
        try:
            from .semantic import SemanticMemory

            self._semantic_memory = SemanticMemory(
                embedding_fn=self._embedding_fn or self._get_openai_embedding,
                persistence_path=self.config.persistence_path,
            )
            logger.info("Semantic memory backend initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize semantic memory: {e}")
            return False

    def _get_openai_embedding(self, text: str) -> list[float]:
        """Get embedding using OpenAI."""
        import openai
        client = openai.OpenAI()
        response = client.embeddings.create(
            model=self.config.embedding_model,
            input=text,
        )
        return response.data[0].embedding

    async def store(
        self,
        content: str,
        source: str = "conversation",
        metadata: dict | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """
        Store a memory.

        Args:
            content: Memory content
            source: Source identifier
            metadata: Additional metadata
            tags: Tags for filtering

        Returns:
            Memory ID
        """
        self._ensure_initialized()

        metadata = metadata or {}
        tags = tags or []

        if self.config.backend == "asmr" and self._asmr_pipeline:
            memory = self._asmr_pipeline.add_memory(
                content=content,
                source=source,
                metadata=metadata,
                tags=tags,
            )
            return memory.id

        elif self._semantic_memory:
            return self._semantic_memory.add(
                content=content,
                metadata={
                    "source": source,
                    "tags": tags,
                    **metadata,
                },
            )

        else:
            raise RuntimeError("No memory backend available")

    async def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        filters: dict | None = None,
    ) -> RetrievalResponse:
        """
        Retrieve relevant memories.

        Args:
            query: Search query
            top_k: Number of results (uses config default if None)
            filters: Optional filters (sources, tags, time_range)

        Returns:
            RetrievalResponse with memories and formatted context
        """
        import time
        start_time = time.time()

        self._ensure_initialized()
        top_k = top_k or self.config.top_k

        memories = []
        context = ""
        backend_used = self.config.backend

        try:
            if self.config.backend == "asmr" and self._asmr_pipeline:
                result = self._asmr_pipeline.retrieve(
                    query=query,
                    top_k=top_k,
                    require_reasoning=self.config.require_reasoning,
                    filters=filters,
                )

                memories = [
                    RetrievedMemory(
                        id=m.id,
                        content=m.content,
                        timestamp=m.timestamp,
                        source=m.source,
                        relevance_score=1.0,  # ASMR filters, so all are relevant
                        metadata=m.metadata,
                    )
                    for m in result.memories
                ]
                context = result.final_context
                backend_used = "asmr"

            elif self._semantic_memory:
                results = self._semantic_memory.search(query, top_k=top_k)
                memories = [
                    RetrievedMemory(
                        id=r["id"],
                        content=r["content"],
                        timestamp=r.get("timestamp"),
                        source=r.get("metadata", {}).get("source", ""),
                        relevance_score=r["similarity"],
                        metadata=r.get("metadata", {}),
                    )
                    for r in results
                ]
                context = self._build_context(memories)
                backend_used = "semantic"

            else:
                logger.warning("No memory backend available")
                backend_used = "none"

        except Exception as e:
            logger.error(f"Memory retrieval failed: {e}")
            backend_used = f"error:{type(e).__name__}"

        latency_ms = (time.time() - start_time) * 1000

        return RetrievalResponse(
            memories=memories,
            context=context,
            backend_used=backend_used,
            latency_ms=latency_ms,
            metadata={
                "query": query,
                "top_k": top_k,
                "result_count": len(memories),
            },
        )

    def _build_context(self, memories: list[RetrievedMemory]) -> str:
        """Build context string from memories."""
        if not memories:
            return ""

        lines = ["Relevant context from memory:\n"]
        for i, m in enumerate(memories, 1):
            source_info = f" [Source: {m.source}]" if m.source else ""
            lines.append(f"{i}. {m.content}{source_info}")

        return "\n".join(lines)

    async def store_conversation_turn(
        self,
        user_message: str,
        assistant_message: str,
        metadata: dict | None = None,
    ) -> tuple[str, str]:
        """
        Store a conversation turn as memories.

        Args:
            user_message: User's message
            assistant_message: Assistant's response
            metadata: Additional metadata (topic, entities, etc.)

        Returns:
            Tuple of (user_memory_id, assistant_memory_id)
        """
        metadata = metadata or {}
        timestamp = datetime.utcnow()

        # Store user message
        user_id = await self.store(
            content=f"User: {user_message}",
            source="conversation",
            metadata={
                "role": "user",
                "timestamp": timestamp.isoformat(),
                **metadata,
            },
            tags=["conversation", "user"],
        )

        # Store assistant response
        assistant_id = await self.store(
            content=f"Assistant: {assistant_message}",
            source="conversation",
            metadata={
                "role": "assistant",
                "timestamp": timestamp.isoformat(),
                "in_response_to": user_id,
                **metadata,
            },
            tags=["conversation", "assistant"],
        )

        return user_id, assistant_id

    def get_context_for_prompt(
        self,
        query: str,
        max_tokens: int | None = None,
    ) -> str:
        """
        Synchronous method to get context for LLM prompt injection.

        Args:
            query: The current query/message
            max_tokens: Maximum context tokens

        Returns:
            Formatted context string
        """
        import asyncio

        # Run async method synchronously
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context, create a new loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.retrieve(query))
                result = future.result()
        else:
            result = loop.run_until_complete(self.retrieve(query))

        return result.context

    def save(self) -> None:
        """Persist memories to disk."""
        if self.config.backend == "asmr" and self._asmr_pipeline:
            self._asmr_pipeline.save()
        elif self._semantic_memory:
            self._semantic_memory.save()


# Convenience function to get global retriever
_global_retriever: MemoryRetriever | None = None


def get_memory_retriever(config: MemoryConfig | None = None) -> MemoryRetriever:
    """Get or create the global memory retriever."""
    global _global_retriever
    if _global_retriever is None:
        _global_retriever = MemoryRetriever(config)
    return _global_retriever
