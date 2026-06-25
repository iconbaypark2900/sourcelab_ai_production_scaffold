"""Tests for research planner."""

from __future__ import annotations

from sourcelab.research.planner import build_research_plan, topic_slug


def test_topic_slug_normalizes():
    assert topic_slug("Multi-Agent Control Plane!") == "multi_agent_control_plane"


def test_agentic_engineering_plan_differs_from_quantum():
    agentic = build_research_plan("run1", "multi-agent software engineering control plane", "agentic_engineering_v1")
    quantum = build_research_plan("run2", "quantum hybrid portfolio optimizer", "quantum_finance_v1")
    biomedical = build_research_plan("run3", "clinical evidence graph assistant", "biomedical_ai_v1")

    assert agentic.source_pack == "agentic_engineering_v1"
    assert quantum.source_pack == "quantum_finance_v1"
    assert biomedical.source_pack == "biomedical_ai_v1"

    assert agentic.research_questions != quantum.research_questions
    assert quantum.pack_focus_areas != biomedical.pack_focus_areas
    assert any("agent" in q.lower() or "control" in q.lower() for q in agentic.research_questions)
    assert any("quantum" in area.lower() or "portfolio" in area.lower() for area in quantum.pack_focus_areas)
    assert any("clinical" in area.lower() or "evidence" in area.lower() for area in biomedical.pack_focus_areas)


def test_plan_includes_subtopics_and_methodology():
    plan = build_research_plan("run1", "clinical evidence graph assistant", "biomedical_ai_v1")
    assert len(plan.subtopics) >= 3
    assert plan.methodology_notes
    assert plan.target_domains
