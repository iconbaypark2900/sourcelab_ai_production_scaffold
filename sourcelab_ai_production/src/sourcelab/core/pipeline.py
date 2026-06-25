"""End-to-end demo pipeline v3.

Instruction:
- This pipeline shows the final production flow in miniature.
- Every step creates an artifact and feeds a proof bundle.
- The production API should call services in the same order.
- Generation v2 adds: generated_lesson_package, generated_lesson.md,
  rubric.json, answer_key.md, generation_trace.json
- Verification v2 adds: verification_report.json, citation_resolution.json,
  human_review_queue.json, atomic_claims.json, evidence_matches.json
- Proof Bundle v2 adds: run_manifest.json, proof_bundle_manifest.json, proof_summary.json
- Learning v2 adds: answer_submission.json, source_grounding_review.json,
  mastery_update.json, skill_profile_snapshot.json, learning_report.json, learning_report.md
- Model Router v2 adds: model_call_trace.json
- Artifacts are written in production order
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from sourcelab.generation.answer_key_generator import AnswerKeyGenerator
from sourcelab.generation.lesson_generator import SourceGroundedLessonGenerator
from sourcelab.generation.rubric_generator import RubricGenerator
from sourcelab.harness.proof_bundle import ProofBundle
from sourcelab.harness.runner import HarnessRunner
from sourcelab.learning.answer_scorer import AnswerScorer
from sourcelab.learning.source_grounding import check_source_grounding
from sourcelab.learning.skill_profile import (
    load_profile,
    save_profile,
    update_from_answer_review,
)
from sourcelab.learning.mastery import update_mastery
from sourcelab.learning.next_task_selector import NextTaskSelector
from sourcelab.learning.report import generate_learning_report, write_learning_artifacts
from sourcelab.learning.answer_history import write_answer_attempt
from sourcelab.learning.schemas import AnswerSubmission
from sourcelab.retrieval.index import PocketIndex
from sourcelab.sources.registry import SourceRegistry
from sourcelab.verification.claim_verifier import ClaimVerifier
from sourcelab.verification.claim_extractor import extract_all_atomic_claims
from sourcelab.verification.citation_checker import compute_citation_resolution
from sourcelab.verification.conflict_detector import detect_all_conflicts
from sourcelab.verification.evidence_matcher import match_all_claims
from sourcelab.verification.grounding_report import (
    generate_verification_report,
    generate_grounding_report_markdown,
    write_grounding_report,
)
from sourcelab.verification.human_review import build_human_review_queue, write_review_queue

if TYPE_CHECKING:
    from sourcelab.generation.model_router import ModelRouter


def allocate_run_id(project_root: Path) -> str:
    """Allocate a unique run id under artifacts/runs (second-resolution + suffix)."""
    runs_dir = project_root / "artifacts" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    base = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = base
    suffix = 1
    while (runs_dir / candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _render_lesson_markdown(package) -> str:
    """Render a lesson package as markdown for human consumption."""
    lines = []
    lines.append(f"# {package.lesson.title if package.lesson else package.topic}")
    lines.append("")

    if package.scenario:
        lines.append("## Scenario")
        lines.append(package.scenario.context)
        lines.append("")
        lines.append(f"**Audience:** {package.scenario.audience}")
        lines.append(f"**Task Format:** {package.scenario.task_format}")
        lines.append(f"**Difficulty:** {package.scenario.difficulty}/5")
        lines.append("")

    if package.lesson:
        lines.append("## Learning Objectives")
        for obj in package.lesson.learning_objectives:
            lines.append(f"- {obj}")
        lines.append("")

        lines.append("## Task Instructions")
        lines.append(package.lesson.task_instructions)
        lines.append("")

        lines.append("## Expected Answer Qualities")
        for q in package.lesson.expected_answer_qualities:
            lines.append(f"- {q}")
        lines.append("")

        lines.append("## Failure Traps")
        for trap in package.lesson.failure_traps:
            lines.append(f"- {trap}")
        lines.append("")

    lines.append("## Sources")
    for sid in package.source_ids:
        lines.append(f"- `{sid}`")
    lines.append("")

    return "\n".join(lines)


def _render_answer_key_markdown(answer_key) -> str:
    """Render an answer key as markdown for human consumption."""
    lines = []
    lines.append("# Answer Key")
    lines.append("")

    lines.append("## Facts")
    for fact in answer_key.facts:
        lines.append(f"- {fact}")
    lines.append("")

    lines.append("## Assumptions")
    for assumption in answer_key.assumptions:
        lines.append(f"- {assumption}")
    lines.append("")

    lines.append("## What Not to Claim")
    for item in answer_key.what_not_to_claim:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## Sample Strong Answer")
    lines.append(answer_key.sample_strong_answer)
    lines.append("")

    lines.append("## Sample Weak Answer")
    lines.append(answer_key.sample_weak_answer)
    lines.append("")

    lines.append("## Source References")
    for ref in answer_key.source_references:
        lines.append(f"- `{ref.source_id}` / `{ref.chunk_id}` ({ref.trust_tier}): {ref.claim}")
    lines.append("")

    return "\n".join(lines)


def _run_verification_v2(
    run_id: str,
    topic: str,
    package,
    lesson,
    search_results: list,
    proof: ProofBundle,
) -> dict:
    """Run verification v2 and write all artifacts.

    Returns a dictionary with verification results for the harness.
    """
    # 1. Extract atomic claims from lesson package
    atomic_claims = extract_all_atomic_claims(package)
    proof.write_json(
        "atomic_claims.json",
        [claim.model_dump() for claim in atomic_claims],
    )

    # 2. Match claims to source chunks
    evidence_map = match_all_claims(atomic_claims, search_results)
    evidence_list = []
    for claim_id, matches in evidence_map.items():
        for match in matches:
            evidence_list.append(match.model_dump())
    proof.write_json("evidence_matches.json", evidence_list)

    # 3. Verify all claims
    verifier = ClaimVerifier()
    verification_results = verifier.verify_all_claims(atomic_claims, evidence_map)

    # 4. Compute citation resolution
    citation_resolution = compute_citation_resolution(verification_results)
    proof.write_json("citation_resolution.json", citation_resolution.model_dump())

    # 5. Detect conflicts
    conflicts = detect_all_conflicts(atomic_claims)

    # 6. Build human review queue
    human_review_items = build_human_review_queue(verification_results, conflicts)
    write_review_queue(human_review_items, proof.run_dir)

    # 7. Generate verification report
    verification_report = generate_verification_report(
        run_id=run_id,
        topic=topic,
        verification_results=verification_results,
        citation_resolution=citation_resolution,
        conflicts=conflicts,
        human_review_items=human_review_items,
    )
    proof.write_json("verification_report.json", verification_report.model_dump())

    # 8. Generate grounding report (both markdown and JSON)
    write_grounding_report(verification_report, proof.run_dir)

    # 9. Generate claim_map.json for backward compatibility
    legacy_claims = verifier.verify_lesson(lesson=lesson, search_results=search_results)
    proof.write_json("claim_map.json", [c.model_dump() for c in legacy_claims])

    return {
        "atomic_claims_count": len(atomic_claims),
        "verification_results": verification_results,
        "citation_resolution": citation_resolution,
        "conflicts": conflicts,
        "human_review_items": human_review_items,
        "verification_report": verification_report,
    }


def run_demo_pipeline(topic: str, project_root: Path, model_router: ModelRouter | None = None, source_pack: str | None = None) -> dict:
    """Run a full local source-grounded learning flow."""

    run_id = allocate_run_id(project_root)
    run_dir = project_root / "artifacts" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    proof = ProofBundle(run_id=run_id, run_dir=run_dir)

    # 1. Source registry (filter for active and approved sources)
    if source_pack:
        registry = SourceRegistry.for_pack(project_root, source_pack)
    else:
        registry = SourceRegistry.bootstrap_demo(project_root)
    filtered_sources = registry.filter_for_retrieval()
    proof.write_json("source_registry_snapshot.json", [s.model_dump(mode="json") for s in filtered_sources])

    # 1a. Source quality and freshness reports
    from sourcelab.sources.quality import generate_quality_report, format_quality_report
    from sourcelab.sources.freshness import check_all_sources_freshness, format_freshness_report

    quality_report = generate_quality_report(registry.sources)
    proof.write_json("source_quality_report.json", format_quality_report(quality_report))

    freshness_results = check_all_sources_freshness(registry.sources)
    proof.write_json("source_freshness_report.json", format_freshness_report(freshness_results))

    # 2. Retrieval with compressed local index
    index = PocketIndex.from_registry(registry)
    search_results = index.search(topic, top_k=4)
    proof.write_json("retrieved_chunks.json", [r.model_dump() for r in search_results])
    proof.write_json("compression_report.json", index.storage_report())

    # 2a. Retrieval diagnostics
    from sourcelab.retrieval.schemas import RetrievalDiagnostics
    retrieval_diagnostics = RetrievalDiagnostics(
        query=topic,
        mode="vector",
        backend=index.backend.name,
        store=index.store.info().get("store", "memory"),
        result_count=len(search_results),
        total_chunks=len(index.chunks),
        final_scores=[r.score for r in search_results],
        source_ids=[r.source_id for r in search_results],
        chunk_ids=[r.chunk_id for r in search_results],
        trust_tiers=[r.trust_tier for r in search_results],
        compression_report=index.storage_report(),
    )
    proof.write_json("retrieval_diagnostics.json", retrieval_diagnostics.model_dump(mode="json"))

    # 3. Source-grounded lesson generation (legacy for backward compatibility)
    generator = SourceGroundedLessonGenerator()
    lesson = generator.generate(topic=topic, search_results=search_results)
    proof.write_json("lesson_task.json", lesson.model_dump())

    # 4. Generation v2: Full lesson package
    package = generator.generate_package(
        topic=topic,
        search_results=search_results,
        difficulty=3,
        task_format="architecture_review",
        audience="engineer",
        model_router=model_router,
    )
    proof.write_json("generated_lesson_package.json", package.model_dump(mode="json"))
    proof.write_text("generated_lesson.md", _render_lesson_markdown(package))

    # 5. Rubric generation
    rubric_gen = RubricGenerator()
    rubric = rubric_gen.generate(package)
    proof.write_json("rubric.json", rubric.model_dump(mode="json"))

    # 6. Answer key generation
    answer_key_gen = AnswerKeyGenerator()
    answer_key = answer_key_gen.generate(package, search_results)
    proof.write_json("answer_key.json", answer_key.model_dump(mode="json"))
    proof.write_text("answer_key.md", _render_answer_key_markdown(answer_key))

    # 7. Generation trace
    if package.generation_trace:
        proof.write_json("generation_trace.json", package.generation_trace.model_dump(mode="json"))

    # 7a. Model call trace (Model Router v2)
    if model_router is not None:
        proof.write_json("model_call_trace.json", model_router.get_trace_log_dict())

    # 8. Verification v2: Full verification pipeline
    verification_results = _run_verification_v2(
        run_id=run_id,
        topic=topic,
        package=package,
        lesson=lesson,
        search_results=search_results,
        proof=proof,
    )

    # 9. Learning v2: Simulated answer scoring with full learning pipeline
    sample_answer = (
        "A safe post-quantum migration plan should start with a cryptographic inventory. "
        "The first step is to identify where public-key cryptography is used, separate immediate "
        "operational risk from long-term confidentiality risk, and avoid claiming that current "
        "quantum computers can break RSA-2048 today without evidence."
    )

    # Write answer submission
    submission = AnswerSubmission(
        topic=topic,
        run_id=run_id,
        answer_text=sample_answer,
    )
    proof.write_json("answer_submission.json", submission.model_dump())

    # Load skill profile
    profile = load_profile(user_id="local_user", project_root=project_root)

    # Score the answer with v2 scorer (enable LLM judge if model_router is provided)
    enable_llm = model_router is not None and os.environ.get("SOURCELAB_ENABLE_LLM_JUDGE", "").lower() in ("1", "true", "yes")
    scorer = AnswerScorer(
        enable_llm_judge=enable_llm,
        model_router=model_router,
    )
    review_v2 = scorer.score_v2(
        topic=topic,
        answer=sample_answer,
        search_results=search_results,
        rubric=rubric,
        package=package,
        run_id=run_id,
    )
    proof.write_json("answer_review.json", review_v2.model_dump())

    # Source grounding review
    source_grounding = check_source_grounding(
        answer_text=sample_answer,
        search_results=search_results,
        answer_key=answer_key,
        package=package,
        topic=topic,
        answer_id=review_v2.answer_id,
    )
    proof.write_json(
        "source_grounding_review.json",
        source_grounding.model_dump(mode="json", by_alias=True),
    )

    # Update skill profile
    profile = update_from_answer_review(
        profile=profile,
        review=review_v2,
        difficulty=3,
        task_format="architecture_review",
    )

    # Update mastery
    mastery_update = update_mastery(
        profile=profile,
        review=review_v2,
        difficulty=3,
    )
    proof.write_json("mastery_update.json", mastery_update.model_dump())

    # Save profile
    save_profile(profile, project_root=project_root)

    # Write skill profile snapshot
    proof.write_json("skill_profile_snapshot.json", profile.model_dump(mode="json"))

    # Next task selection with rationale
    selector = NextTaskSelector()
    next_task, rationale = selector.select_v2(
        topic=topic,
        answer_review=review_v2,
        profile=profile,
        previous_task_format="architecture_review",
    )
    proof.write_json("next_task_decision.json", next_task.model_dump())

    # Learning report
    learning_report = generate_learning_report(
        review=review_v2,
        mastery_update=mastery_update,
        rationale=rationale,
        source_grounding=source_grounding,
        profile=profile,
    )
    write_learning_artifacts(
        report=learning_report,
        mastery_update=mastery_update,
        profile=profile,
        run_dir=run_dir,
    )

    # 10. Proof Bundle v2: Run manifest
    proof.write_run_manifest(
        topic=topic,
        source_policy="local_deterministic",
        retrieval_mode="hybrid",
        generation_backend="deterministic_local",
        verification_version="v2",
        status="complete",
    )

    # 11. Proof Bundle v2: Proof summary
    unsupported_high_risk = verification_results["citation_resolution"].unsupported_high_risk
    proof.write_proof_summary(
        topic=topic,
        harness_passed=True,  # Will be updated after harness validation
        citation_resolution_rate=verification_results["citation_resolution"].resolution_rate,
        unsupported_high_risk=unsupported_high_risk,
        human_review_items=len(verification_results["human_review_items"]),
        conflicts_detected=len(verification_results["conflicts"]),
        release_gate_status=verification_results["verification_report"].summary.release_gate_status,
        answer_score=review_v2.overall_score,
    )

    # 12. Trace
    proof.write_json("trace.json", proof.trace())

    # 13. Harness validation (AFTER all content artifacts are written)
    harness = HarnessRunner()
    harness_report = harness.validate_run(run_dir=run_dir)
    proof.write_json("harness_report.json", harness_report)

    # 14. Proof Bundle v2: Proof bundle manifest (LAST - records state of all artifacts)
    proof.write_proof_bundle_manifest()

    from sourcelab.library.expansion import maybe_write_source_expansion_suggestions

    maybe_write_source_expansion_suggestions(project_root, run_dir, topic)

    # Build release gate status
    from sourcelab.harness.release_gate import verify_release
    release_gate = verify_release(project_root)

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "topic": topic,
        "lesson_title": lesson.title,
        "source_count": len(filtered_sources),
        "retrieved_count": len(search_results),
        "compression_report": index.storage_report(),
        "claims": [c.model_dump() for c in verification_results["verification_results"]],
        "harness_passed": harness_report["passed"],
        "answer_score": review_v2.overall_score,
        "next_task": next_task.model_dump(),
        "learning_report": {
            "overall_score": learning_report.overall_score,
            "topic_mastery_before": learning_report.topic_mastery_before,
            "topic_mastery_after": learning_report.topic_mastery_after,
            "recommended_focus": learning_report.recommended_focus,
            "human_review_flag": learning_report.human_review_flag,
        },
        "artifact_count": len(proof.artifacts),
        "verification": {
            "atomic_claims_count": verification_results["atomic_claims_count"],
            "citation_resolution_rate": verification_results["citation_resolution"].resolution_rate,
            "conflicts_detected": len(verification_results["conflicts"]),
            "human_review_items": len(verification_results["human_review_items"]),
            "release_gate_status": verification_results["verification_report"].summary.release_gate_status,
        },
        "proof_bundle": {
            "run_manifest": (run_dir / "run_manifest.json").exists(),
            "proof_bundle_manifest": (run_dir / "proof_bundle_manifest.json").exists(),
            "proof_summary": (run_dir / "proof_summary.json").exists(),
        },
        "release_gate": {
            "status": release_gate["status"],
            "blocking_failures": release_gate["blocking_failures"],
            "warnings": release_gate["warnings"],
        },
    }


def _resolve_effective_pack(source_pack: str | None, registry: SourceRegistry) -> str:
    """Resolve a non-empty pack name for research planning."""
    if source_pack:
        return source_pack
    for source in registry.sources:
        if source.source_pack:
            return source.source_pack
        if source.pack_name:
            return source.pack_name
    return "local_demo"


def run_lesson_create(
    topic: str,
    project_root: Path,
    difficulty: int = 3,
    task_format: str = "architecture_review",
    model_router: ModelRouter | None = None,
    source_pack: str | None = None,
    retrieval_mode: str = "hybrid",
) -> dict:
    """Run a lesson creation flow (sourcelab lesson create)."""
    run_id = allocate_run_id(project_root)
    run_dir = project_root / "artifacts" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    proof = ProofBundle(run_id=run_id, run_dir=run_dir)

    # 1. Source registry (filter for active and approved sources)
    if source_pack:
        registry = SourceRegistry.for_pack(project_root, source_pack)
    else:
        registry = SourceRegistry.bootstrap_demo(project_root)
    filtered_sources = registry.filter_for_retrieval()
    proof.write_json("source_registry_snapshot.json", [s.model_dump(mode="json") for s in filtered_sources])

    # 1a. Source quality and freshness reports
    from sourcelab.sources.quality import generate_quality_report, format_quality_report
    from sourcelab.sources.freshness import check_all_sources_freshness, format_freshness_report

    quality_report = generate_quality_report(registry.sources)
    proof.write_json("source_quality_report.json", format_quality_report(quality_report))

    freshness_results = check_all_sources_freshness(registry.sources)
    proof.write_json("source_freshness_report.json", format_freshness_report(freshness_results))

    # 1b. Library-Aware Research Engine v1 — plan + retrieval
    from sourcelab.research import (
        execute_library_aware_retrieval,
        finalize_research_artifacts,
        plan_research,
        write_pre_generation_research,
    )
    from sourcelab.research.retrieval_strategy import fallback_pack_search

    effective_pack = _resolve_effective_pack(source_pack, registry)
    research_plan = plan_research(run_id, topic, effective_pack, project_root=project_root)
    retrieval_strategy, search_results = execute_library_aware_retrieval(
        project_root, run_id, topic, effective_pack, plan=research_plan, registry=registry
    )
    pack_source_ids = {source.source_id for source in filtered_sources}
    pack_results = [result for result in search_results if result.source_id in pack_source_ids]
    if pack_results:
        search_results = pack_results[: max(len(pack_results), 4)]
    elif pack_source_ids:
        search_results = fallback_pack_search(registry, topic, top_k=4)
    write_pre_generation_research(proof, research_plan, retrieval_strategy)

    # 2. Retrieval (library-aware; fallback handled in execute_library_aware_retrieval)
    index = PocketIndex.from_registry(registry)
    proof.write_json("retrieved_chunks.json", [r.model_dump() for r in search_results])
    proof.write_json("compression_report.json", index.storage_report())

    # 2a. Retrieval diagnostics
    from sourcelab.retrieval.schemas import RetrievalDiagnostics
    diagnostics_mode = retrieval_mode if retrieval_mode in {"hybrid", "keyword", "vector"} else "hybrid"
    retrieval_diagnostics = RetrievalDiagnostics(
        query=topic,
        mode=diagnostics_mode,
        backend=index.backend.name,
        store=index.store.info().get("store", "memory"),
        result_count=len(search_results),
        total_chunks=len(index.chunks),
        final_scores=[r.score for r in search_results],
        source_ids=[r.source_id for r in search_results],
        chunk_ids=[r.chunk_id for r in search_results],
        trust_tiers=[r.trust_tier for r in search_results],
        compression_report=index.storage_report(),
    )
    proof.write_json("retrieval_diagnostics.json", retrieval_diagnostics.model_dump(mode="json"))

    # 3. Generation v2: Full lesson package
    generator = SourceGroundedLessonGenerator()
    package = generator.generate_package(
        topic=topic,
        search_results=search_results,
        difficulty=difficulty,
        task_format=task_format,
        audience="engineer",
        model_router=model_router,
    )
    proof.write_json("generated_lesson_package.json", package.model_dump(mode="json"))
    proof.write_text("generated_lesson.md", _render_lesson_markdown(package))

    # Keep legacy artifact for backward compatibility
    lesson = generator.generate(topic=topic, search_results=search_results)
    proof.write_json("lesson_task.json", lesson.model_dump())

    # 4. Rubric
    rubric_gen = RubricGenerator()
    rubric = rubric_gen.generate(package)
    proof.write_json("rubric.json", rubric.model_dump(mode="json"))

    # 5. Answer key
    answer_key_gen = AnswerKeyGenerator()
    answer_key = answer_key_gen.generate(package, search_results)
    proof.write_json("answer_key.json", answer_key.model_dump(mode="json"))
    proof.write_text("answer_key.md", _render_answer_key_markdown(answer_key))

    # 6. Generation trace
    if package.generation_trace:
        proof.write_json("generation_trace.json", package.generation_trace.model_dump(mode="json"))

    # 6a. Model call trace (Model Router v2)
    if model_router is not None:
        proof.write_json("model_call_trace.json", model_router.get_trace_log_dict())

    # 7. Verification v2: Full verification pipeline
    verification_results = _run_verification_v2(
        run_id=run_id,
        topic=topic,
        package=package,
        lesson=lesson,
        search_results=search_results,
        proof=proof,
    )

    # 8. Proof Bundle v2: Run manifest
    manifest_retrieval_mode = retrieval_mode if retrieval_mode in {"hybrid", "keyword", "vector"} else "hybrid"
    proof.write_run_manifest(
        topic=topic,
        source_policy="local_deterministic",
        retrieval_mode=manifest_retrieval_mode,
        generation_backend="deterministic_local",
        verification_version="v2",
        status="complete",
    )

    # 9. Proof Bundle v2: Proof summary
    unsupported_high_risk = verification_results["citation_resolution"].unsupported_high_risk
    proof.write_proof_summary(
        topic=topic,
        harness_passed=True,  # Will be updated after harness validation
        citation_resolution_rate=verification_results["citation_resolution"].resolution_rate,
        unsupported_high_risk=unsupported_high_risk,
        human_review_items=len(verification_results["human_review_items"]),
        conflicts_detected=len(verification_results["conflicts"]),
        release_gate_status=verification_results["verification_report"].summary.release_gate_status,
    )

    # 10. Trace
    proof.write_json("trace.json", proof.trace())

    # 11. Harness validation (AFTER all content artifacts are written)
    finalize_research_artifacts(
        project_root=project_root,
        run_dir=run_dir,
        proof=proof,
        plan=research_plan,
        strategy=retrieval_strategy,
        package=package,
    )

    harness = HarnessRunner()
    harness_report = harness.validate_run(run_dir=run_dir)
    proof.write_json("harness_report.json", harness_report)

    # 12. Proof Bundle v2: Proof bundle manifest (LAST - records state of all artifacts)
    proof.write_proof_bundle_manifest()

    # Build release gate status
    from sourcelab.harness.release_gate import verify_release
    release_gate = verify_release(project_root)

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "topic": topic,
        "source_pack": source_pack or "",
        "lesson_title": package.lesson.title if package.lesson else topic,
        "source_count": len(filtered_sources),
        "retrieved_count": len(search_results),
        "harness_passed": harness_report["passed"],
        "artifact_count": len(proof.artifacts),
        "verification": {
            "atomic_claims_count": verification_results["atomic_claims_count"],
            "citation_resolution_rate": verification_results["citation_resolution"].resolution_rate,
            "conflicts_detected": len(verification_results["conflicts"]),
            "human_review_items": len(verification_results["human_review_items"]),
            "release_gate_status": verification_results["verification_report"].summary.release_gate_status,
        },
        "proof_bundle": {
            "run_manifest": (run_dir / "run_manifest.json").exists(),
            "proof_bundle_manifest": (run_dir / "proof_bundle_manifest.json").exists(),
            "proof_summary": (run_dir / "proof_summary.json").exists(),
        },
        "release_gate": {
            "status": release_gate["status"],
            "blocking_failures": release_gate["blocking_failures"],
            "warnings": release_gate["warnings"],
        },
    }


def run_answer_submit(
    topic: str,
    answer_text: str,
    project_root: Path,
    run_id: str | None = None,
) -> dict:
    """Submit and score a learner answer.

    This is used by `sourcelab answer submit` command.
    """
    # Find the run to use
    if run_id:
        run_dir = project_root / "artifacts" / "runs" / run_id
    else:
        runs_dir = project_root / "artifacts" / "runs"
        if not runs_dir.exists():
            return {"error": "No runs found. Run 'sourcelab demo' or 'sourcelab lesson create' first."}
        runs = sorted([p for p in runs_dir.glob("*") if p.is_dir()])
        if not runs:
            return {"error": "No runs found."}
        run_dir = runs[-1]
        run_id = run_dir.name

    # Load required artifacts from the run
    try:
        # Load search results
        chunks_path = run_dir / "retrieved_chunks.json"
        if not chunks_path.exists():
            return {"error": f"No retrieved_chunks.json found in {run_dir}"}
        from sourcelab.core.models import SearchResult
        chunks_data = json.loads(chunks_path.read_text(encoding="utf-8"))
        search_results = [SearchResult(**c) for c in chunks_data]

        # Load rubric
        rubric_path = run_dir / "rubric.json"
        rubric_data = json.loads(rubric_path.read_text(encoding="utf-8")) if rubric_path.exists() else None
        from sourcelab.generation.schemas import GeneratedRubric
        rubric = GeneratedRubric(**rubric_data) if rubric_data else None

        # Load answer key
        answer_key_path = run_dir / "answer_key.json"
        answer_key_data = json.loads(answer_key_path.read_text(encoding="utf-8")) if answer_key_path.exists() else None
        from sourcelab.generation.schemas import GeneratedAnswerKey
        answer_key = GeneratedAnswerKey(**answer_key_data) if answer_key_data else None

        # Load lesson package
        package_path = run_dir / "generated_lesson_package.json"
        package_data = json.loads(package_path.read_text(encoding="utf-8")) if package_path.exists() else None
        from sourcelab.generation.schemas import GeneratedLessonPackage
        package = GeneratedLessonPackage(**package_data) if package_data else None

    except Exception as e:
        return {"error": f"Failed to load run artifacts: {e}"}

    # Create answer submission
    submission = AnswerSubmission(
        topic=topic,
        run_id=run_id,
        answer_text=answer_text,
    )
    submission_path = run_dir / "answer_submission.json"
    submission_path.write_text(
        json.dumps(submission.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )

    # Load skill profile
    profile = load_profile(user_id="local_user", project_root=project_root)

    # Score the answer (enable LLM judge if env var is set)
    enable_llm = os.environ.get("SOURCELAB_ENABLE_LLM_JUDGE", "").lower() in ("1", "true", "yes")
    from sourcelab.generation.model_router import ModelRouter
    model_router = ModelRouter() if enable_llm else None
    scorer = AnswerScorer(
        enable_llm_judge=enable_llm,
        model_router=model_router,
    )
    review_v2 = scorer.score_v2(
        topic=topic,
        answer=answer_text,
        search_results=search_results,
        rubric=rubric,
        package=package,
        run_id=run_id,
    )
    review_path = run_dir / "answer_review.json"
    review_path.write_text(
        json.dumps(review_v2.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )

    # Source grounding review
    source_grounding = check_source_grounding(
        answer_text=answer_text,
        search_results=search_results,
        answer_key=answer_key,
        package=package,
        topic=topic,
        answer_id=review_v2.answer_id,
    )
    grounding_path = run_dir / "source_grounding_review.json"
    grounding_path.write_text(
        json.dumps(source_grounding.model_dump(mode="json", by_alias=True), indent=2, default=str),
        encoding="utf-8",
    )

    # Update skill profile
    profile = update_from_answer_review(
        profile=profile,
        review=review_v2,
        difficulty=3,
        task_format="architecture_review",
    )

    # Update mastery
    mastery_update = update_mastery(
        profile=profile,
        review=review_v2,
        difficulty=3,
    )
    mastery_path = run_dir / "mastery_update.json"
    mastery_path.write_text(
        json.dumps(mastery_update.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )

    # Save profile
    save_profile(profile, project_root=project_root)

    # Write skill profile snapshot
    profile_path = run_dir / "skill_profile_snapshot.json"
    profile_path.write_text(
        json.dumps(profile.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )

    from sourcelab.research.topic_profile import record_answer_submit

    record_answer_submit(project_root, run_dir)

    # Next task selection with rationale
    selector = NextTaskSelector()
    next_task, rationale = selector.select_v2(
        topic=topic,
        answer_review=review_v2,
        profile=profile,
        previous_task_format="architecture_review",
    )
    next_task_path = run_dir / "next_task_decision.json"
    next_task_path.write_text(
        json.dumps(next_task.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )

    # Learning report
    learning_report = generate_learning_report(
        review=review_v2,
        mastery_update=mastery_update,
        rationale=rationale,
        source_grounding=source_grounding,
        profile=profile,
    )
    write_learning_artifacts(
        report=learning_report,
        mastery_update=mastery_update,
        profile=profile,
        run_dir=run_dir,
    )

    next_task_focus = next_task.focus if hasattr(next_task, "focus") else str(next_task.get("focus", ""))
    attempt_id, attempt_dir = write_answer_attempt(
        run_dir=run_dir,
        run_id=run_id,
        user_id=profile.user_id,
        submission=submission,
        review=review_v2,
        source_grounding=source_grounding,
        mastery_update=mastery_update,
        learning_report=learning_report,
        next_task=next_task.model_dump() if hasattr(next_task, "model_dump") else next_task,
        next_task_focus=next_task_focus,
    )

    from sourcelab.library.expansion import maybe_write_source_expansion_suggestions

    expansion = maybe_write_source_expansion_suggestions(project_root, run_dir, topic)

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "topic": topic,
        "answer_id": review_v2.answer_id,
        "attempt_id": attempt_id,
        "attempt_manifest_path": str(attempt_dir / "attempt_manifest.json"),
        "overall_score": review_v2.overall_score,
        "strengths": review_v2.strengths,
        "weaknesses": review_v2.weaknesses,
        "source_grounding_score": review_v2.source_grounding_score,
        "concept_overlap_grounding_score": source_grounding.concept_overlap_grounding_score,
        "topic_mastery_after": mastery_update.topic_mastery_after,
        "recommended_focus": learning_report.recommended_focus,
        "next_task": next_task.model_dump(),
        "source_expansion_suggestions": (
            str(run_dir / "source_expansion_suggestions.json") if expansion else None
        ),
    }
