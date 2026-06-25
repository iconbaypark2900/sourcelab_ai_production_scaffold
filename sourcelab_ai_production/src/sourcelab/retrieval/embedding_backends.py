"""Embedding backends for vector retrieval.

Instruction:
- HashEmbeddingBackend is the default (deterministic, no dependencies).
- SentenceTransformersBackend is optional (requires sentence-transformers).
- OpenAICompatibleEmbeddingBackend is optional (requires httpx; supports vLLM, SGLang, LiteLLM, NIM).
- All backends must implement the BaseEmbeddingBackend interface.
- Backends must preserve source metadata in embedding records.
"""

from __future__ import annotations

import hashlib
import re
import time
from abc import ABC, abstractmethod

import numpy as np

from sourcelab.retrieval.schemas import EmbeddingBackendInfo


TOKEN_RE = re.compile(r"[a-zA-Z0-9_\-]+")


def _tokenize(text: str) -> list[str]:
    """Tokenize text for hash embedding."""
    return [t.lower() for t in TOKEN_RE.findall(text)]


def _stable_hash(token: str) -> int:
    """Create a stable hash for a token."""
    return int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)


class BaseEmbeddingBackend(ABC):
    """Abstract base class for embedding backends."""

    @abstractmethod
    def embed(self, text: str, dim: int = 128) -> np.ndarray:
        """Create an embedding vector for the given text."""

    @abstractmethod
    def embed_batch(self, texts: list[str], dim: int = 128) -> np.ndarray:
        """Create embedding vectors for a batch of texts."""

    @abstractmethod
    def info(self, dim: int = 128) -> EmbeddingBackendInfo:
        """Get information about this backend."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the backend."""


class HashEmbeddingBackend(BaseEmbeddingBackend):
    """Deterministic hash-based embedding backend (default).

    This backend creates embeddings by hashing tokens and accumulating
    sign-weighted values in a fixed-dimensional vector. It is:
    - Deterministic (same text always produces same embedding)
    - Fast (no model loading)
    - No external dependencies
    - Suitable for local demos and testing
    """

    @property
    def name(self) -> str:
        return "hash"

    def embed(self, text: str, dim: int = 128) -> np.ndarray:
        """Create a deterministic hash-based embedding."""
        vec = np.zeros(dim, dtype=np.float32)

        for token in _tokenize(text):
            h = _stable_hash(token)
            idx = h % dim
            sign = 1.0 if ((h >> 8) % 2 == 0) else -1.0
            vec[idx] += sign

        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def embed_batch(self, texts: list[str], dim: int = 128) -> np.ndarray:
        """Create embeddings for a batch of texts."""
        if not texts:
            return np.zeros((0, dim), dtype=np.float32)
        return np.vstack([self.embed(text, dim=dim) for text in texts])

    def info(self, dim: int = 128) -> EmbeddingBackendInfo:
        return EmbeddingBackendInfo(
            name="hash",
            dimension=dim,
            deterministic=True,
            requires_dependencies=False,
            installed=True,
        )


class SentenceTransformersBackend(BaseEmbeddingBackend):
    """Sentence-transformers embedding backend (optional).

    This backend uses the sentence-transformers library for high-quality
    embeddings. It requires the sentence-transformers package to be installed.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize the backend.

        Args:
            model_name: Name of the sentence-transformers model to use.

        Raises:
            ImportError: If sentence-transformers is not installed.
        """
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model_name)
            self._model_name = model_name
        except ImportError:
            raise ImportError(
                "Install retrieval extras: pip install -e '.[retrieval]'"
            )

    @property
    def name(self) -> str:
        return "sentence_transformers"

    def embed(self, text: str, dim: int = 128) -> np.ndarray:
        """Create an embedding using sentence-transformers."""
        embedding = self._model.encode([text], convert_to_numpy=True)[0]
        # Truncate or pad to requested dimension
        if len(embedding) > dim:
            return embedding[:dim].astype(np.float32)
        elif len(embedding) < dim:
            padded = np.zeros(dim, dtype=np.float32)
            padded[: len(embedding)] = embedding
            return padded
        return embedding.astype(np.float32)

    def embed_batch(self, texts: list[str], dim: int = 128) -> np.ndarray:
        """Create embeddings for a batch of texts."""
        if not texts:
            return np.zeros((0, dim), dtype=np.float32)
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        # Truncate or pad each embedding
        result = np.zeros((len(texts), dim), dtype=np.float32)
        for i, emb in enumerate(embeddings):
            actual_dim = min(len(emb), dim)
            result[i, :actual_dim] = emb[:actual_dim]
        return result

    def info(self, dim: int = 128) -> EmbeddingBackendInfo:
        model_dim = self._model.get_sentence_embedding_dimension()
        return EmbeddingBackendInfo(
            name="sentence_transformers",
            dimension=min(model_dim, dim),
            deterministic=False,
            requires_dependencies=True,
            installed=True,
        )


class OpenAICompatibleEmbeddingBackend(BaseEmbeddingBackend):
    """OpenAI-compatible embedding backend (optional).

    Supports vLLM, SGLang, LiteLLM, NIM, and other OpenAI-compatible
    embedding endpoints. Requires httpx (included in the ``retrieval`` extra).
    Calls fail closed with a clear error when httpx is missing or the
    endpoint is unreachable; it never falls back silently.
    """

    def __init__(
        self,
        model_name: str = "",
        base_url: str = "http://localhost:8000/v1",
        timeout_seconds: int = 60,
    ) -> None:
        self._model_name = model_name
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        return "openai_compatible"

    def _require_httpx(self):
        try:
            import httpx  # noqa: F401

            return httpx
        except ImportError as exc:
            raise ImportError(
                "OpenAI-compatible embeddings require httpx. "
                "Install retrieval extras: pip install -e '.[retrieval]'"
            ) from exc

    def _post_embeddings(self, httpx, texts: list[str], dim: int) -> np.ndarray:
        payload = {
            "model": self._model_name,
            "input": texts,
        }
        with httpx.Client(timeout=self._timeout_seconds) as client:
            resp = client.post(f"{self._base_url}/embeddings", json=payload)
            resp.raise_for_status()
            data = resp.json()
        raw = data["data"]
        raw.sort(key=lambda item: item.get("index", 0))
        vecs = [np.asarray(item["embedding"], dtype=np.float32) for item in raw]
        if not vecs:
            return np.zeros((0, dim), dtype=np.float32)
        result = np.zeros((len(vecs), dim), dtype=np.float32)
        for i, emb in enumerate(vecs):
            actual = min(len(emb), dim)
            result[i, :actual] = emb[:actual]
        return result

    def embed(self, text: str, dim: int = 128) -> np.ndarray:
        httpx = self._require_httpx()
        return self._post_embeddings(httpx, [text], dim)[0]

    def embed_batch(self, texts: list[str], dim: int = 128) -> np.ndarray:
        if not texts:
            return np.zeros((0, dim), dtype=np.float32)
        httpx = self._require_httpx()
        return self._post_embeddings(httpx, texts, dim)

    def info(self, dim: int = 128) -> EmbeddingBackendInfo:
        return EmbeddingBackendInfo(
            name="openai_compatible",
            dimension=dim,
            deterministic=False,
            requires_dependencies=True,
            installed=True,
        )

    def health_check(self) -> dict:
        """Return a health-check payload for diagnostics."""
        try:
            httpx = self._require_httpx()
        except ImportError as exc:
            return {
                "backend": "openai_compatible",
                "available": False,
                "model_name": self._model_name,
                "base_url": self._base_url,
                "error": str(exc),
            }
        start = time.time()
        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get(f"{self._base_url}/models")
                available = resp.status_code == 200
                latency_ms = (time.time() - start) * 1000
                return {
                    "backend": "openai_compatible",
                    "available": available,
                    "model_name": self._model_name,
                    "base_url": self._base_url,
                    "latency_ms": round(latency_ms, 2),
                    "status_code": resp.status_code,
                }
        except Exception as exc:
            return {
                "backend": "openai_compatible",
                "available": False,
                "model_name": self._model_name,
                "base_url": self._base_url,
                "error": str(exc),
            }


def get_embedding_backend(
    backend_name: str = "hash",
    **kwargs,
) -> BaseEmbeddingBackend:
    """Factory function to get an embedding backend by name.

    Args:
        backend_name: Name of the backend ("hash", "sentence_transformers",
                      or "openai_compatible").
        **kwargs: Additional arguments for the backend.

    Returns:
        An instance of the requested backend.

    Raises:
        ValueError: If the backend name is unknown.
    """
    if backend_name == "hash":
        return HashEmbeddingBackend()
    elif backend_name == "sentence_transformers":
        model_name = kwargs.get("model_name", "all-MiniLM-L6-v2")
        return SentenceTransformersBackend(model_name=model_name)
    elif backend_name == "openai_compatible":
        model_name = kwargs.get("model_name", "")
        base_url = kwargs.get("base_url", "http://localhost:8000/v1")
        timeout_seconds = kwargs.get("timeout_seconds", 60)
        return OpenAICompatibleEmbeddingBackend(
            model_name=model_name,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
    else:
        raise ValueError(
            f"Unknown embedding backend: {backend_name}. "
            "Available backends: hash, sentence_transformers, openai_compatible"
        )


def available_embedding_backends() -> list[str]:
    """Return the names of all registered embedding backends."""
    return ["hash", "sentence_transformers", "openai_compatible"]
