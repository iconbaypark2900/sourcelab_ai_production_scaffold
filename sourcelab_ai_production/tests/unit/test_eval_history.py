"""Unit tests for golden eval history snapshot and reader functions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sourcelab.evals.runner import (
    read_eval_history,
    snapshot_eval_history,
)
from sourcelab.evals.schemas import GoldenEvalSummary


def _make_summary(
    pack_name: str = "ml_safety_v1",
    total_cases: int = 12,
    total_passed: int = 12,
) -> GoldenEvalSummary:
    return GoldenEvalSummary(
        pack_name=pack_name,
        total_evals=4,
        total_cases=total_cases,
        total_passed=total_passed,
        total_failed=total_cases - total_passed,
        overall_pass_rate=total_passed / total_cases if total_cases else 0.0,
        eval_reports=[],
    )


class TestSnapshotEvalHistory:
    def test_writes_snapshot_to_history_dir(self, tmp_path: Path):
        output_dir = tmp_path / "evals"
        output_dir.mkdir()
        summary = _make_summary()
        snapshot_path = snapshot_eval_history(summary, output_dir)

        assert snapshot_path.exists()
        assert snapshot_path.parent == output_dir / "history"
        assert snapshot_path.suffix == ".json"
        # Filename is a UTC timestamp with Z suffix
        assert snapshot_path.stem.endswith("Z")

    def test_snapshot_payload_includes_summary_fields(self, tmp_path: Path):
        output_dir = tmp_path / "evals"
        output_dir.mkdir()
        summary = _make_summary()
        snapshot_path = snapshot_eval_history(summary, output_dir)

        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        assert payload["pack_name"] == "ml_safety_v1"
        assert payload["total_cases"] == 12
        assert payload["total_passed"] == 12
        assert payload["overall_pass_rate"] == 1.0
        assert "snapshot_at" in payload

    def test_override_timestamp(self, tmp_path: Path):
        from datetime import datetime, timezone

        output_dir = tmp_path / "evals"
        output_dir.mkdir()
        summary = _make_summary()
        ts = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)
        snapshot_path = snapshot_eval_history(summary, output_dir, timestamp=ts)

        assert snapshot_path.stem == "20260624T120000Z"

    def test_multiple_snapshots_accumulate(self, tmp_path: Path):
        from datetime import datetime, timezone

        output_dir = tmp_path / "evals"
        output_dir.mkdir()
        for hour in range(3):
            ts = datetime(2026, 6, 24, hour, 0, 0, tzinfo=timezone.utc)
            snapshot_eval_history(_make_summary(), output_dir, timestamp=ts)

        history_dir = output_dir / "history"
        files = sorted(history_dir.iterdir())
        assert len(files) == 3
        assert files[0].stem == "20260624T000000Z"
        assert files[2].stem == "20260624T020000Z"


class TestReadEvalHistory:
    def test_returns_empty_list_for_missing_dir(self, tmp_path: Path):
        assert read_eval_history("unknown_pack", tmp_path) == []

    def test_returns_empty_list_for_empty_dir(self, tmp_path: Path):
        (tmp_path / "artifacts" / "evals" / "ml_safety_v1" / "history").mkdir(
            parents=True
        )
        assert read_eval_history("ml_safety_v1", tmp_path) == []

    def test_reads_snapshots_newest_first(self, tmp_path: Path):
        history_dir = tmp_path / "artifacts" / "evals" / "ml_safety_v1" / "history"
        history_dir.mkdir(parents=True)
        for day in (1, 2, 3):
            payload = {"snapshot_at": f"2026-06-{day:02d}", "overall_pass_rate": 0.5 + day * 0.1}
            (history_dir / f"2026060{day}T000000Z.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )

        history = read_eval_history("ml_safety_v1", tmp_path)
        assert len(history) == 3
        # Newest first by filename
        assert history[0]["snapshot_at"] == "2026-06-03"
        assert history[2]["snapshot_at"] == "2026-06-01"

    def test_respects_limit(self, tmp_path: Path):
        history_dir = tmp_path / "artifacts" / "evals" / "ml_safety_v1" / "history"
        history_dir.mkdir(parents=True)
        for day in range(1, 8):  # 7 snapshots
            payload = {"snapshot_at": f"2026-06-{day:02d}", "overall_pass_rate": 0.5}
            (history_dir / f"2026060{day}T000000Z.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )

        history = read_eval_history("ml_safety_v1", tmp_path, limit=3)
        assert len(history) == 3

    def test_skips_non_json_files(self, tmp_path: Path):
        history_dir = tmp_path / "artifacts" / "evals" / "ml_safety_v1" / "history"
        history_dir.mkdir(parents=True)
        (history_dir / "20260624T000000Z.json").write_text(
            json.dumps({"snapshot_at": "2026-06-24", "overall_pass_rate": 1.0}),
            encoding="utf-8",
        )
        (history_dir / "README.md").write_text("not a snapshot", encoding="utf-8")

        history = read_eval_history("ml_safety_v1", tmp_path)
        assert len(history) == 1

    def test_skips_invalid_json_files(self, tmp_path: Path):
        history_dir = tmp_path / "artifacts" / "evals" / "ml_safety_v1" / "history"
        history_dir.mkdir(parents=True)
        (history_dir / "broken.json").write_text("not json", encoding="utf-8")
        (history_dir / "good.json").write_text(
            json.dumps({"snapshot_at": "2026-06-24", "overall_pass_rate": 1.0}),
            encoding="utf-8",
        )

        history = read_eval_history("ml_safety_v1", tmp_path)
        assert len(history) == 1
        assert history[0]["snapshot_at"] == "2026-06-24"
