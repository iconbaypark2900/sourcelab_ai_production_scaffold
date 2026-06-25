"""Adaptive Research Loop v1 — lesson evolution reports across follow-up runs."""

from __future__ import annotations

from pathlib import Path

from sourcelab.harness.proof_bundle import ProofBundle
from sourcelab.library.io import load_model, utc_now
from sourcelab.research.slugs import topic_slug
from sourcelab.research.schemas import (
    EvolutionChange,
    EvolutionVerdict,
    GenericnessReport,
    LessonEvolutionReport,
    QualityDelta,
    ResearchPlan,
    SourceCoverageReport,
)
from sourcelab.research.topic_profile import load_topic_profile
from sourcelab.ui.run_loader import list_runs, load_json_artifact


def find_previous_run_ids(
    project_root: Path,
    topic: str,
    source_pack: str,
    current_run_id: str,
) -> list[str]:
    """Return prior run IDs for the same topic slug and source pack."""
    slug = topic_slug(topic)
    previous: list[str] = []
    for summary in list_runs(project_root):
        if summary.run_id == current_run_id:
            continue
        run_dir = project_root / "artifacts" / "runs" / summary.run_id
        plan_path = run_dir / "research_plan.json"
        if plan_path.exists():
            plan = load_model(plan_path, ResearchPlan)
            if topic_slug(plan.topic) == slug and plan.source_pack == source_pack:
                previous.append(summary.run_id)
                continue
        manifest = load_json_artifact(run_dir, "run_manifest.json")
        manifest_pack = manifest.get("source_pack", "") if isinstance(manifest, dict) else ""
        manifest_topic = summary.topic or (manifest.get("topic", "") if isinstance(manifest, dict) else "")
        if manifest_topic and topic_slug(manifest_topic) == slug and manifest_pack == source_pack:
            previous.append(summary.run_id)
    return previous


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


def _compare_plans(current: ResearchPlan, previous: ResearchPlan) -> list[EvolutionChange]:
    changes: list[EvolutionChange] = []
    if current.profile_context_used and not previous.profile_context_used:
        changes.append(
            EvolutionChange(
                area="profile_adaptation",
                description="Follow-up run applied adaptive topic profile context",
            )
        )
    if current.follow_up_focus and current.follow_up_focus != previous.follow_up_focus:
        added = [f for f in current.follow_up_focus if f not in previous.follow_up_focus]
        if added:
            changes.append(
                EvolutionChange(
                    area="follow_up_focus",
                    description=f"Added follow-up sections: {', '.join(added)}",
                )
            )
    new_questions = [q for q in current.research_questions if q not in previous.research_questions]
    if new_questions:
        changes.append(
            EvolutionChange(
                area="research_questions",
                description=f"Added {len(new_questions)} profile-driven research question(s)",
            )
        )
    new_subtopics = [s.title for s in current.subtopics if s.title not in {p.title for p in previous.subtopics}]
    if new_subtopics:
        changes.append(
            EvolutionChange(
                area="subtopics",
                description=f"Added subtopics: {', '.join(new_subtopics[:4])}",
            )
        )
    if current.profile_known_gaps and not previous.profile_known_gaps:
        changes.append(
            EvolutionChange(
                area="known_gaps",
                description=f"Plan targets {len(current.profile_known_gaps)} known gap(s) from profile",
            )
        )
    return changes


def _compute_quality_delta(
    current_coverage: SourceCoverageReport | None,
    previous_coverage: SourceCoverageReport | None,
    current_genericness: GenericnessReport | None,
    previous_genericness: GenericnessReport | None,
    current_plan: ResearchPlan,
) -> QualityDelta:
    coverage_delta: float | None = None
    if current_coverage and previous_coverage:
        coverage_delta = round(current_coverage.coverage_score - previous_coverage.coverage_score, 4)

    genericness_delta: float | None = None
    if current_genericness and previous_genericness:
        genericness_delta = round(
            current_genericness.genericness_score - previous_genericness.genericness_score,
            4,
        )

    prev_gaps = set(previous_coverage.gaps if previous_coverage else [])
    curr_gaps = set(current_coverage.gaps if current_coverage else [])
    gaps_closed = sorted(prev_gaps - curr_gaps)
    gaps_new = sorted(curr_gaps - prev_gaps)

    weak_addressed: list[str] = []
    if current_plan.profile_weak_concepts and current_plan.follow_up_focus:
        weak_addressed = list(current_plan.profile_weak_concepts[:3])

    return QualityDelta(
        coverage_delta=coverage_delta,
        genericness_score_delta=genericness_delta,
        gaps_closed=gaps_closed,
        gaps_new=gaps_new,
        weak_concepts_addressed=weak_addressed,
    )


def _determine_verdict(
    previous_run_ids: list[str],
    quality_delta: QualityDelta,
) -> EvolutionVerdict:
    if not previous_run_ids:
        return "insufficient_history"

    has_metrics = (
        quality_delta.coverage_delta is not None or quality_delta.genericness_score_delta is not None
    )
    if not has_metrics:
        return "insufficient_history"

    improved_signals = 0
    worse_signals = 0

    if quality_delta.coverage_delta is not None:
        if quality_delta.coverage_delta > 0.02:
            improved_signals += 1
        elif quality_delta.coverage_delta < -0.02:
            worse_signals += 1

    if quality_delta.genericness_score_delta is not None:
        if quality_delta.genericness_score_delta < -0.03:
            improved_signals += 1
        elif quality_delta.genericness_score_delta > 0.03:
            worse_signals += 1

    if quality_delta.gaps_closed:
        improved_signals += 1
    if quality_delta.gaps_new and len(quality_delta.gaps_new) > len(quality_delta.gaps_closed):
        worse_signals += 1

    if improved_signals > worse_signals:
        return "improved"
    if worse_signals > improved_signals:
        return "worse"
    return "unchanged"


def build_lesson_evolution_report(
    project_root: Path,
    run_dir: Path,
    plan: ResearchPlan,
    coverage: SourceCoverageReport | None = None,
    genericness: GenericnessReport | None = None,
) -> LessonEvolutionReport:
    """Build an evolution report comparing the current run to prior topic history."""
    run_id = run_dir.name
    previous_run_ids = find_previous_run_ids(project_root, plan.topic, plan.source_pack, run_id)
    profile = load_topic_profile(project_root, plan.source_pack, plan.topic)
    profile_used = plan.profile_context_used or (profile is not None and profile.run_count > 0)

    changes: list[EvolutionChange] = []
    prev_coverage: SourceCoverageReport | None = None
    prev_genericness: GenericnessReport | None = None

    if previous_run_ids:
        prior_id = previous_run_ids[-1]
        prior_dir = project_root / "artifacts" / "runs" / prior_id
        prior_plan_path = prior_dir / "research_plan.json"
        if prior_plan_path.exists():
            prior_plan = load_model(prior_plan_path, ResearchPlan)
            changes = _compare_plans(plan, prior_plan)
        prev_coverage = _load_coverage(prior_dir)
        prev_genericness = _load_genericness(prior_dir)

    current_coverage = coverage or _load_coverage(run_dir)
    current_genericness = genericness or _load_genericness(run_dir)
    quality_delta = _compute_quality_delta(
        current_coverage,
        prev_coverage,
        current_genericness,
        prev_genericness,
        plan,
    )
    verdict = _determine_verdict(previous_run_ids, quality_delta)

    return LessonEvolutionReport(
        run_id=run_id,
        topic=plan.topic,
        source_pack=plan.source_pack,
        generated_at=utc_now(),
        previous_run_ids=previous_run_ids,
        profile_used=profile_used,
        changes_from_previous=changes,
        quality_delta=quality_delta,
        verdict=verdict,
    )


def render_evolution_markdown(report: LessonEvolutionReport) -> str:
    """Render a human-readable evolution report."""
    lines = [
        f"# Lesson Evolution Report — {report.topic}",
        "",
        f"- **Run:** `{report.run_id}`",
        f"- **Source pack:** `{report.source_pack}`",
        f"- **Verdict:** `{report.verdict}`",
        f"- **Profile used:** {report.profile_used}",
        f"- **Generated:** {report.generated_at.isoformat()}",
        "",
        "## Previous runs",
        "",
    ]
    if report.previous_run_ids:
        for run_id in report.previous_run_ids:
            lines.append(f"- `{run_id}`")
    else:
        lines.append("- _(none — first run for this topic)_")

    lines.extend(["", "## Quality delta", ""])
    delta = report.quality_delta
    if delta.coverage_delta is not None:
        lines.append(f"- Coverage delta: {delta.coverage_delta:+.4f}")
    if delta.genericness_score_delta is not None:
        lines.append(f"- Genericness score delta: {delta.genericness_score_delta:+.4f} (negative = less generic)")
    if delta.gaps_closed:
        lines.append("- Gaps closed:")
        for gap in delta.gaps_closed:
            lines.append(f"  - {gap}")
    if delta.gaps_new:
        lines.append("- New gaps:")
        for gap in delta.gaps_new:
            lines.append(f"  - {gap}")
    if delta.weak_concepts_addressed:
        lines.append("- Weak concepts addressed:")
        for concept in delta.weak_concepts_addressed:
            lines.append(f"  - {concept}")

    lines.extend(["", "## Changes from previous", ""])
    if report.changes_from_previous:
        for change in report.changes_from_previous:
            lines.append(f"- **{change.area}:** {change.description}")
    else:
        lines.append("- _(no recorded plan changes)_")
    lines.append("")
    return "\n".join(lines)


def write_lesson_evolution_report(
    project_root: Path,
    run_dir: Path,
    proof: ProofBundle | None,
    plan: ResearchPlan,
    coverage: SourceCoverageReport | None = None,
    genericness: GenericnessReport | None = None,
) -> LessonEvolutionReport:
    """Write lesson_evolution_report.json and .md for a run."""
    report = build_lesson_evolution_report(project_root, run_dir, plan, coverage, genericness)
    markdown = render_evolution_markdown(report)
    if proof is not None:
        proof.write_json("lesson_evolution_report.json", report.model_dump(mode="json"))
        proof.write_text("lesson_evolution_report.md", markdown)
    else:
        (run_dir / "lesson_evolution_report.json").write_text(
            report.model_dump_json(indent=2),
            encoding="utf-8",
        )
        (run_dir / "lesson_evolution_report.md").write_text(markdown, encoding="utf-8")
    return report
