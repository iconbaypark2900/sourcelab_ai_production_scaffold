"""Retrieval schemas for embedding backends, vector stores, and search results.

Instruction:
- These schemas define the interfaces for retrieval components.
- All results must preserve source_id, chunk_id, trust_tier, title, text_preview.
- Use these schemas for proof bundle artifacts and harness validation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EmbeddingRecord(BaseModel):
    """Record of an embedding operation."""

    chunk_id: str
    source_id: str
    text: str
    embedding_dim: int
    backend: str
    created_at: datetime = Field(default_factory=lambda: datetime.now())


class EmbeddingBackendInfo(BaseModel):
    """Information about an embedding backend."""

    name: str
    dimension: int
    deterministic: bool
    requires_dependencies: bool = False
    installed: bool = True


class VectorStoreRecord(BaseModel):
    """Record stored in a vector store."""

    chunk_id: str
    source_id: str
    trust_tier: str
    title: str
    text_preview: str
    embedding: list[float]
    metadata: dict = Field(default_factory=dict)


class VectorSearchRequest(BaseModel):
    """Request for vector similarity search."""

    query_embedding: list[float]
    top_k: int = 4
    source_ids: list[str] | None = None
    min_trust_tier: str | None = None


class VectorSearchResult(BaseModel):
    """Result from vector similarity search."""

    chunk_id: str
    source_id: str
    trust_tier: str
    title: str
    text_preview: str
    score: float
    rank: int


class HybridSearchRequest(BaseModel):
    """Request for hybrid search combining keyword and vector."""

    query: str
    top_k: int = 4
    keyword_weight: float = 0.35
    vector_weight: float = 0.45
    trust_weight: float = 0.15
    freshness_weight: float = 0.05
    source_ids: list[str] | None = None


class HybridSearchResult(BaseModel):
    """Result from hybrid search with score components."""

    chunk_id: str
    source_id: str
    trust_tier: str
    title: str
    text_preview: str
    score: float
    keyword_score: float = 0.0
    vector_score: float = 0.0
    trust_weight_value: float = 1.0
    freshness_score: float = 0.0


class RetrievalDiagnostics(BaseModel):
    """Diagnostics for a retrieval operation."""

    query: str
    mode: str
    backend: str = "hash"
    store: str = "memory"
    result_count: int
    total_chunks: int
    keyword_scores: list[float] = Field(default_factory=list)
    vector_scores: list[float] = Field(default_factory=list)
    trust_weights: list[float] = Field(default_factory=list)
    freshness_scores: list[float] = Field(default_factory=list)
    final_scores: list[float] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    trust_tiers: list[str] = Field(default_factory=list)
    compression_report: dict | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


class RetrievalEvaluationReport(BaseModel):
    """Report from retrieval evaluation."""

    query_count: int
    hit_at_1: float
    hit_at_3: float
    source_match_rate: float
    average_final_score: float
    failed_queries: list[str] = Field(default_factory=list)
    backend: str = "hash"
    store: str = "memory"
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


class CompressionReport(BaseModel):
    """Report from vector compression."""

    original_dim: int
    compressed_dim: int
    original_bytes: int
    compressed_bytes: int
    reduction_ratio: float
    method: str = "int8_quantize"
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


class IndexManifest(BaseModel):
    """Manifest for a persistent index."""

    index_id: str
    created_at: datetime
    backend: str
    store: str
    chunk_count: int
    source_count: int
    vector_dim: int
    compression: str
    artifacts: list[str] = Field(default_factory=list)


class RerankerDiagnostics(BaseModel):
    """Diagnostics for a reranker invocation."""

    query: str
    reranker: str
    original_count: int
    reranked_count: int
    chunk_ids: list[str] = Field(default_factory=list)
    scores: list[float] = Field(default_factory=list)
    trust_tiers: list[str] = Field(default_factory=list)
    parameters: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
