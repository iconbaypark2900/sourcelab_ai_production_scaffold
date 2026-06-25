"""Compressed local search index.

Instruction:
- This scaffold uses in-memory vectors for readability.
- Production should replace this with Qdrant, pgvector, FAISS, or hybrid search.
- Always return source IDs and chunk IDs for grounding.
- PocketIndex now supports pluggable embedding backends and vector stores.
"""

from __future__ import annotations

import math

import numpy as np

from sourcelab.core.models import SearchResult, SourceChunk
from sourcelab.retrieval.compression import int8_dequantize, int8_quantize
from sourcelab.retrieval.embedding_backends import (
    HashEmbeddingBackend,
    BaseEmbeddingBackend,
    get_embedding_backend,
)
from sourcelab.retrieval.vector_store import (
    InMemoryVectorStore,
    BaseVectorStore,
    get_vector_store,
)
from sourcelab.retrieval.chunking import TokenChunker
from sourcelab.sources.chunker import simple_chunk_source
from sourcelab.sources.registry import SourceRegistry
from sourcelab.sources.trust import trust_weight


class PocketIndex:
    """Small compressed vector index for approved sources.

    Supports pluggable embedding backends and vector stores.
    Default: HashEmbeddingBackend + InMemoryVectorStore + int8 compression.
    """

    def __init__(
        self,
        chunks: list[SourceChunk],
        titles: dict[str, str],
        dim: int = 128,
        backend: BaseEmbeddingBackend | None = None,
        store: BaseVectorStore | None = None,
    ):
        self.chunks = chunks
        self.titles = titles
        self.dim = dim
        self.backend = backend or HashEmbeddingBackend()
        self.store = store or InMemoryVectorStore()

        # Create embeddings using the backend
        texts = [c.text for c in chunks]
        if texts:
            self.fp32 = self.backend.embed_batch(texts, dim=dim)
        else:
            self.fp32 = np.zeros((0, dim), dtype=np.float32)

        # Compress for storage report
        self.int8, self.scale = int8_quantize(self.fp32)

    @classmethod
    def from_registry(
        cls,
        registry: SourceRegistry,
        dim: int = 128,
        backend_name: str = "hash",
        store_name: str = "memory",
    ) -> "PocketIndex":
        """Create a PocketIndex from a SourceRegistry.

        Args:
            registry: Source registry with approved sources.
            dim: Embedding dimension.
            backend_name: Name of the embedding backend.
            store_name: Name of the vector store.
        """
        return cls._from_registry(registry, dim=dim, backend_name=backend_name, store_name=store_name)

    @classmethod
    def from_registry_with_config(
        cls,
        registry: SourceRegistry,
        config: object,
    ) -> "PocketIndex":
        cfg = config
        return cls._from_registry(
            registry,
            dim=cfg.embedding_dim,
            backend_name=cfg.embedding_backend,
            store_name=cfg.vector_store,
            chunking_strategy=cfg.chunking_strategy,
            chunking_max_tokens=cfg.chunking_max_tokens,
            chunking_overlap_tokens=cfg.chunking_overlap_tokens,
        )

    @classmethod
    def _from_registry(
        cls,
        registry: SourceRegistry,
        dim: int = 128,
        backend_name: str = "hash",
        store_name: str = "memory",
        chunking_strategy: str | None = None,
        chunking_max_tokens: int = 512,
        chunking_overlap_tokens: int = 64,
    ) -> "PocketIndex":
        """Internal factory with shared logic for all entry points."""
        chunks: list[SourceChunk] = []
        titles: dict[str, str] = {}
        for source in registry.sources:
            titles[source.source_id] = source.title
            if chunking_strategy is not None:
                chunker = TokenChunker(
                    tokenizer_name=chunking_strategy,
                    max_tokens=chunking_max_tokens,
                    overlap_tokens=chunking_overlap_tokens,
                )
                chunks.extend(chunker.chunk_source(source))
            else:
                chunks.extend(simple_chunk_source(source))

        backend = get_embedding_backend(backend_name)
        store = get_vector_store(store_name, dim=dim)

        return cls(
            chunks=chunks,
            titles=titles,
            dim=dim,
            backend=backend,
            store=store,
        )

    def search(self, query: str, top_k: int = 4) -> list[SearchResult]:
        """Search using vector similarity with trust-tier weighting."""
        if not self.chunks:
            return []

        query_vec = self.backend.embed(query, dim=self.dim)
        matrix = int8_dequantize(self.int8, self.scale)
        raw_scores = matrix @ query_vec

        ranked: list[tuple[int, float]] = []
        for idx, raw_score in enumerate(raw_scores):
            chunk = self.chunks[idx]
            adjusted = float(raw_score) * trust_weight(chunk.trust_tier)
            ranked.append((idx, adjusted))

        ranked.sort(key=lambda item: item[1], reverse=True)

        results: list[SearchResult] = []
        for idx, score in ranked[:top_k]:
            chunk = self.chunks[idx]
            results.append(
                SearchResult(
                    chunk_id=chunk.chunk_id,
                    source_id=chunk.source_id,
                    title=self.titles.get(chunk.source_id, chunk.source_id),
                    score=round(float(score), 4),
                    trust_tier=chunk.trust_tier,
                    text_preview=" ".join(chunk.text.split()[:50]),
                )
            )
        return results

    def storage_report(self) -> dict:
        """Generate a compression report."""
        fp32_bytes = int(self.fp32.nbytes)
        int8_bytes = int(self.int8.nbytes)
        return {
            "vector_dim": self.dim,
            "chunks": len(self.chunks),
            "fp32_bytes": fp32_bytes,
            "int8_bytes": int8_bytes,
            "estimated_reduction": round(fp32_bytes / int8_bytes, 2) if int8_bytes else math.inf,
            "compression": "simple_global_int8",
            "backend": self.backend.name,
            "store": self.store.info().get("store", "unknown"),
            "production_note": "Replace with FAISS/Qdrant/pgvector + real quantization adapters.",
        }

    def build_store(self) -> None:
        """Build the vector store from chunks and embeddings."""
        from sourcelab.retrieval.schemas import VectorStoreRecord

        records: list[VectorStoreRecord] = []
        for i, chunk in enumerate(self.chunks):
            embedding = self.fp32[i].tolist() if i < len(self.fp32) else []
            records.append(
                VectorStoreRecord(
                    chunk_id=chunk.chunk_id,
                    source_id=chunk.source_id,
                    trust_tier=chunk.trust_tier,
                    title=self.titles.get(chunk.source_id, chunk.source_id),
                    text_preview=" ".join(chunk.text.split()[:50]),
                    embedding=embedding,
                )
            )
        self.store.add_batch(records)
