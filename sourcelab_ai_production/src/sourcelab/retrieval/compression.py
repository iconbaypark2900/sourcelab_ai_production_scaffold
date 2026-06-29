"""Vector compression.

Instruction:
- This module demonstrates TurboQuant-style product pressure with int8 compression.
- It is not a full TurboQuant implementation.
- Production should add fp16, product quantization, binary quantization, and real TurboQuant adapters.
- CompressionReport schema is now available for structured reporting.
- CompressionAdapter provides a uniform interface; get_compression_adapter selects by name.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from sourcelab.retrieval.schemas import CompressionReport


def int8_quantize(matrix: np.ndarray) -> tuple[np.ndarray, float]:
    """Quantize fp32 vectors to int8 using one global scale."""
    max_abs = float(np.max(np.abs(matrix))) if matrix.size else 1.0
    scale = max_abs / 127.0 if max_abs > 0 else 1.0
    return np.round(matrix / scale).astype(np.int8), scale


def int8_dequantize(matrix: np.ndarray, scale: float) -> np.ndarray:
    """Restore int8 vectors to fp32 approximation."""
    return matrix.astype(np.float32) * scale


def fp16_quantize(matrix: np.ndarray) -> tuple[np.ndarray, float]:
    """Quantize fp32 vectors to fp16 (half precision).

    Returns the fp16 matrix and a scale of 1.0 for API symmetry with int8.
    fp16 halves storage while preserving near-full precision for embeddings.
    """
    if matrix.size == 0:
        return np.zeros((0, 0), dtype=np.float16), 1.0
    return matrix.astype(np.float16), 1.0


def fp16_dequantize(matrix: np.ndarray, scale: float = 1.0) -> np.ndarray:
    """Restore fp16 vectors to fp32 approximation."""
    return matrix.astype(np.float32) * scale


def binary_quantize(matrix: np.ndarray) -> tuple[np.ndarray, float]:
    """Quantize fp32 vectors to 1-bit signs (+1/-1).

    Sign-based binary quantization yields a 32x storage reduction and
    supports fast hamming-distance retrieval. Returns int8 signs and a
    scale of 1.0 for API symmetry.
    """
    if matrix.size == 0:
        return np.zeros((0, 0), dtype=np.int8), 1.0
    signs = np.where(matrix >= 0, 1, -1).astype(np.int8)
    return signs, 1.0


def binary_dequantize(matrix: np.ndarray, scale: float = 1.0) -> np.ndarray:
    """Restore binary sign vectors to fp32 (+1.0/-1.0 scaled)."""
    return matrix.astype(np.float32) * scale


def product_quantize(
    matrix: np.ndarray, subspaces: int = 8, bits: int = 8
) -> tuple[np.ndarray, list[np.ndarray], list[np.ndarray]]:
    """Product quantization (PQ) baseline.

    Splits each vector into ``subspaces`` contiguous subvectors, trains a
    k-means codebook (k = 2**bits) per subspace on the provided matrix,
    and encodes each subvector as the index of its nearest codebook entry.

    Returns:
        codes: int array of shape (n, subspaces) with codebook indices.
        codebooks: list of per-subspace codebooks, each (k, sub_dim).
        boundaries: list of (start, end) column index pairs per subspace.

    This is a lightweight, dependency-free PQ suitable for local demos and
    research stubs; production should use a vetted PQ implementation.
    """
    if matrix.size == 0:
        return (
            np.zeros((0, subspaces), dtype=np.int32),
            [np.zeros((2**bits, 0), dtype=np.float32) for _ in range(subspaces)],
            [(0, 0) for _ in range(subspaces)],
        )

    n, dim = matrix.shape
    subspaces = min(subspaces, dim)
    k = 2**bits
    sub_dim = dim // subspaces
    # Distribute remainder columns across the last subspace
    boundaries: list[tuple[int, int]] = []
    start = 0
    for i in range(subspaces):
        end = start + sub_dim + (dim - start - sub_dim if i == subspaces - 1 else 0)
        boundaries.append((start, end))
        start = end

    matrix_f32 = matrix.astype(np.float32)
    codes = np.zeros((n, subspaces), dtype=np.int32)
    codebooks: list[np.ndarray] = []

    for i, (s, e) in enumerate(boundaries):
        sub = matrix_f32[:, s:e]
        if sub.shape[1] == 0:
            codebooks.append(np.zeros((k, 0), dtype=np.float32))
            continue
        # Train a simple k-means: pick k centers (repeat samples if n < k)
        if n >= k:
            centers = sub[np.random.default_rng(0).choice(n, size=k, replace=False)].copy()
        else:
            centers = np.tile(sub, (k // n + 1, 1))[:k].copy()
        for _ in range(8):
            # Assignment step
            dists = ((sub[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
            assign = np.argmin(dists, axis=1)
            # Update step
            for c in range(k):
                mask = assign == c
                if mask.any():
                    centers[c] = sub[mask].mean(axis=0)
        # Final assignment
        dists = ((sub[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        codes[:, i] = np.argmin(dists, axis=1)
        codebooks.append(centers)

    return codes, codebooks, boundaries


def product_dequantize(
    codes: np.ndarray,
    codebooks: list[np.ndarray],
    boundaries: list[tuple[int, int]],
) -> np.ndarray:
    """Reconstruct fp32 vectors from PQ codes and codebooks."""
    n = codes.shape[0]
    dim = sum(e - s for s, e in boundaries)
    out = np.zeros((n, dim), dtype=np.float32)
    for i, (s, e) in enumerate(boundaries):
        if e - s == 0 or i >= len(codebooks):
            continue
        out[:, s:e] = codebooks[i][codes[:, i]]
    return out


def compression_report(fp32_matrix: np.ndarray, int8_matrix: np.ndarray) -> dict:
    """Generate a compression report from matrices.

    Args:
        fp32_matrix: Original fp32 matrix.
        int8_matrix: Compressed int8 matrix.

    Returns:
        Dictionary with compression statistics.
    """
    original_dim = fp32_matrix.shape[1] if fp32_matrix.size > 0 else 0
    compressed_dim = int8_matrix.shape[1] if int8_matrix.size > 0 else 0
    original_bytes = int(fp32_matrix.nbytes)
    compressed_bytes = int(int8_matrix.nbytes)
    reduction_ratio = round(original_bytes / compressed_bytes, 2) if compressed_bytes else 0

    return {
        "original_dim": original_dim,
        "compressed_dim": compressed_dim,
        "original_bytes": original_bytes,
        "compressed_bytes": compressed_bytes,
        "reduction_ratio": reduction_ratio,
        "method": "int8_quantize",
    }


def compression_report_for(
    fp32_matrix: np.ndarray, compressed_matrix: np.ndarray, method: str
) -> dict:
    """Generate a compression report for any compression method.

    Args:
        fp32_matrix: Original fp32 matrix.
        compressed_matrix: Compressed matrix (any dtype).
        method: Compression method name.

    Returns:
        Dictionary with compression statistics.
    """
    original_dim = fp32_matrix.shape[1] if fp32_matrix.size > 0 else 0
    compressed_dim = compressed_matrix.shape[1] if compressed_matrix.size > 0 else 0
    original_bytes = int(fp32_matrix.nbytes)
    compressed_bytes = int(compressed_matrix.nbytes)
    reduction_ratio = round(original_bytes / compressed_bytes, 2) if compressed_bytes else 0

    return {
        "original_dim": original_dim,
        "compressed_dim": compressed_dim,
        "original_bytes": original_bytes,
        "compressed_bytes": compressed_bytes,
        "reduction_ratio": reduction_ratio,
        "method": method,
    }


class CompressionAdapter(ABC):
    """Abstract base class for vector compression adapters.

    Each adapter implements quantize/dequantize and reports its method name.
    Adapters are local-first, deterministic, and require no external deps.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the compression method."""

    @abstractmethod
    def quantize(self, matrix: np.ndarray) -> tuple[np.ndarray, "object"]:
        """Quantize a matrix; return (compressed, state) for later dequantization."""

    @abstractmethod
    def dequantize(self, compressed: np.ndarray, state: "object") -> np.ndarray:
        """Reconstruct an approximate fp32 matrix from compressed + state."""

    def report(self, fp32_matrix: np.ndarray, compressed: np.ndarray) -> dict:
        """Return a compression report for this adapter."""
        return compression_report_for(fp32_matrix, compressed, self.name)


class Int8CompressionAdapter(CompressionAdapter):
    """int8 scalar quantization adapter (default)."""

    @property
    def name(self) -> str:
        return "int8"

    def quantize(self, matrix: np.ndarray) -> tuple[np.ndarray, float]:
        return int8_quantize(matrix)

    def dequantize(self, compressed: np.ndarray, state: float) -> np.ndarray:
        return int8_dequantize(compressed, state)


class Fp16CompressionAdapter(CompressionAdapter):
    """fp16 (half precision) compression adapter."""

    @property
    def name(self) -> str:
        return "fp16"

    def quantize(self, matrix: np.ndarray) -> tuple[np.ndarray, float]:
        return fp16_quantize(matrix)

    def dequantize(self, compressed: np.ndarray, state: float) -> np.ndarray:
        return fp16_dequantize(compressed, state)


class BinaryCompressionAdapter(CompressionAdapter):
    """1-bit binary (sign) quantization adapter."""

    @property
    def name(self) -> str:
        return "binary"

    def quantize(self, matrix: np.ndarray) -> tuple[np.ndarray, float]:
        return binary_quantize(matrix)

    def dequantize(self, compressed: np.ndarray, state: float) -> np.ndarray:
        return binary_dequantize(compressed, state)


class ProductQuantizationAdapter(CompressionAdapter):
    """Product quantization (PQ) baseline adapter."""

    def __init__(self, subspaces: int = 8, bits: int = 8):
        self.subspaces = subspaces
        self.bits = bits

    @property
    def name(self) -> str:
        return "product_quantization"

    def quantize(
        self, matrix: np.ndarray
    ) -> tuple[np.ndarray, tuple[list[np.ndarray], list[tuple[int, int]]]]:
        codes, codebooks, boundaries = product_quantize(
            matrix, subspaces=self.subspaces, bits=self.bits
        )
        return codes, (codebooks, boundaries)

    def dequantize(
        self,
        compressed: np.ndarray,
        state: tuple[list[np.ndarray], list[tuple[int, int]]],
    ) -> np.ndarray:
        codebooks, boundaries = state
        return product_dequantize(compressed, codebooks, boundaries)

    def report(self, fp32_matrix: np.ndarray, compressed: np.ndarray) -> dict:
        report = compression_report_for(fp32_matrix, compressed, self.name)
        report["subspaces"] = self.subspaces
        report["bits"] = self.bits
        return report


class TurboQuantAdapter(CompressionAdapter):
    """TurboQuant research adapter stub.

    This is a research stub that implements the CompressionAdapter interface
    but delegates to product quantization internally. Replace with a real
    TurboQuant implementation when available.
    """

    def __init__(self, subspaces: int = 8, bits: int = 8):
        self._pq = ProductQuantizationAdapter(subspaces=subspaces, bits=bits)

    @property
    def name(self) -> str:
        return "turboquant"

    def quantize(
        self, matrix: np.ndarray
    ) -> tuple[np.ndarray, tuple[list[np.ndarray], list[tuple[int, int]]]]:
        return self._pq.quantize(matrix)

    def dequantize(
        self,
        compressed: np.ndarray,
        state: tuple[list[np.ndarray], list[tuple[int, int]]],
    ) -> np.ndarray:
        return self._pq.dequantize(compressed, state)

    def report(self, fp32_matrix: np.ndarray, compressed: np.ndarray) -> dict:
        report = self._pq.report(fp32_matrix, compressed)
        report["method"] = "turboquant"
        report["stub"] = True
        report["delegate"] = "product_quantization"
        return report


_ADAPTERS: dict[str, type[CompressionAdapter]] = {
    "int8": Int8CompressionAdapter,
    "fp16": Fp16CompressionAdapter,
    "binary": BinaryCompressionAdapter,
    "product_quantization": ProductQuantizationAdapter,
    "turboquant": TurboQuantAdapter,
}


def get_compression_adapter(name: str = "int8", **kwargs) -> CompressionAdapter:
    """Factory function to get a compression adapter by name.

    Args:
        name: Adapter name ("int8", "fp16", "binary", "product_quantization").
        **kwargs: Additional arguments (e.g. subspaces, bits for PQ).

    Returns:
        An instance of the requested adapter.

    Raises:
        ValueError: If the adapter name is unknown.
    """
    cls = _ADAPTERS.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown compression adapter: {name}. "
            f"Available adapters: {', '.join(_ADAPTERS)}"
        )
    return cls(**kwargs)


def available_compression_adapters() -> list[str]:
    """Return the names of all registered compression adapters."""
    return list(_ADAPTERS)
