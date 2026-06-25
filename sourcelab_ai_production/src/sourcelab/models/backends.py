"""Model backends for SourceLab AI.

Instruction:
- Implement BaseModelBackend as the interface.
- Implement DeterministicBackend (always works, no model required).
- Implement OllamaBackend (calls local Ollama at localhost:11434).
- Implement OpenAICompatibleBackend (supports vLLM, SGLang, LiteLLM, NIM).
- httpx is an optional dependency: pip install -e ".[models]"
"""

from __future__ import annotations

import json
import time
import uuid

from sourcelab.models.schemas import ModelBackendInfo, ModelRequest, ModelResponse


class BaseModelBackend:
    """Base interface for model backends."""

    name: str = "base"

    def generate(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError

    def health_check(self) -> ModelBackendInfo:
        return ModelBackendInfo(name=self.name, available=False)

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4


class DeterministicBackend(BaseModelBackend):
    """Deterministic backend that always works without a model."""

    name = "deterministic"

    def generate(self, request: ModelRequest) -> ModelResponse:
        text = self._deterministic_response(request)
        return ModelResponse(
            text=text,
            backend="deterministic",
            model_name="deterministic",
            route=request.route,
            latency_ms=0.0,
            token_estimate=self._estimate_tokens(text),
        )

    def _deterministic_response(self, request: ModelRequest) -> str:
        prompt_lower = request.prompt.lower()
        if request.json_mode:
            if "criteria_scores" in prompt_lower and "answer" in prompt_lower:
                # answer_judging route — check before "rubric" since judge prompts also mention rubric
                return json.dumps(
                    {
                        "criteria_scores": {
                            "topic_relevance": 0.85,
                            "source_grounding": 0.75,
                            "practical_reasoning": 0.80,
                            "uncertainty_control": 0.70,
                            "trap_avoidance": 0.65,
                            "clarity": 0.90,
                            "citation_use_of_evidence": 0.60,
                        },
                        "feedback": "Deterministic judge: answer demonstrates adequate understanding.",
                        "strengths": ["Strong clarity", "Good topic relevance"],
                        "weaknesses": ["Weak citation use", "Room for trap avoidance"],
                    }
                )
            if "scenario" in prompt_lower:
                return json.dumps(
                    {
                        "scenario": "Deterministic scenario generated",
                        "context": "System design scenario",
                        "task": "Analyze the scenario",
                        "constraints": ["deterministic", "safe"],
                    }
                )
            if "answer_key" in prompt_lower:
                return json.dumps(
                    {
                        "answers": [
                            {
                                "question_id": "q1",
                                "answer": "Deterministic answer",
                                "points": 10,
                                "rationale": "Based on deterministic logic",
                            }
                        ]
                    }
                )
            if "rubric" in prompt_lower and "criteria_scores" not in prompt_lower:
                return json.dumps(
                    {
                        "criteria": [
                            {
                                "name": "deterministic",
                                "description": "Deterministic scoring",
                                "max_points": 10,
                                "weight": 1.0,
                            }
                        ]
                    }
                )
            if "lesson" in prompt_lower:
                return json.dumps(
                    {
                        "title": "Deterministic Lesson",
                        "objective": "Learn through deterministic reasoning",
                        "content": "This lesson was generated deterministically.",
                    }
                )
            return json.dumps({"status": "deterministic", "message": "Generated deterministically"})
        return "This response was generated deterministically without a model."

    def health_check(self) -> ModelBackendInfo:
        return ModelBackendInfo(
            name="deterministic",
            available=True,
            model_name="deterministic",
        )


class OllamaBackend(BaseModelBackend):
    """Backend that calls a local Ollama server."""

    name = "ollama"

    def __init__(
        self,
        model_name: str = "llama2",
        base_url: str = "http://localhost:11434",
        timeout_seconds: int = 60,
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def generate(self, request: ModelRequest) -> ModelResponse:
        try:
            import httpx
        except ImportError:
            return ModelResponse(
                text="",
                backend="ollama",
                model_name=self.model_name,
                route=request.route,
                warnings=["httpx not installed. Run: pip install -e '.[models]'"],
                raw_error="httpx not installed",
            )

        start = time.time()
        payload = {
            "model": self.model_name,
            "prompt": request.prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                data = resp.json()
                text = data.get("response", "")
                latency = (time.time() - start) * 1000
                return ModelResponse(
                    text=text,
                    backend="ollama",
                    model_name=self.model_name,
                    route=request.route,
                    latency_ms=latency,
                    token_estimate=self._estimate_tokens(text),
                )
        except Exception as exc:
            latency = (time.time() - start) * 1000
            return ModelResponse(
                text="",
                backend="ollama",
                model_name=self.model_name,
                route=request.route,
                latency_ms=latency,
                warnings=[f"Ollama call failed: {exc}"],
                raw_error=str(exc),
            )

    def health_check(self) -> ModelBackendInfo:
        try:
            import httpx
        except ImportError:
            return ModelBackendInfo(
                name="ollama",
                available=False,
                model_name=self.model_name,
                base_url=self.base_url,
                error="httpx not installed",
            )

        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                available = self.model_name in models or any(
                    self.model_name in m for m in models
                )
                return ModelBackendInfo(
                    name="ollama",
                    available=available,
                    model_name=self.model_name,
                    base_url=self.base_url,
                    error=None if available else f"Model {self.model_name} not found",
                )
        except Exception as exc:
            return ModelBackendInfo(
                name="ollama",
                available=False,
                model_name=self.model_name,
                base_url=self.base_url,
                error=str(exc),
            )


class OpenAICompatibleBackend(BaseModelBackend):
    """Backend for OpenAI-compatible endpoints (vLLM, SGLang, LiteLLM, NIM)."""

    name = "openai_compatible"

    def __init__(
        self,
        model_name: str = "",
        base_url: str = "http://localhost:8000/v1",
        timeout_seconds: int = 60,
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate(self, request: ModelRequest) -> ModelResponse:
        try:
            import httpx
        except ImportError:
            return ModelResponse(
                text="",
                backend="openai_compatible",
                model_name=self.model_name,
                route=request.route,
                warnings=["httpx not installed. Run: pip install -e '.[models]'"],
                raw_error="httpx not installed",
            )

        start = time.time()
        messages = [{"role": "user", "content": request.prompt}]
        payload: dict = {
            "model": self.model_name,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(f"{self.base_url}/chat/completions", json=payload)
                resp.raise_for_status()
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                latency = (time.time() - start) * 1000
                return ModelResponse(
                    text=text,
                    backend="openai_compatible",
                    model_name=self.model_name,
                    route=request.route,
                    latency_ms=latency,
                    token_estimate=self._estimate_tokens(text),
                )
        except Exception as exc:
            latency = (time.time() - start) * 1000
            return ModelResponse(
                text="",
                backend="openai_compatible",
                model_name=self.model_name,
                route=request.route,
                latency_ms=latency,
                warnings=[f"OpenAI-compatible call failed: {exc}"],
                raw_error=str(exc),
            )

    def health_check(self) -> ModelBackendInfo:
        try:
            import httpx
        except ImportError:
            return ModelBackendInfo(
                name="openai_compatible",
                available=False,
                model_name=self.model_name,
                base_url=self.base_url,
                error="httpx not installed",
            )

        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get(f"{self.base_url}/models")
                resp.raise_for_status()
                data = resp.json()
                models = [m["id"] for m in data.get("data", [])]
                available = self.model_name in models if self.model_name else bool(models)
                return ModelBackendInfo(
                    name="openai_compatible",
                    available=available,
                    model_name=self.model_name,
                    base_url=self.base_url,
                    error=None if available else f"Model {self.model_name} not found",
                )
        except Exception as exc:
            return ModelBackendInfo(
                name="openai_compatible",
                available=False,
                model_name=self.model_name,
                base_url=self.base_url,
                error=str(exc),
            )


def get_backend(backend_type: str, **kwargs: object) -> BaseModelBackend:
    """Factory to get a backend by type."""
    if backend_type == "deterministic":
        return DeterministicBackend()
    if backend_type == "ollama":
        return OllamaBackend(**kwargs)  # type: ignore[arg-type]
    if backend_type == "openai_compatible":
        return OpenAICompatibleBackend(**kwargs)  # type: ignore[arg-type]
    return DeterministicBackend()
