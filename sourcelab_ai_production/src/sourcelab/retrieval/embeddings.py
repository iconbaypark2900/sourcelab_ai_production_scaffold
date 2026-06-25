"""Deterministic local embeddings.

Instruction:
- This is a no-network stand-in for production embeddings.
- Replace with sentence-transformers, OpenAI embeddings, NIM embeddings, or local models.
- HashEmbeddingBackend is now the recommended interface.
- This module is kept for backward compatibility.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np

# Re-export from embedding_backends for backward compatibility
from sourcelab.retrieval.embedding_backends import (  # noqa: F401
    HashEmbeddingBackend,
    BaseEmbeddingBackend,
    get_embedding_backend,
)

TOKEN_RE = re.compile(r"[a-zA-Z0-9_\-]+")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def stable_hash(token: str) -> int:
    return int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)


def hashed_embedding(text: str, dim: int = 128) -> np.ndarray:
    """Create a deterministic embedding-like vector for local demos."""
    vec = np.zeros(dim, dtype=np.float32)

    for token in tokenize(text):
        h = stable_hash(token)
        idx = h % dim
        sign = 1.0 if ((h >> 8) % 2 == 0) else -1.0
        vec[idx] += sign

    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec
