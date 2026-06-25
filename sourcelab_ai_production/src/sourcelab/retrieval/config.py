"""Retrieval configuration.

Instruction:
- Centralizes retrieval parameters for consistent behavior.
- Supports different configurations for demo, testing, and production.
- All weights must sum to 1.0 for hybrid search.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class HybridSearchWeights(BaseModel):
    """Weights for hybrid search scoring."""

    keyword: float = 0.35
    vector: float = 0.45
    trust: float = 0.15
    freshness: float = 0.05

    def validate_sum(self) -> bool:
        """Check that weights sum to 1.0."""
        total = self.keyword + self.vector + self.trust + self.freshness
        return abs(total - 1.0) < 0.01


class RetrievalConfig(BaseModel):
    """Configuration for retrieval operations."""

    # Embedding settings
    embedding_backend: str = "hash"
    embedding_dim: int = 128
    model_name: str | None = None

    # Vector store settings
    vector_store: str = "memory"
    vector_store_path: str = "artifacts/index/vector_store.json"

    # Search settings
    default_top_k: int = 4
    hybrid_weights: HybridSearchWeights = Field(default_factory=HybridSearchWeights)

    # Reranker settings
    reranker_name: str = "trust_tier"
    reranker_kwargs: dict = Field(default_factory=dict)

    # Source filtering
    min_trust_tier: str = "C"
    exclude_rejected: bool = True
    exclude_pending: bool = True
    exclude_archived: bool = True

    # Compression
    compression_method: str = "int8"
    enable_compression: bool = True

    # Index persistence
    index_dir: str = "artifacts/index"

    # Chunking settings
    chunking_strategy: str = "auto"
    chunking_max_tokens: int = 512
    chunking_overlap_tokens: int = 64

    @model_validator(mode="after")
    def _validate_reranker(self) -> "RetrievalConfig":
        # Lazy import to avoid circular dependency at module load time.
        from sourcelab.retrieval.reranker import _RERANKERS

        if self.reranker_name not in _RERANKERS:
            raise ValueError(
                f"Unknown reranker_name: {self.reranker_name}. "
                f"Available rerankers: {', '.join(_RERANKERS)}"
            )
        return self

    @model_validator(mode="after")
    def _validate_chunking(self) -> "RetrievalConfig":
        from sourcelab.retrieval.chunking import CHUNKING_STRATEGIES

        if self.chunking_strategy not in CHUNKING_STRATEGIES:
            raise ValueError(
                f"Unknown chunking_strategy: {self.chunking_strategy}. "
                f"Available: {', '.join(sorted(CHUNKING_STRATEGIES))}"
            )
        if self.chunking_overlap_tokens >= self.chunking_max_tokens:
            raise ValueError(
                f"chunking_overlap_tokens ({self.chunking_overlap_tokens}) "
                f"must be < chunking_max_tokens ({self.chunking_max_tokens})"
            )
        return self

    @classmethod
    def demo(cls) -> "RetrievalConfig":
        """Default configuration for demos."""
        return cls()

    @classmethod
    def testing(cls) -> "RetrievalConfig":
        """Configuration for tests (smaller dimensions)."""
        return cls(
            embedding_dim=64,
            default_top_k=2,
        )

    @classmethod
    def production(cls) -> "RetrievalConfig":
        """Configuration for production use."""
        return cls(
            embedding_backend="sentence_transformers",
            vector_store="faiss",
            embedding_dim=384,
            default_top_k=10,
            hybrid_weights=HybridSearchWeights(
                keyword=0.30,
                vector=0.50,
                trust=0.15,
                freshness=0.05,
            ),
            reranker_name="rrf",
            reranker_kwargs={"k": 60},
        )
