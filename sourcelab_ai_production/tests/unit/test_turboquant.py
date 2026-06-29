"""Tests for TurboQuant compression adapter stub."""

from __future__ import annotations

import numpy as np

from sourcelab.retrieval.compression import (
    TurboQuantAdapter,
    ProductQuantizationAdapter,
    get_compression_adapter,
    available_compression_adapters,
)


class TestTurboQuantAdapter:
    def test_name(self):
        adapter = TurboQuantAdapter()
        assert adapter.name == "turboquant"

    def test_factory_selects_turboquant(self):
        adapter = get_compression_adapter("turboquant")
        assert isinstance(adapter, TurboQuantAdapter)

    def test_available_adapters_includes_turboquant(self):
        assert "turboquant" in available_compression_adapters()

    def test_quantize_dequantize_roundtrip(self):
        rng = np.random.default_rng(42)
        matrix = rng.standard_normal((20, 16)).astype(np.float32)
        adapter = TurboQuantAdapter(subspaces=4, bits=4)
        compressed, state = adapter.quantize(matrix)
        reconstructed = adapter.dequantize(compressed, state)
        assert reconstructed.shape == matrix.shape
        assert reconstructed.dtype == np.float32

    def test_stub_delegates_to_product_quantization(self):
        rng = np.random.default_rng(42)
        matrix = rng.standard_normal((10, 8)).astype(np.float32)
        tq = TurboQuantAdapter(subspaces=4, bits=4)
        pq = ProductQuantizationAdapter(subspaces=4, bits=4)
        tq_compressed, tq_state = tq.quantize(matrix)
        pq_compressed, pq_state = pq.quantize(matrix)
        assert tq_compressed.shape == pq_compressed.shape
        assert tq.dequantize(tq_compressed, tq_state).shape == pq.dequantize(pq_compressed, pq_state).shape

    def test_report_marks_stub(self):
        rng = np.random.default_rng(42)
        matrix = rng.standard_normal((5, 8)).astype(np.float32)
        adapter = TurboQuantAdapter(subspaces=4, bits=4)
        compressed, _ = adapter.quantize(matrix)
        report = adapter.report(matrix, compressed)
        assert report["method"] == "turboquant"
        assert report["stub"] is True
        assert report["delegate"] == "product_quantization"

    def test_empty_matrix(self):
        adapter = TurboQuantAdapter()
        empty = np.zeros((0, 0), dtype=np.float32)
        compressed, state = adapter.quantize(empty)
        reconstructed = adapter.dequantize(compressed, state)
        assert reconstructed.shape == (0, 0)

    def test_factory_accepts_kwargs(self):
        adapter = get_compression_adapter("turboquant", subspaces=4, bits=4)
        assert isinstance(adapter, TurboQuantAdapter)
