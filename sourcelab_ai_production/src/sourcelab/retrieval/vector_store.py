"""Vector store adapters for persistent retrieval.

Instruction:
- BaseVectorStore defines the interface for all vector stores.
- InMemoryVectorStore and JsonVectorStore work without optional dependencies.
- FaissVectorStore requires faiss-cpu (optional).
- QdrantVectorStore requires qdrant-client (optional) and a running Qdrant server.
- PgVectorStore requires psycopg (optional) and a PostgreSQL database with pgvector.
- All stores fall back to in-memory search when their optional dependency is missing.
- All stores must preserve source_id, chunk_id, trust_tier, and metadata.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from sourcelab.retrieval.schemas import VectorSearchResult, VectorStoreRecord


class BaseVectorStore(ABC):
    """Abstract base class for vector stores."""

    @abstractmethod
    def add(self, record: VectorStoreRecord) -> None:
        """Add a record to the vector store."""

    @abstractmethod
    def add_batch(self, records: list[VectorStoreRecord]) -> None:
        """Add multiple records to the vector store."""

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 4,
        source_ids: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        """Search for similar vectors."""

    @abstractmethod
    def get(self, chunk_id: str) -> VectorStoreRecord | None:
        """Get a record by chunk_id."""

    @abstractmethod
    def delete(self, chunk_id: str) -> bool:
        """Delete a record by chunk_id."""

    @abstractmethod
    def clear(self) -> None:
        """Clear all records from the store."""

    @abstractmethod
    def count(self) -> int:
        """Return the number of records in the store."""

    @abstractmethod
    def list_source_ids(self) -> list[str]:
        """Return unique source IDs in the store."""

    @abstractmethod
    def info(self) -> dict:
        """Return information about the store."""


class InMemoryVectorStore(BaseVectorStore):
    """In-memory vector store (no persistence).

    This store works without any optional dependencies and is suitable
    for local demos and testing.
    """

    def __init__(self):
        self._records: dict[str, VectorStoreRecord] = {}

    def add(self, record: VectorStoreRecord) -> None:
        self._records[record.chunk_id] = record

    def add_batch(self, records: list[VectorStoreRecord]) -> None:
        for record in records:
            self._records[record.chunk_id] = record

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 4,
        source_ids: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        if not self._records:
            return []

        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm > 0:
            query_vec = query_vec / query_norm

        results: list[tuple[str, float]] = []
        for chunk_id, record in self._records.items():
            if source_ids and record.source_id not in source_ids:
                continue
            record_vec = np.array(record.embedding, dtype=np.float32)
            record_norm = np.linalg.norm(record_vec)
            if record_norm > 0:
                record_vec = record_vec / record_norm
            score = float(np.dot(query_vec, record_vec))
            results.append((chunk_id, score))

        results.sort(key=lambda x: x[1], reverse=True)

        search_results: list[VectorSearchResult] = []
        for rank, (chunk_id, score) in enumerate(results[:top_k], 1):
            record = self._records[chunk_id]
            search_results.append(
                VectorSearchResult(
                    chunk_id=chunk_id,
                    source_id=record.source_id,
                    trust_tier=record.trust_tier,
                    title=record.title,
                    text_preview=record.text_preview,
                    score=round(score, 4),
                    rank=rank,
                )
            )
        return search_results

    def get(self, chunk_id: str) -> VectorStoreRecord | None:
        return self._records.get(chunk_id)

    def delete(self, chunk_id: str) -> bool:
        if chunk_id in self._records:
            del self._records[chunk_id]
            return True
        return False

    def clear(self) -> None:
        self._records.clear()

    def count(self) -> int:
        return len(self._records)

    def list_source_ids(self) -> list[str]:
        return list(set(r.source_id for r in self._records.values()))

    def info(self) -> dict:
        return {
            "store": "memory",
            "count": self.count(),
            "source_count": len(self.list_source_ids()),
            "persistent": False,
        }


class JsonVectorStore(BaseVectorStore):
    """JSON file-backed vector store.

    Persists records to a JSON file for durability. Works without
    optional dependencies.
    """

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._records: dict[str, VectorStoreRecord] = {}
        self._load()

    def _load(self) -> None:
        """Load records from the JSON file."""
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                for item in data:
                    record = VectorStoreRecord(**item)
                    self._records[record.chunk_id] = record
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self) -> None:
        """Save records to the JSON file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = [r.model_dump(mode="json") for r in self._records.values()]
        self._path.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )

    def add(self, record: VectorStoreRecord) -> None:
        self._records[record.chunk_id] = record
        self._save()

    def add_batch(self, records: list[VectorStoreRecord]) -> None:
        for record in records:
            self._records[record.chunk_id] = record
        self._save()

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 4,
        source_ids: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        if not self._records:
            return []

        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm > 0:
            query_vec = query_vec / query_norm

        results: list[tuple[str, float]] = []
        for chunk_id, record in self._records.items():
            if source_ids and record.source_id not in source_ids:
                continue
            record_vec = np.array(record.embedding, dtype=np.float32)
            record_norm = np.linalg.norm(record_vec)
            if record_norm > 0:
                record_vec = record_vec / record_norm
            score = float(np.dot(query_vec, record_vec))
            results.append((chunk_id, score))

        results.sort(key=lambda x: x[1], reverse=True)

        search_results: list[VectorSearchResult] = []
        for rank, (chunk_id, score) in enumerate(results[:top_k], 1):
            record = self._records[chunk_id]
            search_results.append(
                VectorSearchResult(
                    chunk_id=chunk_id,
                    source_id=record.source_id,
                    trust_tier=record.trust_tier,
                    title=record.title,
                    text_preview=record.text_preview,
                    score=round(score, 4),
                    rank=rank,
                )
            )
        return search_results

    def get(self, chunk_id: str) -> VectorStoreRecord | None:
        return self._records.get(chunk_id)

    def delete(self, chunk_id: str) -> bool:
        if chunk_id in self._records:
            del self._records[chunk_id]
            self._save()
            return True
        return False

    def clear(self) -> None:
        self._records.clear()
        self._save()

    def count(self) -> int:
        return len(self._records)

    def list_source_ids(self) -> list[str]:
        return list(set(r.source_id for r in self._records.values()))

    def info(self) -> dict:
        return {
            "store": "json",
            "path": str(self._path),
            "count": self.count(),
            "source_count": len(self.list_source_ids()),
            "persistent": True,
        }


class FaissVectorStore(BaseVectorStore):
    """FAISS-backed vector store (optional).

    Requires faiss-cpu or faiss-gpu to be installed.
    Falls back to in-memory search if FAISS is not available.
    """

    def __init__(self, dim: int = 128):
        self._dim = dim
        self._records: dict[str, VectorStoreRecord] = {}
        self._index = None
        self._chunk_ids: list[str] = []

        try:
            import faiss
            self._faiss = faiss
            self._index = faiss.IndexFlatIP(dim)
            self._available = True
        except ImportError:
            self._available = False

    def add(self, record: VectorStoreRecord) -> None:
        self._records[record.chunk_id] = record
        if self._available and self._index is not None:
            vec = np.array([record.embedding], dtype=np.float32)
            self._index.add(vec)
            self._chunk_ids.append(record.chunk_id)

    def add_batch(self, records: list[VectorStoreRecord]) -> None:
        for record in records:
            self.add(record)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 4,
        source_ids: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        if not self._records:
            return []

        if self._available and self._index is not None and self._index.ntotal > 0:
            query_vec = np.array([query_embedding], dtype=np.float32)
            k = min(top_k * 2, self._index.ntotal)
            scores, indices = self._index.search(query_vec, k)

            results: list[VectorSearchResult] = []
            rank = 1
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(self._chunk_ids):
                    continue
                chunk_id = self._chunk_ids[idx]
                record = self._records.get(chunk_id)
                if record is None:
                    continue
                if source_ids and record.source_id not in source_ids:
                    continue
                results.append(
                    VectorSearchResult(
                        chunk_id=chunk_id,
                        source_id=record.source_id,
                        trust_tier=record.trust_tier,
                        title=record.title,
                        text_preview=record.text_preview,
                        score=round(float(score), 4),
                        rank=rank,
                    )
                )
                rank += 1
                if len(results) >= top_k:
                    break
            return results

        # Fallback to in-memory search
        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm > 0:
            query_vec = query_vec / query_norm

        scored: list[tuple[str, float]] = []
        for chunk_id, record in self._records.items():
            if source_ids and record.source_id not in source_ids:
                continue
            record_vec = np.array(record.embedding, dtype=np.float32)
            record_norm = np.linalg.norm(record_vec)
            if record_norm > 0:
                record_vec = record_vec / record_norm
            score = float(np.dot(query_vec, record_vec))
            scored.append((chunk_id, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        search_results: list[VectorSearchResult] = []
        for rank, (chunk_id, score) in enumerate(scored[:top_k], 1):
            record = self._records[chunk_id]
            search_results.append(
                VectorSearchResult(
                    chunk_id=chunk_id,
                    source_id=record.source_id,
                    trust_tier=record.trust_tier,
                    title=record.title,
                    text_preview=record.text_preview,
                    score=round(score, 4),
                    rank=rank,
                )
            )
        return search_results

    def get(self, chunk_id: str) -> VectorStoreRecord | None:
        return self._records.get(chunk_id)

    def delete(self, chunk_id: str) -> bool:
        if chunk_id in self._records:
            del self._records[chunk_id]
            # Note: FAISS doesn't support deletion easily; rebuild if needed
            return True
        return False

    def clear(self) -> None:
        self._records.clear()
        self._chunk_ids.clear()
        if self._available:
            self._index = self._faiss.IndexFlatIP(self._dim)

    def count(self) -> int:
        return len(self._records)

    def list_source_ids(self) -> list[str]:
        return list(set(r.source_id for r in self._records.values()))

    def info(self) -> dict:
        return {
            "store": "faiss",
            "available": self._available,
            "count": self.count(),
            "source_count": len(self.list_source_ids()),
            "persistent": False,
            "dimension": self._dim,
        }


class QdrantVectorStore(BaseVectorStore):
    """Qdrant-backed vector store (optional).

    Requires qdrant-client to be installed and a Qdrant server running.
    Falls back to in-memory search if qdrant-client is not available.
    Uses an in-memory record cache for metadata; the Qdrant collection
    stores embeddings and payloads for similarity search.
    """

    def __init__(
        self,
        dim: int = 128,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = "sourcelab_chunks",
        **kwargs,
    ):
        self._dim = dim
        self._host = host
        self._port = port
        self._collection_name = collection_name
        self._records: dict[str, VectorStoreRecord] = {}
        self._client = None
        self._available = False

        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            self._client = QdrantClient(host=host, port=port)
            # Ensure collection exists
            collections = self._client.get_collections().collections
            exists = any(c.name == collection_name for c in collections)
            if not exists:
                self._client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
                )
            self._available = True
        except ImportError:
            self._available = False
        except Exception:
            self._available = False

    def add(self, record: VectorStoreRecord) -> None:
        self._records[record.chunk_id] = record
        if self._available and self._client is not None:
            from qdrant_client.models import PointStruct

            self._client.upsert(
                collection_name=self._collection_name,
                points=[
                    PointStruct(
                        id=record.chunk_id,
                        vector=record.embedding,
                        payload={
                            "chunk_id": record.chunk_id,
                            "source_id": record.source_id,
                            "trust_tier": record.trust_tier,
                            "title": record.title,
                            "text_preview": record.text_preview,
                        },
                    )
                ],
            )

    def add_batch(self, records: list[VectorStoreRecord]) -> None:
        for record in records:
            self.add(record)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 4,
        source_ids: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        if self._available and self._client is not None:
            from qdrant_client.models import Filter, FieldCondition, MatchAny

            query_filter = None
            if source_ids:
                query_filter = Filter(
                    must=[
                        FieldCondition(key="source_id", match=MatchAny(any=source_ids))
                    ]
                )

            hits = self._client.search(
                collection_name=self._collection_name,
                query_vector=query_embedding,
                limit=top_k,
                query_filter=query_filter,
            )

            results: list[VectorSearchResult] = []
            for rank, hit in enumerate(hits, 1):
                payload = hit.payload or {}
                results.append(
                    VectorSearchResult(
                        chunk_id=payload.get("chunk_id", ""),
                        source_id=payload.get("source_id", ""),
                        trust_tier=payload.get("trust_tier", "C"),
                        title=payload.get("title", ""),
                        text_preview=payload.get("text_preview", ""),
                        score=round(float(hit.score), 4),
                        rank=rank,
                    )
                )
            return results

        # Fallback to in-memory search
        if not self._records:
            return []

        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm > 0:
            query_vec = query_vec / query_norm

        scored: list[tuple[str, float]] = []
        for chunk_id, record in self._records.items():
            if source_ids and record.source_id not in source_ids:
                continue
            record_vec = np.array(record.embedding, dtype=np.float32)
            record_norm = np.linalg.norm(record_vec)
            if record_norm > 0:
                record_vec = record_vec / record_norm
            score = float(np.dot(query_vec, record_vec))
            scored.append((chunk_id, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        search_results: list[VectorSearchResult] = []
        for rank, (chunk_id, score) in enumerate(scored[:top_k], 1):
            record = self._records[chunk_id]
            search_results.append(
                VectorSearchResult(
                    chunk_id=chunk_id,
                    source_id=record.source_id,
                    trust_tier=record.trust_tier,
                    title=record.title,
                    text_preview=record.text_preview,
                    score=round(score, 4),
                    rank=rank,
                )
            )
        return search_results

    def get(self, chunk_id: str) -> VectorStoreRecord | None:
        return self._records.get(chunk_id)

    def delete(self, chunk_id: str) -> bool:
        if chunk_id in self._records:
            del self._records[chunk_id]
            if self._available and self._client is not None:
                self._client.delete(
                    collection_name=self._collection_name,
                    points_selector=[chunk_id],
                )
            return True
        return False

    def clear(self) -> None:
        self._records.clear()
        if self._available and self._client is not None:
            self._client.delete_collection(collection_name=self._collection_name)
            from qdrant_client.models import Distance, VectorParams

            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(size=self._dim, distance=Distance.COSINE),
            )

    def count(self) -> int:
        return len(self._records)

    def list_source_ids(self) -> list[str]:
        return list(set(r.source_id for r in self._records.values()))

    def info(self) -> dict:
        return {
            "store": "qdrant",
            "available": self._available,
            "host": self._host,
            "port": self._port,
            "collection": self._collection_name,
            "count": self.count(),
            "source_count": len(self.list_source_ids()),
            "persistent": True,
            "dimension": self._dim,
        }


class PgVectorStore(BaseVectorStore):
    """pgvector-backed vector store (optional).

    Requires psycopg to be installed and a PostgreSQL database with the
    pgvector extension enabled. Falls back to in-memory search if psycopg
    is not available or the database is not reachable.
    Uses an in-memory record cache for metadata; the pgvector table stores
    embeddings for similarity search.
    """

    def __init__(
        self,
        dim: int = 128,
        connection_string: str = "",
        table_name: str = "vector_store",
        **kwargs,
    ):
        import os

        self._dim = dim
        self._connection_string = connection_string or os.environ.get(
            "SOURCELAB_DATABASE_URL", ""
        )
        self._table_name = table_name
        self._records: dict[str, VectorStoreRecord] = {}
        self._conn = None
        self._available = False

        try:
            import psycopg

            self._conn = psycopg.connect(self._connection_string)
            self._conn.autocommit = True
            # Ensure pgvector extension and table exist
            with self._conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._table_name} (
                        chunk_id TEXT PRIMARY KEY,
                        source_id TEXT NOT NULL,
                        trust_tier TEXT NOT NULL DEFAULT 'C',
                        title TEXT DEFAULT '',
                        text_preview TEXT DEFAULT '',
                        embedding vector({dim}),
                        metadata JSONB DEFAULT '{{}}'
                    )
                    """
                )
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self._table_name}_embedding "
                    f"ON {self._table_name} USING ivfflat (embedding vector_cosine_ops)"
                )
            self._available = True
        except ImportError:
            self._available = False
        except Exception:
            self._available = False

    def add(self, record: VectorStoreRecord) -> None:
        self._records[record.chunk_id] = record
        if self._available and self._conn is not None:
            embedding_str = "[" + ",".join(str(x) for x in record.embedding) + "]"
            with self._conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self._table_name} (chunk_id, source_id, trust_tier,
                        title, text_preview, embedding, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata
                    """,
                    (
                        record.chunk_id,
                        record.source_id,
                        record.trust_tier,
                        record.title,
                        record.text_preview,
                        embedding_str,
                        json.dumps(record.metadata),
                    ),
                )

    def add_batch(self, records: list[VectorStoreRecord]) -> None:
        for record in records:
            self.add(record)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 4,
        source_ids: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        if self._available and self._conn is not None:
            embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
            with self._conn.cursor() as cur:
                if source_ids:
                    placeholders = ",".join(["%s" for _ in source_ids])
                    cur.execute(
                        f"""
                        SELECT chunk_id, source_id, trust_tier, title, text_preview,
                               1 - (embedding <=> %s::vector) AS score
                        FROM {self._table_name}
                        WHERE source_id IN ({placeholders})
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (embedding_str, *source_ids, embedding_str, top_k),
                    )
                else:
                    cur.execute(
                        f"""
                        SELECT chunk_id, source_id, trust_tier, title, text_preview,
                               1 - (embedding <=> %s::vector) AS score
                        FROM {self._table_name}
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (embedding_str, embedding_str, top_k),
                    )
                rows = cur.fetchall()

            results: list[VectorSearchResult] = []
            for rank, row in enumerate(rows, 1):
                results.append(
                    VectorSearchResult(
                        chunk_id=row[0],
                        source_id=row[1],
                        trust_tier=row[2],
                        title=row[3],
                        text_preview=row[4],
                        score=round(float(row[5]), 4),
                        rank=rank,
                    )
                )
            return results

        # Fallback to in-memory search
        if not self._records:
            return []

        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm > 0:
            query_vec = query_vec / query_norm

        scored: list[tuple[str, float]] = []
        for chunk_id, record in self._records.items():
            if source_ids and record.source_id not in source_ids:
                continue
            record_vec = np.array(record.embedding, dtype=np.float32)
            record_norm = np.linalg.norm(record_vec)
            if record_norm > 0:
                record_vec = record_vec / record_norm
            score = float(np.dot(query_vec, record_vec))
            scored.append((chunk_id, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        search_results: list[VectorSearchResult] = []
        for rank, (chunk_id, score) in enumerate(scored[:top_k], 1):
            record = self._records[chunk_id]
            search_results.append(
                VectorSearchResult(
                    chunk_id=chunk_id,
                    source_id=record.source_id,
                    trust_tier=record.trust_tier,
                    title=record.title,
                    text_preview=record.text_preview,
                    score=round(score, 4),
                    rank=rank,
                )
            )
        return search_results

    def get(self, chunk_id: str) -> VectorStoreRecord | None:
        return self._records.get(chunk_id)

    def delete(self, chunk_id: str) -> bool:
        if chunk_id in self._records:
            del self._records[chunk_id]
            if self._available and self._conn is not None:
                with self._conn.cursor() as cur:
                    cur.execute(
                        f"DELETE FROM {self._table_name} WHERE chunk_id = %s",
                        (chunk_id,),
                    )
            return True
        return False

    def clear(self) -> None:
        self._records.clear()
        if self._available and self._conn is not None:
            with self._conn.cursor() as cur:
                cur.execute(f"TRUNCATE TABLE {self._table_name}")

    def count(self) -> int:
        return len(self._records)

    def list_source_ids(self) -> list[str]:
        return list(set(r.source_id for r in self._records.values()))

    def info(self) -> dict:
        return {
            "store": "pgvector",
            "available": self._available,
            "table": self._table_name,
            "count": self.count(),
            "source_count": len(self.list_source_ids()),
            "persistent": True,
            "dimension": self._dim,
        }


def get_vector_store(
    store_name: str = "memory",
    **kwargs,
) -> BaseVectorStore:
    """Factory function to get a vector store by name.

    Args:
        store_name: Name of the store ("memory", "json", "faiss",
                    "qdrant", or "pgvector").
        **kwargs: Additional arguments for the store.

    Returns:
        An instance of the requested store.

    Raises:
        ValueError: If the store name is unknown.
    """
    if store_name == "memory":
        return InMemoryVectorStore()
    elif store_name == "json":
        path = kwargs.get("path", "artifacts/index/vector_store.json")
        return JsonVectorStore(path=path)
    elif store_name == "faiss":
        dim = kwargs.get("dim", 128)
        return FaissVectorStore(dim=dim)
    elif store_name == "qdrant":
        return QdrantVectorStore(**kwargs)
    elif store_name == "pgvector":
        return PgVectorStore(**kwargs)
    else:
        raise ValueError(
            f"Unknown vector store: {store_name}. "
            "Available stores: memory, json, faiss, qdrant, pgvector"
        )
