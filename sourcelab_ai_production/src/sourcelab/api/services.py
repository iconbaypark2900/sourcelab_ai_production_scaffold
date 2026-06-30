"""Thin service wrappers over existing CLI/pipeline functions.

Instruction:
- Keep API as a thin layer over existing services.
- Do not duplicate business logic from CLI commands.
- Map service calls to API response schemas.
"""

from __future__ import annotations

import re
from pathlib import Path

from sourcelab.api.config import get_config
from sourcelab.api.errors import (
    bad_request_error,
    internal_error,
    not_found_error,
    validation_error,
)
from sourcelab.core.pipeline import run_demo_pipeline, run_lesson_create, run_answer_submit
from sourcelab.harness.runner import HarnessRunner
from sourcelab.sources.registry import SourceRegistry
from sourcelab.ui.run_loader import (
    list_runs,
    get_latest_run,
    load_run_artifact,
    load_json_artifact,
    load_artifact_inventory,
    load_learning_metrics,
    summarize_run,
)


def _get_project_root() -> Path:
    """Get project root from config."""
    return get_config().project_root


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def list_sources() -> list[dict]:
    """List all sources in the registry."""
    config = get_config()
    registry_path = config.project_root / "data" / "source_registry.json"

    if not registry_path.exists():
        # Bootstrap demo sources if registry doesn't exist
        registry = SourceRegistry.bootstrap_demo(config.project_root)
        return [s.model_dump(mode="json") for s in registry.sources]

    try:
        registry = SourceRegistry.load_from_json(registry_path)
    except FileNotFoundError:
        return []

    return [s.model_dump(mode="json") for s in registry.sources]


def get_source(source_id: str) -> dict:
    """Get a specific source by ID."""
    config = get_config()
    registry_path = config.project_root / "data" / "source_registry.json"

    if not registry_path.exists():
        raise not_found_error("source", source_id)

    try:
        registry = SourceRegistry.load_from_json(registry_path)
    except FileNotFoundError:
        raise not_found_error("source", source_id)

    source = registry.get(source_id)
    if source is None:
        raise not_found_error("source", source_id)

    return source.model_dump(mode="json")


def validate_sources() -> dict:
    """Validate all sources in the registry."""
    config = get_config()
    registry_path = config.project_root / "data" / "source_registry.json"

    if not registry_path.exists():
        return {
            "status": "FAIL",
            "source_count": 0,
            "errors": ["Registry file not found"],
            "warnings": [],
        }

    try:
        registry = SourceRegistry.load_from_json(registry_path)
    except FileNotFoundError as e:
        return {
            "status": "FAIL",
            "source_count": 0,
            "errors": [str(e)],
            "warnings": [],
        }

    errors = registry.validate()
    return {
        "status": "PASS" if not errors else "FAIL",
        "source_count": len(registry.sources),
        "errors": errors,
        "warnings": [],
    }


def approve_source(source_id: str) -> dict:
    """Approve a source."""
    config = get_config()
    registry_path = config.project_root / "data" / "source_registry.json"

    if not registry_path.exists():
        raise not_found_error("source", source_id)

    try:
        registry = SourceRegistry.load_from_json(registry_path)
    except FileNotFoundError:
        raise not_found_error("source", source_id)

    success = registry.approve_source(source_id)
    if not success:
        raise not_found_error("source", source_id)

    registry.save_to_json(registry_path)
    return {
        "source_id": source_id,
        "action": "approve",
        "success": True,
        "message": f"Source '{source_id}' approved",
    }


def reject_source(source_id: str, reason: str = "") -> dict:
    """Reject a source."""
    config = get_config()
    registry_path = config.project_root / "data" / "source_registry.json"

    if not registry_path.exists():
        raise not_found_error("source", source_id)

    try:
        registry = SourceRegistry.load_from_json(registry_path)
    except FileNotFoundError:
        raise not_found_error("source", source_id)

    success = registry.reject_source(source_id, reason)
    if not success:
        raise not_found_error("source", source_id)

    registry.save_to_json(registry_path)
    return {
        "source_id": source_id,
        "action": "reject",
        "success": True,
        "message": f"Source '{source_id}' rejected",
    }


def archive_source(source_id: str) -> dict:
    """Archive a source."""
    config = get_config()
    registry_path = config.project_root / "data" / "source_registry.json"

    if not registry_path.exists():
        raise not_found_error("source", source_id)

    try:
        registry = SourceRegistry.load_from_json(registry_path)
    except FileNotFoundError:
        raise not_found_error("source", source_id)

    success = registry.archive_source(source_id)
    if not success:
        raise not_found_error("source", source_id)

    registry.save_to_json(registry_path)
    return {
        "source_id": source_id,
        "action": "archive",
        "success": True,
        "message": f"Source '{source_id}' archived",
    }


def ingest_source(
    source_id: str,
    path: str,
    title: str = "",
    publisher: str = "local",
    source_type: str = "local_file",
    trust_tier: str = "C",
) -> dict:
    """Ingest a local source file and register it."""
    from sourcelab.sources.ingest_local import ingest_local_source
    from sourcelab.sources.registry import normalize_source_id

    config = get_config()
    project_root = config.project_root
    registry_path = project_root / "data" / "source_registry.json"

    filepath = Path(path)
    if not filepath.is_absolute():
        filepath = project_root / filepath

    if not filepath.exists():
        raise not_found_error("file", str(filepath))

    if registry_path.exists():
        registry = SourceRegistry.load_from_json(registry_path)
    else:
        registry = SourceRegistry(sources=[])

    record = ingest_local_source(
        filepath=filepath,
        trust_tier=trust_tier,
        publisher=publisher,
        source_type=source_type,
        registry=registry,
        project_root=project_root,
    )

    if record is None:
        return {
            "source_id": source_id,
            "status": "failed",
            "message": f"Could not ingest file: {filepath}",
        }

    if title:
        record.title = title

    registry.sources.append(record)
    registry.save_to_json(registry_path)

    return {
        "source_id": record.source_id,
        "status": "pending",
        "message": f"Source '{record.source_id}' ingested from {filepath.name}",
    }


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def search_sources(query: str, top_k: int = 5, mode: str = "hybrid") -> dict:
    """Search sources using hybrid search."""
    config = get_config()
    registry = SourceRegistry.bootstrap_demo(config.project_root)

    try:
        from sourcelab.retrieval.hybrid_search import HybridSearch
        search = HybridSearch.from_registry(registry)
        results, diagnostics = search.search(query, top_k=top_k)
    except Exception as e:
        raise internal_error("Search failed", str(e))

    return {
        "query": query,
        "mode": mode,
        "results": [
            {
                "chunk_id": r.chunk_id,
                "source_id": r.source_id,
                "title": r.title,
                "score": r.score,
                "trust_tier": r.trust_tier,
                "text_preview": r.text_preview,
            }
            for r in results
        ],
        "total": len(results),
    }


def build_index() -> dict:
    """Build search index from registry."""
    config = get_config()
    registry = SourceRegistry.bootstrap_demo(config.project_root)

    try:
        from sourcelab.retrieval.hybrid_search import HybridSearch
        search = HybridSearch.from_registry(registry)
        chunk_count = len(search.pocket_index.chunks)
        source_count = len(registry.sources)
    except Exception as e:
        raise internal_error("Index build failed", str(e))

    return {
        "status": "ok",
        "chunk_count": chunk_count,
        "source_count": source_count,
    }


def get_retrieval_diagnostics() -> dict:
    """Get retrieval diagnostics from the latest run."""
    config = get_config()
    runs_dir = config.project_root / "artifacts" / "runs"

    if not runs_dir.exists():
        return {
            "query": "",
            "mode": "hybrid",
            "result_count": 0,
            "total_chunks": 0,
            "weights": {
                "keyword": 0.35,
                "vector": 0.45,
                "trust": 0.15,
                "freshness": 0.05,
            },
        }

    runs = sorted([p for p in runs_dir.glob("*") if p.is_dir()])
    for run_dir in reversed(runs):
        diagnostics = load_json_artifact(run_dir, "retrieval_diagnostics.json")
        if diagnostics and isinstance(diagnostics, dict):
            return {
                "query": diagnostics.get("query", ""),
                "mode": diagnostics.get("mode", "hybrid"),
                "result_count": diagnostics.get("result_count", 0),
                "total_chunks": diagnostics.get("total_chunks", 0),
                "weights": diagnostics.get("weights", {
                    "keyword": 0.35,
                    "vector": 0.45,
                    "trust": 0.15,
                    "freshness": 0.05,
                }),
            }

    return {
        "query": "",
        "mode": "hybrid",
        "result_count": 0,
        "total_chunks": 0,
        "weights": {
            "keyword": 0.35,
            "vector": 0.45,
            "trust": 0.15,
            "freshness": 0.05,
        },
    }


# ---------------------------------------------------------------------------
# Lessons
# ---------------------------------------------------------------------------

def _resolve_model_router(
    model_mode: str | None,
    model_backend: str | None,
    model_name: str | None,
    model_base_url: str | None,
):
    """Map API model settings to the generation ModelRouter."""
    if not model_mode or model_mode == "deterministic":
        return None

    from sourcelab.generation.model_router import ModelRouter
    from sourcelab.models.schemas import ModelRouterConfig

    router_mode = "local_llm"
    backend = model_backend or "deterministic"
    if model_mode in {"ollama", "openai_compatible"}:
        backend = model_mode
    elif model_mode == "local":
        backend = model_backend or "deterministic"

    mconfig = ModelRouterConfig(
        mode=router_mode,
        backend=backend,
        model_name=model_name or "",
        base_url=model_base_url or "",
    )
    return ModelRouter(config=mconfig)


def create_lesson(
    topic: str,
    source_pack: str,
    level: str = "intermediate",
    source_policy: str = "approved_only",
    difficulty: int = 3,
    task_format: str = "architecture_review",
    retrieval_mode: str = "hybrid",
    audience: str = "engineer",
    model_mode: str | None = None,
    model_backend: str | None = None,
    model_name: str | None = None,
    model_base_url: str | None = None,
) -> dict:
    """Create a lesson package."""
    config = get_config()
    topic = topic.strip()
    source_pack = source_pack.strip()

    if not topic:
        raise validation_error("Topic is required", "Provide a non-empty topic string.")

    if not source_pack:
        raise validation_error(
            "Source pack is required",
            "Provide a source_pack such as pqc_v1.",
        )

    from sourcelab.sources.source_pack import validate_source_pack

    pack_validation = validate_source_pack(config.project_root, source_pack)
    if not pack_validation.get("valid"):
        errors = pack_validation.get("errors") or ["Invalid source pack"]
        raise validation_error(
            f"Invalid source pack: {source_pack}",
            "; ".join(errors),
        )

    model_router = _resolve_model_router(
        model_mode=model_mode,
        model_backend=model_backend,
        model_name=model_name,
        model_base_url=model_base_url,
    )

    try:
        result = run_lesson_create(
            topic=topic,
            project_root=config.project_root,
            difficulty=difficulty,
            task_format=task_format,
            model_router=model_router,
            source_pack=source_pack,
            retrieval_mode=retrieval_mode,
        )
    except Exception as e:
        raise internal_error("Lesson creation failed", str(e))

    run_id = result.get("run_id", "")
    harness_passed = result.get("harness_passed")
    harness_status = "PASS" if harness_passed else "FAIL"
    verification = result.get("verification") or {}
    proof_status = verification.get("release_gate_status") or "UNKNOWN"
    artifact_count = int(result.get("artifact_count") or 0)

    return {
        "lesson_id": run_id,
        "run_id": run_id,
        "status": "created",
        "topic": topic,
        "source_pack": source_pack,
        "harness_status": harness_status,
        "proof_status": proof_status,
        "artifact_count": artifact_count,
        "run_url": f"/runs/{run_id}",
    }


def show_lesson(run_id: str | None = None) -> dict:
    """Show a lesson package."""
    config = get_config()
    project_root = config.project_root

    runs_dir = project_root / "artifacts" / "runs"
    if not runs_dir.exists():
        raise not_found_error("run", run_id or "latest")

    if run_id:
        run_dir = runs_dir / run_id
        if not run_dir.exists():
            raise not_found_error("run", run_id)
    else:
        # Get latest run
        runs = sorted([p for p in runs_dir.glob("*") if p.is_dir()])
        if not runs:
            raise not_found_error("run", "latest")
        run_dir = runs[-1]
        run_id = run_dir.name

    # Load artifacts
    manifest = load_json_artifact(run_dir, "run_manifest.json")
    lesson_md = load_run_artifact(run_dir, "generated_lesson.md")
    answer_key_md = load_run_artifact(run_dir, "answer_key.md")

    topic = manifest.get("topic", "") if manifest else ""
    source_ids = manifest.get("source_ids", []) if manifest else []

    return {
        "run_id": run_id,
        "topic": topic,
        "lesson_markdown": lesson_md or "",
        "answer_key_markdown": answer_key_md,
        "sources": source_ids,
    }


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

def list_all_runs() -> list[dict]:
    """List all runs."""
    config = get_config()
    runs = list_runs(config.project_root)
    return [r.__dict__ for r in runs]


def get_latest_run_summary() -> dict | None:
    """Get latest run summary."""
    config = get_config()
    run = get_latest_run(config.project_root)
    if run is None:
        return None
    return run.__dict__


def get_run_summary(run_id: str) -> dict:
    """Get a specific run summary."""
    config = get_config()
    runs_dir = config.project_root / "artifacts" / "runs" / run_id

    if not runs_dir.exists():
        raise not_found_error("run", run_id)

    summary = summarize_run(runs_dir)
    return summary.__dict__


def get_run_artifacts(run_id: str) -> list[dict]:
    """Get artifacts for a run."""
    config = get_config()
    runs_dir = config.project_root / "artifacts" / "runs" / run_id

    if not runs_dir.exists():
        raise not_found_error("run", run_id)

    artifacts = load_artifact_inventory(runs_dir)
    return [a.__dict__ for a in artifacts]


_SAFE_ARTIFACT_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def get_run_artifact_content(run_id: str, artifact_name: str) -> dict:
    """Return the parsed content of a single artifact for a run.

    Read-only. Reuses the same loaders as the dashboard. Rejects unsafe
    artifact names and refuses to read outside the run directory.
    """
    config = get_config()
    run_dir = config.project_root / "artifacts" / "runs" / run_id

    if not run_dir.exists():
        raise not_found_error("run", run_id)

    if not _SAFE_ARTIFACT_NAME.match(artifact_name) or artifact_name in {".", ".."}:
        raise bad_request_error(
            "Invalid artifact name",
            "Artifact names may only contain letters, digits, '.', '_' and '-'.",
        )

    artifact_path = run_dir / artifact_name
    try:
        artifact_path.resolve().relative_to(run_dir.resolve())
    except ValueError:
        raise bad_request_error("Invalid artifact path", artifact_name)

    if not artifact_path.exists() or not artifact_path.is_file():
        return {
            "run_id": run_id,
            "artifact_name": artifact_name,
            "exists": False,
            "artifact_type": "unknown",
            "content_json": None,
            "content_text": None,
        }

    suffix = artifact_path.suffix.lower()
    if suffix == ".json":
        return {
            "run_id": run_id,
            "artifact_name": artifact_name,
            "exists": True,
            "artifact_type": "json",
            "content_json": load_json_artifact(run_dir, artifact_name),
            "content_text": None,
        }

    return {
        "run_id": run_id,
        "artifact_name": artifact_name,
        "exists": True,
        "artifact_type": "markdown" if suffix in {".md", ".markdown"} else "text",
        "content_json": None,
        "content_text": load_run_artifact(run_dir, artifact_name),
    }


def get_proof_bundle(run_id: str | None = None) -> dict:
    """Get proof bundle for a run."""
    config = get_config()
    runs_dir = config.project_root / "artifacts" / "runs"

    if not runs_dir.exists():
        raise not_found_error("run", run_id or "latest")

    if run_id:
        run_dir = runs_dir / run_id
    else:
        runs = sorted([p for p in runs_dir.glob("*") if p.is_dir()])
        if not runs:
            raise not_found_error("run", "latest")
        run_dir = runs[-1]
        run_id = run_dir.name

    if not run_dir.exists():
        raise not_found_error("run", run_id)

    manifest = load_json_artifact(run_dir, "proof_bundle_manifest.json")
    summary = load_json_artifact(run_dir, "proof_summary.json")

    return {
        "run_id": run_id,
        "status": summary.get("release_gate_status", "unknown") if summary else "unknown",
        "manifest": manifest or {},
        "summary": summary or {},
    }


def get_harness_report(run_id: str | None = None) -> dict:
    """Get harness report for a run."""
    config = get_config()
    runs_dir = config.project_root / "artifacts" / "runs"

    if not runs_dir.exists():
        raise not_found_error("run", run_id or "latest")

    if run_id:
        run_dir = runs_dir / run_id
    else:
        runs = sorted([p for p in runs_dir.glob("*") if p.is_dir()])
        if not runs:
            raise not_found_error("run", "latest")
        run_dir = runs[-1]
        run_id = run_dir.name

    if not run_dir.exists():
        raise not_found_error("run", run_id)

    try:
        runner = HarnessRunner()
        report = runner.validate_run(run_dir)
    except Exception as e:
        raise internal_error("Harness validation failed", str(e))

    return {
        "run_id": run_id,
        "passed": report.get("passed", False),
        "checks": report.get("checks", []),
        "blocking_failures": report.get("blocking_failures", []),
        "warnings": report.get("warnings", []),
        "artifact_count": report.get("artifact_count", 0),
    }


# ---------------------------------------------------------------------------
# Learning
# ---------------------------------------------------------------------------

def _resolve_run_dir(runs_dir: Path, run_id: str | None) -> tuple[Path, str]:
    """Resolve a run id ("latest"/None -> most recent) to a concrete run dir.

    Raises a structured 404 when the run cannot be located.
    """
    requested = (run_id or "").strip()
    if requested in ("", "latest"):
        if not runs_dir.exists():
            raise not_found_error("run", "latest")
        candidates = sorted([p for p in runs_dir.glob("*") if p.is_dir()])
        if not candidates:
            raise not_found_error("run", "latest")
        run_dir = candidates[-1]
        return run_dir, run_dir.name

    run_dir = runs_dir / requested
    if not run_dir.exists() or not run_dir.is_dir():
        raise not_found_error("run", requested)
    return run_dir, requested


def submit_answer(
    answer_text: str,
    run_id: str | None = None,
    topic: str | None = None,
) -> dict:
    """Submit a learner answer for scoring against a run.

    Thin wrapper over :func:`run_answer_submit` (the same function the
    ``answer submit`` CLI uses). It resolves ``run_id`` ("latest"/None -> the
    most recent run), validates the answer, resolves the topic from the run
    manifest when omitted, then re-summarizes the run so the response exposes
    the same transparent learning metrics the run summary renders.
    """
    config = get_config()
    project_root = config.project_root
    runs_dir = project_root / "artifacts" / "runs"

    # Clean validation: empty/whitespace answers are rejected, not scored.
    if not answer_text or not answer_text.strip():
        raise validation_error(
            "answer_text must not be empty",
            "Provide a non-empty learner answer to score.",
        )

    run_dir, resolved_run_id = _resolve_run_dir(runs_dir, run_id)

    # Resolve the topic from the run when the caller did not supply one.
    resolved_topic = (topic or "").strip()
    if not resolved_topic:
        manifest = load_json_artifact(run_dir, "run_manifest.json")
        if isinstance(manifest, dict):
            resolved_topic = str(manifest.get("topic") or "")
    if not resolved_topic:
        package = load_json_artifact(run_dir, "generated_lesson_package.json")
        if isinstance(package, dict):
            resolved_topic = str(package.get("topic") or "")

    # Score via the existing deterministic pipeline (the source of truth).
    try:
        result = run_answer_submit(
            topic=resolved_topic,
            answer_text=answer_text,
            project_root=project_root,
            run_id=resolved_run_id,
        )
    except Exception as e:  # pragma: no cover - defensive
        raise internal_error("Answer submission failed", str(e))

    # run_answer_submit returns a structured {"error": ...} for runs that are
    # missing the artifacts required to score (e.g. retrieved_chunks.json).
    if isinstance(result, dict) and result.get("error"):
        raise bad_request_error("Cannot score answer for this run", str(result["error"]))

    # Re-summarize so the response matches the run summary the UI renders.
    summary = summarize_run(run_dir)
    metrics = load_learning_metrics(run_dir)

    next_task_decision = result.get("next_task") if isinstance(result, dict) else {}
    if not isinstance(next_task_decision, dict):
        next_task_decision = {}
    next_task_focus = next_task_decision.get("focus") or summary.next_task_focus or ""

    learning_report = run_dir / "learning_report.json"
    learning_report_path = str(learning_report) if learning_report.exists() else None

    overall = summary.overall_score
    if overall is None:
        overall = metrics.get("overall_score")
    if overall is None and isinstance(result, dict):
        overall = result.get("overall_score")

    return {
        "run_id": resolved_run_id,
        "topic": resolved_topic or summary.topic,
        "attempt_id": result.get("attempt_id") if isinstance(result, dict) else None,
        "attempt_manifest_path": result.get("attempt_manifest_path") if isinstance(result, dict) else None,
        "overall_score": overall,
        "rubric_alignment_score": summary.rubric_alignment_score,
        "uncapped_score": summary.uncapped_score,
        "source_grounding_score": summary.source_grounding_score,
        "concept_overlap_grounding_score": summary.concept_overlap_grounding_score,
        "needs_review": summary.needs_review,
        "cap_reason": summary.cap_reason or "",
        "human_review_reason": summary.human_review_reason or "",
        "next_task_focus": next_task_focus,
        "next_task_decision": next_task_decision,
        "learning_report_path": learning_report_path,
        # Legacy / backward-compatible fields.
        "score": overall if overall is not None else 0.0,
        "feedback": str(result.get("recommended_focus", "")) if isinstance(result, dict) else "",
        "next_task_id": None,
        "breakdown": {},
    }


def get_skill_profile(topic: str | None = None) -> dict:
    """Get skill profile."""
    config = get_config()

    try:
        from sourcelab.learning.skill_profile import load_profile
        profile = load_profile(project_root=config.project_root)
        if topic:
            # Filter by topic if provided
            profile.topic = topic
        return {
            "profile_id": profile.user_id,
            "topic": topic,
            "attempts": [a.model_dump() for a in profile.attempts],
            "mastery": profile.topic_mastery,
            "criterion_mastery": profile.criterion_mastery,
            "strengths": [s.model_dump() if hasattr(s, 'model_dump') else s for s in profile.strengths],
            "weaknesses": [w.model_dump() for w in profile.weaknesses],
            "source_grounding_history": profile.source_grounding_history,
            "preferred_next_difficulty": profile.preferred_next_difficulty,
            "preferred_guidance_level": profile.preferred_guidance_level,
            "last_practiced": profile.last_practiced,
        }
    except Exception as e:
        raise internal_error("Failed to load skill profile", str(e))


def get_curriculum() -> dict:
    """Get full curriculum overview: profile + latest report + next task."""
    config = get_config()
    project_root = config.project_root

    profile_data: dict = get_skill_profile()

    latest_report: dict | None = None
    try:
        latest_report = get_learning_report()
    except Exception:
        pass

    latest_next_task: dict | None = None
    try:
        latest_next_task = get_next_task()
    except Exception:
        pass

    return {
        "profile": profile_data,
        "latest_report": latest_report,
        "latest_next_task": latest_next_task,
    }


def get_learning_report(run_id: str | None = None) -> dict:
    """Get learning report."""
    config = get_config()
    runs_dir = config.project_root / "artifacts" / "runs"

    if not runs_dir.exists():
        raise not_found_error("run", run_id or "latest")

    if run_id:
        run_dir = runs_dir / run_id
    else:
        runs = sorted([p for p in runs_dir.glob("*") if p.is_dir()])
        if not runs:
            raise not_found_error("run", "latest")
        run_dir = runs[-1]
        run_id = run_dir.name

    if not run_dir.exists():
        raise not_found_error("run", run_id)

    manifest = load_json_artifact(run_dir, "run_manifest.json")
    topic = manifest.get("topic", "") if manifest else ""

    report_md = load_run_artifact(run_dir, "learning_report.md")
    report_json = load_json_artifact(run_dir, "learning_report.json")

    return {
        "run_id": run_id,
        "topic": topic,
        "report_markdown": report_md or "",
        "report_json": report_json or {},
    }


def get_next_task(run_id: str | None = None) -> dict:
    """Get next task recommendation."""
    config = get_config()
    runs_dir = config.project_root / "artifacts" / "runs"

    if not runs_dir.exists():
        raise not_found_error("run", run_id or "latest")

    if run_id:
        run_dir = runs_dir / run_id
    else:
        runs = sorted([p for p in runs_dir.glob("*") if p.is_dir()])
        if not runs:
            raise not_found_error("run", "latest")
        run_dir = runs[-1]
        run_id = run_dir.name

    if not run_dir.exists():
        raise not_found_error("run", run_id)

    next_task = load_json_artifact(run_dir, "next_task_decision.json")
    if not next_task:
        return {
            "topic": "",
            "focus": "",
            "task_format": "",
            "difficulty": 3,
            "guidance_level": 3,
            "reason": "No next task recommendation available",
        }

    return {
        "topic": next_task.get("topic", ""),
        "focus": next_task.get("focus", ""),
        "task_format": next_task.get("task_format", ""),
        "difficulty": next_task.get("difficulty", 3),
        "guidance_level": next_task.get("guidance_level", 3),
        "reason": next_task.get("reason", ""),
    }


def get_answer_history(run_id: str | None = None) -> dict:
    """List immutable answer attempts for a run."""
    config = get_config()
    runs_dir = config.project_root / "artifacts" / "runs"
    run_dir, resolved_run_id = _resolve_run_dir(runs_dir, run_id)
    from sourcelab.learning.answer_history import list_answer_attempts

    history = list_answer_attempts(run_dir, resolved_run_id)
    return history.model_dump()


def get_answer_attempt(run_id: str | None, attempt_id: str) -> dict:
    """Load full detail for a single answer attempt."""
    config = get_config()
    runs_dir = config.project_root / "artifacts" / "runs"
    run_dir, resolved_run_id = _resolve_run_dir(runs_dir, run_id)
    from sourcelab.learning.answer_history import get_answer_attempt_detail

    detail = get_answer_attempt_detail(run_dir, resolved_run_id, attempt_id)
    if detail is None:
        raise not_found_error("attempt", attempt_id)
    return detail.model_dump()


def get_answer_diff(
    run_id: str | None,
    from_attempt_id: str,
    to_attempt_id: str,
) -> dict:
    """Compute delta between two answer attempts."""
    config = get_config()
    runs_dir = config.project_root / "artifacts" / "runs"
    run_dir, resolved_run_id = _resolve_run_dir(runs_dir, run_id)
    from sourcelab.learning.answer_history import compute_answer_diff

    diff = compute_answer_diff(run_dir, resolved_run_id, from_attempt_id, to_attempt_id)
    if diff is None:
        raise not_found_error("attempt", f"{from_attempt_id} or {to_attempt_id}")
    return diff.model_dump()


# ---------------------------------------------------------------------------
# Source Packs
# ---------------------------------------------------------------------------

def list_source_packs_api() -> dict:
    """List available source packs."""
    config = get_config()
    from sourcelab.sources.source_pack import list_source_packs
    packs = list_source_packs(config.project_root)
    return {"packs": packs, "total": len(packs)}


def validate_source_pack_api(pack_name: str) -> dict:
    """Validate a source pack."""
    config = get_config()
    from sourcelab.sources.source_pack import validate_source_pack
    return validate_source_pack(config.project_root, pack_name)


def install_source_pack_api(pack_name: str) -> dict:
    """Install a source pack."""
    config = get_config()
    from sourcelab.sources.source_pack import install_source_pack
    return install_source_pack(config.project_root, pack_name)


def source_pack_status_api(pack_name: str) -> dict:
    """Check source pack installation status."""
    config = get_config()
    from sourcelab.sources.source_pack import source_pack_status
    return source_pack_status(config.project_root, pack_name)


# ---------------------------------------------------------------------------
# Evaluations
# ---------------------------------------------------------------------------

def run_evals_api(pack_name: str, eval_type: str | None = None) -> dict:
    """Run golden evals for a source pack."""
    config = get_config()
    from sourcelab.evals.runner import run_golden_evals

    eval_types = [eval_type] if eval_type else None
    result = run_golden_evals(
        project_root=config.project_root,
        pack_name=pack_name,
        eval_types=eval_types,
    )
    return {
        "status": "ok",
        "pack_name": pack_name,
        "summary": result.get("summary"),
        "results": {k: v for k, v in result.items() if k not in ("summary", "output_dir")},
        "output_dir": result.get("output_dir", ""),
    }


def evals_latest_api(pack_name: str) -> dict:
    """Show latest eval results."""
    config = get_config()
    evals_dir = config.project_root / "artifacts" / "evals" / pack_name

    if not evals_dir.exists():
        return {"pack_name": pack_name, "summary": {}, "markdown": ""}

    summary_path = evals_dir / "golden_eval_summary.json"
    summary = {}
    if summary_path.exists():
        import json
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

    md_path = evals_dir / "golden_eval_summary.md"
    markdown = ""
    if md_path.exists():
        markdown = md_path.read_text(encoding="utf-8")

    return {
        "pack_name": pack_name,
        "summary": summary,
        "markdown": markdown,
    }


def evals_history_api(pack_name: str, limit: int = 50) -> dict:
    """Return eval trend history for a source pack.

    Reads snapshots from ``<project>/artifacts/evals/<pack>/history/``,
    newest first, and computes the pass-rate delta between the two most
    recent snapshots.
    """
    config = get_config()
    from sourcelab.evals.runner import read_eval_history

    raw_history = read_eval_history(pack_name, config.project_root, limit=limit)

    history = [
        {
            "snapshot_at": entry.get("snapshot_at", ""),
            "pack_name": entry.get("pack_name"),
            "total_evals": entry.get("total_evals"),
            "total_cases": entry.get("total_cases"),
            "total_passed": entry.get("total_passed"),
            "total_failed": entry.get("total_failed"),
            "overall_pass_rate": entry.get("overall_pass_rate"),
        }
        for entry in raw_history
    ]

    latest = history[0]["overall_pass_rate"] if history else None
    previous = history[1]["overall_pass_rate"] if len(history) > 1 else None
    delta: float | None = None
    if latest is not None and previous is not None:
        delta = round(latest - previous, 4)

    return {
        "pack_name": pack_name,
        "history": history,
        "latest_pass_rate": latest,
        "previous_pass_rate": previous,
        "pass_rate_delta": delta,
        "run_count": len(history),
    }


def evals_thresholds_api(pack_name: str) -> dict:
    """Return per-pack eval thresholds and compliance against the latest summary."""
    config = get_config()
    from sourcelab.evals.thresholds import (
        evaluate_against_thresholds,
        load_pack_thresholds,
    )

    thresholds = load_pack_thresholds(config.project_root, pack_name)
    summary_path = (
        config.project_root / "artifacts" / "evals" / pack_name / "golden_eval_summary.json"
    )
    summary: dict | None = None
    if summary_path.is_file():
        try:
            import json as _json

            summary = _json.loads(summary_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            summary = None

    evaluation = evaluate_against_thresholds(pack_name, summary, thresholds)
    return evaluation.to_dict()


# ---------------------------------------------------------------------------
# Batch runs & comparison (v2.0)
# ---------------------------------------------------------------------------

def create_batch_runs(batch_name: str, items: list[dict]) -> dict:
    """Create a batch of lesson runs synchronously."""
    from sourcelab.batch.service import create_batch

    config = get_config()
    if not items:
        raise validation_error("items must not be empty", "Provide at least one batch item.")

    try:
        return create_batch(config.project_root, batch_name, items)
    except ValueError as exc:
        raise validation_error(str(exc), str(exc))


def list_all_batches() -> list[dict]:
    """List all batches."""
    from sourcelab.batch.service import list_batches

    config = get_config()
    return list_batches(config.project_root)


def get_batch_detail(batch_id: str) -> dict:
    """Get batch detail."""
    from sourcelab.batch.service import get_batch

    config = get_config()
    try:
        return get_batch(config.project_root, batch_id)
    except FileNotFoundError:
        raise not_found_error("batch", batch_id)


def compare_batch(batch_id: str) -> dict:
    """Compare runs in a batch."""
    from sourcelab.batch.service import compare_batch_runs

    config = get_config()
    try:
        return compare_batch_runs(config.project_root, batch_id)
    except FileNotFoundError:
        raise not_found_error("batch", batch_id)
    except ValueError as exc:
        raise validation_error(str(exc), str(exc))


def get_batch_comparison_report(batch_id: str) -> dict:
    """Get batch comparison report."""
    from sourcelab.batch.service import get_batch_report

    config = get_config()
    try:
        return get_batch_report(config.project_root, batch_id)
    except FileNotFoundError:
        raise not_found_error("batch", batch_id)
    except ValueError as exc:
        raise validation_error(str(exc), str(exc))


def compare_run_ids(run_ids: list[str]) -> dict:
    """Compare two or more runs by ID."""
    from sourcelab.comparison.run_compare import compare_runs

    config = get_config()
    normalized = [rid.strip() for rid in run_ids if rid.strip()]
    if len(normalized) < 2:
        raise validation_error(
            "At least two run_ids are required",
            "Provide run_ids as a comma-separated list with two or more IDs.",
        )

    missing: list[str] = []
    for run_id in normalized:
        run_dir = config.project_root / "artifacts" / "runs" / run_id
        if not run_dir.exists():
            missing.append(run_id)
    if missing:
        raise not_found_error("run", missing[0])

    try:
        result = compare_runs(config.project_root, normalized)
    except FileNotFoundError as exc:
        raise not_found_error("run", str(exc))

    return result.model_dump(mode="json")


def compare_batch_answers(batch_id: str) -> dict:
    """Compare learner answer attempts for all runs in a batch."""
    from sourcelab.comparison.answer_compare import compare_batch_answers as _compare_batch_answers

    config = get_config()
    try:
        result = _compare_batch_answers(config.project_root, batch_id)
    except FileNotFoundError:
        raise not_found_error("batch", batch_id)
    except ValueError as exc:
        raise validation_error(str(exc), str(exc))

    payload = result.model_dump(mode="json")
    payload["batch_id"] = batch_id
    return payload


def compare_run_answers(run_ids: list[str]) -> dict:
    """Compare learner answer attempts across two or more runs."""
    from sourcelab.comparison.answer_compare import compare_run_answers as _compare_run_answers

    config = get_config()
    normalized = [rid.strip() for rid in run_ids if rid.strip()]
    if len(normalized) < 2:
        raise validation_error(
            "At least two run_ids are required",
            "Provide run_ids as a comma-separated list with two or more IDs.",
        )

    missing: list[str] = []
    for run_id in normalized:
        run_dir = config.project_root / "artifacts" / "runs" / run_id
        if not run_dir.exists():
            missing.append(run_id)
    if missing:
        raise not_found_error("run", missing[0])

    try:
        result = _compare_run_answers(config.project_root, normalized)
    except FileNotFoundError as exc:
        raise not_found_error("run", str(exc))

    return result.model_dump(mode="json")
