"""Tests for Local v1.1 distribution hardening."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from sourcelab.cli import build_parser, cmd_release_attest, cmd_release_sbom
from sourcelab.doctor import run_doctor
from sourcelab.release.artifact_names import ATTESTATION_FILENAME, SBOM_FILENAME
from sourcelab.release.attest import write_release_attestation
from sourcelab.release.bundle import (
    BUNDLE_DIR_NAME,
    BUNDLE_DIR_NAME_LEGACY,
    build_release_bundle,
    get_release_bundle_status,
)
from sourcelab.release.checksums import write_release_checksums
from sourcelab.release.sbom import write_release_sbom
from sourcelab.sources.source_pack import validate_source_pack


def _run_json_cmd(func, args) -> dict:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        func(args)
    return json.loads(buffer.getvalue().strip())


def _seed_minimal_project(tmp_path: Path) -> None:
    release_dir = tmp_path / "artifacts" / "release"
    release_dir.mkdir(parents=True)
    (release_dir / "local_v1_release_manifest.json").write_text(
        json.dumps(
            {
                "strict_release_status": "PASS",
                "golden_eval_pass_rate": 1.0,
                "test_count": 10,
            }
        ),
        encoding="utf-8",
    )
    (release_dir / "local_v1_release_report.md").write_text("# Report", encoding="utf-8")
    (tmp_path / "README.md").write_text("# README", encoding="utf-8")
    (tmp_path / "RELEASE_NOTES_LOCAL_V1_GA.md").write_text("# GA", encoding="utf-8")
    (tmp_path / "RELEASE_NOTES_LOCAL_V1_RC.md").write_text("# RC", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("# Changelog", encoding="utf-8")
    demo_dir = tmp_path / "docs" / "demo"
    demo_dir.mkdir(parents=True)
    (demo_dir / "LOCAL_V1_WALKTHROUGH.md").write_text("# Walkthrough", encoding="utf-8")


class TestGABundleNaming:
    def test_primary_bundle_name_is_ga(self):
        assert BUNDLE_DIR_NAME == "sourcelab_local_v1_ga_bundle"
        assert BUNDLE_DIR_NAME_LEGACY == "sourcelab_local_v1_rc_bundle"

    def test_build_bundle_uses_ga_paths(self, tmp_path: Path):
        _seed_minimal_project(tmp_path)
        result = build_release_bundle(tmp_path)
        bundle_dir = tmp_path / "artifacts" / "release" / BUNDLE_DIR_NAME
        bundle_zip = tmp_path / "artifacts" / "release" / f"{BUNDLE_DIR_NAME}.zip"

        assert bundle_dir.is_dir()
        assert bundle_zip.is_file()
        assert BUNDLE_DIR_NAME in result["bundle_dir"]
        assert result["bundle_zip"].endswith(f"{BUNDLE_DIR_NAME}.zip")

    def test_legacy_bundle_detected_with_migration_warning(self, tmp_path: Path):
        release_dir = tmp_path / "artifacts" / "release"
        legacy_dir = release_dir / BUNDLE_DIR_NAME_LEGACY
        legacy_dir.mkdir(parents=True)
        (legacy_dir / "sample.txt").write_text("legacy", encoding="utf-8")

        status = get_release_bundle_status(tmp_path)
        assert status["status"] == "legacy"
        assert "migration_warning" in status
        assert BUNDLE_DIR_NAME_LEGACY in status["migration_warning"]


class TestReleaseChecksumsExtended:
    def test_checksums_includes_ga_zip_and_manifest(self, tmp_path: Path):
        _seed_minimal_project(tmp_path)
        build_release_bundle(tmp_path)
        write_release_sbom(tmp_path)
        write_release_attestation(tmp_path)

        result = write_release_checksums(tmp_path)
        content = (tmp_path / "artifacts" / "release" / "SHA256SUMS").read_text(encoding="utf-8")

        assert result["entry_count"] >= 3
        assert f"{BUNDLE_DIR_NAME}.zip" in content
        assert "local_v1_release_manifest.json" in content
        assert SBOM_FILENAME in content
        assert ATTESTATION_FILENAME in content


class TestReleaseSBOM:
    def test_sbom_writes_json(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = write_release_sbom(tmp_path)
        sbom_path = tmp_path / "artifacts" / "release" / SBOM_FILENAME

        assert result["status"] == "ok"
        assert sbom_path.is_file()
        data = json.loads(sbom_path.read_text(encoding="utf-8"))
        assert data["source"] == "python environment"
        assert "generated_at" in data
        assert "project_version" in data
        assert "packages" in data

    def test_sbom_cli_command(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        args = build_parser().parse_args(["release", "sbom"])
        data = _run_json_cmd(cmd_release_sbom, args)
        assert data["status"] == "ok"
        assert Path(data["sbom_path"]).exists()


class TestReleaseAttestation:
    def test_attest_writes_unsigned_json(self, tmp_path: Path):
        _seed_minimal_project(tmp_path)
        build_release_bundle(tmp_path)
        result = write_release_attestation(tmp_path)
        attestation_path = tmp_path / "artifacts" / "release" / ATTESTATION_FILENAME

        assert result["status"] == "ok"
        assert attestation_path.is_file()
        data = json.loads(attestation_path.read_text(encoding="utf-8"))
        assert data["unsigned"] is True
        assert data["strict_release_status"] == "PASS"
        assert data["golden_eval_pass_rate"] == 1.0
        assert data["bundle_sha256"] is not None

    def test_attest_cli_command(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _seed_minimal_project(tmp_path)
        build_release_bundle(tmp_path)
        args = build_parser().parse_args(["release", "attest"])
        data = _run_json_cmd(cmd_release_attest, args)
        assert data["status"] == "ok"
        assert data["unsigned"] is True


class TestDoctorDependencyLock:
    def test_doctor_reports_dependency_lock_fields(self, tmp_path: Path):
        lock_path = tmp_path / "requirements" / "lock-local-v1.txt"
        lock_path.parent.mkdir(parents=True)
        lock_path.write_text("# lock\npytest==8.0.0\n", encoding="utf-8")

        report = run_doctor(tmp_path)
        assert report["dependency_lock_exists"] is True
        assert report["dependency_lock_path"] == str(lock_path)
        check_names = {c["name"] for c in report["checks"]}
        assert "dependency_lock" in check_names

    def test_doctor_missing_lock(self, tmp_path: Path):
        report = run_doctor(tmp_path)
        assert report["dependency_lock_exists"] is False
        assert report["dependency_lock_path"].endswith("requirements/lock-local-v1.txt")


class TestMakefileFreeze:
    def test_makefile_contains_freeze_target(self):
        makefile = Path.cwd() / "Makefile"
        content = makefile.read_text(encoding="utf-8")
        assert "freeze:" in content
        assert "freeze_requirements.sh" in content


class TestCIWorkflow:
    def test_local_v1_release_workflow_exists(self):
        workflow = Path.cwd() / ".github" / "workflows" / "local-v1-release.yml"
        assert workflow.is_file()
        content = workflow.read_text(encoding="utf-8")
        assert "verify-release --strict" in content
        assert "release bundle" in content
        assert "release sbom" in content
        assert "release attest" in content
        assert "upload-artifact" in content


class TestDashboardComposeProfile:
    def test_dashboard_profile_in_compose(self):
        compose = Path.cwd() / "docker-compose.yml"
        content = compose.read_text(encoding="utf-8")
        assert "sourcelab-dashboard:" in content
        assert "profiles:" in content
        assert "dashboard" in content


class TestSourcePackTemplate:
    def test_template_validates_structurally(self):
        project_root = Path.cwd()
        result = validate_source_pack(project_root, "TEMPLATE")
        assert result["valid"] is True
        assert result["errors"] == []

    def test_source_pack_creation_docs_exist(self):
        doc = Path.cwd() / "docs" / "source_packs" / "CREATING_SOURCE_PACKS.md"
        assert doc.is_file()
        text = doc.read_text(encoding="utf-8")
        assert "pqc_v1" in text
        assert "TEMPLATE" in text
