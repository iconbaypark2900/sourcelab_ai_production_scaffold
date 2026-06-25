"""Tests for Local v1.2 signed release and multi-pack distribution."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from sourcelab.cli import build_parser, cmd_evals_run, cmd_release_sign, cmd_release_verify_signature
from sourcelab.cli import cmd_release_publish, cmd_source_pack_doctor
from sourcelab.doctor import run_doctor
from sourcelab.evals.runner import list_runnable_source_packs, run_all_packs_evals
from sourcelab.harness.release_gate import verify_release
from sourcelab.release.attest import write_release_attestation
from sourcelab.release.bundle import build_release_bundle
from sourcelab.release.checksums import write_release_checksums
from sourcelab.release.publish import PUBLISH_PLAN_FILENAME, write_publish_plan
from sourcelab.release.signing import (
    SIGNATURE_PLAN_FILENAME,
    VERIFICATION_FILENAME,
    write_signature_plan,
    verify_release_signature,
)
from sourcelab.sources.source_pack import doctor_source_pack, validate_source_pack


def _run_json_cmd(func, args) -> dict:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        func(args)
    return json.loads(buffer.getvalue().strip())


def _seed_release_artifacts(tmp_path: Path) -> None:
    release_dir = tmp_path / "artifacts" / "release"
    release_dir.mkdir(parents=True)
    (release_dir / "local_v1_release_manifest.json").write_text(
        json.dumps({"strict_release_status": "PASS", "golden_eval_pass_rate": 1.0}),
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
    lock_dir = tmp_path / "requirements"
    lock_dir.mkdir(parents=True)
    (lock_dir / "lock-local-v1.txt").write_text("# lock\npytest==8.0.0\n", encoding="utf-8")


class TestReleaseSigning:
    def test_dry_run_writes_signature_plan(self, tmp_path: Path):
        _seed_release_artifacts(tmp_path)
        build_release_bundle(tmp_path)
        write_release_checksums(tmp_path)

        result = write_signature_plan(tmp_path, mode="dry-run")
        plan_path = tmp_path / "artifacts" / "release" / SIGNATURE_PLAN_FILENAME

        assert result["status"] == "ok"
        assert result["unsigned"] is True
        assert plan_path.is_file()
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        assert plan["signing_mode"] == "dry-run"
        assert plan["unsigned"] is True
        assert plan["release_version"]
        assert plan["bundle_path"]
        assert plan["checksum_path"]
        assert plan["required_external_tool"] is None

    def test_verify_signature_records_unsigned(self, tmp_path: Path):
        _seed_release_artifacts(tmp_path)
        write_signature_plan(tmp_path, mode="dry-run")
        write_release_checksums(tmp_path)

        result = verify_release_signature(tmp_path)
        verification_path = tmp_path / "artifacts" / "release" / VERIFICATION_FILENAME

        assert verification_path.is_file()
        assert result["unsigned"] is True
        assert result["status"] in {"unsigned", "missing_checksums"}

    def test_sign_cli_dry_run(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _seed_release_artifacts(tmp_path)
        build_release_bundle(tmp_path)
        write_release_checksums(tmp_path)
        args = build_parser().parse_args(["release", "sign", "--mode", "dry-run"])
        data = _run_json_cmd(cmd_release_sign, args)
        assert data["unsigned"] is True

    def test_verify_signature_cli(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        write_signature_plan(tmp_path, mode="dry-run")
        args = build_parser().parse_args(["release", "verify-signature"])
        data = _run_json_cmd(cmd_release_verify_signature, args)
        assert "verification_path" in data


class TestReleaseAttestationV12:
    def test_attestation_includes_v12_fields(self, tmp_path: Path):
        _seed_release_artifacts(tmp_path)
        build_release_bundle(tmp_path)
        write_release_checksums(tmp_path)
        write_release_attestation(tmp_path)

        attestation_path = tmp_path / "artifacts" / "release" / "release_attestation.json"
        data = json.loads(attestation_path.read_text(encoding="utf-8"))

        assert "sbom_sha256" in data
        assert "checksums_sha256" in data
        assert "bundle_zip_sha256" in data
        assert "source_pack_summary" in data
        assert "golden_eval_summary_path" in data
        assert "ci_workflow_path" in data
        assert "lock_file_path" in data
        assert "signature_status" in data
        assert "unsigned_reason" in data
        assert data["unsigned"] is True


class TestReleasePublish:
    def test_publish_dry_run_writes_plan(self, tmp_path: Path):
        _seed_release_artifacts(tmp_path)
        build_release_bundle(tmp_path)
        write_release_checksums(tmp_path)
        write_release_attestation(tmp_path)
        write_signature_plan(tmp_path, mode="dry-run")

        result = write_publish_plan(tmp_path, dry_run=True)
        plan_path = tmp_path / "artifacts" / "release" / PUBLISH_PLAN_FILENAME

        assert result["status"] == "ok"
        assert result["dry_run"] is True
        assert plan_path.is_file()
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        assert plan["upload_performed"] is False
        assert plan["suggested_github_tag"]
        assert plan["suggested_github_title"]
        assert isinstance(plan["warnings"], list)

    def test_publish_cli(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _seed_release_artifacts(tmp_path)
        args = build_parser().parse_args(["release", "publish", "--dry-run"])
        data = _run_json_cmd(cmd_release_publish, args)
        assert data["dry_run"] is True


class TestFreezeCheck:
    def test_makefile_has_freeze_check(self):
        makefile = Path.cwd() / "Makefile"
        content = makefile.read_text(encoding="utf-8")
        assert "freeze-check:" in content
        assert "freeze_requirements.sh --check" in content


class TestSourcePackDoctor:
    def test_pqc_v1_doctor_passes(self):
        result = doctor_source_pack(Path.cwd(), "pqc_v1")
        assert result["valid"] is True
        assert result["strict"] is True

    def test_ai_safety_v1_doctor_passes(self):
        result = doctor_source_pack(Path.cwd(), "ai_safety_v1")
        assert result["valid"] is True
        assert result["source_count"] == 5
        assert result["eval_count"] == 4

    def test_doctor_cli(self):
        args = build_parser().parse_args(["source-pack", "doctor", "ai_safety_v1"])
        data = _run_json_cmd(cmd_source_pack_doctor, args)
        assert data["valid"] is True

    def test_validate_catches_duplicate_source_ids(self, tmp_path: Path):
        pack_dir = tmp_path / "data" / "source_packs" / "bad_pack"
        sources_dir = pack_dir / "sources"
        evals_dir = pack_dir / "evals"
        sources_dir.mkdir(parents=True)
        evals_dir.mkdir(parents=True)
        (pack_dir / "README.md").write_text("# Bad", encoding="utf-8")
        (sources_dir / "a.md").write_text("---\nsource_id: dup\n---\n\nBody", encoding="utf-8")
        (evals_dir / "retrieval_gold.json").write_text("[]", encoding="utf-8")
        (evals_dir / "claim_gold.json").write_text("[]", encoding="utf-8")
        (evals_dir / "answer_gold.json").write_text("[]", encoding="utf-8")
        (evals_dir / "lesson_gold.json").write_text("[]", encoding="utf-8")
        (pack_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "pack_name": "bad_pack",
                    "version": "0.0.1",
                    "title": "Bad",
                    "sources": [
                        {
                            "source_id": "dup",
                            "filename": "a.md",
                            "trust_tier": "B",
                            "publisher": "test",
                            "source_type": "notes",
                        },
                        {
                            "source_id": "dup",
                            "filename": "a.md",
                            "trust_tier": "B",
                            "publisher": "test",
                            "source_type": "notes",
                        },
                    ],
                    "evals": [
                        "retrieval_gold.json",
                        "claim_gold.json",
                        "answer_gold.json",
                        "lesson_gold.json",
                    ],
                }
            ),
            encoding="utf-8",
        )
        result = doctor_source_pack(tmp_path, "bad_pack")
        assert result["valid"] is False
        assert any("Duplicate source_id" in err for err in result["errors"])


class TestMultiPackEvals:
    def test_list_runnable_packs_excludes_template(self):
        packs = list_runnable_source_packs(Path.cwd())
        assert "pqc_v1" in packs
        assert "ai_safety_v1" in packs
        assert "TEMPLATE" not in packs

    @pytest.mark.slow
    def test_all_packs_eval_summary_written(self):
        result = run_all_packs_evals(Path.cwd())
        summary_path = Path(result["combined_summary_path"])
        assert summary_path.is_file()
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert summary["pack_count"] >= 2
        assert "pqc_v1" in [p["pack_name"] for p in summary["packs"]]

    def test_all_packs_cli(self, monkeypatch):
        monkeypatch.chdir(Path.cwd())
        args = build_parser().parse_args(["evals", "run", "--all-packs", "--type", "retrieval"])
        data = _run_json_cmd(cmd_evals_run, args)
        assert "pack_results" in data
        assert "combined_summary_path" in data


class TestDoctorV12:
    def test_doctor_reports_v12_status_fields(self, tmp_path: Path):
        _seed_release_artifacts(tmp_path)
        write_signature_plan(tmp_path, mode="dry-run")
        verify_release_signature(tmp_path)
        write_publish_plan(tmp_path, dry_run=True)

        report = run_doctor(tmp_path)
        check_names = {c["name"] for c in report["checks"]}
        assert "signature_plan_status" in check_names
        assert "signature_verification_status" in check_names
        assert "publish_plan_status" in check_names
        assert "sbom_status" in check_names
        assert "attestation_status" in check_names
        assert "multi_pack_status" in check_names
        assert "dependency_lock_drift" in check_names


class TestStrictReleaseMultiPack:
    def test_other_pack_failure_does_not_block_when_not_strict(self, tmp_path: Path):
        evals_dir = tmp_path / "artifacts" / "evals"
        (evals_dir / "pqc_v1").mkdir(parents=True)
        (evals_dir / "ai_safety_v1").mkdir(parents=True)
        (evals_dir / "pqc_v1" / "golden_eval_summary.json").write_text(
            json.dumps({"overall_pass_rate": 1.0, "eval_reports": []}),
            encoding="utf-8",
        )
        (evals_dir / "ai_safety_v1" / "golden_eval_summary.json").write_text(
            json.dumps({"overall_pass_rate": 0.2, "eval_reports": []}),
            encoding="utf-8",
        )

        report = verify_release(tmp_path, strict=False)
        golden_checks = [c for c in report["checks"] if c["check_name"] == "golden_evals_pass"]
        assert not golden_checks

    def test_pqc_v1_validate_still_passes(self):
        result = validate_source_pack(Path.cwd(), "pqc_v1")
        assert result["valid"] is True


class TestOfflineInstallDoc:
    def test_offline_install_doc_exists(self):
        doc = Path.cwd() / "docs" / "operations" / "OFFLINE_INSTALL.md"
        assert doc.is_file()
        text = doc.read_text(encoding="utf-8")
        assert "SHA256SUMS" in text
        assert "lock-local-v1.txt" in text
