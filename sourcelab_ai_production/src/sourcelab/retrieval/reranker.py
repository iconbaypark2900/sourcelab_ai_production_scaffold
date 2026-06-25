"""Rerankers for retrieval results.

Instruction:
- Production should rerank retrieved chunks using a cross-encoder or LLM-based scorer.
- The reranker must preserve source metadata.
- Trust tier weighting is now integrated into the hybrid search.
- All rerankers are local-first, deterministic, and dependency-free.
- Use ``get_reranker(name)`` to select a reranker by name.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

from sourcelab.core.models import SearchResult
from sourcelab.retrieval.schemas import RerankerDiagnostics
from sourcelab.sources.trust import trust_weight


class BaseReranker(ABC):
    """Abstract base class for rerankers.

    Every reranker takes a list of ``SearchResult`` and returns a new list
    sorted by descending reranked score. All implementations must preserve
    ``chunk_id``, ``source_id``, ``title``, ``trust_tier``, and
    ``text_preview`` on the returned results.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier for this reranker."""

    @abstractmethod
    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        component_scores: list[dict[str, float]] | None = None,
    ) -> list[SearchResult]:
        """Rerank ``results`` for ``query``.

        Args:
            query: The original search query (for diagnostics / logging).
            results: Initial retrieval results to rerank.
            component_scores: Optional per-result component scores (e.g.
                ``{"keyword": 0.7, "vector": 0.4}``). Used by multi-list
                rerankers like RRF. If ``None``, the reranker operates on
                ``result.score`` only.
        """

    def rerank_with_diagnostics(
        self,
        query: str,
        results: list[SearchResult],
        component_scores: list[dict[str, float]] | None = None,
    ) -> tuple[list[SearchResult], RerankerDiagnostics]:
        """Rerank results and return structured diagnostics."""
        reranked = self.rerank(query, results, component_scores=component_scores)
        diagnostics = RerankerDiagnostics(
            query=query,
            reranker=self.name,
            original_count=len(results),
            reranked_count=len(reranked),
            chunk_ids=[r.chunk_id for r in reranked],
            scores=[r.score for r in reranked],
            trust_tiers=[r.trust_tier for r in reranked],
            parameters=self.parameters(),
        )
        return reranked, diagnostics

    def parameters(self) -> dict:
        """Return a serializable snapshot of reranker parameters."""
        return {}


class TrustTierReranker(BaseReranker):
    """Reranker that multiplies scores by a trust-tier factor.

    Each result's score is scaled by ``1.0 + trust_weight_value * trust_weight(tier)``,
    where higher trust tiers (``A``) have a weight of 1.0 and lower tiers have
    smaller weights. This is the default reranker and preserves the
    pre-multiplex reranker behavior.
    """

    def __init__(self, trust_weight_value: float = 0.15):
        if trust_weight_value < 0:
            raise ValueError("trust_weight_value must be >= 0")
        self.trust_weight_value = trust_weight_value

    @property
    def name(self) -> str:
        return "trust_tier"

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        component_scores: list[dict[str, float]] | None = None,
    ) -> list[SearchResult]:
        if not results:
            return []

        reranked: list[SearchResult] = []
        for result in results:
            tw = trust_weight(result.trust_tier)
            adjusted_score = result.score * (1.0 + self.trust_weight_value * tw)
            reranked.append(
                SearchResult(
                    chunk_id=result.chunk_id,
                    source_id=result.source_id,
                    title=result.title,
                    score=round(adjusted_score, 4),
                    trust_tier=result.trust_tier,
                    text_preview=result.text_preview,
                )
            )

        reranked.sort(key=lambda x: x.score, reverse=True)
        return reranked

    def parameters(self) -> dict:
        return {"trust_weight_value": self.trust_weight_value}


class ReciprocalRankFusionReranker(BaseReranker):
    """Reciprocal Rank Fusion (RRF) reranker.

    RRF combines multiple ranked lists into a single score using
    ``rrf_score = sum( 1 / (k + rank_i) )`` across all lists. It is
    robust to score-scale differences between retrievers and requires no
    weight tuning.

    When ``component_scores`` is provided, the reranker computes ranks
    per named component (e.g. ``keyword``, ``vector``) and fuses them.
    When ``component_scores`` is ``None``, it falls back to a single-list
    RRF over the existing ``result.score`` rank, which simply sorts
    by score and re-scores via RRF.
    """

    def __init__(self, k: int = 60):
        if k < 0:
            raise ValueError("k must be >= 0")
        self.k = k

    @property
    def name(self) -> str:
        return "rrf"

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        component_scores: list[dict[str, float]] | None = None,
    ) -> list[SearchResult]:
        if not results:
            return []

        if not component_scores or len(component_scores) != len(results):
            return self._rrf_single_list(results)
        return self._rrf_multi_list(results, component_scores)

    def _rrf_single_list(self, results: list[SearchResult]) -> list[SearchResult]:
        # Sort by score descending; higher rank = better (0-indexed)
        ordered = sorted(results, key=lambda r: r.score, reverse=True)
        rrf_scores: list[float] = []
        for rank, _ in enumerate(ordered):
            rrf_scores.append(1.0 / (self.k + rank + 1))

        reranked: list[SearchResult] = []
        for result, rrf in zip(ordered, rrf_scores):
            reranked.append(
                SearchResult(
                    chunk_id=result.chunk_id,
                    source_id=result.source_id,
                    title=result.title,
                    score=round(rrf, 6),
                    trust_tier=result.trust_tier,
                    text_preview=result.text_preview,
                )
            )
        return reranked

    def _rrf_multi_list(
        self,
        results: list[SearchResult],
        component_scores: list[dict[str, float]],
    ) -> list[SearchResult]:
        # Collect all component names
        component_names: list[str] = []
        seen: set[str] = set()
        for comp in component_scores:
            for name in comp:
                if name not in seen:
                    seen.add(name)
                    component_names.append(name)

        # Compute fused RRF score per result
        fused: list[float] = [0.0] * len(results)
        for comp_name in component_names:
            # Build (index, score) pairs for this component; results missing
            # the component are treated as worst-ranked.
            pairs: list[tuple[int, float]] = []
            for idx, comp in enumerate(component_scores):
                pairs.append((idx, comp.get(comp_name, float("-inf"))))
            # Sort descending by score; higher score = better rank
            ordered = sorted(pairs, key=lambda pair: pair[1], reverse=True)
            for rank, (idx, _score) in enumerate(ordered):
                fused[idx] += 1.0 / (self.k + rank + 1)

        reranked: list[SearchResult] = []
        for result, fused_score in zip(results, fused):
            reranked.append(
                SearchResult(
                    chunk_id=result.chunk_id,
                    source_id=result.source_id,
                    title=result.title,
                    score=round(fused_score, 6),
                    trust_tier=result.trust_tier,
                    text_preview=result.text_preview,
                )
            )

        reranked.sort(key=lambda x: x.score, reverse=True)
        return reranked

    def parameters(self) -> dict:
        return {"k": self.k}


class LengthNormalizedReranker(BaseReranker):
    """Reranker that divides score by sqrt of chunk length.

    Long chunks tend to accumulate higher BM25 and vector scores simply
    because they contain more tokens. Dividing by ``sqrt(len(text_preview))``
    (with a floor to avoid division by zero) reduces this length bias
    while preserving the relative ordering of scores.

    The ``length_weight`` parameter controls how aggressively length is
    penalized: ``0.0`` disables length normalization entirely, and
    ``1.0`` applies full sqrt normalization.
    """

    def __init__(self, length_weight: float = 1.0, min_length: int = 10):
        if length_weight < 0:
            raise ValueError("length_weight must be >= 0")
        if min_length < 1:
            raise ValueError("min_length must be >= 1")
        self.length_weight = length_weight
        self.min_length = min_length

    @property
    def name(self) -> str:
        return "length_normalized"

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        component_scores: list[dict[str, float]] | None = None,
    ) -> list[SearchResult]:
        if not results:
            return []

        reranked: list[SearchResult] = []
        for result in results:
            effective_length = max(len(result.text_preview), self.min_length)
            divisor = math.sqrt(effective_length)
            normalized = result.score / divisor
            # Blend raw and normalized by length_weight for a tunable effect
            blended = (1.0 - self.length_weight) * result.score + self.length_weight * normalized
            reranked.append(
                SearchResult(
                    chunk_id=result.chunk_id,
                    source_id=result.source_id,
                    title=result.title,
                    score=round(blended, 4),
                    trust_tier=result.trust_tier,
                    text_preview=result.text_preview,
                )
            )

        reranked.sort(key=lambda x: x.score, reverse=True)
        return reranked

    def parameters(self) -> dict:
        return {
            "length_weight": self.length_weight,
            "min_length": self.min_length,
        }


# Backward-compatible alias for the original Reranker class.
# Existing tests and callers that import Reranker continue to work.
Reranker = TrustTierReranker


_RERANKERS: dict[str, type[BaseReranker]] = {
    "trust_tier": TrustTierReranker,
    "rrf": ReciprocalRankFusionReranker,
    "length_normalized": LengthNormalizedReranker,
}


def get_reranker(name: str = "trust_tier", **kwargs) -> BaseReranker:
    """Factory function to get a reranker by name.

    Args:
        name: Reranker name. One of ``"trust_tier"``, ``"rrf"``,
            ``"length_normalized"``.
        **kwargs: Constructor arguments for the selected reranker.

    Returns:
        An instance of the requested reranker.

    Raises:
        ValueError: If the name is unknown.
    """
    cls = _RERANKERS.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown reranker: {name}. "
            f"Available rerankers: {', '.join(_RERANKERS)}"
        )
    return cls(**kwargs)


def available_rerankers() -> list[str]:
    """Return the names of all registered rerankers."""
    return list(_RERANKERS)
