"""Tests for library-aware retrieval strategy."""

from __future__ import annotations

from pathlib import Path

import pytest

from sourcelab.library.paths import ensure_library_layout
from sourcelab.research.planner import build_research_plan
from sourcelab.research.retrieval_strategy import (
    build_retrieval_strategy,
    queries_from_plan,
    strategy_to_search_results,
)


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "data" / "source_packs" / "agentic_engineering_v1" / "sources").mkdir(parents=True)
    (root / "data" / "source_packs" / "agentic_engineering_v1" / "sources" / "agent.md").write_text(
        "# Agent control plane\n\nMulti-agent orchestration requires grounding and observability.",
        encoding="utf-8",
    )
    (root / "data" / "source_packs" / "agentic_engineering_v1" / "manifest.json").write_text("{}", encoding="utf-8")
    ensure_library_layout(root)
    return root


def test_queries_from_plan_include_topic_and_subtopics():
    plan = build_research_plan("run1", "multi-agent control plane", "agentic_engineering_v1")
    queries = queries_from_plan(plan)
    assert queries[0].text == plan.topic
    assert len(queries) >= len(plan.subtopics) + 1


def test_retrieval_strategy_labels_origins(project_root: Path):
    plan = build_research_plan("run1", "multi-agent software engineering control plane", "agentic_engineering_v1")
    strategy = build_retrieval_strategy(project_root, "run1", plan.topic, plan.source_pack, plan=plan)
    assert strategy.origins_enabled[0] == "source_pack"
    if strategy.hits:
        assert all(hit.origin in strategy.origins_enabled for hit in strategy.hits)
    results = strategy_to_search_results(strategy)
    assert isinstance(results, list)


def test_three_topics_produce_different_query_sets(project_root: Path):
    topics = [
        ("multi-agent software engineering control plane", "agentic_engineering_v1"),
        ("quantum hybrid portfolio optimizer", "quantum_finance_v1"),
        ("clinical evidence graph assistant", "biomedical_ai_v1"),
    ]
    query_sets = []
    for topic, pack in topics:
        plan = build_research_plan("run_x", topic, pack)
        query_sets.append({q.text for q in queries_from_plan(plan)})
    assert query_sets[0] != query_sets[1]
    assert query_sets[1] != query_sets[2]
