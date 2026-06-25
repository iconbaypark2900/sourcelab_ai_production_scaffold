"""Integration smoke tests for SourceLab Local v1.0 RC."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from sourcelab.cli import (
    build_parser,
    cmd_doctor,
    cmd_evals_run,
    cmd_export,
    cmd_init_local,
    cmd_local_demo,
    cmd_release_manifest,
    cmd_source_pack_validate,
    cmd_verify_release,
    cmd_version,
)
from sourcelab.version import RELEASE_LABEL, __version__


@pytest.fixture
def project_root():
    return Path.cwd()


def _run_cmd(func, args) -> dict | None:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        func(args)
    output = buffer.getvalue().strip()
    if not output:
        return None
    return json.loads(output)


class TestLocalV1SmokeFast:
    """Fast smoke checks that should run on every CI pass."""

    def test_version_metadata(self, project_root):
        args = build_parser().parse_args(["version"])
        data = _run_cmd(cmd_version, args)
        assert data is not None
        assert data["version"] == __version__
        assert data["release_label"] == RELEASE_LABEL
        assert "python_version" in data
        assert data["project_root"] == str(project_root.resolve())
        assert data["artifacts_directory"].endswith("artifacts")

    def test_doctor(self, project_root):
        args = build_parser().parse_args(["doctor"])
        data = _run_cmd(cmd_doctor, args)
        assert data is not None
        assert data["status"] in {"PASS", "FAIL"}
        assert "checks" in data
        check_names = {c["name"] for c in data["checks"]}
        assert "python_version" in check_names
        assert "pqc_source_pack" in check_names

    def test_init_local_idempotent(self, project_root):
        args = build_parser().parse_args(["init-local"])
        first = _run_cmd(cmd_init_local, args)
        second = _run_cmd(cmd_init_local, args)
        assert first is not None
        assert second is not None
        assert first["passed"] is True
        assert second["passed"] is True

    def test_source_pack_validate_pqc_v1(self, project_root):
        args = build_parser().parse_args(["source-pack", "validate", "pqc_v1"])
        data = _run_cmd(cmd_source_pack_validate, args)
        assert data is not None
        assert data["valid"] is True


@pytest.mark.slow
class TestLocalV1SmokeSlow:
    """End-to-end smoke checks — run separately when validating a release."""

    def test_evals_run_pqc_v1(self, project_root):
        args = build_parser().parse_args(["evals", "run", "--pack", "pqc_v1"])
        data = _run_cmd(cmd_evals_run, args)
        assert data is not None
        summary = data.get("summary", {})
        assert summary.get("overall_pass_rate", 0) >= 0.8

    def test_local_demo(self, project_root):
        args = build_parser().parse_args(["local-demo"])
        data = _run_cmd(cmd_local_demo, args)
        assert data is not None
        assert data["passed"] is True
        assert data["strict_release_status"] == "PASS"

    def test_verify_release_strict(self, project_root):
        args = build_parser().parse_args(["verify-release", "--strict"])
        data = _run_cmd(cmd_verify_release, args)
        assert data is not None
        assert data["status"] == "PASS", data.get("blocking_failures")

    def test_release_manifest(self, project_root):
        args = build_parser().parse_args(["release", "manifest"])
        data = _run_cmd(cmd_release_manifest, args)
        assert data is not None
        assert "error" not in data
        assert data.get("version") == __version__
        assert data.get("doctor_status") in {"PASS", "FAIL"}

    def test_export_latest_markdown(self, project_root, tmp_path):
        args = build_parser().parse_args(["export", "latest", "--format", "markdown"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            cmd_export(args)
        output = buffer.getvalue()
        assert "Exported:" in output
        export_path = Path(output.strip().split("Exported:")[-1].strip())
        assert export_path.exists()
        assert export_path.suffix == ".md"
