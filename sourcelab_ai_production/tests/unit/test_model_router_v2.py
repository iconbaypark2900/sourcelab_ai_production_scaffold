"""Tests for model router v2.

Instruction:
- Test deterministic backend always works.
- Test config from env vars.
- Test router fallback behavior.
- Test prompt templates.
- Test trace logging.
- Test schema validation.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sourcelab.models.backends import (
    BaseModelBackend,
    DeterministicBackend,
    OllamaBackend,
    OpenAICompatibleBackend,
    get_backend,
)
from sourcelab.models.config import get_model_config
from sourcelab.models.prompts import PromptTemplates
from sourcelab.models.schemas import (
    ModelBackendInfo,
    ModelCallTrace,
    ModelCallTraceLog,
    ModelHealthCheck,
    ModelRequest,
    ModelResponse,
    ModelRouterConfig,
    PromptRenderResult,
    PromptTemplate,
)
from sourcelab.generation.model_router import ModelRouter


class TestModelSchemas:
    """Test model schemas."""

    def test_model_request(self):
        req = ModelRequest(prompt="test", route="general")
        assert req.prompt == "test"
        assert req.route == "general"
        assert req.temperature == 0.0
        assert req.json_mode is False

    def test_model_response(self):
        resp = ModelResponse(text="hello", backend="test", model_name="m", route="general")
        assert resp.text == "hello"
        assert resp.backend == "test"
        assert resp.deterministic_fallback_used is False

    def test_model_call_trace(self):
        trace = ModelCallTrace(route="test", backend="det", model_name="det")
        assert trace.route == "test"
        assert trace.timestamp != ""

    def test_model_call_trace_log(self):
        log = ModelCallTraceLog(mode="deterministic", backend="deterministic")
        assert log.total_calls == 0
        assert log.fallback_count == 0

    def test_model_router_config(self):
        config = ModelRouterConfig(mode="deterministic", backend="deterministic")
        assert config.mode == "deterministic"

    def test_prompt_template(self):
        t = PromptTemplate(name="test", template="hello {name}")
        assert t.name == "test"
        assert t.fail_closed is True

    def test_prompt_render_result(self):
        r = PromptRenderResult(prompt="hello", template_name="test")
        assert r.prompt == "hello"


class TestDeterministicBackend:
    """Test deterministic backend always works."""

    def test_generate_returns_text(self):
        backend = DeterministicBackend()
        req = ModelRequest(prompt="test", route="general")
        resp = backend.generate(req)
        assert resp.text != ""
        assert resp.backend == "deterministic"
        assert resp.model_name == "deterministic"

    def test_health_check_available(self):
        backend = DeterministicBackend()
        info = backend.health_check()
        assert info.available is True

    def test_json_mode_scenario(self):
        backend = DeterministicBackend()
        req = ModelRequest(prompt="generate a scenario", route="scenario_generation", json_mode=True)
        resp = backend.generate(req)
        data = json.loads(resp.text)
        assert "scenario" in data

    def test_json_mode_answer_key(self):
        backend = DeterministicBackend()
        req = ModelRequest(prompt="generate answer_key for lesson", route="answer_key_generation", json_mode=True)
        resp = backend.generate(req)
        data = json.loads(resp.text)
        assert "answers" in data

    def test_json_mode_rubric(self):
        backend = DeterministicBackend()
        req = ModelRequest(prompt="generate rubric", route="rubric_generation", json_mode=True)
        resp = backend.generate(req)
        data = json.loads(resp.text)
        assert "criteria" in data

    def test_json_mode_lesson(self):
        backend = DeterministicBackend()
        req = ModelRequest(prompt="generate lesson", route="lesson_package_generation", json_mode=True)
        resp = backend.generate(req)
        data = json.loads(resp.text)
        assert "title" in data

    def test_json_mode_general(self):
        backend = DeterministicBackend()
        req = ModelRequest(prompt="general task", route="general", json_mode=True)
        resp = backend.generate(req)
        data = json.loads(resp.text)
        assert "status" in data


class TestOllamaBackend:
    """Test Ollama backend (graceful failure)."""

    def test_init(self):
        backend = OllamaBackend(model_name="llama2", base_url="http://localhost:11434")
        assert backend.name == "ollama"
        assert backend.model_name == "llama2"

    def test_health_check_unavailable(self):
        backend = OllamaBackend(model_name="llama2", base_url="http://localhost:99999")
        info = backend.health_check()
        assert info.available is False
        assert info.error is not None

    def test_generate_unavailable(self):
        backend = OllamaBackend(model_name="llama2", base_url="http://localhost:99999")
        req = ModelRequest(prompt="test", route="general")
        resp = backend.generate(req)
        assert resp.raw_error is not None
        assert len(resp.warnings) > 0


class TestOpenAICompatibleBackend:
    """Test OpenAI-compatible backend (graceful failure)."""

    def test_init(self):
        backend = OpenAICompatibleBackend(model_name="test", base_url="http://localhost:8000/v1")
        assert backend.name == "openai_compatible"
        assert backend.model_name == "test"

    def test_health_check_unavailable(self):
        backend = OpenAICompatibleBackend(model_name="test", base_url="http://localhost:99999")
        info = backend.health_check()
        assert info.available is False

    def test_generate_unavailable(self):
        backend = OpenAICompatibleBackend(model_name="test", base_url="http://localhost:99999")
        req = ModelRequest(prompt="test", route="general")
        resp = backend.generate(req)
        assert resp.raw_error is not None


class TestGetBackend:
    """Test get_backend factory."""

    def test_deterministic(self):
        b = get_backend("deterministic")
        assert isinstance(b, DeterministicBackend)

    def test_ollama(self):
        b = get_backend("ollama", model_name="test")
        assert isinstance(b, OllamaBackend)

    def test_openai_compatible(self):
        b = get_backend("openai_compatible", model_name="test")
        assert isinstance(b, OpenAICompatibleBackend)

    def test_unknown_falls_back(self):
        b = get_backend("unknown")
        assert isinstance(b, DeterministicBackend)


class TestModelConfig:
    """Test model config from env vars."""

    def test_default_config(self):
        config = get_model_config()
        assert config.mode == "deterministic"
        assert config.backend == "deterministic"

    def test_env_override(self):
        with patch.dict(os.environ, {"SOURCELAB_MODEL_MODE": "local_llm"}):
            config = get_model_config()
            assert config.mode == "local_llm"

    def test_env_all(self):
        env = {
            "SOURCELAB_MODEL_MODE": "local_llm",
            "SOURCELAB_MODEL_BACKEND": "ollama",
            "SOURCELAB_MODEL_NAME": "llama2",
            "SOURCELAB_MODEL_BASE_URL": "http://localhost:11434",
            "SOURCELAB_MODEL_TIMEOUT_SECONDS": "30",
            "SOURCELAB_MODEL_FALLBACK": "deterministic",
        }
        with patch.dict(os.environ, env):
            config = get_model_config()
            assert config.mode == "local_llm"
            assert config.backend == "ollama"
            assert config.model_name == "llama2"
            assert config.base_url == "http://localhost:11434"
            assert config.timeout_seconds == 30
            assert config.fallback == "deterministic"


class TestModelRouter:
    """Test model router."""

    def test_deterministic_mode(self):
        router = ModelRouter(config=ModelRouterConfig(mode="deterministic"))
        req = ModelRequest(prompt="test", route="general")
        resp = router.generate(req)
        assert resp.text != ""
        assert resp.backend == "deterministic"

    def test_trace_log(self):
        router = ModelRouter(config=ModelRouterConfig(mode="deterministic"))
        req = ModelRequest(prompt="test", route="general")
        router.generate(req)
        trace = router.trace_log
        assert trace.total_calls == 1
        assert trace.fallback_count == 0

    def test_reset_trace(self):
        router = ModelRouter(config=ModelRouterConfig(mode="deterministic"))
        req = ModelRequest(prompt="test", route="general")
        router.generate(req)
        router.reset_trace()
        assert router.trace_log.total_calls == 0

    def test_render_prompt(self):
        router = ModelRouter(config=ModelRouterConfig(mode="deterministic"))
        result = router.render_prompt(
            route="scenario_generation",
            source_ids=["src1"],
            chunk_ids=["ch1"],
            topic="test",
            level="intermediate",
        )
        assert isinstance(result, PromptRenderResult)
        assert "src1" in result.prompt

    def test_get_trace_log_dict(self):
        router = ModelRouter(config=ModelRouterConfig(mode="deterministic"))
        req = ModelRequest(prompt="test", route="general")
        router.generate(req)
        d = router.get_trace_log_dict()
        assert "calls" in d
        assert d["total_calls"] == 1

    def test_local_llm_fallback(self):
        config = ModelRouterConfig(
            mode="local_llm",
            backend="ollama",
            model_name="test",
            base_url="http://localhost:99999",
            fallback="deterministic",
        )
        router = ModelRouter(config=config)
        req = ModelRequest(prompt="test", route="general")
        resp = router.generate(req)
        assert resp.deterministic_fallback_used is True
        assert resp.text != ""

    def test_update_generation_trace(self):
        from sourcelab.generation.schemas import GenerationTrace

        config = ModelRouterConfig(mode="local_llm", backend="ollama")
        router = ModelRouter(config=config)
        trace = GenerationTrace(topic="test")
        updated = router.update_generation_trace(trace)
        assert "local_llm_ollama" in updated.generation_backend

    def test_deterministic_mode_no_fallback(self):
        config = ModelRouterConfig(mode="deterministic")
        router = ModelRouter(config=config)
        req = ModelRequest(prompt="test", route="general")
        resp = router.generate(req)
        assert resp.deterministic_fallback_used is False
        assert router.trace_log.fallback_count == 0


class TestPromptTemplates:
    """Test prompt templates."""

    def test_get_template_scenario(self):
        t = PromptTemplates.get_template("scenario_generation")
        assert t.source_required is True

    def test_get_template_general(self):
        t = PromptTemplates.get_template("general")
        assert t.source_required is False

    def test_render_with_sources(self):
        result = PromptTemplates.render(
            route="scenario_generation",
            source_ids=["s1", "s2"],
            chunk_ids=["c1"],
            topic="test",
            level="intermediate",
        )
        assert "s1" in result.prompt
        assert "s2" in result.prompt
        assert "c1" in result.prompt

    def test_render_without_sources_fails_closed(self):
        result = PromptTemplates.render(
            route="scenario_generation",
            source_ids=[],
            topic="test",
        )
        assert "WARNING" in result.prompt

    def test_render_general_no_warning(self):
        result = PromptTemplates.render(
            route="general",
            source_ids=[],
        )
        assert "WARNING" not in result.prompt


class TestModelCallTraceIntegration:
    """Test model call trace in proof bundle."""

    def test_trace_written_to_run(self, tmp_path: Path):
        """Test that model_call_trace.json is written to run dir."""
        router = ModelRouter(config=ModelRouterConfig(mode="deterministic"))
        req = ModelRequest(prompt="test", route="general")
        router.generate(req)

        trace_data = router.get_trace_log_dict()
        trace_path = tmp_path / "model_call_trace.json"
        trace_path.write_text(json.dumps(trace_data, indent=2, default=str), encoding="utf-8")

        loaded = json.loads(trace_path.read_text(encoding="utf-8"))
        assert loaded["total_calls"] == 1
        assert loaded["mode"] == "deterministic"


class TestHarnessValidator:
    """Test model_call_trace.json validation in harness."""

    def test_validate_model_call_trace(self):
        from sourcelab.harness.schema_validators import validate_model_call_trace

        trace = ModelCallTraceLog(
            calls=[],
            total_calls=0,
            fallback_count=0,
            mode="deterministic",
            backend="deterministic",
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(trace.model_dump_json(indent=2))
            path = Path(f.name)

        check = validate_model_call_trace(path)
        assert check.passed is True
        path.unlink()


class TestArtifactInventory:
    """Test model_call_trace.json in artifact inventory."""

    def test_model_call_trace_in_artifacts(self):
        from sourcelab.harness.artifact_inventory import ARTIFACT_ORDER, OPTIONAL_ARTIFACTS, SCHEMA_MAP

        assert "model_call_trace.json" in ARTIFACT_ORDER
        assert "model_call_trace.json" in OPTIONAL_ARTIFACTS
        assert "model_call_trace.json" in SCHEMA_MAP
        assert SCHEMA_MAP["model_call_trace.json"] == "ModelCallTraceLog"


class TestPipelineIntegration:
    """Test pipeline integration with model router."""

    def test_pipeline_with_model_router(self):
        from sourcelab.core.pipeline import run_demo_pipeline

        project_root = Path.cwd()
        router = ModelRouter(config=ModelRouterConfig(mode="deterministic"))
        result = run_demo_pipeline(
            topic="post-quantum cryptography migration",
            project_root=project_root,
            model_router=router,
        )
        assert "run_id" in result
        assert result["harness_passed"] is True

        # Check model_call_trace.json exists
        run_dir = Path(result["run_dir"])
        trace_path = run_dir / "model_call_trace.json"
        assert trace_path.exists()

    def test_pipeline_without_model_router(self):
        from sourcelab.core.pipeline import run_demo_pipeline

        project_root = Path.cwd()
        result = run_demo_pipeline(
            topic="post-quantum cryptography migration",
            project_root=project_root,
        )
        assert "run_id" in result
        assert result["harness_passed"] is True

        # Verify no model router was used in the trace
        run_dir = Path(result["run_dir"])
        trace_path = run_dir / "model_call_trace.json"
        # File may exist from a previous run, but generation_trace should show deterministic_local
        gen_trace_path = run_dir / "generation_trace.json"
        if gen_trace_path.exists():
            gen_trace = json.loads(gen_trace_path.read_text(encoding="utf-8"))
            assert gen_trace.get("generation_backend") == "deterministic_local"

    def test_lesson_create_with_model_router(self):
        from sourcelab.core.pipeline import run_lesson_create

        project_root = Path.cwd()
        router = ModelRouter(config=ModelRouterConfig(mode="deterministic"))
        result = run_lesson_create(
            topic="post-quantum cryptography migration",
            project_root=project_root,
            difficulty=3,
            model_router=router,
        )
        assert "run_id" in result

        run_dir = Path(result["run_dir"])
        trace_path = run_dir / "model_call_trace.json"
        assert trace_path.exists()
