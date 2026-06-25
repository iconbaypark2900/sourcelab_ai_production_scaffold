"""Adaptive topic profiles persisted under artifacts/research/topic_profiles/."""

from __future__ import annotations

from pathlib import Path

from sourcelab.library.io import load_model, save_model, utc_now
from sourcelab.research.slugs import topic_slug
from sourcelab.research.schemas import (
    GenericnessReport,
    GapClosureOrchestrationReport,
    GapClosureVerdict,
    SourceCoverageReport,
    TopicProfile,
    TopicProfileUpdate,
)


def topic_profiles_root(project_root: Path) -> Path:
    return project_root / "artifacts" / "research" / "topic_profiles"


def topic_profile_path(project_root: Path, source_pack: str, slug: str) -> Path:
    return topic_profiles_root(project_root) / source_pack / f"{slug}.json"


def load_topic_profile(project_root: Path, source_pack: str, topic: str) -> TopicProfile | None:
    path = topic_profile_path(project_root, source_pack, topic_slug(topic))
    if not path.exists():
        return None
    return load_model(path, TopicProfile)


def default_topic_profile(topic: str, source_pack: str) -> TopicProfile:
    slug = topic_slug(topic)
    return TopicProfile(
        topic=topic,
        topic_slug=slug,
        source_pack=source_pack,
        updated_at=utc_now(),
    )


def build_topic_profile_update(
    run_id: str,
    topic: str,
    source_pack: str,
    coverage: SourceCoverageReport,
    genericness: GenericnessReport,
) -> TopicProfileUpdate:
    """Build a pending topic profile update for a run."""
    return TopicProfileUpdate(
        run_id=run_id,
        topic=topic,
        topic_slug=topic_slug(topic),
        source_pack=source_pack,
        generated_at=utc_now(),
        coverage_score=coverage.coverage_score,
        weak_labels=list(coverage.weak_labels),
        genericness_verdict=genericness.verdict,
        new_gaps=list(coverage.gaps[:5]),
        applied=False,
    )


def apply_topic_profile_update(project_root: Path, update: TopicProfileUpdate) -> TopicProfile:
    """Merge a pending update into the persisted topic profile."""
    profile = load_topic_profile(project_root, update.source_pack, update.topic)
    if profile is None:
        profile = default_topic_profile(update.topic, update.source_pack)

    run_count = profile.run_count + 1
    avg_coverage = (
        (profile.avg_coverage_score * profile.run_count + update.coverage_score) / run_count
        if run_count
        else update.coverage_score
    )

    weak_counts = dict(profile.weak_label_counts)
    for label in update.weak_labels:
        weak_counts[label] = weak_counts.get(label, 0) + 1

    genericness_history = list(profile.genericness_history)
    genericness_history.append(update.genericness_verdict)
    genericness_history = genericness_history[-12:]

    gap_counts: dict[str, int] = {gap: 1 for gap in update.new_gaps}
    for gap in profile.frequent_gaps:
        gap_counts[gap] = gap_counts.get(gap, 0)
    frequent_gaps = [gap for gap, _ in sorted(gap_counts.items(), key=lambda item: item[1], reverse=True)[:8]]

    profile = profile.model_copy(
        update={
            "run_count": run_count,
            "avg_coverage_score": round(avg_coverage, 4),
            "last_coverage_score": update.coverage_score,
            "weak_label_counts": weak_counts,
            "genericness_history": genericness_history,
            "frequent_gaps": frequent_gaps,
            "last_run_id": update.run_id,
            "updated_at": utc_now(),
        }
    )

    path = topic_profile_path(project_root, update.source_pack, update.topic_slug)
    save_model(path, profile)
    return profile


def record_answer_submit(project_root: Path, run_dir: Path) -> TopicProfile | None:
    """Apply topic profile update on answer submit when pending update exists."""
    update_path = run_dir / "topic_profile_update.json"
    if not update_path.exists():
        return None
    update = load_model(update_path, TopicProfileUpdate)
    if update.applied:
        profile = load_topic_profile(project_root, update.source_pack, update.topic)
        return profile

    profile = apply_topic_profile_update(project_root, update)
    applied = update.model_copy(update={"applied": True, "generated_at": utc_now()})
    save_model(update_path, applied)

    profile = profile.model_copy(update={"answer_submit_count": profile.answer_submit_count + 1})
    save_model(topic_profile_path(project_root, update.source_pack, update.topic_slug), profile)
    return profile


def record_orchestration_completion(
    project_root: Path,
    report: GapClosureOrchestrationReport,
) -> TopicProfile:
    """Merge orchestration metadata into the adaptive topic profile."""
    profile = load_topic_profile(project_root, report.source_pack, report.topic)
    if profile is None:
        profile = default_topic_profile(report.topic, report.source_pack)

    orchestration_runs = list(profile.orchestration_runs)
    if report.run_id not in orchestration_runs:
        orchestration_runs.append(report.run_id)

    followup_chain = list(profile.followup_chain)
    if report.run_id and report.run_id not in followup_chain:
        followup_chain.append(report.run_id)
    if report.followup_run_id and report.followup_run_id not in followup_chain:
        followup_chain.append(report.followup_run_id)

    last_verdict: GapClosureVerdict | None = report.gap_closure_verdict or profile.last_gap_closure_verdict

    profile = profile.model_copy(
        update={
            "orchestration_runs": orchestration_runs,
            "followup_chain": followup_chain,
            "last_gap_closure_verdict": last_verdict,
            "last_run_id": report.followup_run_id or report.run_id,
            "updated_at": utc_now(),
        }
    )
    save_model(topic_profile_path(project_root, report.source_pack, profile.topic_slug), profile)
    return profile
