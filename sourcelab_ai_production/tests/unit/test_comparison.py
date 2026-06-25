"""Unit tests for run comparison engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from sourcelab.comparison.run_compare import compare_runs


def _find_two_runs(project_root: Path) -> list[str]:
    runs_dir = project_root / "artifacts" / "runs"
    if not runs_dir.exists():
        pytest.skip("No runs directory")
    runs = sorted(p.name for p in runs_dir.iterdir() if p.is_dir())
    if len(runs) < 2:
        pytest.skip("Need at least two runs for comparison")
    return runs[-2:]


def test_compare_runs_requires_existing_runs():
    with pytest.raises(FileNotFoundError):
        compare_runs(Path.cwd(), ["nonexistent_run_a", "nonexistent_run_b"])


def test_compare_runs_returns_structured_result():
    run_ids = _find_two_runs(Path.cwd())
    result = compare_runs(Path.cwd(), run_ids)

    assert result.run_ids == run_ids
    assert len(result.retrieval_overlap.per_run) == 2
    assert len(result.retrieval_overlap.pairwise) == 1
    assert len(result.claim_deltas.per_run) == 2
    assert len(result.proof_gate_comparison.per_run) == 2
    assert len(result.lesson_comparison.per_run) == 2
    assert result.recommendation


def test_compare_three_runs_pairwise():
    runs_dir = Path.cwd() / "artifacts" / "runs"
    if not runs_dir.exists():
        pytest.skip("No runs directory")
    runs = sorted(p.name for p in runs_dir.iterdir() if p.is_dir())
    if len(runs) < 3:
        pytest.skip("Need at least three runs")
    run_ids = runs[-3:]
    result = compare_runs(Path.cwd(), run_ids)
    assert len(result.retrieval_overlap.pairwise) == 3
