"""Deterministic run comparison from on-disk artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

from sourcelab.comparison.schemas import (
    ClaimComparison,
    ClaimDeltaPair,
    ClaimStatsPerRun,
    LessonComparison,
    LessonComparisonPerRun,
    ProofGateComparison,
    ProofGatePerRun,
    RetrievalOverlapComparison,
    RetrievalOverlapPair,
    RetrievalOverlapPerRun,
    RunComparisonResult,
)
from sourcelab.harness.artifact_inventory import REQUIRED_ARTIFACTS
from sourcelab.ui.run_loader import (
    load_json_artifact,
    load_markdown_artifact,
    load_artifact_inventory,
    summarize_run,
)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _extract_retrieval(run_dir: Path) -> tuple[set[str], set[str]]:
    chunks = load_json_artifact(run_dir, "retrieved_chunks.json")
    source_ids: set[str] = set()
    chunk_ids: set[str] = set()
    if isinstance(chunks, list):
        for item in chunks:
            if not isinstance(item, dict):
                continue
            sid = item.get("source_id")
            cid = item.get("chunk_id")
            if sid:
                source_ids.add(str(sid))
            if cid:
                chunk_ids.add(str(cid))
    return source_ids, chunk_ids


def _extract_claim_stats(run_dir: Path) -> ClaimStatsPerRun:
    run_id = run_dir.name
    citation = load_json_artifact(run_dir, "citation_resolution.json")
    claims = load_json_artifact(run_dir, "atomic_claims.json")
    review_queue = load_json_artifact(run_dir, "human_review_queue.json")

    total_from_claims = len(claims) if isinstance(claims, list) else 0
    if isinstance(citation, dict):
        return ClaimStatsPerRun(
            run_id=run_id,
            total_claims=int(citation.get("total_claims", total_from_claims)),
            supported_claims=int(citation.get("supported_claims", 0)),
            unsupported_claims=int(citation.get("unsupported_claims", 0)),
            uncertain_claims=int(citation.get("uncertain_claims", 0)),
            needs_review=int(citation.get("needs_review", 0)),
            unsupported_high_risk=int(citation.get("unsupported_high_risk", 0)),
            citation_resolution_rate=(
                float(citation["resolution_rate"])
                if citation.get("resolution_rate") is not None
                else None
            ),
            has_blocking_issues=bool(citation.get("has_blocking_issues", False)),
        )

    needs_review_count = 0
    if isinstance(review_queue, list):
        needs_review_count = len(review_queue)

    return ClaimStatsPerRun(
        run_id=run_id,
        total_claims=total_from_claims,
        needs_review=needs_review_count,
    )


def _extract_proof_gate(run_dir: Path) -> ProofGatePerRun:
    run_id = run_dir.name
    summary = summarize_run(run_dir)
    proof_summary = load_json_artifact(run_dir, "proof_summary.json") or {}
    inventory = load_artifact_inventory(run_dir)

    missing_required: list[str] = []
    failed_validation: list[str] = []
    for row in inventory:
        if row.required and not row.exists:
            missing_required.append(row.name)
        if row.exists and not row.validated and row.name in REQUIRED_ARTIFACTS:
            failed_validation.append(row.name)

    release_gate = ""
    if isinstance(proof_summary, dict):
        release_gate = str(proof_summary.get("release_gate_status") or "")

    return ProofGatePerRun(
        run_id=run_id,
        harness_passed=summary.harness_passed,
        proof_bundle_status=summary.proof_bundle_status,
        release_gate_status=release_gate,
        artifact_count=summary.artifact_count,
        missing_required=sorted(missing_required),
        failed_validation=sorted(failed_validation),
    )


def _count_sections(markdown: str | None) -> int:
    if not markdown:
        return 0
    return sum(1 for line in markdown.splitlines() if line.strip().startswith("#"))


def _extract_lesson(run_dir: Path) -> LessonComparisonPerRun:
    run_id = run_dir.name
    manifest = load_json_artifact(run_dir, "run_manifest.json") or {}
    lesson_task = load_json_artifact(run_dir, "lesson_task.json") or {}
    generation_trace = load_json_artifact(run_dir, "generation_trace.json") or {}
    lesson_md = load_markdown_artifact(run_dir, "generated_lesson.md") or ""

    topic = str(manifest.get("topic") or lesson_task.get("topic") or "")
    lesson_format = str(
        lesson_task.get("task_format")
        or generation_trace.get("task_format")
        or manifest.get("task_format")
        or ""
    )
    source_pack = str(
        lesson_task.get("source_pack")
        or generation_trace.get("source_pack")
        or manifest.get("source_pack")
        or ""
    )
    difficulty_raw = lesson_task.get("difficulty") or generation_trace.get("difficulty")
    difficulty = int(difficulty_raw) if difficulty_raw is not None else None

    return LessonComparisonPerRun(
        run_id=run_id,
        topic=topic,
        lesson_format=lesson_format,
        source_pack=source_pack,
        difficulty=difficulty,
        retrieval_mode=str(manifest.get("retrieval_mode") or ""),
        lesson_length_chars=len(lesson_md),
        section_count=_count_sections(lesson_md),
    )


def _build_recommendation(result: RunComparisonResult) -> str:
    proof = result.proof_gate_comparison
    claims = result.claim_deltas

    failing_harness = [
        r.run_id for r in proof.per_run if r.harness_passed is False
    ]
    if failing_harness:
        return (
            f"Review harness failures first ({', '.join(failing_harness)}). "
            "Comparison metrics may be incomplete until required artifacts pass."
        )

    best_resolution: ClaimStatsPerRun | None = None
    for row in claims.per_run:
        if row.citation_resolution_rate is None:
            continue
        if best_resolution is None or (
            row.citation_resolution_rate > (best_resolution.citation_resolution_rate or 0)
        ):
            best_resolution = row

    if best_resolution and len(result.run_ids) >= 2:
        return (
            f"Prefer run {best_resolution.run_id} for highest citation resolution "
            f"({best_resolution.citation_resolution_rate:.2%}) with "
            f"{best_resolution.supported_claims}/{best_resolution.total_claims} supported claims."
        )

    if proof.all_passed_harness and proof.all_passed_proof:
        return "All compared runs passed harness and proof gates; inspect retrieval overlap and claim deltas for substantive differences."

    return "Inspect pairwise retrieval overlap and claim deltas to choose the run that best matches your evaluation goal."


def compare_runs(project_root: Path, run_ids: list[str]) -> RunComparisonResult:
    """Compare two or more runs deterministically from on-disk artifacts."""
    runs_dir = project_root / "artifacts" / "runs"
    normalized_ids = [rid.strip() for rid in run_ids if rid.strip()]
    run_dirs: list[Path] = []
    for run_id in normalized_ids:
        run_dir = runs_dir / run_id
        if not run_dir.exists():
            raise FileNotFoundError(run_id)
        run_dirs.append(run_dir)

    retrieval_per_run: list[RetrievalOverlapPerRun] = []
    retrieval_sets: dict[str, tuple[set[str], set[str]]] = {}
    for run_dir in run_dirs:
        sources, chunks = _extract_retrieval(run_dir)
        retrieval_sets[run_dir.name] = (sources, chunks)
        retrieval_per_run.append(
            RetrievalOverlapPerRun(
                run_id=run_dir.name,
                source_ids=sorted(sources),
                chunk_ids=sorted(chunks),
                source_count=len(sources),
                chunk_count=len(chunks),
            )
        )

    pairwise: list[RetrievalOverlapPair] = []
    for a_id, b_id in combinations(normalized_ids, 2):
        src_a, chk_a = retrieval_sets[a_id]
        src_b, chk_b = retrieval_sets[b_id]
        shared_src = src_a & src_b
        shared_chk = chk_a & chk_b
        pairwise.append(
            RetrievalOverlapPair(
                run_id_a=a_id,
                run_id_b=b_id,
                shared_source_ids=sorted(shared_src),
                shared_chunk_ids=sorted(shared_chk),
                source_jaccard=round(_jaccard(src_a, src_b), 4),
                chunk_jaccard=round(_jaccard(chk_a, chk_b), 4),
                unique_sources_a=sorted(src_a - src_b),
                unique_sources_b=sorted(src_b - src_a),
                unique_chunks_a=sorted(chk_a - chk_b),
                unique_chunks_b=sorted(chk_b - chk_a),
            )
        )

    all_sources = set.intersection(*(retrieval_sets[rid][0] for rid in normalized_ids)) if normalized_ids else set()
    all_chunks = set.intersection(*(retrieval_sets[rid][1] for rid in normalized_ids)) if normalized_ids else set()

    claim_per_run = [_extract_claim_stats(d) for d in run_dirs]
    claim_pairwise: list[ClaimDeltaPair] = []
    claim_by_id = {c.run_id: c for c in claim_per_run}
    for a_id, b_id in combinations(normalized_ids, 2):
        ca = claim_by_id[a_id]
        cb = claim_by_id[b_id]
        rate_delta = None
        if ca.citation_resolution_rate is not None and cb.citation_resolution_rate is not None:
            rate_delta = round(cb.citation_resolution_rate - ca.citation_resolution_rate, 4)
        claim_pairwise.append(
            ClaimDeltaPair(
                run_id_a=a_id,
                run_id_b=b_id,
                total_claims_delta=cb.total_claims - ca.total_claims,
                supported_delta=cb.supported_claims - ca.supported_claims,
                unsupported_delta=cb.unsupported_claims - ca.unsupported_claims,
                resolution_rate_delta=rate_delta,
                high_risk_delta=cb.unsupported_high_risk - ca.unsupported_high_risk,
            )
        )

    proof_per_run = [_extract_proof_gate(d) for d in run_dirs]
    all_passed_harness = all(r.harness_passed is True for r in proof_per_run)
    all_passed_proof = all(
        (r.proof_bundle_status or "").upper() in {"PASS", "READY", "COMPLETE"}
        or (r.release_gate_status or "").upper() == "PASS"
        for r in proof_per_run
    )

    lesson_per_run = [_extract_lesson(d) for d in run_dirs]

    result = RunComparisonResult(
        run_ids=normalized_ids,
        compared_at=datetime.now(timezone.utc).isoformat(),
        retrieval_overlap=RetrievalOverlapComparison(
            per_run=retrieval_per_run,
            pairwise=pairwise,
            all_shared_source_ids=sorted(all_sources),
            all_shared_chunk_ids=sorted(all_chunks),
        ),
        claim_deltas=ClaimComparison(per_run=claim_per_run, pairwise_deltas=claim_pairwise),
        proof_gate_comparison=ProofGateComparison(
            per_run=proof_per_run,
            all_passed_harness=all_passed_harness,
            all_passed_proof=all_passed_proof,
        ),
        lesson_comparison=LessonComparison(per_run=lesson_per_run),
        artifact_paths={
            rid: str(runs_dir / rid)
            for rid in normalized_ids
        },
    )
    result.recommendation = _build_recommendation(result)
    return result
