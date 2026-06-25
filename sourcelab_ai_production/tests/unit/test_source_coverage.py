"""Tests for source coverage metrics."""

from __future__ import annotations

from sourcelab.library.io import utc_now
from sourcelab.research.planner import build_research_plan
from sourcelab.research.schemas import LabeledRetrievalHit, RetrievalQuery, RetrievalStrategy
from sourcelab.research.source_coverage import build_source_coverage_report, detect_weak_labels


def _strategy_with_hits(run_id: str, topic: str, pack: str, hits: list[LabeledRetrievalHit]) -> RetrievalStrategy:
    return RetrievalStrategy(
        run_id=run_id,
        topic=topic,
        source_pack=pack,
        generated_at=utc_now(),
        queries=[
            RetrievalQuery(query_id=f"{run_id}_topic", text=topic, priority="high"),
        ],
        origins_enabled=["source_pack", "library_silver", "promoted_candidate"],
        source_pack_source_count=2,
        library_silver_card_count=5,
        promoted_candidate_count=3,
        hits=hits,
        selected_chunk_ids=[hit.chunk_id for hit in hits],
    )


def test_insufficient_evidence_weak_label():
    plan = build_research_plan("run1", "quantum hybrid portfolio optimizer", "quantum_finance_v1")
    strategy = _strategy_with_hits("run1", plan.topic, plan.source_pack, [])
    coverage = build_source_coverage_report(strategy, plan)
    assert "insufficient_evidence" in coverage.weak_labels
    assert coverage.coverage_score < 0.5


def test_coverage_improves_with_labeled_hits():
    plan = build_research_plan("run2", "clinical evidence graph assistant", "biomedical_ai_v1")
    hits = [
        LabeledRetrievalHit(
            chunk_id="c1",
            source_id="s1",
            library_card_id="card1",
            title="Clinical graph",
            score=0.9,
            trust_tier="B",
            text_preview="clinical evidence graph nodes",
            origin="library_silver",
            query_id="run2_control_plane",
        ),
        LabeledRetrievalHit(
            chunk_id="c2",
            source_id="s2",
            title="Pack source",
            score=0.8,
            trust_tier="A",
            text_preview="provenance requirements",
            origin="source_pack",
            query_id="run2_topic",
        ),
    ]
    strategy = _strategy_with_hits("run2", plan.topic, plan.source_pack, hits)
    coverage = build_source_coverage_report(strategy, plan)
    labels = detect_weak_labels(strategy, coverage.coverage_score)
    assert coverage.retrieval_hit_count == 2
    assert coverage.unique_library_card_count >= 1
    assert "insufficient_evidence" not in labels
