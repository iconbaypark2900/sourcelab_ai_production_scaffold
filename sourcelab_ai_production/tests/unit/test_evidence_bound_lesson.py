"""Tests for evidence-bound lesson plan."""

from __future__ import annotations

from sourcelab.library.io import utc_now
from sourcelab.research.evidence_bound_lesson import build_evidence_bound_lesson_plan
from sourcelab.research.planner import build_research_plan
from sourcelab.research.schemas import LabeledRetrievalHit, RetrievalStrategy


def test_sections_bind_chunk_and_card_ids():
    plan = build_research_plan("run1", "multi-agent software engineering control plane", "agentic_engineering_v1")
    strategy = RetrievalStrategy(
        run_id="run1",
        topic=plan.topic,
        source_pack=plan.source_pack,
        generated_at=utc_now(),
        hits=[
            LabeledRetrievalHit(
                chunk_id="agent::chunk-000",
                source_id="agent",
                library_card_id=None,
                title="Agent doc",
                score=0.88,
                trust_tier="A",
                text_preview="control plane observability",
                origin="source_pack",
                query_id=f"run1_{plan.subtopics[0].subtopic_id}",
            )
        ],
        selected_chunk_ids=["agent::chunk-000"],
    )
    lesson_plan = build_evidence_bound_lesson_plan(strategy, plan)
    assert lesson_plan.sections
    first = lesson_plan.sections[0]
    assert first.chunk_ids
    assert first.evidence_strength in {"strong", "moderate", "weak", "missing"}
