"""Tests for Harness v2 components.

Tests for:
- schemas.py (Pydantic schemas)
- artifact_inventory.py (artifact ordering and validation)
- schema_validators.py (JSON schema validation)
- proof_bundle.py v2 (sha256, manifests, proof summary)
- runner.py v2 (structured checks)
- release_gate.py v2 (comprehensive release verification)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sourcelab.harness.schemas import (
    ArtifactRecord,
    HarnessCheck,
    HarnessReport,
    ProofBundleManifest,
    ReleaseGateReport,
    RunManifest,
    RunStatus,
)
from sourcelab.harness.artifact_inventory import (
    ARTIFACT_ORDER,
    REQUIRED_ARTIFACTS,
    OPTIONAL_ARTIFACTS,
    FULL_DEMO_ARTIFACTS,
    SCHEMA_MAP,
    ARTIFACT_TYPES,
    get_artifact_record,
    build_artifact_inventory,
)
from sourcelab.harness.schema_validators import (
    validate_generated_lesson_package,
    validate_rubric,
    validate_answer_key,
    validate_generation_trace,
    validate_verification_report,
    validate_citation_resolution,
    validate_human_review_queue,
    validate_answer_review,
    validate_next_task_decision,
    validate_run_manifest,
    validate_proof_summary,
    validate_all_schemas,
)
from sourcelab.harness.proof_bundle import ProofBundle
from sourcelab.harness.runner import HarnessRunner
from sourcelab.harness.release_gate import verify_release


# ===== Schema Tests =====


class TestSchemas:
    def test_artifact_record_schema(self):
        record = ArtifactRecord(
            artifact_name="test.json",
            path="/tmp/test.json",
            artifact_type="json",
            required=True,
            exists=True,
            sha256="abc123",
            schema_name="TestSchema",
            validated=True,
        )
        assert record.artifact_name == "test.json"
        assert record.required is True
        assert record.exists is True

    def test_harness_check_schema(self):
        check = HarnessCheck(
            check_name="test_check",
            passed=True,
            severity="blocking",
            message="All good",
        )
        assert check.check_name == "test_check"
        assert check.passed is True
        assert check.severity == "blocking"

    def test_harness_check_default_severity(self):
        check = HarnessCheck(
            check_name="test_check",
            passed=True,
            message="All good",
        )
        assert check.severity == "blocking"

    def test_run_manifest_schema(self):
        manifest = RunManifest(
            run_id="test-run",
            created_at="2026-01-01T00:00:00Z",
            topic="test topic",
        )
        assert manifest.run_id == "test-run"
        assert manifest.artifact_count == 0
        assert manifest.status == "complete"

    def test_proof_bundle_manifest_schema(self):
        manifest = ProofBundleManifest(
            run_id="test-run",
            created_at="2026-01-01T00:00:00Z",
        )
        assert manifest.run_id == "test-run"
        assert manifest.total_artifacts == 0
        assert manifest.missing_required == []

    def test_run_status_schema(self):
        status = RunStatus(
            run_id="test-run",
            run_dir="/tmp/test",
            topic="test topic",
            harness_passed=True,
            proof_bundle_complete=True,
            release_gate_status="PASS",
            artifact_count=5,
        )
        assert status.run_id == "test-run"
        assert status.harness_passed is True
        assert status.release_gate_status == "PASS"


# ===== Artifact Inventory Tests =====


class TestArtifactInventory:
    def test_artifact_order_is_unique(self):
        assert len(ARTIFACT_ORDER) == len(set(ARTIFACT_ORDER))

    def test_required_artifacts_are_subset_of_order(self):
        for artifact in REQUIRED_ARTIFACTS:
            assert artifact in ARTIFACT_ORDER, f"{artifact} not in ARTIFACT_ORDER"

    def test_optional_artifacts_are_subset_of_order(self):
        for artifact in OPTIONAL_ARTIFACTS:
            assert artifact in ARTIFACT_ORDER, f"{artifact} not in ARTIFACT_ORDER"

    def test_full_demo_artifacts_are_subset_of_order(self):
        for artifact in FULL_DEMO_ARTIFACTS:
            assert artifact in ARTIFACT_ORDER, f"{artifact} not in ARTIFACT_ORDER"

    def test_schema_map_covers_json_artifacts(self):
        for artifact in ARTIFACT_ORDER:
            if artifact.endswith(".json"):
                assert artifact in SCHEMA_MAP, f"{artifact} missing from SCHEMA_MAP"

    def test_artifact_types_covers_all(self):
        for artifact in ARTIFACT_ORDER:
            assert artifact in ARTIFACT_TYPES, f"{artifact} missing from ARTIFACT_TYPES"

    def test_get_artifact_record_existing(self, tmp_path):
        test_file = tmp_path / "test.json"
        test_file.write_text('{"key": "value"}', encoding="utf-8")

        record = get_artifact_record("test.json", tmp_path, required=True)
        assert record.exists is True
        assert record.required is True
        assert record.sha256 != ""
        assert record.validated is True

    def test_get_artifact_record_missing(self, tmp_path):
        record = get_artifact_record("nonexistent.json", tmp_path, required=True)
        assert record.exists is False
        assert record.required is True
        assert record.sha256 == ""

    def test_get_artifact_record_invalid_json(self, tmp_path):
        test_file = tmp_path / "bad.json"
        test_file.write_text("not json", encoding="utf-8")

        record = get_artifact_record("bad.json", tmp_path, required=True)
        assert record.exists is True
        assert record.error is not None
        assert record.validated is False

    def test_build_artifact_inventory(self, tmp_path):
        # Create some artifacts
        (tmp_path / "source_registry_snapshot.json").write_text("[]", encoding="utf-8")
        (tmp_path / "retrieved_chunks.json").write_text("[]", encoding="utf-8")

        inventory = build_artifact_inventory(tmp_path)
        assert len(inventory) == len(ARTIFACT_ORDER)

        # Check that existing artifacts are marked as existing
        source_record = next(r for r in inventory if r.artifact_name == "source_registry_snapshot.json")
        assert source_record.exists is True

        # Check that missing artifacts are marked as not existing
        rubric_record = next(r for r in inventory if r.artifact_name == "rubric.json")
        assert rubric_record.exists is False

    def test_build_artifact_inventory_with_string_path(self, tmp_path):
        inventory = build_artifact_inventory(str(tmp_path))
        assert len(inventory) == len(ARTIFACT_ORDER)


# ===== Schema Validator Tests =====


class TestSchemaValidators:
    def test_validate_generated_lesson_package_valid(self, tmp_path):
        data = {"topic": "test topic"}
        (tmp_path / "generated_lesson_package.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        check = validate_generated_lesson_package(tmp_path / "generated_lesson_package.json")
        assert check.passed is True

    def test_validate_generated_lesson_package_missing_topic(self, tmp_path):
        (tmp_path / "generated_lesson_package.json").write_text(
            '{"other": "data"}', encoding="utf-8"
        )
        check = validate_generated_lesson_package(tmp_path / "generated_lesson_package.json")
        assert check.passed is False

    def test_validate_rubric_valid(self, tmp_path):
        data = {"criteria": [{"name": "test", "weight": 1.0}]}
        (tmp_path / "rubric.json").write_text(json.dumps(data), encoding="utf-8")
        check = validate_rubric(tmp_path / "rubric.json")
        assert check.passed is True

    def test_validate_rubric_weights_not_one(self, tmp_path):
        data = {"criteria": [{"name": "test", "weight": 0.5}]}
        (tmp_path / "rubric.json").write_text(json.dumps(data), encoding="utf-8")
        check = validate_rubric(tmp_path / "rubric.json")
        assert check.passed is False

    def test_validate_answer_key_valid(self, tmp_path):
        data = {"source_references": [{"source_id": "s1", "chunk_id": "c1"}]}
        (tmp_path / "answer_key.json").write_text(json.dumps(data), encoding="utf-8")
        check = validate_answer_key(tmp_path / "answer_key.json")
        assert check.passed is True

    def test_validate_answer_key_markdown_fallback(self, tmp_path):
        (tmp_path / "answer_key.md").write_text(
            "# Answer Key\n\n## Source References\n- test",
            encoding="utf-8",
        )
        check = validate_answer_key(tmp_path / "answer_key.json")
        assert check.passed is True

    def test_validate_generation_trace_valid(self, tmp_path):
        data = {"source_ids": ["s1"], "chunk_ids": ["c1"]}
        (tmp_path / "generation_trace.json").write_text(json.dumps(data), encoding="utf-8")
        check = validate_generation_trace(tmp_path / "generation_trace.json")
        assert check.passed is True

    def test_validate_generation_trace_fail_closed(self, tmp_path):
        data = {"source_ids": ["s1"], "chunk_ids": ["c1"], "fail_closed_reason": "no sources"}
        (tmp_path / "generation_trace.json").write_text(json.dumps(data), encoding="utf-8")
        check = validate_generation_trace(tmp_path / "generation_trace.json")
        assert check.passed is False

    def test_validate_verification_report_pass(self, tmp_path):
        data = {"summary": {"release_gate_status": "PASS"}}
        (tmp_path / "verification_report.json").write_text(json.dumps(data), encoding="utf-8")
        check = validate_verification_report(tmp_path / "verification_report.json")
        assert check.passed is True

    def test_validate_verification_report_fail(self, tmp_path):
        data = {"summary": {"release_gate_status": "FAIL"}, "blocking_reasons": ["reason"]}
        (tmp_path / "verification_report.json").write_text(json.dumps(data), encoding="utf-8")
        check = validate_verification_report(tmp_path / "verification_report.json")
        assert check.passed is False

    def test_validate_citation_resolution_valid(self, tmp_path):
        data = {"resolution_rate": 0.9, "unsupported_high_risk": 0}
        (tmp_path / "citation_resolution.json").write_text(json.dumps(data), encoding="utf-8")
        check = validate_citation_resolution(tmp_path / "citation_resolution.json")
        assert check.passed is True

    def test_validate_citation_resolution_high_risk(self, tmp_path):
        data = {"resolution_rate": 0.9, "unsupported_high_risk": 3}
        (tmp_path / "citation_resolution.json").write_text(json.dumps(data), encoding="utf-8")
        check = validate_citation_resolution(tmp_path / "citation_resolution.json")
        assert check.passed is False

    def test_validate_human_review_queue_valid(self, tmp_path):
        data = {"total_items": 5, "high_priority": 0}
        (tmp_path / "human_review_queue.json").write_text(json.dumps(data), encoding="utf-8")
        check = validate_human_review_queue(tmp_path / "human_review_queue.json")
        assert check.passed is True

    def test_validate_human_review_queue_high_priority(self, tmp_path):
        data = {"total_items": 5, "high_priority": 2}
        (tmp_path / "human_review_queue.json").write_text(json.dumps(data), encoding="utf-8")
        check = validate_human_review_queue(tmp_path / "human_review_queue.json")
        assert check.passed is False

    def test_validate_answer_review_valid(self, tmp_path):
        data = {
            "overall_score": 0.8,
            "criterion_scores": [
                {"criterion_name": "topic_relevance", "score": 0.9},
                {"criterion_name": "source_grounding", "score": 0.7},
            ],
            "strengths": ["Strong topic relevance"],
            "weaknesses": [],
        }
        (tmp_path / "answer_review.json").write_text(json.dumps(data), encoding="utf-8")
        check = validate_answer_review(tmp_path / "answer_review.json")
        assert check.passed is True

    def test_validate_next_task_decision_valid(self, tmp_path):
        data = {"difficulty": 3, "reason": "next task"}
        (tmp_path / "next_task_decision.json").write_text(json.dumps(data), encoding="utf-8")
        check = validate_next_task_decision(tmp_path / "next_task_decision.json")
        assert check.passed is True

    def test_validate_next_task_decision_invalid_difficulty(self, tmp_path):
        data = {"difficulty": 10, "reason": "next task"}
        (tmp_path / "next_task_decision.json").write_text(json.dumps(data), encoding="utf-8")
        check = validate_next_task_decision(tmp_path / "next_task_decision.json")
        assert check.passed is False

    def test_validate_run_manifest_valid(self, tmp_path):
        data = {"run_id": "test-run", "artifact_count": 5}
        (tmp_path / "run_manifest.json").write_text(json.dumps(data), encoding="utf-8")
        check = validate_run_manifest(tmp_path / "run_manifest.json")
        assert check.passed is True

    def test_validate_run_manifest_zero_artifacts(self, tmp_path):
        data = {"run_id": "test-run", "artifact_count": 0}
        (tmp_path / "run_manifest.json").write_text(json.dumps(data), encoding="utf-8")
        check = validate_run_manifest(tmp_path / "run_manifest.json")
        assert check.passed is False

    def test_validate_proof_summary_valid(self, tmp_path):
        data = {"run_id": "test-run"}
        (tmp_path / "proof_summary.json").write_text(json.dumps(data), encoding="utf-8")
        check = validate_proof_summary(tmp_path / "proof_summary.json")
        assert check.passed is True

    def test_validate_all_schemas(self, tmp_path):
        # Create valid artifacts
        (tmp_path / "generated_lesson_package.json").write_text(
            json.dumps({"topic": "test"}), encoding="utf-8"
        )
        (tmp_path / "rubric.json").write_text(
            json.dumps({"criteria": [{"name": "test", "weight": 1.0}]}), encoding="utf-8"
        )
        (tmp_path / "run_manifest.json").write_text(
            json.dumps({"run_id": "test", "artifact_count": 1}), encoding="utf-8"
        )

        checks = validate_all_schemas(tmp_path)
        assert len(checks) > 0
        # All created artifacts should pass
        for check in checks:
            assert check.passed is True


# ===== Proof Bundle v2 Tests =====


class TestProofBundleV2:
    def test_proof_bundle_write_json(self, tmp_path):
        proof = ProofBundle(run_id="test-run", run_dir=tmp_path)
        path = proof.write_json("test.json", {"key": "value"})
        assert path.exists()
        assert "test.json" in proof.artifacts

    def test_proof_bundle_write_text(self, tmp_path):
        proof = ProofBundle(run_id="test-run", run_dir=tmp_path)
        path = proof.write_text("test.md", "# Test")
        assert path.exists()
        assert "test.md" in proof.artifacts

    def test_proof_bundle_sha256(self, tmp_path):
        proof = ProofBundle(run_id="test-run", run_dir=tmp_path)
        proof.write_json("test.json", {"key": "value"})
        assert len(proof.artifact_records) == 1
        assert proof.artifact_records[0].sha256 != ""

    def test_proof_bundle_write_run_manifest(self, tmp_path):
        proof = ProofBundle(run_id="test-run", run_dir=tmp_path)
        path = proof.write_run_manifest(topic="test topic")
        assert path.exists()
        assert (tmp_path / "run_manifest.json").exists()

    def test_proof_bundle_write_proof_bundle_manifest(self, tmp_path):
        proof = ProofBundle(run_id="test-run", run_dir=tmp_path)
        proof.write_json("test.json", {"key": "value"})
        path = proof.write_proof_bundle_manifest()
        assert path.exists()
        assert (tmp_path / "proof_bundle_manifest.json").exists()

    def test_proof_bundle_write_proof_summary(self, tmp_path):
        proof = ProofBundle(run_id="test-run", run_dir=tmp_path)
        path = proof.write_proof_summary(
            topic="test topic",
            harness_passed=True,
            citation_resolution_rate=0.9,
        )
        assert path.exists()
        assert (tmp_path / "proof_summary.json").exists()

    def test_proof_bundle_trace(self, tmp_path):
        proof = ProofBundle(run_id="test-run", run_dir=tmp_path)
        proof.write_json("test.json", {"key": "value"})
        trace = proof.trace()
        assert trace["run_id"] == "test-run"
        assert "test.json" in trace["artifacts"]


# ===== Harness Runner v2 Tests =====


class TestHarnessRunnerV2:
    def test_validate_run_passes(self, tmp_path):
        # Create all required artifacts
        for artifact in REQUIRED_ARTIFACTS:
            if artifact.endswith(".json"):
                (tmp_path / artifact).write_text("{}", encoding="utf-8")
            else:
                (tmp_path / artifact).write_text("", encoding="utf-8")

        # Create valid content
        rubric_data = {"criteria": [{"name": "test", "weight": 1.0}]}
        (tmp_path / "rubric.json").write_text(json.dumps(rubric_data), encoding="utf-8")

        (tmp_path / "answer_key.md").write_text(
            "# Answer Key\n\n## Source References\n- test", encoding="utf-8"
        )

        trace_data = {"source_ids": ["s1"], "chunk_ids": ["c1"]}
        (tmp_path / "generation_trace.json").write_text(json.dumps(trace_data), encoding="utf-8")

        citation_data = {"resolution_rate": 0.9, "unsupported_high_risk": 0}
        (tmp_path / "citation_resolution.json").write_text(json.dumps(citation_data), encoding="utf-8")

        verification_data = {"summary": {"release_gate_status": "PASS"}}
        (tmp_path / "verification_report.json").write_text(json.dumps(verification_data), encoding="utf-8")

        lesson_data = {"topic": "test"}
        (tmp_path / "generated_lesson_package.json").write_text(json.dumps(lesson_data), encoding="utf-8")

        run_manifest = {"run_id": "test", "artifact_count": 5}
        (tmp_path / "run_manifest.json").write_text(json.dumps(run_manifest), encoding="utf-8")

        proof_summary = {"run_id": "test"}
        (tmp_path / "proof_summary.json").write_text(json.dumps(proof_summary), encoding="utf-8")

        runner = HarnessRunner()
        report = runner.validate_run(tmp_path)
        assert report["passed"] is True
        assert len(report["blocking_failures"]) == 0

    def test_validate_run_fails_missing_artifacts(self, tmp_path):
        runner = HarnessRunner()
        report = runner.validate_run(tmp_path)
        assert report["passed"] is False
        assert len(report["blocking_failures"]) > 0

    def test_validate_run_structured_checks(self, tmp_path):
        # Create minimal valid run
        for artifact in REQUIRED_ARTIFACTS:
            if artifact.endswith(".json"):
                (tmp_path / artifact).write_text("{}", encoding="utf-8")
            else:
                (tmp_path / artifact).write_text("", encoding="utf-8")

        rubric_data = {"criteria": [{"name": "test", "weight": 1.0}]}
        (tmp_path / "rubric.json").write_text(json.dumps(rubric_data), encoding="utf-8")

        (tmp_path / "answer_key.md").write_text(
            "# Answer Key\n\n## Source References\n- test", encoding="utf-8"
        )

        trace_data = {"source_ids": ["s1"], "chunk_ids": ["c1"]}
        (tmp_path / "generation_trace.json").write_text(json.dumps(trace_data), encoding="utf-8")

        citation_data = {"resolution_rate": 0.9, "unsupported_high_risk": 0}
        (tmp_path / "citation_resolution.json").write_text(json.dumps(citation_data), encoding="utf-8")

        verification_data = {"summary": {"release_gate_status": "PASS"}}
        (tmp_path / "verification_report.json").write_text(json.dumps(verification_data), encoding="utf-8")

        lesson_data = {"topic": "test"}
        (tmp_path / "generated_lesson_package.json").write_text(json.dumps(lesson_data), encoding="utf-8")

        run_manifest = {"run_id": "test", "artifact_count": 5}
        (tmp_path / "run_manifest.json").write_text(json.dumps(run_manifest), encoding="utf-8")

        proof_summary = {"run_id": "test"}
        (tmp_path / "proof_summary.json").write_text(json.dumps(proof_summary), encoding="utf-8")

        runner = HarnessRunner()
        report = runner.validate_run(tmp_path)
        assert "checks" in report
        assert "blocking_failures" in report
        assert "warnings" in report
        assert "artifact_count" in report


# ===== Release Gate v2 Tests =====


class TestReleaseGateV2:
    def test_release_gate_passes_without_runs(self):
        """Release gate passes when only docs/modules exist (no run directory)."""
        report = verify_release(Path.cwd())
        # Should pass documentation checks
        doc_checks = [c for c in report["checks"] if c["check_name"] in ["required_files_exist", "required_modules_exist"]]
        assert all(c["passed"] for c in doc_checks)

    def test_release_gate_structure(self):
        report = verify_release(Path.cwd())
        assert "status" in report
        assert "checks" in report
        assert "blocking_failures" in report
        assert "warnings" in report
        assert "claim" in report

    def test_release_gate_find_latest_run(self):
        """Test _find_latest_run helper."""
        from sourcelab.harness.release_gate import _find_latest_run

        # Test with no runs directory
        result = _find_latest_run(Path("/nonexistent"))
        assert result is None
