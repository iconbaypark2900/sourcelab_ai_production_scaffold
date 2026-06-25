"""Hybrid search combining BM25 keyword and vector retrieval.

Instruction:
- Combines keyword score, vector score, trust-tier weighting, and freshness.
- Returns results with score components for diagnostics.
- Production should add reranker and compression adapters.
- Default weights: keyword=0.35, vector=0.45, trust=0.15, freshness=0.05.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sourcelab.core.models import SearchResult, SourceChunk
from sourcelab.retrieval.bm25 import BM25Index
from sourcelab.retrieval.chunking import TokenChunker
from sourcelab.retrieval.index import PocketIndex
from sourcelab.sources.trust import trust_weight


@dataclass
class HybridResult:
    """Search result with detailed score components."""

    chunk_id: str
    source_id: str
    title: str
    score: float
    trust_tier: str
    text_preview: str
    keyword_score: float = 0.0
    vector_score: float = 0.0
    trust_weight_value: float = 1.0
    freshness_score: float = 0.0


@dataclass
class HybridSearchDiagnostics:
    """Diagnostics for a hybrid search query."""

    query: str
    mode: str
    result_count: int
    total_chunks: int
    keyword_scores: list[float] = field(default_factory=list)
    vector_scores: list[float] = field(default_factory=list)
    trust_weights: list[float] = field(default_factory=list)
    freshness_scores: list[float] = field(default_factory=list)
    final_scores: list[float] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)
    trust_tiers: list[str] = field(default_factory=list)
    compression_report: dict | None = None
    weights: dict[str, float] = field(default_factory=dict)


class HybridSearch:
    """Combine BM25 keyword search with vector search and trust-tier weighting."""

    def __init__(
        self,
        pocket_index: PocketIndex,
        bm25_index: BM25Index,
        keyword_weight: float = 0.35,
        vector_weight: float = 0.45,
        trust_weight_value: float = 0.15,
        freshness_weight: float = 0.05,
    ):
        self.pocket_index = pocket_index
        self.bm25_index = bm25_index
        self.keyword_weight = keyword_weight
        self.vector_weight = vector_weight
        self.trust_weight_value = trust_weight_value
        self.freshness_weight = freshness_weight

    @classmethod
    def from_registry(
        cls,
        registry,
        dim: int = 128,
        keyword_weight: float = 0.35,
        vector_weight: float = 0.45,
        trust_weight_value: float = 0.15,
        freshness_weight: float = 0.05,
    ) -> "HybridSearch":
        """Create a HybridSearch from a SourceRegistry (legacy)."""
        return cls._from_registry_impl(
            registry, dim=dim,
            keyword_weight=keyword_weight,
            vector_weight=vector_weight,
            trust_weight_value=trust_weight_value,
            freshness_weight=freshness_weight,
        )

    @classmethod
    def from_registry_with_config(
        cls,
        registry,
        config: object,
    ) -> "HybridSearch":
        """Create a HybridSearch from a SourceRegistry with a RetrievalConfig."""
        cfg = config
        return cls._from_registry_impl(
            registry,
            dim=cfg.embedding_dim,
            keyword_weight=cfg.hybrid_weights.keyword,
            vector_weight=cfg.hybrid_weights.vector,
            trust_weight_value=cfg.hybrid_weights.trust,
            freshness_weight=cfg.hybrid_weights.freshness,
            chunking_strategy=cfg.chunking_strategy,
            chunking_max_tokens=cfg.chunking_max_tokens,
            chunking_overlap_tokens=cfg.chunking_overlap_tokens,
        )

    @classmethod
    def _from_registry_impl(
        cls,
        registry,
        dim: int = 128,
        keyword_weight: float = 0.35,
        vector_weight: float = 0.45,
        trust_weight_value: float = 0.15,
        freshness_weight: float = 0.05,
        chunking_strategy: str | None = None,
        chunking_max_tokens: int = 512,
        chunking_overlap_tokens: int = 64,
    ) -> "HybridSearch":
        """Internal factory shared by both entry points."""
        from sourcelab.sources.chunker import simple_chunk_source

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

        pocket_index = PocketIndex(chunks=chunks, titles=titles, dim=dim)
        bm25_index = BM25Index(chunks=chunks, titles=titles)
        return cls(
            pocket_index=pocket_index,
            bm25_index=bm25_index,
            keyword_weight=keyword_weight,
            vector_weight=vector_weight,
            trust_weight_value=trust_weight_value,
            freshness_weight=freshness_weight,
        )

    def search(
        self,
        query: str,
        top_k: int = 4,
        keyword_weight: float | None = None,
        vector_weight: float | None = None,
    ) -> tuple[list[SearchResult], HybridSearchDiagnostics]:
        """Search using combined keyword + vector scoring.

        Returns:
            Tuple of (results, diagnostics) for transparency.
        """
        kw = keyword_weight if keyword_weight is not None else self.keyword_weight
        vw = vector_weight if vector_weight is not None else self.vector_weight

        # Handle empty query
        if not query or not query.strip():
            empty_diag = HybridSearchDiagnostics(
                query=query,
                mode="hybrid",
                result_count=0,
                total_chunks=len(self.pocket_index.chunks),
                weights={"keyword": kw, "vector": vw, "trust": self.trust_weight_value, "freshness": self.freshness_weight},
            )
            return [], empty_diag

        # Get results from both retrievers
        keyword_results = self.bm25_index.search(query, top_k=top_k * 2)
        vector_results = self.pocket_index.search(query, top_k=top_k * 2)

        # Normalize scores to [0, 1] range
        keyword_max = max((r.score for r in keyword_results), default=1.0) or 1.0
        vector_max = max((r.score for r in vector_results), default=1.0) or 1.0

        # Build score maps by chunk_id
        keyword_scores: dict[str, float] = {}
        for r in keyword_results:
            keyword_scores[r.chunk_id] = r.score / keyword_max

        vector_scores: dict[str, float] = {}
        for r in vector_results:
            vector_scores[r.chunk_id] = r.score / vector_max

        # Collect all unique chunk IDs
        all_chunk_ids = set(keyword_scores.keys()) | set(vector_scores.keys())

        # Build chunk lookup
        chunk_map: dict[str, SourceChunk] = {}
        for chunk in self.pocket_index.chunks:
            chunk_map[chunk.chunk_id] = chunk

        # Score each chunk
        hybrid_results: list[HybridResult] = []
        for chunk_id in all_chunk_ids:
            chunk = chunk_map.get(chunk_id)
            if not chunk:
                continue

            kw_score = keyword_scores.get(chunk_id, 0.0)
            vec_score = vector_scores.get(chunk_id, 0.0)
            tw = trust_weight(chunk.trust_tier)
            freshness = 1.0  # Default freshness (could be computed from source metadata)

            combined = kw * kw_score + vw * vec_score + self.trust_weight_value * tw + self.freshness_weight * freshness
            final_score = combined

            hybrid_results.append(
                HybridResult(
                    chunk_id=chunk_id,
                    source_id=chunk.source_id,
                    title=self.pocket_index.titles.get(chunk.source_id, chunk.source_id),
                    score=round(final_score, 4),
                    trust_tier=chunk.trust_tier,
                    text_preview=" ".join(chunk.text.split()[:50]),
                    keyword_score=round(kw_score, 4),
                    vector_score=round(vec_score, 4),
                    trust_weight_value=tw,
                    freshness_score=round(freshness, 4),
                )
            )

        # Sort by combined score
        hybrid_results.sort(key=lambda x: x.score, reverse=True)
        top_results = hybrid_results[:top_k]

        # Convert to SearchResult
        results = [
            SearchResult(
                chunk_id=r.chunk_id,
                source_id=r.source_id,
                title=r.title,
                score=r.score,
                trust_tier=r.trust_tier,
                text_preview=r.text_preview,
            )
            for r in top_results
        ]

        # Build diagnostics
        diagnostics = HybridSearchDiagnostics(
            query=query,
            mode="hybrid",
            result_count=len(results),
            total_chunks=len(self.pocket_index.chunks),
            keyword_scores=[r.keyword_score for r in top_results],
            vector_scores=[r.vector_score for r in top_results],
            trust_weights=[r.trust_weight_value for r in top_results],
            freshness_scores=[r.freshness_score for r in top_results],
            final_scores=[r.score for r in top_results],
            source_ids=[r.source_id for r in top_results],
            chunk_ids=[r.chunk_id for r in top_results],
            trust_tiers=[r.trust_tier for r in top_results],
            compression_report=self.pocket_index.storage_report(),
            weights={"keyword": kw, "vector": vw, "trust": self.trust_weight_value, "freshness": self.freshness_weight},
        )

        return results, diagnostics
