"""Batch run service — synchronous multi-run creation and comparison artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sourcelab.api.services import create_lesson
from sourcelab.comparison.run_compare import compare_runs
from sourcelab.comparison.schemas import RunComparisonResult
from sourcelab.comparison.answer_compare import answer_compare_to_markdown, compare_run_answers
from sourcelab.comparison.schemas import AnswerCompareResult
from sourcelab.ui.run_loader import summarize_run

BATCH_VERSION = "v2.3"


def _batches_dir(project_root: Path) -> Path:
    return project_root / "artifacts" / "batches"


def _new_batch_id(project_root: Path) -> str:
    base = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batches = _batches_dir(project_root)
    candidate = base
    suffix = 1
    while (batches / candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _build_batch_summary(
    batch_id: str,
    batch_name: str,
    created_at: str,
    runs: list[dict],
    failures: list[dict],
    comparison: RunComparisonResult | None,
) -> dict[str, Any]:
    run_ids = [r["run_id"] for r in runs if r.get("run_id")]
    topics = sorted({r.get("topic", "") for r in runs if r.get("topic")})
    source_packs = sorted({r.get("source_pack", "") for r in runs if r.get("source_pack")})

    harness_pass = sum(1 for r in runs if r.get("harness_status") == "PASS")
    proof_pass = sum(
        1 for r in runs if str(r.get("proof_status", "")).upper() in {"PASS", "READY", "COMPLETE"}
    )
    artifact_total = sum(int(r.get("artifact_count") or 0) for r in runs)

    summary: dict[str, Any] = {
        "batch_id": batch_id,
        "batch_name": batch_name,
        "created_at": created_at,
        "version": BATCH_VERSION,
        "totals": {
            "requested": len(runs) + len(failures),
            "created": len(runs),
            "failed": len(failures),
            "harness_pass": harness_pass,
            "harness_fail": len(runs) - harness_pass,
            "proof_pass": proof_pass,
            "artifact_count": artifact_total,
        },
        "run_ids": run_ids,
        "topics": topics,
        "source_packs": source_packs,
    }

    if comparison is not None:
        summary["comparison"] = {
            "run_ids": comparison.run_ids,
            "compared_at": comparison.compared_at,
            "all_passed_harness": comparison.proof_gate_comparison.all_passed_harness,
            "all_passed_proof": comparison.proof_gate_comparison.all_passed_proof,
            "recommendation": comparison.recommendation,
        }

    return summary


def _answer_comparison_to_markdown(answer_comparison: AnswerCompareResult) -> list[str]:
    return answer_compare_to_markdown(answer_comparison).splitlines()


def _comparison_to_markdown(
    batch_id: str,
    batch_name: str,
    summary: dict[str, Any],
    comparison: RunComparisonResult,
    answer_comparison: AnswerCompareResult | None = None,
) -> str:
    lines: list[str] = []
    lines.append(f"# Batch Comparison Report: {batch_name}")
    lines.append("")
    lines.append(f"**Batch ID:** `{batch_id}`")
    lines.append(f"**Created:** {summary.get('created_at', '')}")
    lines.append("")

    totals = summary.get("totals", {})
    lines.append("## Batch Summary")
    lines.append("")
    lines.append(f"- **Runs created:** {totals.get('created', 0)}")
    lines.append(f"- **Failures:** {totals.get('failed', 0)}")
    lines.append(f"- **Harness pass:** {totals.get('harness_pass', 0)}")
    lines.append(f"- **Proof pass:** {totals.get('proof_pass', 0)}")
    lines.append(f"- **Total artifacts:** {totals.get('artifact_count', 0)}")
    lines.append("")

    lines.append("## Run Table")
    lines.append("")
    lines.append("| Run ID | Topic | Harness | Proof | Artifacts |")
    lines.append("| --- | --- | --- | --- | --- |")
    for lesson in comparison.lesson_comparison.per_run:
        proof_row = next(
            (p for p in comparison.proof_gate_comparison.per_run if p.run_id == lesson.run_id),
            None,
        )
        harness = "PASS" if proof_row and proof_row.harness_passed else "FAIL"
        proof = proof_row.proof_bundle_status if proof_row else "unknown"
        artifact_count = proof_row.artifact_count if proof_row else 0
        lines.append(
            f"| `{lesson.run_id}` | {lesson.topic} | {harness} | {proof} | {artifact_count} |"
        )
    lines.append("")

    lines.append("## Retrieval Overlap")
    lines.append("")
    for pair in comparison.retrieval_overlap.pairwise:
        lines.append(
            f"- **{pair.run_id_a} vs {pair.run_id_b}:** "
            f"source Jaccard {pair.source_jaccard:.2%}, "
            f"chunk Jaccard {pair.chunk_jaccard:.2%}, "
            f"{len(pair.shared_chunk_ids)} shared chunks"
        )
    if comparison.retrieval_overlap.all_shared_chunk_ids:
        lines.append(
            f"- **All runs share:** {len(comparison.retrieval_overlap.all_shared_chunk_ids)} chunks"
        )
    lines.append("")

    lines.append("## Claim Deltas")
    lines.append("")
    for row in comparison.claim_deltas.per_run:
        rate = (
            f"{row.citation_resolution_rate:.2%}"
            if row.citation_resolution_rate is not None
            else "N/A"
        )
        lines.append(
            f"- **`{row.run_id}`:** {row.supported_claims}/{row.total_claims} supported, "
            f"resolution {rate}, high-risk unsupported {row.unsupported_high_risk}"
        )
    for delta in comparison.claim_deltas.pairwise_deltas:
        rate_delta = (
            f"{delta.resolution_rate_delta:+.2%}"
            if delta.resolution_rate_delta is not None
            else "N/A"
        )
        lines.append(
            f"- **{delta.run_id_a} → {delta.run_id_b}:** "
            f"supported Δ{delta.supported_delta:+d}, resolution Δ{rate_delta}"
        )
    lines.append("")

    lines.append("## Proof / Harness Comparison")
    lines.append("")
    for row in comparison.proof_gate_comparison.per_run:
        harness = "PASS" if row.harness_passed else "FAIL"
        lines.append(
            f"- **`{row.run_id}`:** harness {harness}, proof {row.proof_bundle_status or 'unknown'}, "
            f"release gate {row.release_gate_status or 'unknown'}, "
            f"missing required {len(row.missing_required)}"
        )
    lines.append("")

    lines.append("## Recommendation")
    lines.append("")
    lines.append(comparison.recommendation)
    lines.append("")

    if answer_comparison is not None:
        lines.extend(_answer_comparison_to_markdown(answer_comparison))

    lines.append("## Artifact Paths")
    lines.append("")
    for run_id, path in comparison.artifact_paths.items():
        lines.append(f"- `{run_id}`: `{path}`")
    lines.append("")

    return "\n".join(lines)


def _persist_batch_artifacts(
    project_root: Path,
    batch_id: str,
    batch_name: str,
    created_at: str,
    items: list[dict],
    runs: list[dict],
    failures: list[dict],
) -> RunComparisonResult | None:
    batch_dir = _batches_dir(project_root) / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)

    run_ids = [r["run_id"] for r in runs if r.get("run_id")]
    comparison: RunComparisonResult | None = None
    if len(run_ids) >= 2:
        comparison = compare_runs(project_root, run_ids)

    manifest = {
        "batch_id": batch_id,
        "batch_name": batch_name,
        "created_at": created_at,
        "version": BATCH_VERSION,
        "items": items,
        "run_ids": run_ids,
        "runs": runs,
        "failures": failures,
        "status": "complete" if not failures else "partial",
    }
    _write_json(batch_dir / "batch_manifest.json", manifest)

    summary = _build_batch_summary(batch_id, batch_name, created_at, runs, failures, comparison)
    _write_json(batch_dir / "batch_summary.json", summary)

    if comparison is not None:
        comparison_payload = comparison.model_dump(mode="json")
        _write_json(batch_dir / "comparison_report.json", comparison_payload)
        answer_comparison: AnswerCompareResult | None = None
        try:
            answer_comparison = compare_run_answers(project_root, run_ids)
        except (FileNotFoundError, ValueError):
            answer_comparison = None
        md = _comparison_to_markdown(
            batch_id, batch_name, summary, comparison, answer_comparison
        )
        (batch_dir / "comparison_report.md").write_text(md, encoding="utf-8")

    return comparison


def create_batch(
    project_root: Path,
    batch_name: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a batch of lesson runs synchronously."""
    batch_name = batch_name.strip()
    if not batch_name:
        raise ValueError("batch_name is required")
    if not items:
        raise ValueError("items must not be empty")

    batch_id = _new_batch_id(project_root)
    created_at = datetime.now(timezone.utc).isoformat()
    runs: list[dict] = []
    failures: list[dict] = []

    for index, item in enumerate(items):
        topic = str(item.get("topic", "")).strip()
        source_pack = str(item.get("source_pack", "")).strip()
        try:
            result = create_lesson(
                topic=topic,
                source_pack=source_pack,
                difficulty=int(item.get("difficulty", 3)),
                task_format=str(item.get("lesson_format") or item.get("task_format") or "architecture_review"),
                retrieval_mode=str(item.get("retrieval_mode", "hybrid")),
                model_mode=item.get("model_mode"),
            )
            runs.append({
                "index": index,
                "run_id": result["run_id"],
                "topic": result["topic"],
                "source_pack": result["source_pack"],
                "status": result["status"],
                "harness_status": result["harness_status"],
                "proof_status": result["proof_status"],
                "artifact_count": result["artifact_count"],
                "run_url": result["run_url"],
            })
        except Exception as exc:
            failures.append({
                "index": index,
                "topic": topic,
                "source_pack": source_pack,
                "error": str(exc),
            })

    _persist_batch_artifacts(project_root, batch_id, batch_name, created_at, items, runs, failures)

    status = "complete" if runs and not failures else "partial" if runs else "failed"
    return {
        "batch_id": batch_id,
        "batch_name": batch_name,
        "status": status,
        "created_at": created_at,
        "runs": runs,
        "failures": failures,
    }


def list_batches(project_root: Path) -> list[dict[str, Any]]:
    """List all batch manifests."""
    batches_root = _batches_dir(project_root)
    if not batches_root.exists():
        return []

    results: list[dict[str, Any]] = []
    for batch_dir in sorted(batches_root.iterdir()):
        if not batch_dir.is_dir():
            continue
        manifest_path = batch_dir / "batch_manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        summary_path = batch_dir / "batch_summary.json"
        summary: dict[str, Any] = {}
        if summary_path.exists():
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                summary = {}
        results.append({
            "batch_id": manifest.get("batch_id", batch_dir.name),
            "batch_name": manifest.get("batch_name", ""),
            "created_at": manifest.get("created_at", ""),
            "status": manifest.get("status", "unknown"),
            "run_count": len(manifest.get("run_ids", [])),
            "failure_count": len(manifest.get("failures", [])),
            "topics": summary.get("topics", []),
            "source_packs": summary.get("source_packs", []),
        })
    return results


def get_batch(project_root: Path, batch_id: str) -> dict[str, Any]:
    """Load batch manifest and enrich run summaries."""
    batch_dir = _batches_dir(project_root) / batch_id
    manifest_path = batch_dir / "batch_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(batch_id)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary: dict[str, Any] = {}
    summary_path = batch_dir / "batch_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

    run_summaries: list[dict] = []
    runs_dir = project_root / "artifacts" / "runs"
    for run_id in manifest.get("run_ids", []):
        run_dir = runs_dir / run_id
        if run_dir.exists():
            run_summaries.append(summarize_run(run_dir).__dict__)

    return {
        "batch_id": manifest.get("batch_id", batch_id),
        "batch_name": manifest.get("batch_name", ""),
        "created_at": manifest.get("created_at", ""),
        "status": manifest.get("status", "unknown"),
        "version": manifest.get("version", BATCH_VERSION),
        "items": manifest.get("items", []),
        "runs": manifest.get("runs", []),
        "failures": manifest.get("failures", []),
        "run_ids": manifest.get("run_ids", []),
        "run_summaries": run_summaries,
        "summary": summary,
        "batch_dir": str(batch_dir),
        "has_comparison": (batch_dir / "comparison_report.json").exists(),
    }


def compare_batch_runs(project_root: Path, batch_id: str) -> dict[str, Any]:
    """Compare all runs in a batch (recomputes from artifacts)."""
    batch = get_batch(project_root, batch_id)
    run_ids = batch.get("run_ids", [])
    if len(run_ids) < 2:
        raise ValueError("At least two runs are required for comparison")

    comparison = compare_runs(project_root, run_ids)
    batch_dir = _batches_dir(project_root) / batch_id
    _write_json(batch_dir / "comparison_report.json", comparison.model_dump(mode="json"))

    summary_path = batch_dir / "batch_summary.json"
    summary: dict[str, Any] = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        summary = _build_batch_summary(
            batch_id,
            batch.get("batch_name", ""),
            batch.get("created_at", ""),
            batch.get("runs", []),
            batch.get("failures", []),
            comparison,
        )
    summary["comparison"] = {
        "run_ids": comparison.run_ids,
        "compared_at": comparison.compared_at,
        "all_passed_harness": comparison.proof_gate_comparison.all_passed_harness,
        "all_passed_proof": comparison.proof_gate_comparison.all_passed_proof,
        "recommendation": comparison.recommendation,
    }
    _write_json(summary_path, summary)

    md = _comparison_to_markdown(
        batch_id,
        batch.get("batch_name", ""),
        summary,
        comparison,
        _safe_answer_comparison(project_root, run_ids),
    )
    (batch_dir / "comparison_report.md").write_text(md, encoding="utf-8")

    return comparison.model_dump(mode="json")


def _safe_answer_comparison(project_root: Path, run_ids: list[str]) -> AnswerCompareResult | None:
    try:
        return compare_run_answers(project_root, run_ids)
    except (FileNotFoundError, ValueError):
        return None


def get_batch_report(project_root: Path, batch_id: str) -> dict[str, Any]:
    """Return comparison report JSON and markdown for a batch."""
    batch_dir = _batches_dir(project_root) / batch_id
    if not batch_dir.exists():
        raise FileNotFoundError(batch_id)

    json_path = batch_dir / "comparison_report.json"
    md_path = batch_dir / "comparison_report.md"
    summary_path = batch_dir / "batch_summary.json"

    if not json_path.exists():
        batch = get_batch(project_root, batch_id)
        run_ids = batch.get("run_ids", [])
        if len(run_ids) < 2:
            raise ValueError("At least two runs are required for a comparison report")
        compare_batch_runs(project_root, batch_id)

    comparison_json = json.loads(json_path.read_text(encoding="utf-8"))
    comparison_md = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    summary: dict[str, Any] = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

    return {
        "batch_id": batch_id,
        "comparison_report_json": comparison_json,
        "comparison_report_md": comparison_md,
        "batch_summary": summary,
        "report_paths": {
            "json": str(json_path),
            "markdown": str(md_path),
        },
    }
