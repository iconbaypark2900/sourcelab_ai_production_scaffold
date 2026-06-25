"""Library-Aware Research Engine v1 orchestration."""

from __future__ import annotations

from pathlib import Path

from sourcelab.core.models import SearchResult
from sourcelab.generation.schemas import GeneratedLessonPackage
from sourcelab.sources.registry import SourceRegistry
from sourcelab.harness.proof_bundle import ProofBundle
from sourcelab.library.expansion import maybe_write_source_expansion_suggestions
from sourcelab.library.io import save_model
from sourcelab.research.evidence_bound_lesson import build_evidence_bound_lesson_plan
from sourcelab.research.genericness import build_genericness_report
from sourcelab.research.planner import build_research_plan, render_research_plan_markdown
from sourcelab.research.retrieval_strategy import (
    build_retrieval_strategy,
    fallback_pack_search,
    strategy_to_search_results,
)
from sourcelab.research.schemas import (
    EvidenceBoundLessonPlan,
    GenericnessReport,
    ResearchPlan,
    RetrievalStrategy,
    SourceCoverageReport,
    TopicProfileUpdate,
)
from sourcelab.research.source_coverage import build_source_coverage_report, render_coverage_markdown
from sourcelab.research.evolution import write_lesson_evolution_report
from sourcelab.research.library_expansion_plan import maybe_write_library_expansion_plan
from sourcelab.research.topic_profile import build_topic_profile_update


def plan_research(
    run_id: str,
    topic: str,
    source_pack: str,
    project_root: Path | None = None,
) -> ResearchPlan:
    """Build a research plan without executing retrieval."""
    return build_research_plan(run_id, topic, source_pack, project_root=project_root)


def execute_library_aware_retrieval(
    project_root: Path,
    run_id: str,
    topic: str,
    source_pack: str,
    plan: ResearchPlan | None = None,
    registry: SourceRegistry | None = None,
) -> tuple[RetrievalStrategy, list[SearchResult]]:
    """Execute library-aware retrieval; returns strategy and SearchResult list."""
    plan = plan or build_research_plan(run_id, topic, source_pack)
    strategy = build_retrieval_strategy(project_root, run_id, topic, source_pack, plan=plan)
    results: list[SearchResult] = strategy_to_search_results(strategy)
    if not results:
        pack_registry = registry or SourceRegistry.for_pack(project_root, source_pack)
        results = fallback_pack_search(pack_registry, topic)
    return strategy, results


def finalize_research_artifacts(
    project_root: Path,
    run_dir: Path,
    proof: ProofBundle,
    plan: ResearchPlan,
    strategy: RetrievalStrategy,
    package: GeneratedLessonPackage | None = None,
) -> dict[str, object]:
    """Write post-generation research artifacts and return key objects."""
    coverage = build_source_coverage_report(strategy, plan, package)
    lesson_plan = build_evidence_bound_lesson_plan(strategy, plan, package)
    genericness = build_genericness_report(
        run_id=plan.run_id,
        topic=plan.topic,
        source_pack=plan.source_pack,
        plan=plan,
        coverage=coverage,
        package=package,
    )
    profile_update = build_topic_profile_update(
        run_id=plan.run_id,
        topic=plan.topic,
        source_pack=plan.source_pack,
        coverage=coverage,
        genericness=genericness,
    )

    proof.write_json("research_plan.json", plan.model_dump(mode="json"))
    proof.write_text("research_plan.md", render_research_plan_markdown(plan))
    proof.write_json("retrieval_strategy.json", strategy.model_dump(mode="json"))
    proof.write_json("source_coverage_report.json", coverage.model_dump(mode="json"))
    proof.write_text("source_coverage_report.md", render_coverage_markdown(coverage))
    proof.write_json("evidence_bound_lesson_plan.json", lesson_plan.model_dump(mode="json"))
    proof.write_json("genericness_report.json", genericness.model_dump(mode="json"))
    save_model(run_dir / "topic_profile_update.json", profile_update)

    maybe_write_source_expansion_suggestions(project_root, run_dir, plan.topic)
    maybe_write_library_expansion_plan(run_dir, plan, proof=proof)
    write_lesson_evolution_report(
        project_root,
        run_dir,
        proof,
        plan,
        coverage=coverage,
        genericness=genericness,
    )

    return {
        "plan": plan,
        "strategy": strategy,
        "coverage": coverage,
        "lesson_plan": lesson_plan,
        "genericness": genericness,
        "profile_update": profile_update,
    }


def write_pre_generation_research(
    proof: ProofBundle,
    plan: ResearchPlan,
    strategy: RetrievalStrategy,
) -> None:
    """Write research plan and retrieval strategy before lesson generation."""
    proof.write_json("research_plan.json", plan.model_dump(mode="json"))
    proof.write_text("research_plan.md", render_research_plan_markdown(plan))
    proof.write_json("retrieval_strategy.json", strategy.model_dump(mode="json"))


__all__ = [
    "EvidenceBoundLessonPlan",
    "GenericnessReport",
    "ResearchPlan",
    "RetrievalStrategy",
    "SourceCoverageReport",
    "TopicProfileUpdate",
    "execute_library_aware_retrieval",
    "finalize_research_artifacts",
    "plan_research",
    "write_pre_generation_research",
]
