"""Unit tests for per-pack golden eval thresholds."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sourcelab.evals.thresholds import (
    BUILTIN_THRESHOLDS,
    DEFAULT_MIN_CASES,
    DEFAULT_MIN_PASS_RATE,
    DEFAULT_THRESHOLDS,
    PackEvalThresholds,
    evaluate_against_thresholds,
    load_pack_thresholds,
    write_pack_thresholds,
)


def _write_manifest(
    pack_dir: Path,
    pack_name: str,
    eval_thresholds: dict | None = None,
) -> Path:
    pack_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "pack_name": pack_name,
        "version": "1.0.0",
        "title": pack_name,
        "sources": [],
        "evals": [],
    }
    if eval_thresholds is not None:
        manifest["eval_thresholds"] = eval_thresholds
    manifest_path = pack_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def _make_summary(
    pass_rate: float = 1.0,
    total_cases: int = 10,
    eval_names: list[str] | None = None,
) -> dict:
    return {
        "pack_name": "ml_safety_v1",
        "total_evals": 4,
        "total_cases": total_cases,
        "total_passed": int(total_cases * pass_rate),
        "total_failed": total_cases - int(total_cases * pass_rate),
        "overall_pass_rate": pass_rate,
        "eval_reports": [
            {"eval_name": name, "pass_rate": pass_rate} for name in (eval_names or [])
        ],
    }


class TestPackEvalThresholds:
    def test_defaults(self):
        t = PackEvalThresholds()
        assert t.min_pass_rate == DEFAULT_MIN_PASS_RATE
        assert t.min_cases == DEFAULT_MIN_CASES
        assert t.required_evals == []
        assert t.is_default()

    def test_to_dict_roundtrip(self):
        t = PackEvalThresholds(
            min_pass_rate=0.9, min_cases=12, required_evals=["retrieval_gold"]
        )
        d = t.to_dict()
        assert d["min_pass_rate"] == 0.9
        assert d["min_cases"] == 12
        assert d["required_evals"] == ["retrieval_gold"]
        assert not t.is_default()


class TestLoadPackThresholds:
    def test_returns_default_for_missing_pack(self, tmp_path: Path):
        thresholds = load_pack_thresholds(tmp_path, "nonexistent")
        assert thresholds == DEFAULT_THRESHOLDS

    def test_returns_builtin_for_pqc_v1(self, tmp_path: Path):
        # pqc_v1 has a builtin preset even without a manifest
        (tmp_path / "data" / "source_packs" / "pqc_v1").mkdir(parents=True)
        thresholds = load_pack_thresholds(tmp_path, "pqc_v1")
        assert thresholds.min_pass_rate == 1.0
        assert thresholds == BUILTIN_THRESHOLDS["pqc_v1"]

    def test_returns_manifest_thresholds(self, tmp_path: Path):
        _write_manifest(
            tmp_path / "data" / "source_packs" / "ml_safety_v1",
            "ml_safety_v1",
            eval_thresholds={
                "min_pass_rate": 0.85,
                "min_cases": 8,
                "required_evals": ["retrieval_gold"],
            },
        )
        thresholds = load_pack_thresholds(tmp_path, "ml_safety_v1")
        assert thresholds.min_pass_rate == 0.85
        assert thresholds.min_cases == 8
        assert thresholds.required_evals == ["retrieval_gold"]

    def test_invalid_payload_falls_back_to_default(self, tmp_path: Path):
        pack_dir = tmp_path / "data" / "source_packs" / "bad"
        pack_dir.mkdir(parents=True)
        (pack_dir / "manifest.json").write_text(
            json.dumps({"pack_name": "bad", "eval_thresholds": "not a dict"}),
            encoding="utf-8",
        )
        thresholds = load_pack_thresholds(tmp_path, "bad")
        assert thresholds == DEFAULT_THRESHOLDS

    def test_out_of_range_pass_rate_clamped(self, tmp_path: Path):
        _write_manifest(
            tmp_path / "data" / "source_packs" / "ml_safety_v1",
            "ml_safety_v1",
            eval_thresholds={"min_pass_rate": 1.5},
        )
        thresholds = load_pack_thresholds(tmp_path, "ml_safety_v1")
        assert thresholds.min_pass_rate == DEFAULT_MIN_PASS_RATE

    def test_missing_manifest_with_builtin(self, tmp_path: Path):
        # builtin applies even when manifest doesn't exist
        thresholds = load_pack_thresholds(tmp_path, "ai_safety_v1")
        assert thresholds.min_pass_rate == 1.0


class TestWritePackThresholds:
    def test_writes_thresholds_preserving_other_fields(self, tmp_path: Path):
        manifest_path = _write_manifest(
            tmp_path / "data" / "source_packs" / "ml_safety_v1",
            "ml_safety_v1",
        )
        thresholds = PackEvalThresholds(
            min_pass_rate=0.9, min_cases=10, required_evals=["retrieval_gold"]
        )
        returned = write_pack_thresholds(tmp_path, "ml_safety_v1", thresholds)
        assert returned == manifest_path

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["pack_name"] == "ml_safety_v1"
        assert manifest["sources"] == []
        assert manifest["eval_thresholds"]["min_pass_rate"] == 0.9
        assert manifest["eval_thresholds"]["min_cases"] == 10
        assert manifest["eval_thresholds"]["required_evals"] == ["retrieval_gold"]

    def test_raises_for_missing_manifest(self, tmp_path: Path):
        thresholds = PackEvalThresholds()
        with pytest.raises(FileNotFoundError):
            write_pack_thresholds(tmp_path, "missing", thresholds)

    def test_raises_for_invalid_json(self, tmp_path: Path):
        pack_dir = tmp_path / "data" / "source_packs" / "broken"
        pack_dir.mkdir(parents=True)
        (pack_dir / "manifest.json").write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError):
            write_pack_thresholds(
                tmp_path, "broken", PackEvalThresholds()
            )


class TestEvaluateAgainstThresholds:
    def test_passing_summary_meets_thresholds(self):
        summary = _make_summary(pass_rate=1.0, total_cases=12)
        thresholds = PackEvalThresholds(min_pass_rate=0.9, min_cases=10)
        result = evaluate_against_thresholds("ml_safety_v1", summary, thresholds)
        assert result.meets_thresholds is True
        assert result.overall_pass_rate == 1.0
        assert result.total_cases == 12

    def test_failing_pass_rate_fails(self):
        summary = _make_summary(pass_rate=0.5, total_cases=10)
        thresholds = PackEvalThresholds(min_pass_rate=0.9, min_cases=1)
        result = evaluate_against_thresholds("ml_safety_v1", summary, thresholds)
        assert result.meets_thresholds is False
        pass_check = next(c for c in result.checks if c.name == "min_pass_rate")
        assert pass_check.passed is False

    def test_failing_case_count_fails(self):
        summary = _make_summary(pass_rate=1.0, total_cases=2)
        thresholds = PackEvalThresholds(min_pass_rate=0.5, min_cases=10)
        result = evaluate_against_thresholds("ml_safety_v1", summary, thresholds)
        assert result.meets_thresholds is False
        case_check = next(c for c in result.checks if c.name == "min_cases")
        assert case_check.passed is False

    def test_missing_required_eval_fails(self):
        summary = _make_summary(
            pass_rate=1.0, total_cases=10, eval_names=["retrieval_gold"]
        )
        thresholds = PackEvalThresholds(
            min_pass_rate=0.5, min_cases=1, required_evals=["retrieval_gold", "claim_gold"]
        )
        result = evaluate_against_thresholds("ml_safety_v1", summary, thresholds)
        assert result.meets_thresholds is False
        missing = [c for c in result.checks if c.name == "required_eval:claim_gold"]
        assert missing[0].passed is False

    def test_present_required_evals_pass(self):
        summary = _make_summary(
            pass_rate=1.0,
            total_cases=10,
            eval_names=["retrieval_gold", "claim_gold"],
        )
        thresholds = PackEvalThresholds(
            min_pass_rate=0.5, min_cases=1, required_evals=["retrieval_gold", "claim_gold"]
        )
        result = evaluate_against_thresholds("ml_safety_v1", summary, thresholds)
        assert result.meets_thresholds is True

    def test_none_summary_fails(self):
        result = evaluate_against_thresholds(
            "ml_safety_v1", None, PackEvalThresholds()
        )
        assert result.meets_thresholds is False
        assert result.total_cases == 0
        assert any(c.name == "summary_present" for c in result.checks)

    def test_to_dict_roundtrip(self):
        summary = _make_summary(pass_rate=1.0, total_cases=10)
        thresholds = PackEvalThresholds(min_pass_rate=0.9, min_cases=5)
        result = evaluate_against_thresholds("ml_safety_v1", summary, thresholds)
        d = result.to_dict()
        assert d["pack_name"] == "ml_safety_v1"
        assert d["thresholds"]["min_pass_rate"] == 0.9
        assert d["meets_thresholds"] is True
        assert isinstance(d["checks"], list)


class TestSourcePackDoctorThresholdCompliance:
    def test_doctor_includes_threshold_compliance_for_pqc_v1(self, tmp_path: Path):
        from sourcelab.sources.source_pack import doctor_source_pack

        pack_dir = tmp_path / "data" / "source_packs" / "pqc_v1"
        pack_dir.mkdir(parents=True)
        # Minimal manifest to pass structural checks
        _write_manifest(pack_dir, "pqc_v1")
        # A passing summary
        evals_dir = tmp_path / "artifacts" / "evals" / "pqc_v1"
        evals_dir.mkdir(parents=True)
        (evals_dir / "golden_eval_summary.json").write_text(
            json.dumps(_make_summary(pass_rate=1.0, total_cases=45)),
            encoding="utf-8",
        )

        result = doctor_source_pack(tmp_path, "pqc_v1")
        # The doctor currently requires more (sources/evals dirs, README) for
        # pqc_v1, so we just verify the threshold compliance field exists.
        assert "threshold_compliance" in result
        assert result["threshold_compliance"]["thresholds"]["min_pass_rate"] == 1.0
        assert result["threshold_compliance"]["meets_thresholds"] is True

    def test_doctor_flags_pack_below_threshold(self, tmp_path: Path):
        from sourcelab.sources.source_pack import doctor_source_pack

        pack_dir = tmp_path / "data" / "source_packs" / "failing"
        pack_dir.mkdir(parents=True)
        _write_manifest(
            pack_dir,
            "failing",
            eval_thresholds={"min_pass_rate": 1.0, "min_cases": 1},
        )
        evals_dir = tmp_path / "artifacts" / "evals" / "failing"
        evals_dir.mkdir(parents=True)
        (evals_dir / "golden_eval_summary.json").write_text(
            json.dumps(_make_summary(pass_rate=0.5, total_cases=10)),
            encoding="utf-8",
        )

        result = doctor_source_pack(tmp_path, "failing")
        # Even though other structural checks may fail, threshold_compliance
        # should be present and report the failure.
        assert "threshold_compliance" in result
        assert result["threshold_compliance"]["meets_thresholds"] is False
        # The strict mode adds an error for the threshold failure
        assert any("threshold" in err.lower() for err in result["errors"])
