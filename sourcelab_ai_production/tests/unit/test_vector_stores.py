"""Tests for QdrantVectorStore and PgVectorStore.

Tests cover:
- Graceful fallback when optional dependency is not installed
- In-memory fallback search when server is not reachable
- Record management (add, get, delete, clear, count, list_source_ids)
- Info method returns correct store metadata
- Factory function creates correct store type
"""

from __future__ import annotations

import numpy as np

from sourcelab.retrieval.schemas import VectorStoreRecord, VectorSearchResult
from sourcelab.retrieval.vector_store import (
    BaseVectorStore,
    FaissVectorStore,
    InMemoryVectorStore,
    PgVectorStore,
    QdrantVectorStore,
    get_vector_store,
)


def _make_record(
    chunk_id: str = "chunk_001",
    source_id: str = "src_001",
    embedding: list[float] | None = None,
) -> VectorStoreRecord:
    if embedding is None:
        rng = np.random.default_rng(42)
        embedding = rng.standard_normal(8).tolist()
    return VectorStoreRecord(
        chunk_id=chunk_id,
        source_id=source_id,
        trust_tier="B",
        title="Test chunk",
        text_preview="This is a test chunk for search.",
        embedding=embedding,
    )


# ---------------------------------------------------------------------------
# QdrantVectorStore — fallback tests (no qdrant-client installed)
# ---------------------------------------------------------------------------


class TestQdrantVectorStoreFallback:
    def test_init_without_qdrant_client(self):
        store = QdrantVectorStore(dim=8)
        assert store._available is False
        assert store._client is None

    def test_add_and_get(self):
        store = QdrantVectorStore(dim=8)
        record = _make_record()
        store.add(record)
        assert store.get("chunk_001") is not None
        assert store.get("chunk_001").source_id == "src_001"

    def test_add_batch(self):
        store = QdrantVectorStore(dim=8)
        records = [_make_record("c1"), _make_record("c2")]
        store.add_batch(records)
        assert store.count() == 2

    def test_search_fallback_in_memory(self):
        store = QdrantVectorStore(dim=8)
        record = _make_record(embedding=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        store.add(record)
        results = store.search(
            query_embedding=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            top_k=1,
        )
        assert len(results) == 1
        assert results[0].chunk_id == "chunk_001"

    def test_search_empty_store(self):
        store = QdrantVectorStore(dim=8)
        results = store.search([0.0] * 8, top_k=5)
        assert results == []

    def test_search_filtered_by_source_id(self):
        store = QdrantVectorStore(dim=8)
        store.add(_make_record("c1", "src_a", [1, 0, 0, 0, 0, 0, 0, 0]))
        store.add(_make_record("c2", "src_b", [0, 1, 0, 0, 0, 0, 0, 0]))
        results = store.search([1, 0, 0, 0, 0, 0, 0, 0], top_k=5, source_ids=["src_a"])
        assert len(results) == 1
        assert results[0].source_id == "src_a"

    def test_delete(self):
        store = QdrantVectorStore(dim=8)
        store.add(_make_record("c1"))
        assert store.delete("c1") is True
        assert store.get("c1") is None
        assert store.delete("nonexistent") is False

    def test_clear(self):
        store = QdrantVectorStore(dim=8)
        store.add(_make_record("c1"))
        store.add(_make_record("c2"))
        store.clear()
        assert store.count() == 0

    def test_count(self):
        store = QdrantVectorStore(dim=8)
        store.add(_make_record("c1"))
        store.add(_make_record("c2"))
        assert store.count() == 2

    def test_list_source_ids(self):
        store = QdrantVectorStore(dim=8)
        store.add(_make_record("c1", "src_a"))
        store.add(_make_record("c2", "src_b"))
        ids = store.list_source_ids()
        assert set(ids) == {"src_a", "src_b"}

    def test_info(self):
        store = QdrantVectorStore(dim=8, host="myhost", port=7333, collection_name="test")
        info = store.info()
        assert info["store"] == "qdrant"
        assert info["available"] is False
        assert info["host"] == "myhost"
        assert info["port"] == 7333
        assert info["collection"] == "test"
        assert info["dimension"] == 8

    def test_is_base_vector_store(self):
        store = QdrantVectorStore(dim=8)
        assert isinstance(store, BaseVectorStore)


# ---------------------------------------------------------------------------
# PgVectorStore — fallback tests (no psycopg installed)
# ---------------------------------------------------------------------------


class TestPgVectorStoreFallback:
    def test_init_without_psycopg(self):
        store = PgVectorStore(dim=8, connection_string="postgresql://localhost/test")
        assert store._available is False
        assert store._conn is None

    def test_init_without_connection_string(self):
        store = PgVectorStore(dim=8)
        assert store._available is False

    def test_add_and_get(self):
        store = PgVectorStore(dim=8)
        record = _make_record()
        store.add(record)
        assert store.get("chunk_001") is not None
        assert store.get("chunk_001").source_id == "src_001"

    def test_add_batch(self):
        store = PgVectorStore(dim=8)
        records = [_make_record("c1"), _make_record("c2")]
        store.add_batch(records)
        assert store.count() == 2

    def test_search_fallback_in_memory(self):
        store = PgVectorStore(dim=8)
        record = _make_record(embedding=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        store.add(record)
        results = store.search(
            query_embedding=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            top_k=1,
        )
        assert len(results) == 1
        assert results[0].chunk_id == "chunk_001"

    def test_search_empty_store(self):
        store = PgVectorStore(dim=8)
        results = store.search([0.0] * 8, top_k=5)
        assert results == []

    def test_search_filtered_by_source_id(self):
        store = PgVectorStore(dim=8)
        store.add(_make_record("c1", "src_a", [1, 0, 0, 0, 0, 0, 0, 0]))
        store.add(_make_record("c2", "src_b", [0, 1, 0, 0, 0, 0, 0, 0]))
        results = store.search([1, 0, 0, 0, 0, 0, 0, 0], top_k=5, source_ids=["src_a"])
        assert len(results) == 1
        assert results[0].source_id == "src_a"

    def test_delete(self):
        store = PgVectorStore(dim=8)
        store.add(_make_record("c1"))
        assert store.delete("c1") is True
        assert store.get("c1") is None
        assert store.delete("nonexistent") is False

    def test_clear(self):
        store = PgVectorStore(dim=8)
        store.add(_make_record("c1"))
        store.add(_make_record("c2"))
        store.clear()
        assert store.count() == 0

    def test_count(self):
        store = PgVectorStore(dim=8)
        store.add(_make_record("c1"))
        store.add(_make_record("c2"))
        assert store.count() == 2

    def test_list_source_ids(self):
        store = PgVectorStore(dim=8)
        store.add(_make_record("c1", "src_a"))
        store.add(_make_record("c2", "src_b"))
        ids = store.list_source_ids()
        assert set(ids) == {"src_a", "src_b"}

    def test_info(self):
        store = PgVectorStore(dim=8, table_name="my_table")
        info = store.info()
        assert info["store"] == "pgvector"
        assert info["available"] is False
        assert info["table"] == "my_table"
        assert info["dimension"] == 8

    def test_is_base_vector_store(self):
        store = PgVectorStore(dim=8)
        assert isinstance(store, BaseVectorStore)


# ---------------------------------------------------------------------------
# Factory function tests
# ---------------------------------------------------------------------------


class TestVectorStoreFactory:
    def test_create_qdrant(self):
        store = get_vector_store("qdrant", dim=8)
        assert isinstance(store, QdrantVectorStore)

    def test_create_pgvector(self):
        store = get_vector_store("pgvector", dim=8)
        assert isinstance(store, PgVectorStore)

    def test_create_memory(self):
        store = get_vector_store("memory")
        assert isinstance(store, InMemoryVectorStore)

    def test_create_faiss(self):
        store = get_vector_store("faiss", dim=8)
        assert isinstance(store, FaissVectorStore)

    def test_unknown_raises(self):
        import pytest

        with pytest.raises(ValueError, match="Unknown vector store"):
            get_vector_store("nonexistent_store")
