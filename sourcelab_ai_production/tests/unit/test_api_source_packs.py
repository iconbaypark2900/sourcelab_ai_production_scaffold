"""Unit tests for source pack and eval API schemas and services.

These tests validate the new Pydantic models and service functions for
source packs and golden evaluations.
Run with: pytest tests/unit/test_api_source_packs.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sourcelab.api.schemas import (
    SourcePackInfo,
    SourcePackListResponse,
    SourcePackValidationResponse,
    SourcePackInstallRequest,
    SourcePackInstallResponse,
    SourcePackStatusResponse,
    EvalsRunRequest,
    EvalsRunResponse,
    EvalsLatestResponse,
    EvalsHistoryEntry,
    EvalsHistoryResponse,
    GoldenEvalSummaryResponse,
)


class TestSourcePackSchemas:
    """Test source pack API schemas."""

    def test_source_pack_info(self):
        info = SourcePackInfo(
            pack_name="pqc_v1",
            version="1.0.0",
            title="PQC Pack",
            description="Post-quantum cryptography pack",
            source_count=7,
            eval_count=4,
        )
        assert info.pack_name == "pqc_v1"
        assert info.source_count == 7

    def test_source_pack_list_response(self):
        response = SourcePackListResponse(
            packs=[
                SourcePackInfo(pack_name="pqc_v1", source_count=7),
            ],
            total=1,
        )
        assert response.total == 1
        assert len(response.packs) == 1

    def test_source_pack_validation_response(self):
        response = SourcePackValidationResponse(
            valid=True,
            errors=[],
            warnings=[],
        )
        assert response.valid is True

    def test_source_pack_install_request(self):
        request = SourcePackInstallRequest(pack_name="pqc_v1")
        assert request.pack_name == "pqc_v1"

    def test_source_pack_install_response(self):
        response = SourcePackInstallResponse(
            success=True,
            pack_name="pqc_v1",
            installed=7,
            skipped=0,
            total_sources=7,
            installed_sources=["src1", "src2"],
        )
        assert response.success is True
        assert response.installed == 7

    def test_source_pack_install_response_error(self):
        response = SourcePackInstallResponse(
            success=False,
            error="Pack not found",
        )
        assert response.success is False
        assert response.error == "Pack not found"

    def test_source_pack_status_response(self):
        response = SourcePackStatusResponse(
            installed=True,
            pack_name="pqc_v1",
            version="1.0.0",
            total_sources=7,
            installed_count=7,
        )
        assert response.installed is True
        assert response.installed_count == 7


class TestEvalSchemas:
    """Test eval API schemas."""

    def test_evals_run_request(self):
        request = EvalsRunRequest(pack_name="pqc_v1")
        assert request.pack_name == "pqc_v1"
        assert request.eval_type is None

    def test_evals_run_request_with_type(self):
        request = EvalsRunRequest(pack_name="pqc_v1", eval_type="retrieval")
        assert request.eval_type == "retrieval"

    def test_golden_eval_summary_response(self):
        summary = GoldenEvalSummaryResponse(
            pack_name="pqc_v1",
            total_evals=4,
            total_cases=45,
            total_passed=40,
            total_failed=5,
            overall_pass_rate=0.8889,
        )
        assert summary.overall_pass_rate == 0.8889

    def test_evals_run_response(self):
        response = EvalsRunResponse(
            status="ok",
            pack_name="pqc_v1",
            summary=GoldenEvalSummaryResponse(
                pack_name="pqc_v1",
                total_evals=4,
                total_cases=45,
                total_passed=40,
                total_failed=5,
                overall_pass_rate=0.8889,
            ),
        )
        assert response.status == "ok"
        assert response.summary is not None

    def test_evals_latest_response(self):
        response = EvalsLatestResponse(
            pack_name="pqc_v1",
            summary={"overall_pass_rate": 0.8889},
            markdown="# Eval Results\nPassed: 40/45",
        )
        assert response.pack_name == "pqc_v1"
        assert "markdown" in response.model_dump()


class TestSourcePackServices:
    """Test source pack service functions."""

    def test_list_source_packs_api(self):
        from sourcelab.api.services import list_source_packs_api
        result = list_source_packs_api()
        assert "packs" in result
        assert "total" in result
        assert result["total"] >= 1

    def test_validate_source_pack_api(self):
        from sourcelab.api.services import validate_source_pack_api
        result = validate_source_pack_api("pqc_v1")
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_install_source_pack_api(self):
        from sourcelab.api.services import install_source_pack_api
        result = install_source_pack_api("pqc_v1")
        assert result["success"] is True
        total = result["installed"] + result["skipped"]
        assert total == 7

    def test_source_pack_status_api(self):
        from sourcelab.api.services import source_pack_status_api
        result = source_pack_status_api("pqc_v1")
        assert "installed" in result
        assert result["pack_name"] == "pqc_v1"


class TestEvalServices:
    """Test eval service functions."""

    def test_evals_latest_api(self):
        from sourcelab.api.services import evals_latest_api
        result = evals_latest_api("pqc_v1")
        assert result["pack_name"] == "pqc_v1"
        assert "summary" in result
        assert "markdown" in result


class TestEvalsHistorySchemas:
    """Test eval history Pydantic schemas."""

    def test_history_entry_defaults(self):
        entry = EvalsHistoryEntry(snapshot_at="2026-06-24T00:00:00+00:00")
        assert entry.snapshot_at == "2026-06-24T00:00:00+00:00"
        assert entry.pack_name is None
        assert entry.total_cases is None
        assert entry.overall_pass_rate is None

    def test_history_response_empty(self):
        response = EvalsHistoryResponse(pack_name="pqc_v1")
        assert response.pack_name == "pqc_v1"
        assert response.history == []
        assert response.latest_pass_rate is None
        assert response.previous_pass_rate is None
        assert response.pass_rate_delta is None
        assert response.run_count == 0

    def test_history_response_with_entries(self):
        response = EvalsHistoryResponse(
            pack_name="pqc_v1",
            history=[
                EvalsHistoryEntry(
                    snapshot_at="2026-06-24T00:00:00+00:00",
                    overall_pass_rate=1.0,
                    total_cases=12,
                ),
                EvalsHistoryEntry(
                    snapshot_at="2026-06-23T00:00:00+00:00",
                    overall_pass_rate=0.9,
                    total_cases=12,
                ),
            ],
            latest_pass_rate=1.0,
            previous_pass_rate=0.9,
            pass_rate_delta=0.1,
            run_count=2,
        )
        assert response.run_count == 2
        assert response.latest_pass_rate == 1.0
        assert response.previous_pass_rate == 0.9
        assert response.pass_rate_delta == 0.1


class TestEvalsHistoryService:
    """Test the evals_history_api service function."""

    def test_returns_empty_history_for_unknown_pack(self, tmp_path: Path):
        from sourcelab.api.services import evals_history_api
        from sourcelab.api.config import APIConfig

        # Override config to use a temp project root with no evals
        original = APIConfig.from_env
        try:
            APIConfig.from_env = classmethod(lambda cls: APIConfig(project_root=tmp_path))
            result = evals_history_api("nonexistent_pack_v1")
        finally:
            APIConfig.from_env = original

        assert result["pack_name"] == "nonexistent_pack_v1"
        assert result["history"] == []
        assert result["latest_pass_rate"] is None
        assert result["previous_pass_rate"] is None
        assert result["pass_rate_delta"] is None
        assert result["run_count"] == 0

    def test_reads_snapshot_history_and_computes_delta(self, tmp_path: Path):
        from sourcelab.api.services import evals_history_api
        from sourcelab.api.config import APIConfig

        # Create fake history directory with two snapshots
        history_dir = tmp_path / "artifacts" / "evals" / "ml_safety_v1" / "history"
        history_dir.mkdir(parents=True)

        snapshot_old = {
            "snapshot_at": "2026-06-23T12:00:00+00:00",
            "pack_name": "ml_safety_v1",
            "total_evals": 4,
            "total_cases": 12,
            "total_passed": 10,
            "total_failed": 2,
            "overall_pass_rate": 0.8333,
        }
        snapshot_new = {
            "snapshot_at": "2026-06-24T12:00:00+00:00",
            "pack_name": "ml_safety_v1",
            "total_evals": 4,
            "total_cases": 12,
            "total_passed": 12,
            "total_failed": 0,
            "overall_pass_rate": 1.0,
        }
        (history_dir / "20260623T120000Z.json").write_text(
            json.dumps(snapshot_old), encoding="utf-8"
        )
        (history_dir / "20260624T120000Z.json").write_text(
            json.dumps(snapshot_new), encoding="utf-8"
        )

        original = APIConfig.from_env
        try:
            APIConfig.from_env = classmethod(lambda cls: APIConfig(project_root=tmp_path))
            result = evals_history_api("ml_safety_v1")
        finally:
            APIConfig.from_env = original

        assert result["pack_name"] == "ml_safety_v1"
        assert result["run_count"] == 2
        # Newest first
        assert result["history"][0]["overall_pass_rate"] == 1.0
        assert result["history"][1]["overall_pass_rate"] == 0.8333
        assert result["latest_pass_rate"] == 1.0
        assert result["previous_pass_rate"] == 0.8333
        assert abs(result["pass_rate_delta"] - 0.1667) < 0.001

    def test_respects_limit(self, tmp_path: Path):
        from sourcelab.api.services import evals_history_api
        from sourcelab.api.config import APIConfig

        history_dir = tmp_path / "artifacts" / "evals" / "ml_safety_v1" / "history"
        history_dir.mkdir(parents=True)

        for i in range(5):
            payload = {
                "snapshot_at": f"2026-06-2{i}T12:00:00+00:00",
                "overall_pass_rate": 1.0 - i * 0.1,
            }
            (history_dir / f"2026062{i}T120000Z.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )

        original = APIConfig.from_env
        try:
            APIConfig.from_env = classmethod(lambda cls: APIConfig(project_root=tmp_path))
            result = evals_history_api("ml_safety_v1", limit=3)
        finally:
            APIConfig.from_env = original

        assert result["run_count"] == 3
        # Newest first
        assert result["history"][0]["overall_pass_rate"] == 0.6
        assert result["history"][2]["overall_pass_rate"] == 0.8

    def test_skips_invalid_history_files(self, tmp_path: Path):
        from sourcelab.api.services import evals_history_api
        from sourcelab.api.config import APIConfig

        history_dir = tmp_path / "artifacts" / "evals" / "ml_safety_v1" / "history"
        history_dir.mkdir(parents=True)

        (history_dir / "20260624T120000Z.json").write_text(
            "not valid json", encoding="utf-8"
        )
        (history_dir / "20260623T120000Z.json").write_text(
            json.dumps({"snapshot_at": "2026-06-23", "overall_pass_rate": 0.5}),
            encoding="utf-8",
        )

        original = APIConfig.from_env
        try:
            APIConfig.from_env = classmethod(lambda cls: APIConfig(project_root=tmp_path))
            result = evals_history_api("ml_safety_v1")
        finally:
            APIConfig.from_env = original

        # Invalid file is skipped
        assert result["run_count"] == 1
        assert result["history"][0]["overall_pass_rate"] == 0.5

    def test_single_snapshot_has_no_delta(self, tmp_path: Path):
        from sourcelab.api.services import evals_history_api
        from sourcelab.api.config import APIConfig

        history_dir = tmp_path / "artifacts" / "evals" / "ml_safety_v1" / "history"
        history_dir.mkdir(parents=True)
        (history_dir / "20260624T120000Z.json").write_text(
            json.dumps({"snapshot_at": "2026-06-24", "overall_pass_rate": 0.8}),
            encoding="utf-8",
        )

        original = APIConfig.from_env
        try:
            APIConfig.from_env = classmethod(lambda cls: APIConfig(project_root=tmp_path))
            result = evals_history_api("ml_safety_v1")
        finally:
            APIConfig.from_env = original

        assert result["run_count"] == 1
        assert result["latest_pass_rate"] == 0.8
        assert result["previous_pass_rate"] is None
        assert result["pass_rate_delta"] is None


class TestEvalHistoryRoute:
    """Test the /evals/history/{pack_name} HTTP route."""

    def test_history_route_registered(self):
        from sourcelab.api.main import app
        from fastapi.routing import APIRoute

        # The evals router is included with prefix "/evals", so the history
        # route inside the router is at "/history/{pack_name}". Walk through
        # included routers to find it.
        def _walk_routes(routes):
            for r in routes:
                if isinstance(r, APIRoute):
                    yield r
                original = getattr(r, "original_router", None)
                if original is not None and hasattr(original, "routes"):
                    yield from _walk_routes(original.routes)

        all_routes = list(_walk_routes(app.routes))
        history_routes = [r for r in all_routes if r.path == "/history/{pack_name}"]
        assert len(history_routes) == 1
        assert "GET" in history_routes[0].methods

    def test_history_endpoint_via_test_client(self):
        from fastapi.testclient import TestClient
        from sourcelab.api.main import app

        client = TestClient(app)
        response = client.get("/evals/history/ml_safety_v1")
        assert response.status_code == 200
        body = response.json()
        assert body["pack_name"] == "ml_safety_v1"
        assert "history" in body
        assert "run_count" in body
