"""Model schemas for the model router.

Instruction:
- These schemas define the model routing interface.
- Every field must be serializable to JSON for the proof bundle.
- Keep schemas explicit so the harness can validate them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class ModelRequest(BaseModel):
    """A request to a model backend."""

    prompt: str
    route: str = "general"
    temperature: float = 0.0
    max_tokens: int = 2048
    json_mode: bool = False
    source_ids: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    extra: dict = Field(default_factory=dict)


class ModelResponse(BaseModel):
    """Response from a model backend."""

    text: str
    backend: str
    model_name: str
    route: str
    latency_ms: float = 0.0
    token_estimate: int = 0
    deterministic_fallback_used: bool = False
    warnings: list[str] = Field(default_factory=list)
    raw_error: str | None = None


class ModelBackendInfo(BaseModel):
    """Information about a model backend."""

    name: str
    available: bool
    model_name: str = ""
    base_url: str = ""
    timeout_seconds: int = 60
    error: str | None = None


class ModelRoute(BaseModel):
    """A named route through the model router."""

    route_name: str
    prompt_template: str = ""
    description: str = ""
    supports_json_mode: bool = True


class ModelRouterConfig(BaseModel):
    """Configuration for the model router."""

    mode: Literal["deterministic", "local_llm"] = "deterministic"
    backend: Literal["deterministic", "ollama", "openai_compatible"] = "deterministic"
    model_name: str = ""
    base_url: str = ""
    timeout_seconds: int = 60
    fallback: Literal["deterministic"] = "deterministic"
    routes: dict[str, ModelRoute] = Field(default_factory=dict)


class ModelCallTrace(BaseModel):
    """Trace of a single model call for the proof bundle."""

    route: str
    backend: str
    model_name: str
    prompt_preview: str = ""
    response_preview: str = ""
    latency_ms: float = 0.0
    token_estimate: int = 0
    deterministic_fallback_used: bool = False
    warnings: list[str] = Field(default_factory=list)
    raw_error: str | None = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ModelCallTraceLog(BaseModel):
    """Complete log of all model calls in a pipeline run."""

    calls: list[ModelCallTrace] = Field(default_factory=list)
    total_calls: int = 0
    fallback_count: int = 0
    total_latency_ms: float = 0.0
    mode: str = "deterministic"
    backend: str = "deterministic"


class ModelHealthCheck(BaseModel):
    """Health check result for a model backend."""

    backend: str
    available: bool
    model_name: str = ""
    latency_ms: float = 0.0
    error: str | None = None
    checked_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class PromptTemplate(BaseModel):
    """A prompt template with metadata."""

    name: str
    template: str
    description: str = ""
    expects_json: bool = False
    source_required: bool = True
    fail_closed: bool = True


class PromptRenderResult(BaseModel):
    """Result of rendering a prompt template."""

    prompt: str
    template_name: str
    source_ids: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    rendered_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
