"""Model router API endpoints.

Instruction:
- Provide /models/config, /models/health, /models/test endpoints.
- Allow model params on lesson creation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

try:
    from fastapi import APIRouter
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore

if APIRouter:
    router = APIRouter()

    class ModelConfigResponse(BaseModel):
        """Model configuration response."""
        mode: str = "deterministic"
        backend: str = "deterministic"
        model_name: str = ""
        base_url: str = ""
        timeout_seconds: int = 60
        fallback: str = "deterministic"

    class ModelHealthResponse(BaseModel):
        """Model health check response."""
        backend: str
        available: bool
        model_name: str = ""
        latency_ms: float = 0.0
        error: str | None = None

    class ModelTestRequest(BaseModel):
        """Model test request."""
        mode: Literal["deterministic", "local_llm"] = "deterministic"
        backend: Literal["deterministic", "ollama", "openai_compatible"] = "deterministic"
        model_name: str = ""
        base_url: str = ""
        prompt: str = "What is post-quantum cryptography?"

    class ModelTestResponse(BaseModel):
        """Model test response."""
        text: str
        backend: str
        model_name: str
        route: str
        latency_ms: float = 0.0
        deterministic_fallback_used: bool = False
        warnings: list[str] = Field(default_factory=list)

    @router.get("/config", response_model=ModelConfigResponse)
    def get_model_config_endpoint() -> ModelConfigResponse:
        from sourcelab.models.config import get_model_config
        config = get_model_config()
        return ModelConfigResponse(
            mode=config.mode,
            backend=config.backend,
            model_name=config.model_name,
            base_url=config.base_url,
            timeout_seconds=config.timeout_seconds,
            fallback=config.fallback,
        )

    @router.get("/health", response_model=ModelHealthResponse)
    def get_model_health_endpoint() -> ModelHealthResponse:
        from sourcelab.models.config import get_model_config
        from sourcelab.models.backends import get_backend

        config = get_model_config()
        backend = get_backend(
            config.backend,
            model_name=config.model_name,
            base_url=config.base_url,
            timeout_seconds=config.timeout_seconds,
        )
        health = backend.health_check()
        return ModelHealthResponse(
            backend=health.name,
            available=health.available,
            model_name=health.model_name,
            latency_ms=health.latency_ms,
            error=health.error,
        )

    @router.post("/test", response_model=ModelTestResponse)
    def test_model_endpoint(request: ModelTestRequest) -> ModelTestResponse:
        from sourcelab.generation.model_router import ModelRouter
        from sourcelab.models.schemas import ModelRequest, ModelRouterConfig

        config = ModelRouterConfig(
            mode=request.mode,
            backend=request.backend,
            model_name=request.model_name,
            base_url=request.base_url,
        )
        router_instance = ModelRouter(config=config)

        model_request = ModelRequest(
            prompt=request.prompt,
            route="general",
        )
        response = router_instance.generate(model_request)
        return ModelTestResponse(
            text=response.text[:500],
            backend=response.backend,
            model_name=response.model_name,
            route=response.route,
            latency_ms=response.latency_ms,
            deterministic_fallback_used=response.deterministic_fallback_used,
            warnings=response.warnings,
        )
