"""Model router v2.

Instruction:
- Routes between deterministic and local_llm backends.
- Deterministic mode is the default and always works.
- All model calls emit ModelCallTrace for the proof bundle.
- Fallback to deterministic mode on any error.
"""

from __future__ import annotations

from sourcelab.generation.schemas import GenerationTrace
from sourcelab.models.backends import BaseModelBackend, get_backend
from sourcelab.models.config import get_model_config
from sourcelab.models.prompts import PromptTemplates
from sourcelab.models.schemas import (
    ModelCallTrace,
    ModelCallTraceLog,
    ModelRequest,
    ModelResponse,
    ModelRouterConfig,
    PromptRenderResult,
)


class ModelRouter:
    """Route model requests to the configured backend with fallback."""

    def __init__(self, config: ModelRouterConfig | None = None) -> None:
        self.config = config or get_model_config()
        self._backend: BaseModelBackend | None = None
        self._trace_log = ModelCallTraceLog(
            mode=self.config.mode,
            backend=self.config.backend,
        )

    @property
    def backend(self) -> BaseModelBackend:
        if self._backend is None:
            self._backend = get_backend(
                self.config.backend,
                model_name=self.config.model_name,
                base_url=self.config.base_url,
                timeout_seconds=self.config.timeout_seconds,
            )
        return self._backend

    @property
    def trace_log(self) -> ModelCallTraceLog:
        return self._trace_log

    def reset_trace(self) -> None:
        self._trace_log = ModelCallTraceLog(
            mode=self.config.mode,
            backend=self.config.backend,
        )

    def render_prompt(
        self,
        route: str,
        source_ids: list[str] | None = None,
        chunk_ids: list[str] | None = None,
        **kwargs: object,
    ) -> PromptRenderResult:
        return PromptTemplates.render(
            route=route,
            source_ids=source_ids,
            chunk_ids=chunk_ids,
            **kwargs,
        )

    def generate(
        self,
        request: ModelRequest,
        source_ids: list[str] | None = None,
        chunk_ids: list[str] | None = None,
    ) -> ModelResponse:
        if self.config.mode == "deterministic":
            return self._deterministic_call(request)

        response = self.backend.generate(request)

        if response.raw_error or not response.text:
            if self.config.fallback == "deterministic":
                response.deterministic_fallback_used = True
                response.warnings.append(
                    f"Fallback to deterministic: {response.raw_error or 'empty response'}"
                )
                fallback = self._deterministic_call(request)
                response.text = fallback.text
                response.raw_error = None

        trace = ModelCallTrace(
            route=request.route,
            backend=response.backend,
            model_name=response.model_name,
            prompt_preview=request.prompt[:200],
            response_preview=response.text[:200],
            latency_ms=response.latency_ms,
            token_estimate=response.token_estimate,
            deterministic_fallback_used=response.deterministic_fallback_used,
            warnings=response.warnings,
            raw_error=response.raw_error,
        )
        self._trace_log.calls.append(trace)
        self._trace_log.total_calls += 1
        if response.deterministic_fallback_used:
            self._trace_log.fallback_count += 1
        self._trace_log.total_latency_ms += response.latency_ms

        return response

    def generate_with_fallbacks(
        self,
        request: ModelRequest,
        fallback_backends: list[str] | None = None,
    ) -> ModelResponse:
        """Generate with explicit fallback backend chain.

        Tries the primary backend, then each fallback in order.
        Always ends with deterministic backend (never fails completely).
        Fallback events are logged to the trace log.
        """
        if self.config.mode == "deterministic":
            return self._deterministic_call(request)

        chain: list[str] = [self.config.backend]
        if fallback_backends:
            chain.extend(b for b in fallback_backends if b not in chain)
        if "deterministic" not in chain:
            chain.append("deterministic")

        last_error: str | None = None
        for i, backend_name in enumerate(chain):
            try:
                backend = get_backend(
                    backend_name,
                    model_name=self.config.model_name,
                    base_url=self.config.base_url,
                    timeout_seconds=self.config.timeout_seconds,
                )
                response = backend.generate(request)

                if not response.raw_error and response.text:
                    if i > 0:
                        response.deterministic_fallback_used = backend_name == "deterministic"
                        response.warnings.append(
                            f"Fallback to {backend_name}: {last_error or 'primary backend failed'}"
                        )

                    trace = ModelCallTrace(
                        route=request.route,
                        backend=response.backend,
                        model_name=response.model_name,
                        prompt_preview=request.prompt[:200],
                        response_preview=response.text[:200],
                        latency_ms=response.latency_ms,
                        token_estimate=response.token_estimate,
                        deterministic_fallback_used=response.deterministic_fallback_used,
                        warnings=response.warnings,
                        raw_error=None,
                    )
                    self._trace_log.calls.append(trace)
                    self._trace_log.total_calls += 1
                    if response.deterministic_fallback_used:
                        self._trace_log.fallback_count += 1
                    self._trace_log.total_latency_ms += response.latency_ms

                    return response

                last_error = response.raw_error or "empty response"
            except Exception as exc:
                last_error = str(exc)
                continue

        return self._deterministic_call(request)

    def _deterministic_call(self, request: ModelRequest) -> ModelResponse:
        det_backend = get_backend("deterministic")
        response = det_backend.generate(request)
        response.deterministic_fallback_used = self.config.mode != "deterministic"

        trace = ModelCallTrace(
            route=request.route,
            backend="deterministic",
            model_name="deterministic",
            prompt_preview=request.prompt[:200],
            response_preview=response.text[:200],
            latency_ms=0.0,
            token_estimate=response.token_estimate,
            deterministic_fallback_used=response.deterministic_fallback_used,
        )
        self._trace_log.calls.append(trace)
        self._trace_log.total_calls += 1
        if response.deterministic_fallback_used:
            self._trace_log.fallback_count += 1

        return response

    def update_generation_trace(
        self, trace: GenerationTrace
    ) -> GenerationTrace:
        if self.config.mode != "deterministic":
            trace.generation_backend = f"local_llm_{self.config.backend}"
            if self._trace_log.fallback_count > 0:
                trace.warnings.append(
                    f"{self._trace_log.fallback_count} model calls fell back to deterministic"
                )
        return trace

    def get_trace_log_dict(self) -> dict:
        return self._trace_log.model_dump()
