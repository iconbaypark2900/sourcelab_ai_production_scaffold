"""Unit tests for Retrieval v2.

Instruction:
- Tests for embedding backends, vector stores, hybrid search, and evaluation.
- All tests must be deterministic and pass without optional dependencies.
- Use hash embedding backend for all tests.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from sourcelab.core.models import SourceChunk, SourceRecord
from sourcelab.retrieval.embedding_backends import (
    HashEmbeddingBackend,
    OpenAICompatibleEmbeddingBackend,
    available_embedding_backends,
    get_embedding_backend,
)
from sourcelab.retrieval.vector_store import (
    InMemoryVectorStore,
    JsonVectorStore,
    get_vector_store,
)
from sourcelab.retrieval.index import PocketIndex
from sourcelab.retrieval.hybrid_search import HybridSearch
from sourcelab.retrieval.compression import (
    binary_dequantize,
    binary_quantize,
    compression_report,
    compression_report_for,
    fp16_dequantize,
    fp16_quantize,
    get_compression_adapter,
    int8_dequantize,
    int8_quantize,
    product_dequantize,
    product_quantize,
    available_compression_adapters,
)
from sourcelab.retrieval.reranker import (
    BaseReranker,
    LengthNormalizedReranker,
    ReciprocalRankFusionReranker,
    Reranker,
    TrustTierReranker,
    available_rerankers,
    get_reranker,
)
from sourcelab.retrieval.config import RetrievalConfig, HybridSearchWeights
from sourcelab.retrieval.evaluation import (
    load_eval_fixtures,
    evaluate_retrieval,
    format_evaluation_report,
)
from sourcelab.retrieval.schemas import (
    EmbeddingRecord,
    EmbeddingBackendInfo,
    VectorStoreRecord,
    VectorSearchRequest,
    VectorSearchResult,
    HybridSearchRequest,
    HybridSearchResult,
    RetrievalDiagnostics,
    RetrievalEvaluationReport,
    CompressionReport,
    IndexManifest,
)
from sourcelab.sources.registry import SourceRegistry


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_chunks():
    """Create sample chunks for testing."""
    return [
        SourceChunk(
            chunk_id="chunk-1",
            source_id="source-a",
            text="Post-quantum cryptography migration requires careful planning.",
            section_title="intro",
            trust_tier="A",
            token_count=10,
        ),
        SourceChunk(
            chunk_id="chunk-2",
            source_id="source-b",
            text="NIST PQC standards include CRYSTALS-Kyber and CRYSTALS-Dilithium.",
            section_title="standards",
            trust_tier="B",
            token_count=10,
        ),
        SourceChunk(
            chunk_id="chunk-3",
            source_id="source-a",
            text="Cryptographic inventory helps identify vulnerable algorithms.",
            section_title="inventory",
            trust_tier="A",
            token_count=8,
        ),
        SourceChunk(
            chunk_id="chunk-4",
            source_id="source-c",
            text="Quantum computers threaten RSA and ECC encryption.",
            section_title="threats",
            trust_tier="C",
            token_count=8,
        ),
    ]


@pytest.fixture
def sample_titles():
    """Create sample titles for testing."""
    return {
        "source-a": "Post-Quantum Guide",
        "source-b": "NIST Standards",
        "source-c": "Quantum Threats",
    }


@pytest.fixture
def hash_backend():
    """Create a hash embedding backend."""
    return HashEmbeddingBackend()


@pytest.fixture
def memory_store():
    """Create an in-memory vector store."""
    return InMemoryVectorStore()


# ============================================================================
# Embedding Backend Tests
# ============================================================================


class TestHashEmbeddingBackend:
    """Tests for the hash embedding backend."""

    def test_is_deterministic(self, hash_backend):
        """Hash backend must produce the same embedding for the same text."""
        text = "post-quantum cryptography"
        emb1 = hash_backend.embed(text, dim=128)
        emb2 = hash_backend.embed(text, dim=128)
        np.testing.assert_array_equal(emb1, emb2)

    def test_different_texts_different_embeddings(self, hash_backend):
        """Different texts should produce different embeddings."""
        emb1 = hash_backend.embed("hello world", dim=128)
        emb2 = hash_backend.embed("goodbye world", dim=128)
        assert not np.allclose(emb1, emb2)

    def test_embedding_dimension(self, hash_backend):
        """Embedding should have the requested dimension."""
        emb = hash_backend.embed("test", dim=64)
        assert emb.shape == (64,)

    def test_embedding_is_normalized(self, hash_backend):
        """Embedding should be L2-normalized."""
        emb = hash_backend.embed("test text", dim=128)
        norm = np.linalg.norm(emb)
        assert abs(norm - 1.0) < 1e-5 or norm == 0

    def test_embed_batch(self, hash_backend):
        """Batch embedding should produce correct shape."""
        texts = ["hello", "world", "test"]
        batch = hash_backend.embed_batch(texts, dim=128)
        assert batch.shape == (3, 128)

    def test_embed_batch_empty(self, hash_backend):
        """Empty batch should produce empty array."""
        batch = hash_backend.embed_batch([], dim=128)
        assert batch.shape == (0, 128)

    def test_info(self, hash_backend):
        """Info should return correct backend information."""
        info = hash_backend.info(dim=128)
        assert info.name == "hash"
        assert info.dimension == 128
        assert info.deterministic is True
        assert info.requires_dependencies is False
        assert info.installed is True

    def test_name(self, hash_backend):
        """Name should be 'hash'."""
        assert hash_backend.name == "hash"


class TestSentenceTransformersBackend:
    """Tests for the sentence-transformers backend (optional)."""

    def test_missing_dependency_raises_clear_error(self):
        """Should raise ImportError with clear message if sentence-transformers missing."""
        # This test assumes sentence-transformers is not installed
        try:
            from sentence_transformers import SentenceTransformer
            pytest.skip("sentence-transformers is installed")
        except ImportError:
            pass

        with pytest.raises(ImportError) as exc_info:
            get_embedding_backend("sentence_transformers")
        assert "pip install -e '.[retrieval]'" in str(exc_info.value)


class TestGetEmbeddingBackend:
    """Tests for the backend factory."""

    def test_get_hash_backend(self):
        """Should return HashEmbeddingBackend."""
        backend = get_embedding_backend("hash")
        assert isinstance(backend, HashEmbeddingBackend)

    def test_get_unknown_backend_raises(self):
        """Should raise ValueError for unknown backend."""
        with pytest.raises(ValueError) as exc_info:
            get_embedding_backend("unknown")
        assert "Unknown embedding backend" in str(exc_info.value)


# ============================================================================
# Vector Store Tests
# ============================================================================


class TestInMemoryVectorStore:
    """Tests for the in-memory vector store."""

    def test_add_and_get(self, memory_store):
        """Should add and retrieve a record."""
        record = VectorStoreRecord(
            chunk_id="c1",
            source_id="s1",
            trust_tier="A",
            title="Test",
            text_preview="Hello",
            embedding=[0.1, 0.2, 0.3],
        )
        memory_store.add(record)
        retrieved = memory_store.get("c1")
        assert retrieved is not None
        assert retrieved.chunk_id == "c1"

    def test_add_batch(self, memory_store):
        """Should add multiple records."""
        records = [
            VectorStoreRecord(
                chunk_id=f"c{i}",
                source_id="s1",
                trust_tier="A",
                title=f"Test {i}",
                text_preview=f"Text {i}",
                embedding=[float(i), 0.0, 0.0],
            )
            for i in range(3)
        ]
        memory_store.add_batch(records)
        assert memory_store.count() == 3

    def test_search(self, memory_store):
        """Should return similar vectors."""
        records = [
            VectorStoreRecord(
                chunk_id="c1",
                source_id="s1",
                trust_tier="A",
                title="Test 1",
                text_preview="Hello world",
                embedding=[1.0, 0.0, 0.0],
            ),
            VectorStoreRecord(
                chunk_id="c2",
                source_id="s1",
                trust_tier="A",
                title="Test 2",
                text_preview="Goodbye world",
                embedding=[0.0, 1.0, 0.0],
            ),
        ]
        memory_store.add_batch(records)
        results = memory_store.search([1.0, 0.0, 0.0], top_k=2)
        assert len(results) > 0
        assert results[0].chunk_id == "c1"

    def test_delete(self, memory_store):
        """Should delete a record."""
        record = VectorStoreRecord(
            chunk_id="c1",
            source_id="s1",
            trust_tier="A",
            title="Test",
            text_preview="Hello",
            embedding=[0.1, 0.2, 0.3],
        )
        memory_store.add(record)
        assert memory_store.delete("c1")
        assert memory_store.get("c1") is None

    def test_clear(self, memory_store):
        """Should clear all records."""
        record = VectorStoreRecord(
            chunk_id="c1",
            source_id="s1",
            trust_tier="A",
            title="Test",
            text_preview="Hello",
            embedding=[0.1, 0.2, 0.3],
        )
        memory_store.add(record)
        memory_store.clear()
        assert memory_store.count() == 0

    def test_list_source_ids(self, memory_store):
        """Should return unique source IDs."""
        records = [
            VectorStoreRecord(
                chunk_id="c1",
                source_id="s1",
                trust_tier="A",
                title="Test 1",
                text_preview="Hello",
                embedding=[0.1, 0.2, 0.3],
            ),
            VectorStoreRecord(
                chunk_id="c2",
                source_id="s2",
                trust_tier="A",
                title="Test 2",
                text_preview="World",
                embedding=[0.4, 0.5, 0.6],
            ),
        ]
        memory_store.add_batch(records)
        source_ids = memory_store.list_source_ids()
        assert set(source_ids) == {"s1", "s2"}

    def test_info(self, memory_store):
        """Should return store information."""
        info = memory_store.info()
        assert info["store"] == "memory"
        assert info["persistent"] is False


class TestJsonVectorStore:
    """Tests for the JSON vector store."""

    def test_persists_and_reloads(self, tmp_path):
        """Should persist records to disk and reload them."""
        path = tmp_path / "test_store.json"
        store1 = JsonVectorStore(path)
        record = VectorStoreRecord(
            chunk_id="c1",
            source_id="s1",
            trust_tier="A",
            title="Test",
            text_preview="Hello",
            embedding=[0.1, 0.2, 0.3],
        )
        store1.add(record)

        # Reload from disk
        store2 = JsonVectorStore(path)
        assert store2.count() == 1
        retrieved = store2.get("c1")
        assert retrieved is not None
        assert retrieved.chunk_id == "c1"

    def test_search_persists(self, tmp_path):
        """Search should work after reload."""
        path = tmp_path / "test_store.json"
        store1 = JsonVectorStore(path)
        records = [
            VectorStoreRecord(
                chunk_id="c1",
                source_id="s1",
                trust_tier="A",
                title="Test 1",
                text_preview="Hello",
                embedding=[1.0, 0.0, 0.0],
            ),
            VectorStoreRecord(
                chunk_id="c2",
                source_id="s1",
                trust_tier="A",
                title="Test 2",
                text_preview="World",
                embedding=[0.0, 1.0, 0.0],
            ),
        ]
        store1.add_batch(records)

        store2 = JsonVectorStore(path)
        results = store2.search([1.0, 0.0, 0.0], top_k=2)
        assert len(results) > 0


class TestGetVectorStore:
    """Tests for the vector store factory."""

    def test_get_memory_store(self):
        """Should return InMemoryVectorStore."""
        store = get_vector_store("memory")
        assert isinstance(store, InMemoryVectorStore)

    def test_get_json_store(self):
        """Should return JsonVectorStore."""
        store = get_vector_store("json", path="/tmp/test.json")
        assert isinstance(store, JsonVectorStore)

    def test_get_unknown_store_raises(self):
        """Should raise ValueError for unknown store."""
        with pytest.raises(ValueError) as exc_info:
            get_vector_store("unknown")
        assert "Unknown vector store" in str(exc_info.value)


# ============================================================================
# PocketIndex Tests
# ============================================================================


class TestPocketIndex:
    """Tests for the PocketIndex class."""

    def test_from_registry(self, sample_chunks, sample_titles):
        """Should create index from registry."""
        index = PocketIndex(
            chunks=sample_chunks,
            titles=sample_titles,
            dim=128,
        )
        assert len(index.chunks) == 4
        assert index.dim == 128
        assert index.backend.name == "hash"

    def test_search_returns_results(self, sample_chunks, sample_titles):
        """Search should return results."""
        index = PocketIndex(
            chunks=sample_chunks,
            titles=sample_titles,
            dim=128,
        )
        results = index.search("cryptography", top_k=2)
        assert len(results) > 0
        assert results[0].source_id in sample_titles

    def test_search_empty_index(self):
        """Search on empty index should return empty list."""
        index = PocketIndex(chunks=[], titles={}, dim=128)
        results = index.search("test", top_k=4)
        assert results == []

    def test_storage_report(self, sample_chunks, sample_titles):
        """Storage report should contain required fields."""
        index = PocketIndex(
            chunks=sample_chunks,
            titles=sample_titles,
            dim=128,
        )
        report = index.storage_report()
        assert "vector_dim" in report
        assert "chunks" in report
        assert "fp32_bytes" in report
        assert "int8_bytes" in report
        assert "backend" in report

    def test_preserves_source_metadata(self, sample_chunks, sample_titles):
        """Results should preserve source_id, chunk_id, trust_tier."""
        index = PocketIndex(
            chunks=sample_chunks,
            titles=sample_titles,
            dim=128,
        )
        results = index.search("cryptography", top_k=4)
        for result in results:
            assert result.source_id
            assert result.chunk_id
            assert result.trust_tier
            assert result.title


# ============================================================================
# Hybrid Search Tests
# ============================================================================


class TestHybridSearch:
    """Tests for the hybrid search class."""

    def test_from_registry(self):
        """Should create HybridSearch from registry."""
        registry = SourceRegistry.bootstrap_demo(Path.cwd())
        hybrid = HybridSearch.from_registry(registry)
        assert hybrid.pocket_index is not None
        assert hybrid.bm25_index is not None

    def test_search_returns_diagnostics(self):
        """Search should return diagnostics with score components."""
        registry = SourceRegistry.bootstrap_demo(Path.cwd())
        hybrid = HybridSearch.from_registry(registry)
        results, diagnostics = hybrid.search("cryptography", top_k=2)
        assert diagnostics.result_count == len(results)
        assert len(diagnostics.keyword_scores) == len(results)
        assert len(diagnostics.vector_scores) == len(results)
        assert len(diagnostics.trust_weights) == len(results)
        assert len(diagnostics.final_scores) == len(results)

    def test_search_empty_query(self):
        """Empty query should return empty results."""
        registry = SourceRegistry.bootstrap_demo(Path.cwd())
        hybrid = HybridSearch.from_registry(registry)
        results, diagnostics = hybrid.search("", top_k=4)
        assert len(results) == 0
        assert diagnostics.result_count == 0

    def test_hybrid_weights_applied(self):
        """Hybrid search should apply configurable weights."""
        registry = SourceRegistry.bootstrap_demo(Path.cwd())
        hybrid = HybridSearch.from_registry(
            registry,
            keyword_weight=0.5,
            vector_weight=0.5,
            trust_weight_value=0.0,
            freshness_weight=0.0,
        )
        results, diagnostics = hybrid.search("cryptography", top_k=2)
        assert diagnostics.weights["keyword"] == 0.5
        assert diagnostics.weights["vector"] == 0.5
        assert diagnostics.weights["trust"] == 0.0

    def test_diagnostics_include_source_ids(self):
        """Diagnostics should include source_ids and chunk_ids."""
        registry = SourceRegistry.bootstrap_demo(Path.cwd())
        hybrid = HybridSearch.from_registry(registry)
        results, diagnostics = hybrid.search("cryptography", top_k=2)
        assert len(diagnostics.source_ids) > 0
        assert len(diagnostics.chunk_ids) > 0


# ============================================================================
# Compression Tests
# ============================================================================


class TestCompression:
    """Tests for vector compression."""

    def test_int8_quantize_dequantize(self):
        """Quantize then dequantize should approximate original."""
        original = np.array([[0.5, -0.3, 0.8], [0.1, 0.9, -0.4]], dtype=np.float32)
        quantized, scale = int8_quantize(original)
        dequantized = int8_dequantize(quantized, scale)
        np.testing.assert_allclose(original, dequantized, atol=0.05)

    def test_compression_report(self):
        """Compression report should have required fields."""
        original = np.zeros((10, 128), dtype=np.float32)
        quantized, scale = int8_quantize(original)
        report = compression_report(original, quantized)
        assert "original_dim" in report
        assert "compressed_dim" in report
        assert "original_bytes" in report
        assert "compressed_bytes" in report
        assert "reduction_ratio" in report


class TestFp16Compression:
    """Tests for fp16 (half precision) compression."""

    def test_fp16_quantize_dequantize_preserves_shape(self):
        original = np.array([[0.5, -0.3, 0.8], [0.1, 0.9, -0.4]], dtype=np.float32)
        quantized, scale = fp16_quantize(original)
        assert quantized.dtype == np.float16
        assert scale == 1.0
        dequantized = fp16_dequantize(quantized, scale)
        assert dequantized.shape == original.shape
        np.testing.assert_allclose(original, dequantized, atol=1e-2)

    def test_fp16_halves_storage(self):
        original = np.zeros((10, 128), dtype=np.float32)
        quantized, _ = fp16_quantize(original)
        assert quantized.nbytes == original.nbytes // 2

    def test_fp16_empty_matrix(self):
        empty = np.zeros((0, 0), dtype=np.float32)
        quantized, scale = fp16_quantize(empty)
        assert quantized.shape == (0, 0)


class TestBinaryCompression:
    """Tests for 1-bit binary (sign) quantization."""

    def test_binary_quantize_produces_signs(self):
        original = np.array([[0.5, -0.3, 0.0, 0.8], [-0.1, 0.9, -0.4, 0.2]], dtype=np.float32)
        quantized, scale = binary_quantize(original)
        assert quantized.dtype == np.int8
        assert set(np.unique(quantized).tolist()).issubset({-1, 1})
        assert scale == 1.0

    def test_binary_dequantize_returns_signs(self):
        original = np.array([[0.5, -0.3], [0.1, -0.9]], dtype=np.float32)
        quantized, _ = binary_quantize(original)
        dequantized = binary_dequantize(quantized)
        np.testing.assert_array_equal(dequantized, quantized.astype(np.float32))

    def test_binary_reduces_storage_32x(self):
        original = np.zeros((10, 128), dtype=np.float32)
        quantized, _ = binary_quantize(original)
        # fp32 (4 bytes) -> int8 (1 byte) = 4x from dtype, but 1-bit info
        assert quantized.nbytes == original.nbytes // 4

    def test_binary_empty_matrix(self):
        empty = np.zeros((0, 0), dtype=np.float32)
        quantized, _ = binary_quantize(empty)
        assert quantized.shape == (0, 0)


class TestProductQuantization:
    """Tests for product quantization (PQ) baseline."""

    def test_pq_quantize_dequantize_preserves_shape(self):
        rng = np.random.default_rng(42)
        original = rng.standard_normal((20, 16)).astype(np.float32)
        codes, codebooks, boundaries = product_quantize(original, subspaces=4, bits=4)
        assert codes.shape == (20, 4)
        assert len(codebooks) == 4
        assert len(boundaries) == 4
        reconstructed = product_dequantize(codes, codebooks, boundaries)
        assert reconstructed.shape == original.shape

    def test_pq_codes_within_codebook_range(self):
        rng = np.random.default_rng(7)
        original = rng.standard_normal((15, 8)).astype(np.float32)
        codes, _codebooks, _boundaries = product_quantize(original, subspaces=4, bits=4)
        # k = 2**4 = 16, so codes should be in [0, 15]
        assert codes.max() < 16
        assert codes.min() >= 0

    def test_pq_is_deterministic_with_seed(self):
        rng = np.random.default_rng(99)
        original = rng.standard_normal((12, 8)).astype(np.float32)
        codes_a, _cb_a, _b_a = product_quantize(original, subspaces=4, bits=4)
        codes_b, _cb_b, _b_b = product_quantize(original, subspaces=4, bits=4)
        np.testing.assert_array_equal(codes_a, codes_b)

    def test_pq_empty_matrix(self):
        codes, codebooks, boundaries = product_quantize(
            np.zeros((0, 0), dtype=np.float32), subspaces=4, bits=4
        )
        assert codes.shape == (0, 4)


class TestCompressionAdapters:
    """Tests for the compression adapter registry."""

    def test_available_adapters_lists_all(self):
        names = available_compression_adapters()
        assert "int8" in names
        assert "fp16" in names
        assert "binary" in names
        assert "product_quantization" in names

    def test_get_int8_adapter(self):
        adapter = get_compression_adapter("int8")
        assert adapter.name == "int8"
        original = np.array([[0.5, -0.3]], dtype=np.float32)
        compressed, state = adapter.quantize(original)
        reconstructed = adapter.dequantize(compressed, state)
        np.testing.assert_allclose(original, reconstructed, atol=0.05)

    def test_get_fp16_adapter(self):
        adapter = get_compression_adapter("fp16")
        assert adapter.name == "fp16"
        original = np.array([[0.5, -0.3]], dtype=np.float32)
        compressed, state = adapter.quantize(original)
        reconstructed = adapter.dequantize(compressed, state)
        assert reconstructed.shape == original.shape

    def test_get_binary_adapter(self):
        adapter = get_compression_adapter("binary")
        assert adapter.name == "binary"
        original = np.array([[0.5, -0.3]], dtype=np.float32)
        compressed, _state = adapter.quantize(original)
        assert set(np.unique(compressed).tolist()).issubset({-1, 1})

    def test_get_pq_adapter(self):
        adapter = get_compression_adapter("product_quantization", subspaces=4, bits=4)
        assert adapter.name == "product_quantization"
        rng = np.random.default_rng(3)
        original = rng.standard_normal((10, 8)).astype(np.float32)
        compressed, state = adapter.quantize(original)
        reconstructed = adapter.dequantize(compressed, state)
        assert reconstructed.shape == original.shape

    def test_adapter_report_includes_method(self):
        adapter = get_compression_adapter("fp16")
        original = np.zeros((10, 128), dtype=np.float32)
        compressed, _ = adapter.quantize(original)
        report = adapter.report(original, compressed)
        assert report["method"] == "fp16"
        assert "reduction_ratio" in report

    def test_pq_adapter_report_includes_subspaces(self):
        adapter = get_compression_adapter("product_quantization", subspaces=4, bits=4)
        rng = np.random.default_rng(3)
        original = rng.standard_normal((10, 8)).astype(np.float32)
        compressed, _ = adapter.quantize(original)
        report = adapter.report(original, compressed)
        assert report["method"] == "product_quantization"
        assert report["subspaces"] == 4
        assert report["bits"] == 4

    def test_unknown_adapter_raises(self):
        with pytest.raises(ValueError, match="Unknown compression adapter"):
            get_compression_adapter("turboquant")

    def test_compression_report_for_any_method(self):
        original = np.zeros((10, 128), dtype=np.float32)
        compressed = original.astype(np.float16)
        report = compression_report_for(original, compressed, "fp16")
        assert report["method"] == "fp16"
        assert report["reduction_ratio"] == 2.0


class TestOpenAICompatibleEmbeddingBackend:
    """Tests for the OpenAI-compatible embedding backend (no network)."""

    def test_name(self):
        backend = OpenAICompatibleEmbeddingBackend(model_name="test-model")
        assert backend.name == "openai_compatible"

    def test_info_reports_dependencies(self):
        backend = OpenAICompatibleEmbeddingBackend()
        info = backend.info()
        assert info.name == "openai_compatible"
        assert info.requires_dependencies is True
        assert info.deterministic is False

    def test_embed_batch_empty(self):
        backend = OpenAICompatibleEmbeddingBackend()
        result = backend.embed_batch([], dim=64)
        assert result.shape == (0, 64)

    def test_embed_raises_without_httpx(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "httpx":
                raise ImportError("simulated missing httpx")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        backend = OpenAICompatibleEmbeddingBackend()
        with pytest.raises(ImportError, match="OpenAI-compatible embeddings require httpx"):
            backend.embed("hello")

    def test_health_check_without_httpx(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "httpx":
                raise ImportError("simulated missing httpx")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        backend = OpenAICompatibleEmbeddingBackend(model_name="m", base_url="http://x/v1")
        result = backend.health_check()
        assert result["backend"] == "openai_compatible"
        assert result["available"] is False

    def test_available_embedding_backends(self):
        names = available_embedding_backends()
        assert "hash" in names
        assert "sentence_transformers" in names
        assert "openai_compatible" in names

    def test_get_embedding_backend_openai_compatible(self):
        backend = get_embedding_backend(
            "openai_compatible", model_name="m", base_url="http://x/v1"
        )
        assert backend.name == "openai_compatible"

    def test_get_embedding_backend_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown embedding backend"):
            get_embedding_backend("totally_unknown")


# ============================================================================
# Reranker Tests
# ============================================================================


class TestReranker:
    """Tests for the reranker."""

    def test_rerank_with_trust_weight(self):
        """Reranker should apply trust weight."""
        from sourcelab.core.models import SearchResult

        results = [
            SearchResult(
                chunk_id="c1",
                source_id="s1",
                title="Test",
                score=1.0,
                trust_tier="A",
                text_preview="Hello",
            ),
            SearchResult(
                chunk_id="c2",
                source_id="s1",
                title="Test",
                score=1.0,
                trust_tier="C",
                text_preview="World",
            ),
        ]
        reranker = Reranker(trust_weight_value=0.5)
        reranked = reranker.rerank("test", results)
        # Tier A (1.0) should rank higher than Tier C (0.65)
        assert reranked[0].trust_tier == "A"

    def test_rerank_empty(self):
        """Rerank empty list should return empty."""
        reranker = Reranker()
        reranked = reranker.rerank("test", [])
        assert reranked == []


class TestTrustTierReranker:
    """Tests for TrustTierReranker (the default reranker)."""

    def test_name(self):
        assert TrustTierReranker().name == "trust_tier"

    def test_reranker_alias_points_to_trust_tier(self):
        assert Reranker is TrustTierReranker

    def test_preserves_source_metadata(self):
        from sourcelab.core.models import SearchResult

        result = SearchResult(
            chunk_id="c1",
            source_id="s1",
            title="My Title",
            score=1.0,
            trust_tier="A",
            text_preview="Hello",
        )
        reranked = TrustTierReranker().rerank("q", [result])
        assert reranked[0].chunk_id == "c1"
        assert reranked[0].source_id == "s1"
        assert reranked[0].title == "My Title"
        assert reranked[0].trust_tier == "A"
        assert reranked[0].text_preview == "Hello"

    def test_trust_tier_a_outranks_c(self):
        from sourcelab.core.models import SearchResult

        results = [
            SearchResult(
                chunk_id="low", source_id="s1", title="t", score=1.0,
                trust_tier="C", text_preview="x",
            ),
            SearchResult(
                chunk_id="high", source_id="s1", title="t", score=1.0,
                trust_tier="A", text_preview="x",
            ),
        ]
        reranked = TrustTierReranker(trust_weight_value=0.5).rerank("q", results)
        assert reranked[0].chunk_id == "high"
        assert reranked[1].chunk_id == "low"

    def test_score_multiplied_by_trust_factor(self):
        from sourcelab.core.models import SearchResult

        result = SearchResult(
            chunk_id="c1", source_id="s1", title="t", score=1.0,
            trust_tier="A", text_preview="x",
        )
        reranked = TrustTierReranker(trust_weight_value=0.15).rerank("q", [result])
        # A tier weight = 1.0, so factor = 1 + 0.15 * 1.0 = 1.15
        assert abs(reranked[0].score - 1.15) < 0.001

    def test_empty_results(self):
        assert TrustTierReranker().rerank("q", []) == []

    def test_component_scores_ignored(self):
        from sourcelab.core.models import SearchResult

        result = SearchResult(
            chunk_id="c1", source_id="s1", title="t", score=1.0,
            trust_tier="A", text_preview="x",
        )
        # Component scores are accepted but not used by this reranker
        reranked = TrustTierReranker().rerank(
            "q", [result], component_scores=[{"keyword": 0.9, "vector": 0.1}]
        )
        assert reranked[0].chunk_id == "c1"

    def test_negative_weight_raises(self):
        with pytest.raises(ValueError, match="trust_weight_value must be >= 0"):
            TrustTierReranker(trust_weight_value=-0.1)

    def test_rerank_with_diagnostics_returns_schema(self):
        from sourcelab.core.models import SearchResult
        from sourcelab.retrieval.schemas import RerankerDiagnostics

        result = SearchResult(
            chunk_id="c1", source_id="s1", title="t", score=1.0,
            trust_tier="A", text_preview="x",
        )
        _, diag = TrustTierReranker().rerank_with_diagnostics("q", [result])
        assert isinstance(diag, RerankerDiagnostics)
        assert diag.reranker == "trust_tier"
        assert diag.original_count == 1
        assert diag.reranked_count == 1
        assert diag.parameters == {"trust_weight_value": 0.15}


class TestReciprocalRankFusionReranker:
    """Tests for ReciprocalRankFusionReranker."""

    def test_name(self):
        assert ReciprocalRankFusionReranker().name == "rrf"

    def test_single_list_sorts_by_score_descending(self):
        from sourcelab.core.models import SearchResult

        results = [
            SearchResult(
                chunk_id="c1", source_id="s1", title="t", score=0.5,
                trust_tier="C", text_preview="x",
            ),
            SearchResult(
                chunk_id="c2", source_id="s1", title="t", score=1.0,
                trust_tier="C", text_preview="x",
            ),
        ]
        reranked = ReciprocalRankFusionReranker().rerank("q", results)
        assert reranked[0].chunk_id == "c2"
        assert reranked[1].chunk_id == "c1"

    def test_single_list_score_is_rrf_formula(self):
        from sourcelab.core.models import SearchResult

        results = [
            SearchResult(
                chunk_id=f"c{i}", source_id="s1", title="t", score=1.0 - i * 0.1,
                trust_tier="C", text_preview="x",
            )
            for i in range(3)
        ]
        reranked = ReciprocalRankFusionReranker(k=60).rerank("q", results)
        # RRF score = 1 / (60 + rank + 1), rank 0 = best
        # c0 rank 0 -> 1/61, c1 rank 1 -> 1/62, c2 rank 2 -> 1/63
        assert abs(reranked[0].score - 1.0 / 61) < 1e-6
        assert abs(reranked[1].score - 1.0 / 62) < 1e-6
        assert abs(reranked[2].score - 1.0 / 63) < 1e-6

    def test_multi_list_fuses_component_ranks(self):
        from sourcelab.core.models import SearchResult

        results = [
            SearchResult(
                chunk_id="c1", source_id="s1", title="t", score=0.0,
                trust_tier="C", text_preview="x",
            ),
            SearchResult(
                chunk_id="c2", source_id="s1", title="t", score=0.0,
                trust_tier="C", text_preview="x",
            ),
        ]
        # c1 is top in keyword but last in vector; c2 is opposite
        component_scores = [
            {"keyword": 0.9, "vector": 0.1},  # c1: kw rank 0, vec rank 1
            {"keyword": 0.1, "vector": 0.9},  # c2: kw rank 1, vec rank 0
        ]
        reranked = ReciprocalRankFusionReranker(k=60).rerank(
            "q", results, component_scores=component_scores
        )
        # Both get equal fused RRF score (1/61 + 1/62), so order is a stable sort
        assert {r.chunk_id for r in reranked} == {"c1", "c2"}

    def test_multi_list_promotes_consistently_top_result(self):
        from sourcelab.core.models import SearchResult

        results = [
            SearchResult(
                chunk_id="always_top", source_id="s1", title="t", score=0.0,
                trust_tier="C", text_preview="x",
            ),
            SearchResult(
                chunk_id="middle", source_id="s1", title="t", score=0.0,
                trust_tier="C", text_preview="x",
            ),
            SearchResult(
                chunk_id="always_bottom", source_id="s1", title="t", score=0.0,
                trust_tier="C", text_preview="x",
            ),
        ]
        # always_top wins both lists, always_bottom loses both
        component_scores = [
            {"keyword": 0.9, "vector": 0.9},  # always_top
            {"keyword": 0.5, "vector": 0.5},  # middle
            {"keyword": 0.1, "vector": 0.1},  # always_bottom
        ]
        reranked = ReciprocalRankFusionReranker().rerank(
            "q", results, component_scores=component_scores
        )
        assert reranked[0].chunk_id == "always_top"
        assert reranked[1].chunk_id == "middle"
        assert reranked[2].chunk_id == "always_bottom"

    def test_multi_list_treats_missing_component_as_worst(self):
        from sourcelab.core.models import SearchResult

        results = [
            SearchResult(
                chunk_id="c1", source_id="s1", title="t", score=0.0,
                trust_tier="C", text_preview="x",
            ),
            SearchResult(
                chunk_id="c2", source_id="s1", title="t", score=0.0,
                trust_tier="C", text_preview="x",
            ),
        ]
        # c1 has a low keyword score and is missing the vector component;
        # c2 has a higher keyword score and a top vector score, so c2
        # should win in both components and rank first after fusion.
        component_scores = [
            {"keyword": 0.1},  # c1: missing vector -> worst rank
            {"keyword": 0.9, "vector": 0.9},  # c2: top in both
        ]
        reranked = ReciprocalRankFusionReranker().rerank(
            "q", results, component_scores=component_scores
        )
        assert reranked[0].chunk_id == "c2"
        assert reranked[1].chunk_id == "c1"

    def test_falls_back_to_single_list_when_length_mismatch(self):
        from sourcelab.core.models import SearchResult

        results = [
            SearchResult(
                chunk_id="c1", source_id="s1", title="t", score=0.5,
                trust_tier="C", text_preview="x",
            ),
            SearchResult(
                chunk_id="c2", source_id="s1", title="t", score=1.0,
                trust_tier="C", text_preview="x",
            ),
        ]
        # Mismatched length -> falls back to single-list RRF
        reranked = ReciprocalRankFusionReranker().rerank(
            "q", results, component_scores=[{"keyword": 0.9}]
        )
        assert reranked[0].chunk_id == "c2"

    def test_empty_results(self):
        assert ReciprocalRankFusionReranker().rerank("q", []) == []

    def test_negative_k_raises(self):
        with pytest.raises(ValueError, match="k must be >= 0"):
            ReciprocalRankFusionReranker(k=-1)

    def test_parameters(self):
        reranker = ReciprocalRankFusionReranker(k=42)
        assert reranker.parameters() == {"k": 42}


class TestLengthNormalizedReranker:
    """Tests for LengthNormalizedReranker."""

    def test_name(self):
        assert LengthNormalizedReranker().name == "length_normalized"

    def test_length_weight_zero_is_identity(self):
        from sourcelab.core.models import SearchResult

        results = [
            SearchResult(
                chunk_id="c1", source_id="s1", title="t", score=0.5,
                trust_tier="C", text_preview="x",
            ),
        ]
        reranked = LengthNormalizedReranker(length_weight=0.0).rerank("q", results)
        assert reranked[0].score == 0.5

    def test_long_chunks_demoted_relative_to_short(self):
        from sourcelab.core.models import SearchResult

        results = [
            SearchResult(
                chunk_id="long", source_id="s1", title="t", score=1.0,
                trust_tier="C", text_preview="x" * 400,
            ),
            SearchResult(
                chunk_id="short", source_id="s1", title="t", score=1.0,
                trust_tier="C", text_preview="x" * 16,
            ),
        ]
        reranked = LengthNormalizedReranker(length_weight=1.0).rerank("q", results)
        # Short chunk has higher score after sqrt-normalization
        assert reranked[0].chunk_id == "short"
        assert reranked[1].chunk_id == "long"

    def test_preserves_order_when_lengths_equal(self):
        from sourcelab.core.models import SearchResult

        results = [
            SearchResult(
                chunk_id="low", source_id="s1", title="t", score=0.3,
                trust_tier="C", text_preview="x" * 100,
            ),
            SearchResult(
                chunk_id="high", source_id="s1", title="t", score=0.7,
                trust_tier="C", text_preview="x" * 100,
            ),
        ]
        reranked = LengthNormalizedReranker().rerank("q", results)
        assert reranked[0].chunk_id == "high"
        assert reranked[1].chunk_id == "low"

    def test_min_length_floor_prevents_division_by_zero(self):
        from sourcelab.core.models import SearchResult

        result = SearchResult(
            chunk_id="c1", source_id="s1", title="t", score=1.0,
            trust_tier="C", text_preview="",
        )
        reranked = LengthNormalizedReranker(length_weight=1.0, min_length=10).rerank(
            "q", [result]
        )
        # Score is divided by sqrt(min_length) = sqrt(10)
        assert reranked[0].score > 0

    def test_empty_results(self):
        assert LengthNormalizedReranker().rerank("q", []) == []

    def test_negative_weight_raises(self):
        with pytest.raises(ValueError, match="length_weight must be >= 0"):
            LengthNormalizedReranker(length_weight=-0.1)

    def test_min_length_zero_raises(self):
        with pytest.raises(ValueError, match="min_length must be >= 1"):
            LengthNormalizedReranker(min_length=0)

    def test_preserves_source_metadata(self):
        from sourcelab.core.models import SearchResult

        result = SearchResult(
            chunk_id="c1", source_id="s1", title="My Title", score=1.0,
            trust_tier="A", text_preview="x" * 100,
        )
        reranked = LengthNormalizedReranker().rerank("q", [result])
        assert reranked[0].chunk_id == "c1"
        assert reranked[0].source_id == "s1"
        assert reranked[0].title == "My Title"
        assert reranked[0].trust_tier == "A"

    def test_parameters(self):
        reranker = LengthNormalizedReranker(length_weight=0.5, min_length=20)
        assert reranker.parameters() == {"length_weight": 0.5, "min_length": 20}


class TestRerankerFactory:
    """Tests for the reranker factory and registry."""

    def test_get_trust_tier(self):
        reranker = get_reranker("trust_tier")
        assert isinstance(reranker, TrustTierReranker)
        assert reranker.name == "trust_tier"

    def test_get_rrf(self):
        reranker = get_reranker("rrf", k=42)
        assert isinstance(reranker, ReciprocalRankFusionReranker)
        assert reranker.k == 42

    def test_get_length_normalized(self):
        reranker = get_reranker("length_normalized", length_weight=0.5)
        assert isinstance(reranker, LengthNormalizedReranker)
        assert reranker.length_weight == 0.5

    def test_default_is_trust_tier(self):
        reranker = get_reranker()
        assert isinstance(reranker, TrustTierReranker)

    def test_unknown_reranker_raises(self):
        with pytest.raises(ValueError, match="Unknown reranker"):
            get_reranker("cross_encoder")

    def test_available_rerankers(self):
        names = available_rerankers()
        assert "trust_tier" in names
        assert "rrf" in names
        assert "length_normalized" in names


class TestRerankerConfigIntegration:
    """Tests for reranker integration with RetrievalConfig."""

    def test_default_reranker_is_trust_tier(self):
        config = RetrievalConfig()
        assert config.reranker_name == "trust_tier"
        assert config.reranker_kwargs == {}

    def test_demo_config_uses_trust_tier(self):
        config = RetrievalConfig.demo()
        assert config.reranker_name == "trust_tier"

    def test_production_config_uses_rrf(self):
        config = RetrievalConfig.production()
        assert config.reranker_name == "rrf"
        assert config.reranker_kwargs == {"k": 60}

    def test_can_select_rrf_with_kwargs(self):
        config = RetrievalConfig(reranker_name="rrf", reranker_kwargs={"k": 30})
        assert config.reranker_name == "rrf"
        assert config.reranker_kwargs == {"k": 30}

    def test_unknown_reranker_name_raises(self):
        with pytest.raises(ValueError, match="Unknown reranker_name"):
            RetrievalConfig(reranker_name="cross_encoder")

    def test_factory_uses_config_reranker_name(self):
        config = RetrievalConfig(reranker_name="rrf", reranker_kwargs={"k": 50})
        reranker = get_reranker(config.reranker_name, **config.reranker_kwargs)
        assert isinstance(reranker, ReciprocalRankFusionReranker)
        assert reranker.k == 50


# ============================================================================
# Config Tests
# ============================================================================


class TestRetrievalConfig:
    """Tests for retrieval configuration."""

    def test_demo_config(self):
        """Demo config should have defaults."""
        config = RetrievalConfig.demo()
        assert config.embedding_backend == "hash"
        assert config.vector_store == "memory"
        assert config.embedding_dim == 128

    def test_testing_config(self):
        """Testing config should have smaller dimensions."""
        config = RetrievalConfig.testing()
        assert config.embedding_dim == 64
        assert config.default_top_k == 2

    def test_hybrid_weights_sum_to_one(self):
        """Hybrid weights should sum to 1.0."""
        weights = HybridSearchWeights()
        assert weights.validate_sum()

    def test_custom_hybrid_weights(self):
        """Custom weights should be accepted."""
        weights = HybridSearchWeights(keyword=0.5, vector=0.5, trust=0.0, freshness=0.0)
        assert weights.validate_sum()


# ============================================================================
# Evaluation Tests
# ============================================================================


class TestRetrievalEvaluation:
    """Tests for retrieval evaluation."""

    def test_load_eval_fixtures(self):
        """Should load evaluation fixtures."""
        fixtures = load_eval_fixtures(Path.cwd())
        assert len(fixtures) > 0
        assert "query" in fixtures[0]
        assert "expected_source_ids" in fixtures[0]

    def test_evaluate_retrieval(self):
        """Should compute evaluation metrics."""
        from sourcelab.core.models import SearchResult

        def mock_search(query, top_k):
            return [
                SearchResult(
                    chunk_id="c1",
                    source_id="source-a",
                    title="Test",
                    score=0.9,
                    trust_tier="A",
                    text_preview="Hello",
                ),
            ]

        queries = [
            {"query": "test", "expected_source_ids": ["source-a"]},
        ]
        report = evaluate_retrieval(mock_search, queries, top_k=1)
        assert report.query_count == 1
        assert report.hit_at_1 == 1.0
        assert report.source_match_rate == 1.0

    def test_format_evaluation_report(self):
        """Should format report for display."""
        from sourcelab.retrieval.schemas import RetrievalEvaluationReport

        report = RetrievalEvaluationReport(
            query_count=5,
            hit_at_1=0.6,
            hit_at_3=0.8,
            source_match_rate=0.7,
            average_final_score=0.5,
        )
        formatted = format_evaluation_report(report)
        assert "hit_at_1" in formatted
        assert "query_count" in formatted


# ============================================================================
# Schema Tests
# ============================================================================


class TestSchemas:
    """Tests for retrieval schemas."""

    def test_embedding_record(self):
        """EmbeddingRecord should be valid."""
        record = EmbeddingRecord(
            chunk_id="c1",
            source_id="s1",
            text="Hello",
            embedding_dim=128,
            backend="hash",
        )
        assert record.chunk_id == "c1"

    def test_vector_store_record(self):
        """VectorStoreRecord should be valid."""
        record = VectorStoreRecord(
            chunk_id="c1",
            source_id="s1",
            trust_tier="A",
            title="Test",
            text_preview="Hello",
            embedding=[0.1, 0.2],
        )
        assert record.embedding == [0.1, 0.2]

    def test_vector_search_result(self):
        """VectorSearchResult should be valid."""
        result = VectorSearchResult(
            chunk_id="c1",
            source_id="s1",
            trust_tier="A",
            title="Test",
            text_preview="Hello",
            score=0.9,
            rank=1,
        )
        assert result.rank == 1

    def test_retrieval_diagnostics(self):
        """RetrievalDiagnostics should be valid."""
        diag = RetrievalDiagnostics(
            query="test",
            mode="hybrid",
            result_count=4,
            total_chunks=100,
        )
        assert diag.mode == "hybrid"

    def test_retrieval_evaluation_report(self):
        """RetrievalEvaluationReport should be valid."""
        report = RetrievalEvaluationReport(
            query_count=10,
            hit_at_1=0.5,
            hit_at_3=0.8,
            source_match_rate=0.7,
            average_final_score=0.6,
        )
        assert report.hit_at_1 == 0.5

    def test_compression_report(self):
        """CompressionReport should be valid."""
        report = CompressionReport(
            original_dim=128,
            compressed_dim=128,
            original_bytes=512,
            compressed_bytes=128,
            reduction_ratio=4.0,
        )
        assert report.reduction_ratio == 4.0

    def test_index_manifest(self):
        """IndexManifest should be valid."""
        from datetime import datetime, timezone

        manifest = IndexManifest(
            index_id="test-123",
            created_at=datetime.now(timezone.utc),
            backend="hash",
            store="memory",
            chunk_count=10,
            source_count=2,
            vector_dim=128,
            compression="int8",
        )
        assert manifest.backend == "hash"


# ============================================================================
# CLI Integration Tests
# ============================================================================


class TestCLIIntegration:
    """Tests for CLI commands."""

    def test_index_build_accessible(self):
        """Index build command should be accessible."""
        from sourcelab.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["index", "build", "--backend", "hash", "--store", "json"])
        assert args.func.__name__ == "cmd_index_build"
        assert args.backend == "hash"
        assert args.store == "json"

    def test_index_stats_accessible(self):
        """Index stats command should be accessible."""
        from sourcelab.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["index", "stats"])
        assert args.func.__name__ == "cmd_index_stats"

    def test_index_clear_accessible(self):
        """Index clear command should be accessible."""
        from sourcelab.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["index", "clear"])
        assert args.func.__name__ == "cmd_index_clear"

    def test_retrieval_eval_accessible(self):
        """Retrieval eval command should be accessible."""
        from sourcelab.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["retrieval", "eval", "--backend", "hash", "--top-k", "3"])
        assert args.func.__name__ == "cmd_retrieval_eval"
        assert args.top_k == 3

    def test_search_with_diagnostics_flag(self):
        """Search command should accept diagnostics flag."""
        from sourcelab.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "search", "test",
            "--mode", "hybrid",
            "--backend", "hash",
            "--store", "memory",
            "--diagnostics",
        ])
        assert args.diagnostics is True
        assert args.backend == "hash"
        assert args.store == "memory"
