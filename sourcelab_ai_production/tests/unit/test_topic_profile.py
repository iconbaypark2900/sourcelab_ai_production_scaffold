"""Tests for adaptive topic profiles."""

from __future__ import annotations

from pathlib import Path

from sourcelab.library.io import utc_now
from sourcelab.research.schemas import GenericnessReport, SourceCoverageReport, TopicProfileUpdate
from sourcelab.research.topic_profile import (
    apply_topic_profile_update,
    build_topic_profile_update,
    load_topic_profile,
    record_answer_submit,
)


def test_profile_update_and_apply(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    coverage = SourceCoverageReport(
        run_id="run1",
        topic="clinical evidence graph assistant",
        source_pack="biomedical_ai_v1",
        generated_at=utc_now(),
        coverage_score=0.61,
        weak_labels=["thin_lesson"],
        gaps=["No PubMed cards"],
    )
    genericness = GenericnessReport(
        run_id="run1",
        topic=coverage.topic,
        source_pack=coverage.source_pack,
        generated_at=utc_now(),
        verdict="somewhat_generic",
        genericness_score=0.42,
    )
    update = build_topic_profile_update("run1", coverage.topic, coverage.source_pack, coverage, genericness)
    profile = apply_topic_profile_update(root, update)
    assert profile.run_count == 1
    assert profile.last_coverage_score == 0.61
    assert profile.weak_label_counts.get("thin_lesson") == 1

    run_dir = root / "artifacts" / "runs" / "run1"
    run_dir.mkdir(parents=True)
    from sourcelab.library.io import save_model

    save_model(run_dir / "topic_profile_update.json", update)
    applied = record_answer_submit(root, run_dir)
    assert applied is not None
    assert applied.answer_submit_count == 1
    reloaded = load_topic_profile(root, "biomedical_ai_v1", coverage.topic)
    assert reloaded is not None
    assert reloaded.answer_submit_count == 1
