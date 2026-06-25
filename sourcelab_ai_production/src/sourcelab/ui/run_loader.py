"""Run loading utilities for the SourceLab dashboard and terminal explorer.

Instruction:
- Load and summarize run artifacts from the artifacts/runs directory.
- Provide functions for listing runs, loading artifacts, and summarizing run status.
- Used by the Streamlit dashboard, terminal explorer, and export modules.
- Missing artifacts should be handled gracefully without crashing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class RunSummary:
    """Summary of a SourceLab run."""

    run_id: str
    run_dir: str
    topic: str = ""
    harness_passed: bool | None = None
    proof_bundle_status: str = ""
    answer_score: float | None = None
    has_answer: bool = False
    rubric_alignment_score: float | None = None
    uncapped_score: float | None = None
    overall_score: float | None = None
    cap_reason: str = ""
    needs_review: bool | None = None
    human_review_reason: str = ""
    source_grounding_score: float | None = None
    concept_overlap_grounding_score: float | None = None
    citation_resolution_rate: float | None = None
    unsupported_high_risk_claims: int = 0
    human_review_count: int = 0
    artifact_count: int = 0
    created_at: str = ""
    next_task_focus: str = ""


@dataclass
class ArtifactRow:
    """Dashboard-friendly row for artifact inventory."""

    name: str
    artifact_type: str
    required: bool
    exists: bool
    validated: bool
    sha256: str = ""
    size: int = 0


def list_runs(project_root: Path) -> list[RunSummary]:
    """List all runs in artifacts/runs, sorted by run_id ascending."""
    runs_dir = project_root / "artifacts" / "runs"
    if not runs_dir.exists():
        return []

    run_dirs = sorted(
        [d for d in runs_dir.iterdir() if d.is_dir()],
        key=lambda p: p.name,
    )
    return [summarize_run(d) for d in run_dirs]


def get_latest_run(project_root: Path) -> RunSummary | None:
    """Get the most recent run summary, or None if no runs exist."""
    runs_dir = project_root / "artifacts" / "runs"
    if not runs_dir.exists():
        return None

    run_dirs = sorted(
        [d for d in runs_dir.iterdir() if d.is_dir()],
        key=lambda p: p.name,
    )
    if not run_dirs:
        return None
    return summarize_run(run_dirs[-1])


def load_run_artifact(run_dir: Path, artifact_name: str) -> str | None:
    """Load raw text content of an artifact. Returns None if missing."""
    path = run_dir / artifact_name
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def load_json_artifact(run_dir: Path, artifact_name: str) -> dict | list | None:
    """Load and parse a JSON artifact. Returns None if missing or invalid."""
    content = load_run_artifact(run_dir, artifact_name)
    if content is None:
        return None
    try:
        return json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return None


def load_markdown_artifact(run_dir: Path, artifact_name: str) -> str | None:
    """Load a markdown artifact. Returns None if missing."""
    return load_run_artifact(run_dir, artifact_name)


def _optional_float(data: dict | None, key: str) -> float | None:
    """Return a float field from a dict when present; otherwise None."""
    if not data or not isinstance(data, dict):
        return None
    if key not in data or data[key] is None:
        return None
    return float(data[key])


def derive_answer_score(run_dir: Path) -> float | None:
    """Derive the displayed answer score from learning artifacts.

    Priority:
    1. answer_review.json.overall_score
    2. answer_review.json.final_score (if present)
    3. learning_report.json.final_score
    4. learning_report.json.overall_score
    5. None when no scoring artifact exists
    """
    answer_review = load_json_artifact(run_dir, "answer_review.json")
    if answer_review and isinstance(answer_review, dict):
        score = _optional_float(answer_review, "overall_score")
        if score is not None:
            return score
        score = _optional_float(answer_review, "final_score")
        if score is not None:
            return score

    learning_report = load_json_artifact(run_dir, "learning_report.json")
    if learning_report and isinstance(learning_report, dict):
        score = _optional_float(learning_report, "final_score")
        if score is not None:
            return score
        score = _optional_float(learning_report, "overall_score")
        if score is not None:
            return score

    return None


def has_answer_submitted(run_dir: Path) -> bool:
    """Return True when the run has a submitted or scored answer."""
    return any(
        (run_dir / name).exists()
        for name in ("answer_submission.json", "answer_review.json", "learning_report.json")
    )


def load_learning_metrics(run_dir: Path) -> dict[str, float | bool | str | None]:
    """Load transparent learning metrics for summaries and exports."""
    answer_review = load_json_artifact(run_dir, "answer_review.json")
    learning_report = load_json_artifact(run_dir, "learning_report.json")
    source_grounding = load_json_artifact(run_dir, "source_grounding_review.json")

    review = answer_review if isinstance(answer_review, dict) else {}
    report = learning_report if isinstance(learning_report, dict) else {}
    grounding = source_grounding if isinstance(source_grounding, dict) else {}

    answer_score = derive_answer_score(run_dir)
    rubric_alignment_score = _optional_float(review, "rubric_alignment_score")
    if rubric_alignment_score is None:
        rubric_alignment_score = _optional_float(report, "rubric_alignment_score")

    uncapped_score = _optional_float(review, "uncapped_score")
    if uncapped_score is None:
        uncapped_score = _optional_float(report, "uncapped_score")

    cap_reason = review.get("cap_reason") or report.get("cap_reason") or ""

    needs_review: bool | None = None
    if "needs_review" in review:
        needs_review = bool(review.get("needs_review"))
    elif "human_review_flag" in report:
        needs_review = bool(report.get("human_review_flag"))

    human_review_reason = report.get("human_review_reason") or review.get("review_reason") or ""

    source_grounding_score = _optional_float(review, "source_grounding_score")
    concept_overlap_grounding_score = _optional_float(grounding, "source_grounding_score")

    return {
        "answer_score": answer_score,
        "has_answer": has_answer_submitted(run_dir),
        "rubric_alignment_score": rubric_alignment_score,
        "uncapped_score": uncapped_score,
        "overall_score": answer_score,
        "cap_reason": cap_reason,
        "needs_review": needs_review,
        "human_review_reason": human_review_reason,
        "source_grounding_score": source_grounding_score,
        "concept_overlap_grounding_score": concept_overlap_grounding_score,
    }


def load_artifact_inventory(run_dir: Path) -> list[ArtifactRow]:
    """Load artifact inventory as dashboard-friendly rows."""
    from sourcelab.harness.artifact_inventory import build_artifact_inventory

    inventory = build_artifact_inventory(run_dir)
    rows = []
    for record in inventory:
        path = Path(record.path)
        size = path.stat().st_size if path.exists() else 0
        rows.append(
            ArtifactRow(
                name=record.artifact_name,
                artifact_type=record.artifact_type,
                required=record.required,
                exists=record.exists,
                validated=record.validated,
                sha256=record.sha256,
                size=size,
            )
        )
    return rows


def summarize_run(run_dir: Path) -> RunSummary:
    """Build a RunSummary from the artifacts in run_dir."""
    run_id = run_dir.name
    created_at = ""
    try:
        stat = run_dir.stat()
        created_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
    except OSError:
        pass

    # Topic from run_manifest.json
    topic = ""
    manifest = load_json_artifact(run_dir, "run_manifest.json")
    if manifest and isinstance(manifest, dict):
        topic = manifest.get("topic", "")

    # Harness status
    harness_report = load_json_artifact(run_dir, "harness_report.json")
    harness_passed = None
    if harness_report and isinstance(harness_report, dict):
        harness_passed = harness_report.get("passed")

    # Proof summary
    proof_summary = load_json_artifact(run_dir, "proof_summary.json")
    proof_bundle_status = "unknown"
    citation_resolution_rate = None
    unsupported_high_risk_claims = 0
    human_review_count = 0
    if proof_summary and isinstance(proof_summary, dict):
        proof_bundle_status = proof_summary.get("release_gate_status", "unknown")
        citation_resolution_rate = proof_summary.get("citation_resolution_rate")
        unsupported_high_risk_claims = proof_summary.get("unsupported_high_risk_claims", 0)
        human_review_count = proof_summary.get("human_review_items", 0)

    learning_metrics = load_learning_metrics(run_dir)

    # Artifact count
    artifact_count = len([
        f for f in run_dir.iterdir()
        if f.is_file() and f.suffix in [".json", ".md", ".txt"]
    ])

    # Next task focus
    next_task = load_json_artifact(run_dir, "next_task_decision.json")
    next_task_focus = ""
    if next_task and isinstance(next_task, dict):
        next_task_focus = next_task.get("focus_area", next_task.get("reason", ""))

    return RunSummary(
        run_id=run_id,
        run_dir=str(run_dir),
        topic=topic,
        harness_passed=harness_passed,
        proof_bundle_status=proof_bundle_status,
        answer_score=learning_metrics["answer_score"],
        has_answer=bool(learning_metrics["has_answer"]),
        rubric_alignment_score=learning_metrics["rubric_alignment_score"],
        uncapped_score=learning_metrics["uncapped_score"],
        overall_score=learning_metrics["overall_score"],
        cap_reason=str(learning_metrics["cap_reason"] or ""),
        needs_review=learning_metrics["needs_review"],
        human_review_reason=str(learning_metrics["human_review_reason"] or ""),
        source_grounding_score=learning_metrics["source_grounding_score"],
        concept_overlap_grounding_score=learning_metrics["concept_overlap_grounding_score"],
        citation_resolution_rate=citation_resolution_rate,
        unsupported_high_risk_claims=unsupported_high_risk_claims,
        human_review_count=human_review_count,
        artifact_count=artifact_count,
        created_at=created_at,
        next_task_focus=next_task_focus,
    )
