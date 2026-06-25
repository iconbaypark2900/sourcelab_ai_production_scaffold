"""Tests for the UI module: run_loader, terminal, and export."""

import json
from pathlib import Path

import pytest

from sourcelab.ui.run_loader import (
    RunSummary,
    ArtifactRow,
    list_runs,
    get_latest_run,
    load_run_artifact,
    load_json_artifact,
    load_markdown_artifact,
    summarize_run,
)
from sourcelab.ui.terminal import print_run_summary, print_run_list
from sourcelab.ui.export import (
    generate_markdown_report,
    generate_html_report,
    export_run,
)


def _create_run_dir(base: Path, run_id: str, **kwargs) -> Path:
    """Create a run directory with specified artifacts."""
    run_dir = base / "artifacts" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Create run_manifest.json
    manifest = {
        "topic": kwargs.get("topic", "test topic"),
        "run_id": run_id,
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    # Create harness_report.json
    harness = {
        "passed": kwargs.get("harness_passed", True),
        "artifact_count": kwargs.get("artifact_count", 5),
        "blocking_failures": [],
        "warnings": [],
    }
    (run_dir / "harness_report.json").write_text(json.dumps(harness), encoding="utf-8")

    # Create proof_summary.json
    proof = {
        "release_gate_status": kwargs.get("proof_status", "pass"),
        "answer_score": kwargs.get("answer_score", 0.75),
        "citation_resolution_rate": kwargs.get("citation_rate", 0.85),
        "unsupported_high_risk_claims": kwargs.get("unsupported_claims", 0),
        "human_review_items": kwargs.get("human_review_count", 0),
    }
    (run_dir / "proof_summary.json").write_text(json.dumps(proof), encoding="utf-8")

    if kwargs.get("answer_review") is not None:
        (run_dir / "answer_review.json").write_text(
            json.dumps(kwargs["answer_review"]),
            encoding="utf-8",
        )
    if kwargs.get("learning_report") is not None:
        (run_dir / "learning_report.json").write_text(
            json.dumps(kwargs["learning_report"]),
            encoding="utf-8",
        )
    if kwargs.get("source_grounding_review") is not None:
        (run_dir / "source_grounding_review.json").write_text(
            json.dumps(kwargs["source_grounding_review"]),
            encoding="utf-8",
        )
    if kwargs.get("has_answer_submission"):
        submission = {"topic": kwargs.get("topic", "test topic"), "answer_text": "sample answer"}
        (run_dir / "answer_submission.json").write_text(json.dumps(submission), encoding="utf-8")

    # Create optional artifacts
    if kwargs.get("has_lesson"):
        (run_dir / "generated_lesson.md").write_text("# Lesson\n\nTest content.", encoding="utf-8")
    if kwargs.get("has_grounding"):
        (run_dir / "grounding_report.md").write_text("# Grounding Report\n\nTest.", encoding="utf-8")
    if kwargs.get("has_learning"):
        (run_dir / "learning_report.md").write_text("# Learning Report\n\nTest.", encoding="utf-8")
    if kwargs.get("has_next_task"):
        next_task = {
            "format": "architecture_review",
            "difficulty": 3,
            "focus_area": "crypto inventory",
            "reason": "Weakness in area X",
        }
        (run_dir / "next_task_decision.json").write_text(json.dumps(next_task), encoding="utf-8")

    return run_dir


# --- run_loader tests ---


def test_list_runs_empty(tmp_path):
    """list_runs returns empty list when no runs exist."""
    runs = list_runs(tmp_path)
    assert runs == []


def test_list_runs_with_runs(tmp_path):
    """list_runs returns summaries for all runs."""
    _create_run_dir(tmp_path, "run_20250101_120000", topic="topic A")
    _create_run_dir(tmp_path, "run_20250102_120000", topic="topic B")

    runs = list_runs(tmp_path)
    assert len(runs) == 2
    assert runs[0].topic == "topic A"
    assert runs[1].topic == "topic B"


def test_get_latest_run_none(tmp_path):
    """get_latest_run returns None when no runs exist."""
    assert get_latest_run(tmp_path) is None


def test_get_latest_run_returns_last(tmp_path):
    """get_latest_run returns the last run by ID."""
    _create_run_dir(tmp_path, "run_001", topic="first")
    _create_run_dir(tmp_path, "run_002", topic="second")

    latest = get_latest_run(tmp_path)
    assert latest is not None
    assert latest.run_id == "run_002"
    assert latest.topic == "second"


def test_load_run_artifact_exists(tmp_path):
    """load_run_artifact returns content when file exists."""
    run_dir = _create_run_dir(tmp_path, "run_001")
    content = load_run_artifact(run_dir, "run_manifest.json")
    assert content is not None
    assert "topic" in content


def test_load_run_artifact_missing(tmp_path):
    """load_run_artifact returns None when file is missing."""
    run_dir = _create_run_dir(tmp_path, "run_001")
    content = load_run_artifact(run_dir, "nonexistent.json")
    assert content is None


def test_load_json_artifact_exists(tmp_path):
    """load_json_artifact returns parsed JSON when file exists."""
    run_dir = _create_run_dir(tmp_path, "run_001")
    data = load_json_artifact(run_dir, "run_manifest.json")
    assert data is not None
    assert isinstance(data, dict)
    assert data["topic"] == "test topic"


def test_load_json_artifact_invalid_json(tmp_path):
    """load_json_artifact returns None when JSON is invalid."""
    run_dir = _create_run_dir(tmp_path, "run_001")
    (run_dir / "bad.json").write_text("not json {{{", encoding="utf-8")
    data = load_json_artifact(run_dir, "bad.json")
    assert data is None


def test_load_markdown_artifact(tmp_path):
    """load_markdown_artifact returns content when file exists."""
    run_dir = _create_run_dir(tmp_path, "run_001", has_lesson=True)
    content = load_markdown_artifact(run_dir, "generated_lesson.md")
    assert content is not None
    assert "# Lesson" in content


def test_summarize_run_basic(tmp_path):
    """summarize_run builds a RunSummary from artifacts."""
    run_dir = _create_run_dir(
        tmp_path,
        "run_20250101",
        topic="crypto migration",
        harness_passed=True,
        answer_score=0.0,
        citation_rate=0.90,
        has_answer_submission=True,
        answer_review={"overall_score": 0.85, "topic": "crypto migration"},
    )
    summary = summarize_run(run_dir)
    assert summary.run_id == "run_20250101"
    assert summary.topic == "crypto migration"
    assert summary.harness_passed is True
    assert summary.answer_score == 0.85
    assert summary.has_answer is True
    assert summary.citation_resolution_rate == 0.90
    assert summary.proof_bundle_status == "pass"


def test_summarize_run_prefers_answer_review_over_stale_proof_summary(tmp_path):
    """Run summary reads answer_review.overall_score instead of proof_summary.answer_score."""
    run_dir = _create_run_dir(
        tmp_path,
        "run_scored",
        answer_score=0.0,
        has_answer_submission=True,
        answer_review={"overall_score": 1.0, "topic": "test topic"},
    )
    summary = summarize_run(run_dir)
    assert summary.answer_score == 1.0


def test_summarize_run_falls_back_to_learning_report_final_score(tmp_path):
    """Run summary falls back to learning_report.final_score when answer_review is absent."""
    run_dir = _create_run_dir(
        tmp_path,
        "run_learning_only",
        answer_score=0.0,
        has_answer_submission=True,
        learning_report={"final_score": 0.72, "overall_score": 0.65, "topic": "test topic"},
    )
    summary = summarize_run(run_dir)
    assert summary.answer_score == 0.72


def test_summarize_run_missing_answer_score_is_none_not_zero(tmp_path):
    """Missing answer score is null, not 0.00, when no scoring artifact exists."""
    run_dir = _create_run_dir(tmp_path, "run_unscored", answer_score=0.0)
    summary = summarize_run(run_dir)
    assert summary.answer_score is None
    assert summary.has_answer is False


def test_summarize_run_capped_answer_includes_uncapped_and_cap_reason(tmp_path):
    """Capped answer includes uncapped_score and cap_reason in the summary."""
    run_dir = _create_run_dir(
        tmp_path,
        "run_capped",
        has_answer_submission=True,
        answer_review={
            "overall_score": 0.09,
            "uncapped_score": 1.0,
            "cap_reason": "Unsupported high-risk claim detected",
            "needs_review": True,
            "review_reason": "Needs human review",
            "topic": "test topic",
        },
    )
    summary = summarize_run(run_dir)
    assert summary.answer_score == 0.09
    assert summary.uncapped_score == 1.0
    assert summary.cap_reason == "Unsupported high-risk claim detected"
    assert summary.needs_review is True
    assert summary.human_review_reason == "Needs human review"


def test_summarize_run_missing_artifacts(tmp_path):
    """summarize_run handles missing artifacts gracefully."""
    run_dir = tmp_path / "artifacts" / "runs" / "empty_run"
    run_dir.mkdir(parents=True)
    summary = summarize_run(run_dir)
    assert summary.run_id == "empty_run"
    assert summary.topic == ""
    assert summary.harness_passed is None
    assert summary.answer_score is None


# --- terminal tests ---


def test_print_run_summary(capsys):
    """print_run_summary prints formatted output."""
    summary = RunSummary(
        run_id="run_001",
        run_dir="/tmp/run",
        topic="test topic",
        harness_passed=True,
        proof_bundle_status="pass",
        answer_score=0.75,
        has_answer=True,
        citation_resolution_rate=0.85,
        artifact_count=5,
    )
    print_run_summary(summary)
    captured = capsys.readouterr()
    assert "run_001" in captured.out
    assert "test topic" in captured.out
    assert "PASS" in captured.out
    assert "0.75" in captured.out


def test_print_run_summary_missing_answer_score_shows_na(capsys):
    """print_run_summary shows N/A when no answer was submitted."""
    summary = RunSummary(
        run_id="run_003",
        run_dir="/tmp/run",
        topic="test topic",
        harness_passed=True,
    )
    print_run_summary(summary)
    captured = capsys.readouterr()
    assert "Answer score:    N/A" in captured.out


def test_print_run_summary_capped_answer_shows_cap_details(capsys):
    """print_run_summary shows uncapped score and cap reason when capped."""
    summary = RunSummary(
        run_id="run_004",
        run_dir="/tmp/run",
        topic="test topic",
        harness_passed=True,
        has_answer=True,
        answer_score=0.09,
        uncapped_score=1.0,
        cap_reason="Unsupported high-risk claim detected",
        needs_review=True,
    )
    print_run_summary(summary)
    captured = capsys.readouterr()
    assert "Answer score:    0.09" in captured.out
    assert "Uncapped score:  1.00" in captured.out
    assert "Cap reason:      Unsupported high-risk claim detected" in captured.out
    assert "Needs review:    Yes" in captured.out


def test_cmd_runs_latest_shows_correct_score(tmp_path, monkeypatch, capsys):
    """sourcelab runs latest shows corrected score from answer_review."""
    _create_run_dir(
        tmp_path,
        "run_latest",
        answer_score=0.0,
        has_answer_submission=True,
        answer_review={"overall_score": 1.0, "topic": "test topic"},
    )
    monkeypatch.chdir(tmp_path)

    from sourcelab.cli import cmd_runs_latest
    from argparse import Namespace

    cmd_runs_latest(Namespace())
    captured = capsys.readouterr()
    assert "Answer score:    1.00" in captured.out
    assert "Answer score:    0.00" not in captured.out


def test_print_run_summary_harness_fail(capsys):
    """print_run_summary shows FAIL for failed harness."""
    summary = RunSummary(
        run_id="run_002",
        run_dir="/tmp/run",
        harness_passed=False,
    )
    print_run_summary(summary)
    captured = capsys.readouterr()
    assert "FAIL" in captured.out


def test_print_run_list(capsys):
    """print_run_list prints a table of runs."""
    summaries = [
        RunSummary(run_id="run_001", run_dir="/tmp/1", topic="topic A", harness_passed=True, answer_score=0.8),
        RunSummary(run_id="run_002", run_dir="/tmp/2", topic="topic B", harness_passed=False),
    ]
    print_run_list(summaries)
    captured = capsys.readouterr()
    assert "run_001" in captured.out
    assert "run_002" in captured.out
    assert "Total: 2 run(s)" in captured.out


def test_print_run_list_empty(capsys):
    """print_run_list prints message when no runs found."""
    print_run_list([])
    captured = capsys.readouterr()
    assert "No runs found" in captured.out


# --- export tests ---


def test_generate_markdown_report(tmp_path):
    """generate_markdown_report produces valid markdown."""
    run_dir = _create_run_dir(
        tmp_path,
        "run_001",
        has_lesson=True,
        has_grounding=True,
        has_answer_submission=True,
        answer_review={
            "overall_score": 0.09,
            "uncapped_score": 1.0,
            "rubric_alignment_score": 0.8075,
            "cap_reason": "Unsupported high-risk claim detected",
            "needs_review": True,
            "review_reason": "Needs human review",
            "source_grounding_score": 0.35,
            "topic": "test topic",
        },
        source_grounding_review={"source_grounding_score": 0.179},
    )
    md = generate_markdown_report(run_dir)
    assert "# SourceLab Run Report: run_001" in md
    assert "## Overview" in md
    assert "**Answer Score:** 0.09" in md
    assert "**Uncapped Score:** 1.00" in md
    assert "**Cap Reason:** Unsupported high-risk claim detected" in md
    assert "**Concept Overlap Grounding Score:** 0.18" in md
    assert "## Generated Lesson" in md
    assert "## Grounding Report" in md
    assert "## Artifact Inventory" in md


def test_generate_markdown_report_missing_answer_score(tmp_path):
    """generate_markdown_report shows N/A when no answer was submitted."""
    run_dir = _create_run_dir(tmp_path, "run_001")
    md = generate_markdown_report(run_dir)
    assert "**Answer Score:** N/A (no answer submitted)" in md


def test_generate_html_report():
    """generate_html_report produces valid HTML."""
    md = "# Title\n\n- item1\n- item2\n\n## Section\n\n| A | B |\n|---|---|\n| 1 | 2 |"
    html = generate_html_report(md)
    assert "<!DOCTYPE html>" in html
    assert "<h1>Title</h1>" in html
    assert "<h2>Section</h2>" in html
    assert "<li>item1</li>" in html
    assert "<table>" in html
    assert "<th>A</th>" in html
    assert "<td>1</td>" in html


def test_export_run_markdown(tmp_path):
    """export_run creates a markdown file."""
    _create_run_dir(tmp_path, "run_001")
    path = export_run(tmp_path, run_id="run_001", fmt="markdown")
    assert path.exists()
    assert path.suffix == ".md"
    content = path.read_text(encoding="utf-8")
    assert "# SourceLab Run Report" in content


def test_export_run_html(tmp_path):
    """export_run creates an HTML file."""
    _create_run_dir(tmp_path, "run_001")
    path = export_run(tmp_path, run_id="run_001", fmt="html")
    assert path.exists()
    assert path.suffix == ".html"
    content = path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content


def test_export_run_latest(tmp_path):
    """export_run with run_id='latest' exports the most recent run."""
    _create_run_dir(tmp_path, "run_001", topic="first")
    _create_run_dir(tmp_path, "run_002", topic="second")
    path = export_run(tmp_path, run_id="latest", fmt="markdown")
    content = path.read_text(encoding="utf-8")
    assert "run_002" in content


def test_export_run_no_runs_dir(tmp_path):
    """export_run raises FileNotFoundError when no runs directory exists."""
    with pytest.raises(FileNotFoundError, match="No runs directory"):
        export_run(tmp_path, run_id="latest")


def test_export_run_no_runs(tmp_path):
    """export_run raises FileNotFoundError when no runs exist."""
    runs_dir = tmp_path / "artifacts" / "runs"
    runs_dir.mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="No runs found"):
        export_run(tmp_path, run_id="latest")


def test_export_run_nonexistent_run(tmp_path):
    """export_run raises FileNotFoundError for nonexistent run ID."""
    runs_dir = tmp_path / "artifacts" / "runs"
    runs_dir.mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="Run not found"):
        export_run(tmp_path, run_id="nonexistent")


def test_api_run_summary_returns_corrected_score(tmp_path, monkeypatch):
    """API run summary returns corrected score from learning artifacts."""
    run_id = "run_api_score"
    _create_run_dir(
        tmp_path,
        run_id,
        answer_score=0.0,
        has_answer_submission=True,
        answer_review={
            "overall_score": 1.0,
            "rubric_alignment_score": 1.0,
            "uncapped_score": 1.0,
            "topic": "test topic",
        },
    )
    monkeypatch.chdir(tmp_path)

    from sourcelab.api.services import get_run_summary

    summary = get_run_summary(run_id)
    assert summary["answer_score"] == 1.0
    assert summary["overall_score"] == 1.0
    assert summary["has_answer"] is True
    assert summary["rubric_alignment_score"] == 1.0
