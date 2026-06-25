"""BM25-style keyword retriever.

Instruction:
- Lightweight BM25 implementation for local keyword search.
- No heavy external dependencies (no rank_bm25, no nltk).
- Preserves source_id, chunk_id, trust_tier, and text preview.
- Production should replace with a real BM25 library or Elasticsearch.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from sourcelab.core.models import SearchResult, SourceChunk
from sourcelab.sources.trust import trust_weight


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenizer with punctuation removal."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [t for t in text.split() if len(t) > 1]


class BM25Index:
    """Lightweight BM25 index over SourceChunks.

    Parameters match the Okapi BM25 formula:
    - k1: term frequency saturation (default 1.5)
    - b:  document length normalization (default 0.75)
    """

    def __init__(
        self,
        chunks: list[SourceChunk],
        titles: dict[str, str],
        k1: float = 1.5,
        b: float = 0.75,
    ):
        self.chunks = chunks
        self.titles = titles
        self.k1 = k1
        self.b = b
        self.n = len(chunks)

        # Pre-compute token lists and document lengths
        self._token_lists: list[list[str]] = [_tokenize(c.text) for c in chunks]
        self._doc_lens = [len(toks) for toks in self._token_lists]
        self._avg_doc_len = sum(self._doc_lens) / self.n if self.n > 0 else 1.0

        # Build inverted index: term -> set of doc indices
        self._df: dict[str, int] = {}
        for toks in self._token_lists:
            unique_terms = set(toks)
            for term in unique_terms:
                self._df[term] = self._df.get(term, 0) + 1

    def search(self, query: str, top_k: int = 4) -> list[SearchResult]:
        """Search chunks using BM25 scoring with trust-tier weighting."""
        if not self.chunks:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        # Score each chunk
        scores: list[tuple[int, float]] = []
        for idx in range(self.n):
            score = self._score_chunk(query_tokens, idx)
            # Apply trust-tier weighting
            chunk = self.chunks[idx]
            adjusted = score * trust_weight(chunk.trust_tier)
            scores.append((idx, adjusted))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        # Build results
        results: list[SearchResult] = []
        for idx, score in scores[:top_k]:
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

    def _score_chunk(self, query_tokens: list[str], doc_idx: int) -> float:
        """Compute BM25 score for a single document."""
        doc_len = self._doc_lens[doc_idx]
        doc_tokens = self._token_lists[doc_idx]
        term_freq = Counter(doc_tokens)

        score = 0.0
        for term in query_tokens:
            if term not in self._df:
                continue

            df = self._df[term]
            tf = term_freq.get(term, 0)

            # IDF component: log((N - df + 0.5) / (df + 0.5) + 1)
            idf = math.log((self.n - df + 0.5) / (df + 0.5) + 1)

            # TF component with saturation and length normalization
            tf_norm = (tf * (self.k1 + 1)) / (
                tf + self.k1 * (1 - self.b + self.b * doc_len / self._avg_doc_len)
            )

            score += idf * tf_norm

        return score
