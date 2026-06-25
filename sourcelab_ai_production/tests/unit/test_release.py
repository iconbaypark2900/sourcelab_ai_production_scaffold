"""Tests for release manifest and checklist modules."""

from __future__ import annotations

import json
from pathlib import Path

from sourcelab.release.config import ReleaseThresholds, get_default_thresholds
from sourcelab.release.schemas import ReleaseManifest
from sourcelab.release.manifest import build_release_manifest
from sourcelab.release.checklist import run_release_checklist
from sourcelab.version import __version__


class TestReleaseThresholds:
    """Tests for ReleaseThresholds."""

    def test_default_thresholds(self):
        """Default thresholds are reasonable."""
        t = get_default_thresholds()
        assert 0.0 <= t.retrieval_min_pass_rate <= 1.0
        assert 0.0 <= t.golden_eval_min_pass_rate <= 1.0
        assert 0.0 <= t.citation_resolution_required <= 1.0
        assert t.unsupported_high_risk_allowed >= 0

    def test_custom_thresholds(self):
        """Custom thresholds can be set."""
        t = ReleaseThresholds(
            retrieval_min_pass_rate=0.9,
            golden_eval_min_pass_rate=0.9,
            citation_resolution_required=1.0,
            unsupported_high_risk_allowed=0,
        )
        assert t.retrieval_min_pass_rate == 0.9
        assert t.golden_eval_min_pass_rate == 0.9

    def test_to_dict(self):
        """Thresholds can be converted to dict."""
        t = get_default_thresholds()
        d = t.to_dict()
        assert "retrieval_min_pass_rate" in d
        assert "golden_eval_min_pass_rate" in d


class TestReleaseManifestSchemas:
    """Tests for Pydantic release manifest schemas."""

    def test_manifest_creation(self):
        """ReleaseManifest can be created with required fields."""
        manifest = ReleaseManifest(
            version="1.0.0",
        )
        assert manifest.version == "1.0.0"
        assert manifest.project_name == "SourceLab AI"
        assert manifest.pytest_status == ""
        assert manifest.strict_release_status == "unknown"

    def test_manifest_json_roundtrip(self):
        """Manifest can be serialized to JSON and back."""
        manifest = ReleaseManifest(
            version="1.0.0",
            strict_release_status="PASS",
        )
        data = manifest.model_dump()
        assert data["version"] == "1.0.0"
        assert data["strict_release_status"] == "PASS"


class TestBuildReleaseManifest:
    """Tests for build_release_manifest."""

    def test_build_manifest_returns_model(self, tmp_path: Path):
        """build_release_manifest returns a ReleaseManifest."""
        manifest = build_release_manifest(tmp_path)
        assert isinstance(manifest, ReleaseManifest)
        assert manifest.version == __version__
        assert manifest.project_name == "SourceLab AI"

    def test_build_manifest_checks_files(self, tmp_path: Path):
        """build_release_manifest checks for various files."""
        manifest = build_release_manifest(tmp_path)
        # Without any files, most things should be missing
        assert manifest.pytest_status == ""
        assert manifest.pqc_pack_installed is False

    def test_build_manifest_with_test_results(self, tmp_path: Path):
        """build_release_manifest reads test results."""
        # Create a minimal source registry for validation
        data_dir = tmp_path / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        registry_file = data_dir / "source_registry.json"
        registry_file.write_text(json.dumps({
            "version": 1,
            "generated_at": "2024-01-01T00:00:00Z",
            "sources": [],
        }), encoding="utf-8")

        manifest = build_release_manifest(tmp_path)
        # The manifest should be buildable without errors
        assert manifest.version == __version__


class TestRunReleaseChecklist:
    """Tests for run_release_checklist."""

    def test_checklist_returns_dict(self, tmp_path: Path):
        """run_release_checklist returns a dict."""
        result = run_release_checklist(tmp_path)
        assert isinstance(result, dict)
        assert "status" in result
        assert "checks" in result
        assert "blocking" in result
        assert "warnings" in result

    def test_checklist_has_all_checks(self, tmp_path: Path):
        """run_release_checklist includes all expected checks."""
        result = run_release_checklist(tmp_path)
        check_names = [c["name"] for c in result["checks"]]
        assert "tests_exist" in check_names
        assert "pqc_pack_installed" in check_names
        assert "source_validation" in check_names
        assert "retrieval_eval" in check_names
        assert "golden_evals" in check_names
        assert "latest_proof_bundle" in check_names
        assert "harness_passed" in check_names
        assert "citation_resolution" in check_names
        assert "high_risk_claims" in check_names
        assert "model_call_trace" in check_names
        assert "ui_commands" in check_names
        assert "api_routes" in check_names

    def test_checklist_missing_files(self, tmp_path: Path):
        """Checklist reports missing when files not present."""
        result = run_release_checklist(tmp_path)
        for check in result["checks"]:
            if check["name"] in ("latest_proof_bundle", "harness_passed"):
                # These require files to exist
                assert check["passed"] is False or check.get("severity") == "warning"
