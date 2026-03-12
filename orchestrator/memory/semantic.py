"""
Semantic Memory: Long-term knowledge storage with vector search.

Semantic memory stores information with embeddings, enabling:
- Similarity-based retrieval
- RAG (Retrieval Augmented Generation)
- Knowledge accumulation across sessions

Use cases:
- Storing learned facts and preferences
- Building a knowledge base
- RAG for grounding responses
- Cross-session memory
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np


@dataclass
class MemoryEntry:
    """
    A single entry in semantic memory.

    Each entry has:
    - content: The text content
    - embedding: Vector representation for similarity search
    - metadata: Additional structured data
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    content: str = ""
    embedding: list[float] | None = None
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    # Source tracking
    source: str | None = None  # where this came from
    source_type: str = "unknown"  # document, conversation, tool, etc.

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "source": self.source,
            "source_type": self.source_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        return cls(
            id=data.get("id", str(uuid4())),
            content=data.get("content", ""),
            embedding=data.get("embedding"),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            source=data.get("source"),
            source_type=data.get("source_type", "unknown"),
        )


class SemanticMemory:
    """
    Vector-based semantic memory with similarity search.

    Features:
    - Add entries with automatic embedding generation
    - Similarity search using cosine similarity
    - Hybrid search (semantic + keyword)
    - Persistence to disk
    - Integration with external vector stores

    By default, uses a simple in-memory store. For production,
    connect to ChromaDB, Pinecone, Weaviate, etc.
    """

    def __init__(
        self,
        embedding_fn: callable | None = None,
        embedding_dim: int = 1536,  # OpenAI default
    ):
        """
        Initialize semantic memory.

        Args:
            embedding_fn: Function to generate embeddings.
                          Signature: (text: str) -> list[float]
                          If None, uses OpenAI embeddings.
            embedding_dim: Dimension of embedding vectors
        """
        self.entries: list[MemoryEntry] = []
        self.embedding_fn = embedding_fn
        self.embedding_dim = embedding_dim
        self._embeddings_matrix: np.ndarray | None = None

    async def add(
        self,
        content: str,
        metadata: dict | None = None,
        source: str | None = None,
        source_type: str = "unknown",
        embedding: list[float] | None = None,
    ) -> MemoryEntry:
        """
        Add an entry to semantic memory.

        Args:
            content: The text content to store
            metadata: Additional structured data
            source: Where this content came from
            source_type: Type of source (document, conversation, etc.)
            embedding: Pre-computed embedding (optional)
        """
        # Generate embedding if not provided
        if embedding is None:
            embedding = await self._get_embedding(content)

        entry = MemoryEntry(
            content=content,
            embedding=embedding,
            metadata=metadata or {},
            source=source,
            source_type=source_type,
        )
        self.entries.append(entry)

        # Invalidate cached matrix
        self._embeddings_matrix = None

        return entry

    async def search(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.0,
        filter_fn: callable | None = None,
    ) -> list[tuple[MemoryEntry, float]]:
        """
        Search for similar entries.

        Args:
            query: The search query
            top_k: Number of results to return
            threshold: Minimum similarity score (0-1)
            filter_fn: Optional function to filter entries

        Returns:
            List of (entry, similarity_score) tuples
        """
        if not self.entries:
            return []

        # Get query embedding
        query_embedding = await self._get_embedding(query)

        # Build embeddings matrix if needed
        if self._embeddings_matrix is None:
            self._build_embeddings_matrix()

        # Compute similarities
        query_vec = np.array(query_embedding)
        similarities = self._cosine_similarity(query_vec, self._embeddings_matrix)

        # Get top results
        results = []
        indices = np.argsort(similarities)[::-1]

        for idx in indices:
            if len(results) >= top_k:
                break

            score = float(similarities[idx])
            if score < threshold:
                continue

            entry = self.entries[idx]

            # Apply filter
            if filter_fn and not filter_fn(entry):
                continue

            results.append((entry, score))

        return results

    async def search_hybrid(
        self,
        query: str,
        top_k: int = 5,
        semantic_weight: float = 0.7,
    ) -> list[tuple[MemoryEntry, float]]:
        """
        Hybrid search combining semantic and keyword matching.

        Args:
            query: The search query
            top_k: Number of results to return
            semantic_weight: Weight for semantic vs keyword (0-1)
        """
        # Semantic search
        semantic_results = await self.search(query, top_k=top_k * 2)
        semantic_scores = {entry.id: score for entry, score in semantic_results}

        # Keyword search
        query_terms = set(query.lower().split())
        keyword_scores = {}
        for entry in self.entries:
            content_terms = set(entry.content.lower().split())
            overlap = len(query_terms & content_terms)
            if overlap > 0:
                keyword_scores[entry.id] = overlap / len(query_terms)

        # Combine scores
        all_ids = set(semantic_scores.keys()) | set(keyword_scores.keys())
        combined = []
        for entry_id in all_ids:
            sem_score = semantic_scores.get(entry_id, 0)
            key_score = keyword_scores.get(entry_id, 0)
            combined_score = semantic_weight * sem_score + (1 - semantic_weight) * key_score
            entry = next(e for e in self.entries if e.id == entry_id)
            combined.append((entry, combined_score))

        # Sort and return top_k
        combined.sort(key=lambda x: x[1], reverse=True)
        return combined[:top_k]

    def get_by_source(self, source: str) -> list[MemoryEntry]:
        """Get all entries from a specific source."""
        return [e for e in self.entries if e.source == source]

    def get_by_type(self, source_type: str) -> list[MemoryEntry]:
        """Get all entries of a specific source type."""
        return [e for e in self.entries if e.source_type == source_type]

    def delete(self, entry_id: str) -> bool:
        """Delete an entry by ID."""
        for i, entry in enumerate(self.entries):
            if entry.id == entry_id:
                del self.entries[i]
                self._embeddings_matrix = None
                return True
        return False

    def clear(self):
        """Clear all entries."""
        self.entries = []
        self._embeddings_matrix = None

    async def _get_embedding(self, text: str) -> list[float]:
        """Get embedding for text."""
        if self.embedding_fn:
            return await self.embedding_fn(text)
        return await self._openai_embedding(text)

    async def _openai_embedding(self, text: str) -> list[float]:
        """Get embedding using OpenAI API."""
        import openai
        client = openai.AsyncOpenAI()
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding

    def _build_embeddings_matrix(self):
        """Build numpy matrix of all embeddings."""
        embeddings = []
        for entry in self.entries:
            if entry.embedding:
                embeddings.append(entry.embedding)
            else:
                # Use zero vector for entries without embeddings
                embeddings.append([0.0] * self.embedding_dim)
        self._embeddings_matrix = np.array(embeddings)

    def _cosine_similarity(self, query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
        """Compute cosine similarity between query and all entries."""
        # Normalize
        query_norm = query / (np.linalg.norm(query) + 1e-8)
        matrix_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-8)
        # Dot product
        return np.dot(matrix_norm, query_norm)

    def save(self, path: str | Path):
        """Save to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [e.to_dict() for e in self.entries]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: str | Path):
        """Load from JSON file."""
        path = Path(path)
        if not path.exists():
            return
        with open(path) as f:
            data = json.load(f)
        self.entries = [MemoryEntry.from_dict(e) for e in data]
        self._embeddings_matrix = None

    def __len__(self) -> int:
        return len(self.entries)

    def __repr__(self) -> str:
        return f"SemanticMemory({len(self.entries)} entries)"
