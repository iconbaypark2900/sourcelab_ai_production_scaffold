"""Tests for GA release bundle, checksums, doctor, and process docs."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from sourcelab.cli import build_parser, cmd_doctor, cmd_release_bundle, cmd_release_checksums
from sourcelab.doctor import run_doctor
from sourcelab.release.bundle import BUNDLE_DIR_NAME, build_release_bundle, get_release_bundle_status
from sourcelab.release.checksums import write_release_checksums
from sourcelab.ui.release_dashboard import load_release_dashboard_summary
from sourcelab.version import __version__


def _run_json_cmd(func, args) -> dict:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        func(args)
    return json.loads(buffer.getvalue().strip())


def _seed_minimal_project(tmp_path: Path) -> None:
    release_dir = tmp_path / "artifacts" / "release"
    release_dir.mkdir(parents=True)
    (release_dir / "local_v1_release_manifest.json").write_text("{}", encoding="utf-8")
    (release_dir / "local_v1_release_report.md").write_text("# Report", encoding="utf-8")
    (tmp_path / "README.md").write_text("# README", encoding="utf-8")
    (tmp_path / "RELEASE_NOTES_LOCAL_V1_GA.md").write_text("# GA", encoding="utf-8")
    (tmp_path / "RELEASE_NOTES_LOCAL_V1_RC.md").write_text("# RC", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("# Changelog", encoding="utf-8")
    demo_dir = tmp_path / "docs" / "demo"
    demo_dir.mkdir(parents=True)
    (demo_dir / "LOCAL_V1_WALKTHROUGH.md").write_text("# Walkthrough", encoding="utf-8")


class TestReleaseBundle:
    def test_bundle_dir_name_is_ga(self):
        assert BUNDLE_DIR_NAME == "sourcelab_local_v1_ga_bundle"

    def test_build_bundle_creates_directory_and_zip(self, tmp_path: Path):
        _seed_minimal_project(tmp_path)
        result = build_release_bundle(tmp_path)
        bundle_dir = tmp_path / "artifacts" / "release" / BUNDLE_DIR_NAME
        bundle_zip = tmp_path / "artifacts" / "release" / f"{BUNDLE_DIR_NAME}.zip"

        assert bundle_dir.is_dir()
        assert bundle_zip.is_file()
        assert result["status"] == "ok"
        assert result["file_count"] >= 1

    def test_bundle_contains_manifest_and_release_notes(self, tmp_path: Path):
        _seed_minimal_project(tmp_path)
        build_release_bundle(tmp_path)
        bundle_dir = tmp_path / "artifacts" / "release" / BUNDLE_DIR_NAME

        assert (bundle_dir / "release" / "local_v1_release_manifest.json").exists()
        assert (bundle_dir / "release" / "local_v1_release_report.md").exists()
        assert (bundle_dir / "docs" / "RELEASE_NOTES_LOCAL_V1_GA.md").exists()
        assert (bundle_dir / "bundle_manifest.json").exists()


class TestReleaseChecksums:
    def test_checksums_writes_sha256sums(self, tmp_path: Path):
        release_dir = tmp_path / "artifacts" / "release"
        bundle_dir = release_dir / BUNDLE_DIR_NAME
        bundle_dir.mkdir(parents=True)
        (bundle_dir / "sample.txt").write_text("hello", encoding="utf-8")

        result = write_release_checksums(tmp_path)
        sums_path = release_dir / "SHA256SUMS"

        assert sums_path.is_file()
        assert result["entry_count"] >= 1
        content = sums_path.read_text(encoding="utf-8")
        assert "sample.txt" in content
        assert len(content.splitlines()[0].split()[0]) == 64


class TestDoctorGA:
    def test_doctor_includes_bundle_and_strict_status(self, tmp_path: Path):
        report = run_doctor(tmp_path)
        check_names = {c["name"] for c in report["checks"]}
        assert "release_bundle" in check_names
        assert "strict_release_status" in check_names
        assert "release_bundle" in report
        assert "strict_release_status" in report
        assert "recommended_next_command" in report

    def test_doctor_cli_json(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        args = build_parser().parse_args(["doctor"])
        data = _run_json_cmd(cmd_doctor, args)
        assert data["release_bundle"]["status"] == "missing"


class TestReleaseDashboardSummary:
    def test_handles_missing_bundle(self, tmp_path: Path):
        summary = load_release_dashboard_summary(tmp_path)
        assert summary["bundle_status"]["status"] == "missing"
        assert "sourcelab release bundle" in summary["recommended_next_commands"]


class TestReleaseCLICommands:
    def test_release_bundle_command(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _seed_minimal_project(tmp_path)
        args = build_parser().parse_args(["release", "bundle"])
        data = _run_json_cmd(cmd_release_bundle, args)
        assert data["status"] == "ok"
        assert Path(data["bundle_zip"]).exists()

    def test_release_checksums_command(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        bundle_dir = tmp_path / "artifacts" / "release" / BUNDLE_DIR_NAME
        bundle_dir.mkdir(parents=True)
        (bundle_dir / "a.txt").write_text("x", encoding="utf-8")

        args = build_parser().parse_args(["release", "checksums"])
        data = _run_json_cmd(cmd_release_checksums, args)
        assert data["entry_count"] >= 1
        assert (tmp_path / "artifacts" / "release" / "SHA256SUMS").exists()


class TestMakefileAndDocker:
    def test_makefile_contains_ga_check(self):
        makefile = Path.cwd() / "Makefile"
        content = makefile.read_text(encoding="utf-8")
        assert "ga-check:" in content
        assert "release bundle" in content
        assert "release checksums" in content
        assert "release sbom" in content
        assert "release attest" in content

    def test_docker_compose_includes_dashboard_service(self):
        compose = Path.cwd() / "docker-compose.yml"
        content = compose.read_text(encoding="utf-8")
        assert "sourcelab-dashboard:" in content
        assert "profiles:" in content

    def test_release_process_doc_exists(self):
        doc = Path.cwd() / "docs" / "operations" / "RELEASE_PROCESS.md"
        assert doc.is_file()
        text = doc.read_text(encoding="utf-8")
        assert "git tag -a local-v1.0.0" in text
        assert "release bundle" in text
        assert "sourcelab_local_v1_ga_bundle" in text


class TestReleaseBundleStatus:
    def test_missing_bundle_status(self, tmp_path: Path):
        status = get_release_bundle_status(tmp_path)
        assert status["status"] == "missing"
