"""FastAPI application for SourceLab AI.

Instruction:
- Install with `pip install -e ".[api]"`.
- Run with `uvicorn sourcelab.api.main:app --reload`.
- This API is a thin layer over existing CLI/pipeline functions.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:  # pragma: no cover
    FastAPI = None

if FastAPI:
    from sourcelab.api.config import get_config
    from sourcelab.api.errors import api_error_handler, generic_error_handler, APIError
    from sourcelab.api.schemas import HealthResponse, ReadinessResponse, VersionResponse
    from sourcelab.version import __version__
    from sourcelab.api.routes_sources import router as sources_router
    from sourcelab.api.routes_retrieval import router as retrieval_router
    from sourcelab.api.routes_lessons import router as lessons_router
    from sourcelab.api.routes_runs import router as runs_router
    from sourcelab.api.routes_batches import router as batches_router
    from sourcelab.api.routes_learning import router as learning_router
    from sourcelab.api.routes_models import router as models_router
    from sourcelab.api.routes_source_packs import router as source_packs_router
    from sourcelab.api.routes_evals import router as evals_router


if FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Startup and shutdown events."""
        # Startup
        config = get_config()
        app.state.config = config
        yield
        # Shutdown

    app = FastAPI(
        title="SourceLab AI",
        description="REST API for SourceLab AI production scaffold",
        version=__version__,
        lifespan=lifespan,
    )

    # CORS middleware (local development only)
    config = get_config()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=config.cors_methods,
        allow_headers=config.cors_headers,
    )

    # Exception handlers
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)

    # Include routers
    app.include_router(sources_router, prefix="/sources", tags=["sources"])
    app.include_router(retrieval_router, prefix="/retrieval", tags=["retrieval"])
    app.include_router(lessons_router, prefix="/lessons", tags=["lessons"])
    app.include_router(runs_router, prefix="/runs", tags=["runs"])
    app.include_router(batches_router, prefix="/batches", tags=["batches"])
    app.include_router(learning_router, prefix="/learning", tags=["learning"])
    app.include_router(models_router, prefix="/models", tags=["models"])
    app.include_router(source_packs_router, prefix="/source-packs", tags=["source-packs"])
    app.include_router(evals_router, prefix="/evals", tags=["evals"])

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/ready", response_model=ReadinessResponse)
    def readiness() -> ReadinessResponse:
        """Check if the API is ready to serve requests."""
        components = {}

        # Check source registry
        try:
            from pathlib import Path
            config = get_config()
            registry_path = config.project_root / "data" / "source_registry.json"
            if registry_path.exists():
                components["source_registry"] = "ok"
            else:
                components["source_registry"] = "demo_mode"
        except Exception as e:
            components["source_registry"] = f"error: {e}"

        # Check runs directory
        try:
            from pathlib import Path
            config = get_config()
            runs_dir = config.project_root / "artifacts" / "runs"
            if runs_dir.exists():
                components["runs_directory"] = "ok"
            else:
                components["runs_directory"] = "no_runs"
        except Exception as e:
            components["runs_directory"] = f"error: {e}"

        return ReadinessResponse(
            status="ready",
            components=components,
        )

    @app.get("/version", response_model=VersionResponse)
    def version() -> VersionResponse:
        from sourcelab.version import version_info

        config = get_config()
        return VersionResponse(**version_info(config.project_root))

    @app.post("/demo")
    def demo(topic: str = "post-quantum cryptography migration") -> dict:
        from pathlib import Path
        from sourcelab.core.pipeline import run_demo_pipeline
        return run_demo_pipeline(topic=topic, project_root=Path.cwd())

else:
    app = None  # pragma: no cover
