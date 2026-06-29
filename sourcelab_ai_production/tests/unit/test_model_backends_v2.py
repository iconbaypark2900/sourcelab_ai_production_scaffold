"""Tests for DiffusionGemma backend and fallback model routing."""

from __future__ import annotations

import json

from sourcelab.generation.model_router import ModelRouter
from sourcelab.models.backends import (
    DeterministicBackend,
    DiffusionGemmaBackend,
    get_backend,
)
from sourcelab.models.schemas import ModelRequest, ModelResponse, ModelRouterConfig


class TestDiffusionGemmaBackend:
    def test_name(self):
        backend = DiffusionGemmaBackend()
        assert backend.name == "diffusion_gemma"

    def test_default_config(self):
        backend = DiffusionGemmaBackend()
        assert backend.model_name == "diffusion-gemma"
        assert "localhost:8001" in backend.base_url

    def test_get_backend_factory(self):
        backend = get_backend("diffusion_gemma")
        assert isinstance(backend, DiffusionGemmaBackend)

    def test_get_backend_unknown_falls_back_to_deterministic(self):
        backend = get_backend("unknown_backend")
        assert isinstance(backend, DeterministicBackend)

    def test_health_check_without_httpx(self):
        backend = DiffusionGemmaBackend()
        info = backend.health_check()
        assert info.name == "diffusion_gemma"
        assert info.available is False

    def test_health_check_with_invalid_url(self):
        backend = DiffusionGemmaBackend(base_url="http://127.0.0.1:99999/v1")
        info = backend.health_check()
        assert info.available is False

    def test_generate_returns_error_without_server(self):
        backend = DiffusionGemmaBackend(base_url="http://127.0.0.1:99999/v1")
        request = ModelRequest(
            prompt="test prompt",
            route="general",
        )
        response = backend.generate(request)
        assert response.backend == "diffusion_gemma"
        assert response.raw_error is not None
        assert any("DiffusionGemma" in w for w in response.warnings)


class TestModelRouterConfigDiffusionGemma:
    def test_config_accepts_diffusion_gemma(self):
        config = ModelRouterConfig(
            mode="local_llm",
            backend="diffusion_gemma",
            base_url="http://localhost:8001/v1",
        )
        assert config.backend == "diffusion_gemma"

    def test_router_uses_diffusion_gemma_backend(self):
        config = ModelRouterConfig(
            mode="local_llm",
            backend="diffusion_gemma",
            base_url="http://127.0.0.1:99999/v1",
        )
        router = ModelRouter(config=config)
        request = ModelRequest(prompt="test", route="general")
        response = router.generate(request)
        assert response.deterministic_fallback_used is True
        assert response.text != ""


class TestFallbackModelRouting:
    def test_generate_with_fallbacks_in_deterministic_mode(self):
        config = ModelRouterConfig(mode="deterministic")
        router = ModelRouter(config=config)
        request = ModelRequest(prompt="test", route="general")
        response = router.generate_with_fallbacks(request)
        assert response.backend == "deterministic"

    def test_generate_with_fallbacks_primary_success(self):
        config = ModelRouterConfig(mode="deterministic")
        router = ModelRouter(config=config)
        request = ModelRequest(prompt="test", route="general", json_mode=True)
        response = router.generate_with_fallbacks(request, fallback_backends=["ollama"])
        assert response.backend == "deterministic"
        assert response.deterministic_fallback_used is False

    def test_generate_with_fallbacks_all_fail_to_deterministic(self):
        config = ModelRouterConfig(
            mode="local_llm",
            backend="diffusion_gemma",
            base_url="http://127.0.0.1:99999/v1",
        )
        router = ModelRouter(config=config)
        request = ModelRequest(prompt="test", route="general", json_mode=True)
        response = router.generate_with_fallbacks(
            request,
            fallback_backends=["ollama", "openai_compatible"],
        )
        assert response.backend == "deterministic"
        assert response.deterministic_fallback_used is True

    def test_generate_with_fallbacks_logs_trace(self):
        config = ModelRouterConfig(mode="deterministic")
        router = ModelRouter(config=config)
        request = ModelRequest(prompt="test fallback trace", route="general")
        router.generate_with_fallbacks(request, fallback_backends=["ollama"])
        assert router.trace_log.total_calls >= 1

    def test_generate_with_fallbacks_empty_chain(self):
        config = ModelRouterConfig(mode="deterministic")
        router = ModelRouter(config=config)
        request = ModelRequest(prompt="test", route="general")
        response = router.generate_with_fallbacks(request, fallback_backends=[])
        assert response.text != ""
