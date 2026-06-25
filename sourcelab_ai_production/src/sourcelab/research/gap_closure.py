"""Gap closure report comparing weak baseline vs follow-up lesson runs."""

from __future__ import annotations

from pathlib import Path

from sourcelab.library.io import load_model, utc_now
from sourcelab.research.evolution import find_previous_run_ids
from sourcelab.research.schemas import (
    GapClosureOrchestrationReport,
    GapClosureReport,
    GapClosureVerdict,
    GenericnessReport,
    LibraryExpansionExecution,
    ResearchPlan,
    RetrievalStrategy,
    SourceCoverageReport,
)


def _load_coverage(run_dir: Path) -> SourceCoverageReport | None:
    path = run_dir / "source_coverage_report.json"
    if not path.exists():
        return None
    return load_model(path, SourceCoverageReport)


def _load_genericness(run_dir: Path) -> GenericnessReport | None:
    path = run_dir / "genericness_report.json"
    if not path.exists():
        return None
    return load_model(path, GenericnessReport)


def _load_strategy(run_dir: Path) -> RetrievalStrategy | None:
    path = run_dir / "retrieval_strategy.json"
    if not path.exists():
        return None
    return load_model(path, RetrievalStrategy)


def _load_expansion_execution(run_dir: Path) -> LibraryExpansionExecution | None:
    path = run_dir / "library_expansion_execution.json"
    if not path.exists():
        return None
    return load_model(path, LibraryExpansionExecution)


def _load_orchestration(run_dir: Path) -> GapClosureOrchestrationReport | None:
    path = run_dir / "gap_closure_orchestration.json"
    if not path.exists():
        return None
    return load_model(path, GapClosureOrchestrationReport)


def _resolve_chain_origin_baseline(
    project_root: Path,
    follow_up_run_id: str,
    previous_run_ids: list[str],
) -> str | None:
    """Walk orchestration followup_run_id links to the chain origin run."""
    chain_parents: dict[str, str] = {}
    for run_id in previous_run_ids:
        run_dir = project_root / "artifacts" / "runs" / run_id
        orchestration = _load_orchestration(run_dir)
        if orchestration and orchestration.followup_run_id:
            chain_parents[orchestration.followup_run_id] = run_id

    if follow_up_run_id not in chain_parents:
        return None

    current = follow_up_run_id
    visited: set[str] = set()
    while current in chain_parents and current not in visited:
        visited.add(current)
        current = chain_parents[current]
    return current


def _find_baseline_run_id(
    project_root: Path,
    topic: str,
    source_pack: str,
    follow_up_run_id: str,
    previous_run_ids: list[str],
) -> str | None:
    """Pick the weak baseline run — prefer persisted baseline_run_id from expansion execution."""
    chain_origin = _resolve_chain_origin_baseline(project_root, follow_up_run_id, previous_run_ids)
    if chain_origin:
        return chain_origin

    if not previous_run_ids:
        return None

    for run_id in reversed(previous_run_ids):
        run_dir = project_root / "artifacts" / "runs" / run_id
        execution = _load_expansion_execution(run_dir)
        if execution is None:
            continue
        if execution.baseline_run_id:
            return execution.baseline_run_id
        return run_id

    expansion_runs = [
        run_id
        for run_id in previous_run_ids
        if (project_root / "artifacts" / "runs" / run_id / "library_expansion_execution.json").exists()
    ]
    if expansion_runs:
        return expansion_runs[-1]

    weak_runs: list[str] = []
    for run_id in previous_run_ids:
        run_dir = project_root / "artifacts" / "runs" / run_id
        coverage = _load_coverage(run_dir)
        if coverage and (
            coverage.coverage_score < 0.5
            or coverage.weak_labels
            or coverage.gaps
        ):
            weak_runs.append(run_id)
    if weak_runs:
        return weak_runs[0]

    return previous_run_ids[0] if previous_run_ids else None


def _new_sources_used(baseline: RetrievalStrategy | None, follow_up: RetrievalStrategy | None) -> list[str]:
    if not baseline or not follow_up:
        return []
    before = {hit.source_id for hit in baseline.hits}
    after = {hit.source_id for hit in follow_up.hits}
    return sorted(after - before)


def _new_library_cards_used(baseline: RetrievalStrategy | None, follow_up: RetrievalStrategy | None) -> list[str]:
    if not baseline or not follow_up:
        return []
    before = {hit.library_card_id for hit in baseline.hits if hit.library_card_id}
    after = {hit.library_card_id for hit in follow_up.hits if hit.library_card_id}
    return sorted(after - before)


def _determine_gap_closure_verdict(
    coverage_before: SourceCoverageReport | None,
    coverage_after: SourceCoverageReport | None,
    genericness_before: GenericnessReport | None,
    genericness_after: GenericnessReport | None,
    gaps_closed: list[str],
    gaps_remaining: list[str],
    gaps_new: list[str],
) -> GapClosureVerdict:
    if not coverage_before or not coverage_after:
        return "insufficient_data"

    improved_signals = 0
    worse_signals = 0

    coverage_delta = coverage_after.coverage_score - coverage_before.coverage_score
    if coverage_delta > 0.02:
        improved_signals += 1
    elif coverage_delta < -0.02:
        worse_signals += 1

    if genericness_before and genericness_after:
        genericness_delta = genericness_after.genericness_score - genericness_before.genericness_score
        if genericness_delta < -0.03:
            improved_signals += 1
        elif genericness_delta > 0.03:
            worse_signals += 1

    if gaps_closed:
        improved_signals += 1
    if gaps_new and len(gaps_new) > len(gaps_closed):
        worse_signals += 1

    if improved_signals == 0 and worse_signals == 0:
        return "unchanged"
    if improved_signals > worse_signals:
        return "improved"
    if worse_signals > improved_signals:
        return "worse"
    return "unchanged"


def build_gap_closure_report(
    project_root: Path,
    run_dir: Path,
    plan: ResearchPlan,
) -> GapClosureReport:
    """Compare baseline weak run vs follow-up run for gap closure."""
    follow_up_run_id = run_dir.name
    previous_run_ids = find_previous_run_ids(
        project_root,
        plan.topic,
        plan.source_pack,
        follow_up_run_id,
    )
    baseline_run_id = _find_baseline_run_id(
        project_root,
        plan.topic,
        plan.source_pack,
        follow_up_run_id,
        previous_run_ids,
    )

    baseline_dir = (
        project_root / "artifacts" / "runs" / baseline_run_id if baseline_run_id else None
    )
    baseline_coverage = _load_coverage(baseline_dir) if baseline_dir else None
    follow_up_coverage = _load_coverage(run_dir)

    baseline_genericness = _load_genericness(baseline_dir) if baseline_dir else None
    follow_up_genericness = _load_genericness(run_dir)

    baseline_strategy = _load_strategy(baseline_dir) if baseline_dir else None
    follow_up_strategy = _load_strategy(run_dir)

    prev_gaps = set(baseline_coverage.gaps if baseline_coverage else [])
    curr_gaps = set(follow_up_coverage.gaps if follow_up_coverage else [])
    gaps_closed = sorted(prev_gaps - curr_gaps)
    gaps_remaining = sorted(curr_gaps)
    gaps_new = sorted(curr_gaps - prev_gaps)

    verdict = _determine_gap_closure_verdict(
        baseline_coverage,
        follow_up_coverage,
        baseline_genericness,
        follow_up_genericness,
        gaps_closed,
        gaps_remaining,
        gaps_new,
    )

    return GapClosureReport(
        run_id=follow_up_run_id,
        topic=plan.topic,
        source_pack=plan.source_pack,
        generated_at=utc_now(),
        baseline_run_id=baseline_run_id,
        follow_up_run_id=follow_up_run_id,
        coverage_score_before=baseline_coverage.coverage_score if baseline_coverage else None,
        coverage_score_after=follow_up_coverage.coverage_score if follow_up_coverage else None,
        genericness_before=baseline_genericness.genericness_score if baseline_genericness else None,
        genericness_after=follow_up_genericness.genericness_score if follow_up_genericness else None,
        missing_evidence_before=sorted(prev_gaps),
        missing_evidence_after=sorted(curr_gaps),
        new_sources_used=_new_sources_used(baseline_strategy, follow_up_strategy),
        new_library_cards_used=_new_library_cards_used(baseline_strategy, follow_up_strategy),
        gaps_closed=gaps_closed,
        gaps_remaining=gaps_remaining,
        verdict=verdict,
    )


def render_gap_closure_markdown(report: GapClosureReport) -> str:
    """Render a human-readable gap closure report."""
    lines = [
        f"# Gap Closure Report — {report.topic}",
        "",
        f"- **Follow-up run:** `{report.follow_up_run_id}`",
        f"- **Baseline run:** `{report.baseline_run_id or 'unknown'}`",
        f"- **Source pack:** `{report.source_pack}`",
        f"- **Verdict:** `{report.verdict}`",
        f"- **Generated:** {report.generated_at.isoformat()}",
        "",
        "## Coverage & genericness",
        "",
    ]
    if report.coverage_score_before is not None and report.coverage_score_after is not None:
        delta = report.coverage_score_after - report.coverage_score_before
        lines.append(
            f"- Coverage: {report.coverage_score_before:.3f} → {report.coverage_score_after:.3f} ({delta:+.3f})"
        )
    if report.genericness_before is not None and report.genericness_after is not None:
        delta = report.genericness_after - report.genericness_before
        lines.append(
            f"- Genericness: {report.genericness_before:.3f} → {report.genericness_after:.3f} ({delta:+.3f})"
        )

    lines.extend(["", "## Gaps", ""])
    if report.gaps_closed:
        lines.append("- Closed:")
        for gap in report.gaps_closed:
            lines.append(f"  - {gap}")
    if report.gaps_remaining:
        lines.append("- Remaining:")
        for gap in report.gaps_remaining:
            lines.append(f"  - {gap}")

    lines.extend(["", "## New evidence used", ""])
    if report.new_sources_used:
        lines.append(f"- New sources: {', '.join(report.new_sources_used)}")
    if report.new_library_cards_used:
        lines.append(f"- New library cards: {', '.join(report.new_library_cards_used)}")
    if not report.new_sources_used and not report.new_library_cards_used:
        lines.append("- _(none detected)_")

    lines.append("")
    return "\n".join(lines)


def write_gap_closure_report(
    project_root: Path,
    run_dir: Path,
    plan: ResearchPlan,
) -> GapClosureReport:
    """Write gap_closure_report.json and .md."""
    report = build_gap_closure_report(project_root, run_dir, plan)
    (run_dir / "gap_closure_report.json").write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (run_dir / "gap_closure_report.md").write_text(
        render_gap_closure_markdown(report),
        encoding="utf-8",
    )
    return report
