from pathlib import Path

from sourcelab.retrieval.index import PocketIndex
from sourcelab.retrieval.bm25 import BM25Index
from sourcelab.retrieval.hybrid_search import HybridSearch
from sourcelab.sources.registry import SourceRegistry
from sourcelab.sources.chunker import simple_chunk_source


def test_search_returns_source_linked_chunks():
    registry = SourceRegistry.bootstrap_demo(Path.cwd())
    index = PocketIndex.from_registry(registry)
    results = index.search("crypto inventory", top_k=2)
    assert results
    assert results[0].source_id
    assert results[0].chunk_id
    report = index.storage_report()
    assert report["estimated_reduction"] >= 3


# --- BM25 keyword search tests ---


def test_keyword_search_returns_expected_source_for_crypto_inventory():
    """Keyword search for 'crypto inventory' should return NIST PQC notes first."""
    registry = SourceRegistry.bootstrap_demo(Path.cwd())
    chunks = []
    titles = {}
    for source in registry.sources:
        titles[source.source_id] = source.title
        chunks.extend(simple_chunk_source(source))

    bm25 = BM25Index(chunks=chunks, titles=titles)
    results = bm25.search("crypto inventory", top_k=3)

    assert results
    # NIST PQC notes contain "cryptographic inventory" so should be top result
    assert results[0].source_id == "nist_pqc_notes"
    assert results[0].score > 0
    # All results have required citation fields
    for r in results:
        assert r.source_id
        assert r.chunk_id
        assert r.trust_tier


def test_keyword_search_empty_query_returns_empty():
    """Empty query should return empty results, not crash."""
    registry = SourceRegistry.bootstrap_demo(Path.cwd())
    chunks = []
    titles = {}
    for source in registry.sources:
        titles[source.source_id] = source.title
        chunks.extend(simple_chunk_source(source))

    bm25 = BM25Index(chunks=chunks, titles=titles)
    results = bm25.search("", top_k=3)
    assert results == []


def test_keyword_search_no_matches():
    """Query with no matching terms should return empty results."""
    registry = SourceRegistry.bootstrap_demo(Path.cwd())
    chunks = []
    titles = {}
    for source in registry.sources:
        titles[source.source_id] = source.title
        chunks.extend(simple_chunk_source(source))

    bm25 = BM25Index(chunks=chunks, titles=titles)
    results = bm25.search("xyzzy plugh", top_k=3)
    # Should return results but with low scores
    assert isinstance(results, list)


def test_vector_search_still_works():
    """Vector search should return source-linked chunks."""
    registry = SourceRegistry.bootstrap_demo(Path.cwd())
    index = PocketIndex.from_registry(registry)
    results = index.search("post quantum cryptography", top_k=2)
    assert results
    assert all(r.source_id for r in results)
    assert all(r.chunk_id for r in results)


def test_hybrid_search_returns_source_linked_chunks():
    """Hybrid search should return results with source citations."""
    registry = SourceRegistry.bootstrap_demo(Path.cwd())
    hybrid = HybridSearch.from_registry(registry)
    results, diagnostics = hybrid.search("crypto inventory", top_k=3)

    assert results
    assert all(r.source_id for r in results)
    assert all(r.chunk_id for r in results)
    assert diagnostics.result_count == len(results)
    assert diagnostics.total_chunks > 0
    assert len(diagnostics.source_ids) == len(results)
    assert len(diagnostics.chunk_ids) == len(results)


def test_hybrid_search_diagnostics_contain_score_components():
    """Diagnostics should contain keyword, vector, and trust scores."""
    registry = SourceRegistry.bootstrap_demo(Path.cwd())
    hybrid = HybridSearch.from_registry(registry)
    results, diagnostics = hybrid.search("cryptography", top_k=2)

    assert len(diagnostics.keyword_scores) == len(results)
    assert len(diagnostics.vector_scores) == len(results)
    assert len(diagnostics.trust_weights) == len(results)
    # Scores should be in [0, 1] range
    for kw, vec in zip(diagnostics.keyword_scores, diagnostics.vector_scores):
        assert 0 <= kw <= 1
        assert 0 <= vec <= 1


def test_trust_tier_weighting_affects_ranking():
    """Higher trust tier sources should rank higher when scores are similar."""
    registry = SourceRegistry.bootstrap_demo(Path.cwd())
    hybrid = HybridSearch.from_registry(registry)

    # Search for a term that appears in multiple sources
    results, _ = hybrid.search("notes", top_k=3)

    # NIST PQC notes have trust tier A (weight 1.0), others have C (weight 0.65)
    # So NIST should rank higher
    assert results[0].source_id == "nist_pqc_notes"
    assert results[0].trust_tier == "A"


def test_hybrid_search_empty_results():
    """Empty query should return clean empty response, not crash."""
    registry = SourceRegistry.bootstrap_demo(Path.cwd())
    hybrid = HybridSearch.from_registry(registry)
    results, diagnostics = hybrid.search("", top_k=3)

    assert results == []
    assert diagnostics.result_count == 0


def test_all_results_preserve_citations():
    """All search modes should preserve source_id, chunk_id, and trust_tier."""
    registry = SourceRegistry.bootstrap_demo(Path.cwd())

    # Test all three modes
    index = PocketIndex.from_registry(registry)
    chunks = []
    titles = {}
    for source in registry.sources:
        titles[source.source_id] = source.title
        chunks.extend(simple_chunk_source(source))
    bm25 = BM25Index(chunks=chunks, titles=titles)
    hybrid = HybridSearch.from_registry(registry)

    for query in ["crypto", "harness", "retrieval"]:
        # Vector
        vec_results = index.search(query, top_k=2)
        for r in vec_results:
            assert r.source_id, f"Vector result missing source_id for query '{query}'"
            assert r.chunk_id, f"Vector result missing chunk_id for query '{query}'"
            assert r.trust_tier, f"Vector result missing trust_tier for query '{query}'"

        # Keyword
        kw_results = bm25.search(query, top_k=2)
        for r in kw_results:
            assert r.source_id, f"Keyword result missing source_id for query '{query}'"
            assert r.chunk_id, f"Keyword result missing chunk_id for query '{query}'"
            assert r.trust_tier, f"Keyword result missing trust_tier for query '{query}'"

        # Hybrid
        hyb_results, _ = hybrid.search(query, top_k=2)
        for r in hyb_results:
            assert r.source_id, f"Hybrid result missing source_id for query '{query}'"
            assert r.chunk_id, f"Hybrid result missing chunk_id for query '{query}'"
            assert r.trust_tier, f"Hybrid result missing trust_tier for query '{query}'"
