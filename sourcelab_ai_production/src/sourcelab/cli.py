"""Command line interface for SourceLab AI.

Instructions:
- Use `sourcelab demo` to run the full local proof flow.
- Use `sourcelab verify-release` to run built-in release gates.
- Use `sourcelab ingest-local` to add local sources to the registry.
- Use `sourcelab lesson create` to generate a lesson package.
- Use `sourcelab lesson show --latest` to view the latest lesson.
- Use `sourcelab verify latest` to verify the latest run.
- Use `sourcelab verify run <run_id>` to verify a specific run.
- Use `sourcelab verify claims --latest` to view claims from the latest run.
- Use `sourcelab review queue --latest` to view the human review queue.
- Use `sourcelab proof latest` to view the latest proof bundle.
- Use `sourcelab proof run <run_id>` to view a specific proof bundle.
- Use `sourcelab proof artifacts --latest` to list artifacts from the latest run.
- Use `sourcelab harness latest` to view the latest harness report.
- Use `sourcelab harness run <run_id>` to view a specific harness report.
- Use `sourcelab dashboard` to launch the Streamlit dashboard.
- Use `sourcelab runs list` to list all runs.
- Use `sourcelab runs latest` to show the latest run summary.
- Use `sourcelab runs show <run_id>` to explore a specific run.
- Use `sourcelab export latest --format markdown` to export the latest run.
- Use `sourcelab api` to start the API server.
- This CLI avoids external APIs so the scaffold works offline.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sourcelab.core.pipeline import run_demo_pipeline, run_lesson_create, run_answer_submit
from sourcelab.harness.release_gate import verify_release
from sourcelab.harness.runner import HarnessRunner
from sourcelab.doctor import run_doctor
from sourcelab.init_local import run_init_local
from sourcelab.version import version_info
from sourcelab.sources.registry import (
    SourceRegistry,
    SUPPORTED_EXTENSIONS,
    VALID_TRUST_TIERS,
    normalize_source_id,
)
from sourcelab.sources.source_pack import (
    list_source_packs,
    load_source_pack_manifest,
    install_source_pack,
    validate_source_pack,
    doctor_source_pack,
    source_pack_status,
)
from sourcelab.retrieval.index import PocketIndex


def _json(data: object) -> None:
    print(json.dumps(data, indent=2, default=str))


def _get_latest_run_dir() -> Path | None:
    """Get the latest run directory."""
    runs_dir = Path("artifacts/runs")
    if not runs_dir.exists():
        return None
    runs = sorted([p for p in runs_dir.glob("*") if p.is_dir()])
    return runs[-1] if runs else None


def _get_run_dir(run_id: str | None = None) -> Path | None:
    """Get a specific run directory or the latest one."""
    if run_id:
        run_dir = Path("artifacts/runs") / run_id
        return run_dir if run_dir.exists() else None
    return _get_latest_run_dir()


def cmd_version(args: argparse.Namespace) -> None:
    """Print package version metadata."""
    _json(version_info(Path.cwd()))


def cmd_doctor(args: argparse.Namespace) -> None:
    """Run environment readiness checks."""
    _json(run_doctor(Path.cwd()))


def cmd_init_local(args: argparse.Namespace) -> None:
    """Run idempotent first-run local setup."""
    result = run_init_local(Path.cwd())
    _json(result)
    if result.get("passed"):
        print("\nNext commands:", file=sys.stderr)
        for command in result.get("next_commands", []):
            print(f"  {command}", file=sys.stderr)


def cmd_demo(args: argparse.Namespace) -> None:
    model_router = None
    if getattr(args, "model_mode", None):
        from sourcelab.generation.model_router import ModelRouter
        from sourcelab.models.schemas import ModelRouterConfig

        config = ModelRouterConfig(
            mode=args.model_mode,
            backend=getattr(args, "model_backend", "deterministic"),
            model_name=getattr(args, "model_name", ""),
            base_url=getattr(args, "model_base_url", ""),
        )
        model_router = ModelRouter(config=config)

    result = run_demo_pipeline(topic=args.topic, project_root=Path.cwd(), model_router=model_router)
    _json(result)


def cmd_status(args: argparse.Namespace) -> None:
    runs_dir = Path("artifacts/runs")
    runs = sorted([p for p in runs_dir.glob("*") if p.is_dir()]) if runs_dir.exists() else []
    _json({
        "project_root": str(Path.cwd()),
        "run_count": len(runs),
        "latest_run": str(runs[-1]) if runs else None,
    })


def cmd_sources_list(args: argparse.Namespace) -> None:
    registry = SourceRegistry.bootstrap_demo(Path.cwd())
    _json([source.model_dump() for source in registry.sources])


def cmd_sources_validate(args: argparse.Namespace) -> None:
    registry_path = Path.cwd() / "data" / "source_registry.json"
    try:
        registry = SourceRegistry.load_from_json(registry_path)
    except FileNotFoundError as e:
        _json({"status": "FAIL", "source_count": 0, "errors": [str(e)], "warnings": []})
        return

    errors = registry.validate()
    _json({
        "status": "PASS" if not errors else "FAIL",
        "source_count": len(registry.sources),
        "errors": errors,
        "warnings": [],
    })


def cmd_sources_export(args: argparse.Namespace) -> None:
    registry_path = Path.cwd() / "data" / "source_registry.json"
    try:
        registry = SourceRegistry.load_from_json(registry_path)
    except FileNotFoundError as e:
        _json({"error": str(e)})
        return
    _json(registry.export_snapshot())


def cmd_sources_approve(args: argparse.Namespace) -> None:
    """Approve a source."""
    registry_path = Path.cwd() / "data" / "source_registry.json"
    try:
        registry = SourceRegistry.load_from_json(registry_path)
    except FileNotFoundError as e:
        _json({"status": "FAIL", "error": str(e)})
        return

    success = registry.approve_source(args.source_id)
    if success:
        registry.save_to_json(registry_path)
        _json({"status": "PASS", "message": f"Source '{args.source_id}' approved"})
    else:
        _json({"status": "FAIL", "error": f"Source '{args.source_id}' not found"})


def cmd_sources_reject(args: argparse.Namespace) -> None:
    """Reject a source."""
    registry_path = Path.cwd() / "data" / "source_registry.json"
    try:
        registry = SourceRegistry.load_from_json(registry_path)
    except FileNotFoundError as e:
        _json({"status": "FAIL", "error": str(e)})
        return

    success = registry.reject_source(args.source_id, args.reason)
    if success:
        registry.save_to_json(registry_path)
        _json({
            "status": "PASS",
            "message": f"Source '{args.source_id}' rejected",
            "reason": args.reason,
        })
    else:
        _json({"status": "FAIL", "error": f"Source '{args.source_id}' not found"})


def cmd_sources_archive(args: argparse.Namespace) -> None:
    """Archive a source."""
    registry_path = Path.cwd() / "data" / "source_registry.json"
    try:
        registry = SourceRegistry.load_from_json(registry_path)
    except FileNotFoundError as e:
        _json({"status": "FAIL", "error": str(e)})
        return

    success = registry.archive_source(args.source_id)
    if success:
        registry.save_to_json(registry_path)
        _json({"status": "PASS", "message": f"Source '{args.source_id}' archived"})
    else:
        _json({"status": "FAIL", "error": f"Source '{args.source_id}' not found"})


def cmd_sources_pending(args: argparse.Namespace) -> None:
    """List sources pending review."""
    registry_path = Path.cwd() / "data" / "source_registry.json"
    try:
        registry = SourceRegistry.load_from_json(registry_path)
    except FileNotFoundError as e:
        _json({"status": "FAIL", "error": str(e)})
        return

    pending = registry.get_pending_sources()
    _json({
        "status": "PASS",
        "pending_count": len(pending),
        "sources": [s.model_dump() for s in pending],
    })


def cmd_sources_freshness(args: argparse.Namespace) -> None:
    """Check source freshness."""
    from sourcelab.sources.freshness import check_all_sources_freshness, format_freshness_report

    registry_path = Path.cwd() / "data" / "source_registry.json"
    try:
        registry = SourceRegistry.load_from_json(registry_path)
    except FileNotFoundError as e:
        _json({"status": "FAIL", "error": str(e)})
        return

    results = check_all_sources_freshness(registry.sources)
    report = format_freshness_report(results)
    _json({"status": "PASS", **report})


def cmd_sources_quality(args: argparse.Namespace) -> None:
    """Generate source quality report."""
    from sourcelab.sources.quality import generate_quality_report, format_quality_report

    registry_path = Path.cwd() / "data" / "source_registry.json"
    try:
        registry = SourceRegistry.load_from_json(registry_path)
    except FileNotFoundError as e:
        _json({"status": "FAIL", "error": str(e)})
        return

    report = generate_quality_report(registry.sources)
    formatted = format_quality_report(report)
    _json({"status": "PASS", **formatted})


def cmd_ingest_local(args: argparse.Namespace) -> None:
    from sourcelab.sources.ingest_local import ingest_local_source, SUPPORTED_EXTENSIONS

    source_dir = Path(args.folder)
    if not source_dir.is_dir():
        _json({"status": "FAIL", "error": f"Not a directory: {source_dir}"})
        return

    if args.trust_tier not in VALID_TRUST_TIERS:
        _json({
            "status": "FAIL",
            "error": f"Invalid trust tier '{args.trust_tier}'. Must be one of {sorted(VALID_TRUST_TIERS)}",
        })
        return

    # Discover supported files
    files = sorted(
        f for f in source_dir.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not files:
        _json({
            "status": "WARN",
            "message": f"No .md, .txt, or .pdf files found in {source_dir}",
            "ingested": 0,
            "skipped": 0,
            "updated": 0,
        })
        return

    # Load existing registry
    registry_path = Path.cwd() / "data" / "source_registry.json"
    if registry_path.exists():
        registry = SourceRegistry.load_from_json(registry_path)
    else:
        registry = SourceRegistry(sources=[])

    ingested = []
    updated = []
    skipped = []
    errors = []

    for filepath in files:
        suffix = filepath.suffix.lower()

        # Handle PDF files
        if suffix == ".pdf":
            record = ingest_local_source(
                filepath=filepath,
                trust_tier=args.trust_tier,
                publisher=args.publisher,
                source_type=args.source_type,
                registry=registry,
                project_root=Path.cwd(),
            )
            if record is None:
                errors.append(f"Failed to extract text from {filepath.name}")
                continue

            # Check if already exists
            existing = next((s for s in registry.sources if s.path == record.path), None)
            if existing:
                if existing.hash_sha256 == record.hash_sha256:
                    skipped.append(filepath.name)
                    continue
                existing.hash_sha256 = record.hash_sha256
                existing.retrieved_at = datetime.now(timezone.utc)
                existing.status = "active"
                updated.append(filepath.name)
                continue

            registry.add_source(record)
            ingested.append(filepath.name)
            continue

        # Handle text and markdown files
        text = filepath.read_text(encoding="utf-8")
        file_hash = SourceRegistry._hash_text(text)
        normalized_id = normalize_source_id(filepath.stem)

        # Check if this path already exists in registry
        existing = next((s for s in registry.sources if s.path == str(filepath)), None)

        if existing:
            if existing.hash_sha256 == file_hash:
                skipped.append(filepath.name)
                continue
            # File changed, update hash
            existing.hash_sha256 = file_hash
            existing.retrieved_at = datetime.now(timezone.utc)
            existing.status = "active"
            updated.append(filepath.name)
            continue

        # New source
        record = SourceRegistry._create_source_record(
            source_id=normalized_id,
            filepath=filepath,
            text=text,
            file_hash=file_hash,
            publisher=args.publisher,
            source_type=args.source_type,
            trust_tier=args.trust_tier,
        )
        registry.add_source(record)
        ingested.append(filepath.name)

    # Save updated registry
    registry.save_to_json(registry_path)

    _json({
        "status": "PASS" if not errors else "WARN",
        "folder": str(source_dir),
        "total_files_found": len(files),
        "ingested": len(ingested),
        "updated": len(updated),
        "skipped": len(skipped),
        "files_ingested": ingested,
        "files_updated": updated,
        "files_skipped": skipped,
        "errors": errors,
        "registry_path": str(registry_path),
        "total_sources_in_registry": len(registry.sources),
    })


def cmd_ingest_url(args: argparse.Namespace) -> None:
    """Ingest a source from a URL."""
    from sourcelab.sources.ingest_url import ingest_url_source

    if args.trust_tier not in VALID_TRUST_TIERS:
        _json({
            "status": "FAIL",
            "error": f"Invalid trust tier '{args.trust_tier}'. Must be one of {sorted(VALID_TRUST_TIERS)}",
        })
        return

    # Load existing registry
    registry_path = Path.cwd() / "data" / "source_registry.json"
    if registry_path.exists():
        registry = SourceRegistry.load_from_json(registry_path)
    else:
        registry = SourceRegistry(sources=[])

    record = ingest_url_source(
        url=args.url,
        trust_tier=args.trust_tier,
        publisher=args.publisher,
        source_type=args.source_type,
        project_root=Path.cwd(),
    )

    if record is None:
        _json({
            "status": "FAIL",
            "error": f"Failed to ingest URL: {args.url}",
            "hint": "Install dependencies: pip install -e '.[ingest]'",
        })
        return

    # Check if URL already exists
    existing = next((s for s in registry.sources if s.url == args.url), None)
    if existing:
        if existing.hash_sha256 == record.hash_sha256:
            _json({
                "status": "SKIP",
                "message": f"URL already ingested with same content: {args.url}",
                "source_id": existing.source_id,
            })
            return
        # URL content changed, update
        existing.hash_sha256 = record.hash_sha256
        existing.retrieved_at = record.retrieved_at
        existing.last_checked_at = record.last_checked_at
        existing.status = "active"
        registry.save_to_json(registry_path)
        _json({
            "status": "UPDATED",
            "message": f"URL content updated: {args.url}",
            "source_id": existing.source_id,
            "registry_path": str(registry_path),
        })
        return

    registry.add_source(record)
    registry.save_to_json(registry_path)

    _json({
        "status": "PASS",
        "url": args.url,
        "source_id": record.source_id,
        "title": record.title,
        "path": record.path,
        "registry_path": str(registry_path),
        "total_sources_in_registry": len(registry.sources),
    })


def cmd_search(args: argparse.Namespace) -> None:
    registry = SourceRegistry.bootstrap_demo(Path.cwd())
    mode = getattr(args, "mode", "vector")
    backend_name = getattr(args, "backend", "hash")
    store_name = getattr(args, "store", "memory")
    diagnostics_flag = getattr(args, "diagnostics", False)

    if mode == "keyword":
        from sourcelab.retrieval.bm25 import BM25Index
        from sourcelab.sources.chunker import simple_chunk_source

        chunks = []
        titles = {}
        for source in registry.sources:
            titles[source.source_id] = source.title
            chunks.extend(simple_chunk_source(source))
        bm25 = BM25Index(chunks=chunks, titles=titles)
        results = bm25.search(args.query, top_k=args.top_k)
        output = {
            "query": args.query,
            "mode": "keyword",
            "result_count": len(results),
            "total_chunks": len(chunks),
            "results": [r.model_dump() for r in results],
        }
        if diagnostics_flag:
            output["diagnostics"] = {
                "backend": backend_name,
                "store": store_name,
                "scores": [r.score for r in results],
                "source_ids": [r.source_id for r in results],
                "chunk_ids": [r.chunk_id for r in results],
            }
        _json(output)

    elif mode == "hybrid":
        from sourcelab.retrieval.hybrid_search import HybridSearch

        hybrid = HybridSearch.from_registry(registry)
        results, diagnostics = hybrid.search(args.query, top_k=args.top_k)
        output = {
            "query": args.query,
            "mode": "hybrid",
            "result_count": diagnostics.result_count,
            "total_chunks": diagnostics.total_chunks,
            "results": [r.model_dump() for r in results],
        }
        if diagnostics_flag:
            output["diagnostics"] = {
                "keyword_scores": diagnostics.keyword_scores,
                "vector_scores": diagnostics.vector_scores,
                "trust_weights": diagnostics.trust_weights,
                "freshness_scores": diagnostics.freshness_scores,
                "final_scores": diagnostics.final_scores,
                "source_ids": diagnostics.source_ids,
                "chunk_ids": diagnostics.chunk_ids,
                "trust_tiers": diagnostics.trust_tiers,
                "compression_report": diagnostics.compression_report,
                "weights": diagnostics.weights,
            }
        _json(output)

    else:
        # Default: vector mode
        from sourcelab.retrieval.index import PocketIndex

        index = PocketIndex.from_registry(
            registry,
            backend_name=backend_name,
            store_name=store_name,
        )
        results = index.search(args.query, top_k=args.top_k)
        output = {
            "query": args.query,
            "mode": "vector",
            "result_count": len(results),
            "total_chunks": len(index.chunks),
            "results": [r.model_dump() for r in results],
            "compression_report": index.storage_report(),
        }
        if diagnostics_flag:
            output["diagnostics"] = {
                "backend": backend_name,
                "store": store_name,
                "scores": [r.score for r in results],
                "source_ids": [r.source_id for r in results],
                "chunk_ids": [r.chunk_id for r in results],
                "trust_tiers": [r.trust_tier for r in results],
            }
        _json(output)


def cmd_lesson_create(args: argparse.Namespace) -> None:
    """Create a new lesson package."""
    model_router = None
    if getattr(args, "model_mode", None):
        from sourcelab.generation.model_router import ModelRouter
        from sourcelab.models.schemas import ModelRouterConfig

        config = ModelRouterConfig(
            mode=args.model_mode,
            backend=getattr(args, "model_backend", "deterministic"),
            model_name=getattr(args, "model_name", ""),
            base_url=getattr(args, "model_base_url", ""),
        )
        model_router = ModelRouter(config=config)

    result = run_lesson_create(
        topic=args.topic,
        project_root=Path.cwd(),
        difficulty=args.difficulty,
        task_format=args.format,
        model_router=model_router,
        source_pack=getattr(args, "source_pack", None),
    )
    _json(result)


def cmd_lesson_show(args: argparse.Namespace) -> None:
    """Show the latest generated lesson."""
    runs_dir = Path("artifacts/runs")
    if not runs_dir.exists():
        _json({"error": "No runs directory found. Run 'sourcelab demo' or 'sourcelab lesson create' first."})
        return

    runs = sorted([p for p in runs_dir.glob("*") if p.is_dir()])
    if not runs:
        _json({"error": "No runs found. Run 'sourcelab demo' or 'sourcelab lesson create' first."})
        return

    latest_run = runs[-1]
    lesson_path = latest_run / "generated_lesson.md"
    if not lesson_path.exists():
        _json({"error": f"No generated_lesson.md found in {latest_run}"})
        return

    content = lesson_path.read_text(encoding="utf-8")
    print(content)


def cmd_verify_release(args: argparse.Namespace) -> None:
    strict = getattr(args, "strict", False)
    report = verify_release(project_root=Path.cwd(), strict=strict)
    _json(report)


def cmd_verify_latest(args: argparse.Namespace) -> None:
    """Verify the latest run."""
    run_dir = _get_latest_run_dir()
    if not run_dir:
        _json({"error": "No runs found. Run 'sourcelab demo' or 'sourcelab lesson create' first."})
        return

    harness = HarnessRunner()
    report = harness.validate_run(run_dir=run_dir)
    report["run_dir"] = str(run_dir)
    report["run_id"] = run_dir.name
    _json(report)


def cmd_verify_run(args: argparse.Namespace) -> None:
    """Verify a specific run."""
    run_dir = _get_run_dir(args.run_id)
    if not run_dir:
        _json({"error": f"Run not found: {args.run_id}"})
        return

    harness = HarnessRunner()
    report = harness.validate_run(run_dir=run_dir)
    report["run_dir"] = str(run_dir)
    report["run_id"] = run_dir.name
    _json(report)


def cmd_verify_claims(args: argparse.Namespace) -> None:
    """View claims from a run."""
    run_dir = _get_run_dir(args.run_id if hasattr(args, "run_id") else None)
    if not run_dir:
        _json({"error": "No runs found."})
        return

    claim_map_path = run_dir / "claim_map.json"
    if not claim_map_path.exists():
        _json({"error": f"No claim_map.json found in {run_dir}"})
        return

    claims = json.loads(claim_map_path.read_text(encoding="utf-8"))
    _json({
        "run_id": run_dir.name,
        "claim_count": len(claims),
        "claims": claims,
    })


def cmd_review_queue(args: argparse.Namespace) -> None:
    """View the human review queue."""
    run_dir = _get_run_dir(args.run_id if hasattr(args, "run_id") else None)
    if not run_dir:
        _json({"error": "No runs found."})
        return

    queue_path = run_dir / "human_review_queue.json"
    if not queue_path.exists():
        _json({"error": f"No human_review_queue.json found in {run_dir}"})
        return

    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    _json({
        "run_id": run_dir.name,
        "queue": queue,
    })


def cmd_proof_latest(args: argparse.Namespace) -> None:
    """View the latest proof bundle."""
    run_dir = _get_latest_run_dir()
    if not run_dir:
        _json({"error": "No runs found. Run 'sourcelab demo' or 'sourcelab lesson create' first."})
        return

    _show_proof_bundle(run_dir)


def cmd_proof_run(args: argparse.Namespace) -> None:
    """View a specific proof bundle."""
    run_dir = _get_run_dir(args.run_id)
    if not run_dir:
        _json({"error": f"Run not found: {args.run_id}"})
        return

    _show_proof_bundle(run_dir)


def _show_proof_bundle(run_dir: Path) -> None:
    """Show proof bundle information for a run."""
    result = {
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
    }

    # Proof summary
    summary_path = run_dir / "proof_summary.json"
    if summary_path.exists():
        result["proof_summary"] = json.loads(summary_path.read_text(encoding="utf-8"))

    # Run manifest
    manifest_path = run_dir / "run_manifest.json"
    if manifest_path.exists():
        result["run_manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Proof bundle manifest
    bundle_manifest_path = run_dir / "proof_bundle_manifest.json"
    if bundle_manifest_path.exists():
        result["proof_bundle_manifest"] = json.loads(bundle_manifest_path.read_text(encoding="utf-8"))

    # List all artifacts
    artifacts = sorted([
        f.name for f in run_dir.iterdir()
        if f.is_file() and f.suffix in [".json", ".md", ".txt"]
    ])
    result["artifacts"] = artifacts
    result["artifact_count"] = len(artifacts)

    _json(result)


def cmd_proof_artifacts(args: argparse.Namespace) -> None:
    """List artifacts from a run."""
    run_dir = _get_latest_run_dir() if args.latest else _get_run_dir(args.run_id)
    if not run_dir:
        _json({"error": "No runs found."})
        return

    artifacts = []
    for f in sorted(run_dir.iterdir()):
        if f.is_file() and f.suffix in [".json", ".md", ".txt"]:
            stat = f.stat()
            artifacts.append({
                "name": f.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })

    _json({
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    })


def cmd_harness_latest(args: argparse.Namespace) -> None:
    """View the latest harness report."""
    run_dir = _get_latest_run_dir()
    if not run_dir:
        _json({"error": "No runs found. Run 'sourcelab demo' or 'sourcelab lesson create' first."})
        return

    _show_harness_report(run_dir)


def cmd_harness_run(args: argparse.Namespace) -> None:
    """View a specific harness report."""
    run_dir = _get_run_dir(args.run_id)
    if not run_dir:
        _json({"error": f"Run not found: {args.run_id}"})
        return

    _show_harness_report(run_dir)


def _show_harness_report(run_dir: Path) -> None:
    """Show harness report for a run."""
    harness_path = run_dir / "harness_report.json"
    if not harness_path.exists():
        _json({"error": f"No harness_report.json found in {run_dir}"})
        return

    report = json.loads(harness_path.read_text(encoding="utf-8"))
    report["run_id"] = run_dir.name
    report["run_dir"] = str(run_dir)
    _json(report)


def cmd_answer_submit(args: argparse.Namespace) -> None:
    """Submit and score a learner answer."""
    from pathlib import Path

    answer_file = Path(args.file) if args.file else None
    if answer_file and answer_file.exists():
        answer_text = answer_file.read_text(encoding="utf-8")
    elif args.text:
        answer_text = args.text
    else:
        _json({"error": "Provide either --file <path> or --text <answer>"})
        return

    run_id = args.run_id
    if run_id == "latest":
        run_id = None

    topic = args.topic
    if not topic:
        run_dir = _get_run_dir(run_id)
        if run_dir:
            package_path = run_dir / "generated_lesson_package.json"
            if package_path.exists():
                package_data = json.loads(package_path.read_text(encoding="utf-8"))
                topic = package_data.get("topic")
        if not topic:
            _json({"error": "Provide --topic or run against a run with generated_lesson_package.json"})
            return

    result = run_answer_submit(
        topic=topic,
        answer_text=answer_text,
        project_root=Path.cwd(),
        run_id=run_id,
    )
    _json(result)


def _resolve_cli_run_dir(run_id: str | None) -> Path | None:
    """Resolve a run directory from CLI --run / --run-id (supports 'latest')."""
    if run_id in (None, "", "latest"):
        return _get_latest_run_dir()
    return _get_run_dir(run_id)


def cmd_answer_history(args: argparse.Namespace) -> None:
    """List immutable answer attempts for a run."""
    from sourcelab.learning.answer_history import list_answer_attempts

    run_dir = _resolve_cli_run_dir(args.run_id)
    if not run_dir:
        _json({"error": "No runs found. Run 'sourcelab demo' or 'sourcelab lesson create' first."})
        return

    history = list_answer_attempts(run_dir, run_dir.name)
    _json(history.model_dump())


def cmd_answer_show(args: argparse.Namespace) -> None:
    """Show detail for a single answer attempt."""
    from sourcelab.learning.answer_history import get_answer_attempt_detail

    run_dir = _resolve_cli_run_dir(args.run_id)
    if not run_dir:
        _json({"error": "No runs found."})
        return

    if not args.attempt:
        _json({"error": "Provide --attempt <attempt_id>"})
        return

    detail = get_answer_attempt_detail(run_dir, run_dir.name, args.attempt)
    if detail is None:
        _json({"error": f"Attempt not found: {args.attempt}"})
        return
    _json(detail.model_dump())


def cmd_answer_diff(args: argparse.Namespace) -> None:
    """Compute delta between two answer attempts."""
    from sourcelab.learning.answer_history import compute_answer_diff

    run_dir = _resolve_cli_run_dir(args.run_id)
    if not run_dir:
        _json({"error": "No runs found."})
        return

    if not args.from_attempt or not args.to_attempt:
        _json({"error": "Provide --from <attempt_id> and --to <attempt_id>"})
        return

    diff = compute_answer_diff(run_dir, run_dir.name, args.from_attempt, args.to_attempt)
    if diff is None:
        _json({"error": f"Attempt not found: {args.from_attempt} or {args.to_attempt}"})
        return
    _json(diff.model_dump())


def cmd_profile_show(args: argparse.Namespace) -> None:
    """Show the current skill profile."""
    from pathlib import Path
    from sourcelab.learning.skill_profile import load_profile

    profile = load_profile(user_id="local_user", project_root=Path.cwd())
    _json({
        "user_id": profile.user_id,
        "overall_mastery": profile.overall_mastery if hasattr(profile, 'overall_mastery') else sum(profile.topic_mastery.values()) / max(1, len(profile.topic_mastery)),
        "topic_mastery": profile.topic_mastery,
        "attempts": len(profile.attempts),
        "criteria_mastery": profile.criterion_mastery,
        "strengths": profile.strengths,
        "weaknesses": [w.model_dump() for w in profile.weaknesses],
        "source_grounding_history": profile.source_grounding_history,
        "preferred_next_difficulty": profile.preferred_next_difficulty,
        "preferred_guidance_level": profile.preferred_guidance_level,
    })


def cmd_profile_topic(args: argparse.Namespace) -> None:
    """Show mastery for a specific topic."""
    from pathlib import Path
    from sourcelab.learning.skill_profile import load_profile

    profile = load_profile(user_id="local_user", project_root=Path.cwd())
    mastery = profile.topic_mastery.get(args.topic, 0.0)
    band = "novice"
    if mastery >= 0.8:
        band = "expert"
    elif mastery >= 0.6:
        band = "advanced"
    elif mastery >= 0.4:
        band = "intermediate"
    elif mastery >= 0.2:
        band = "beginner"
    _json({
        "topic": args.topic,
        "mastery": mastery,
        "band": band,
        "attempts": profile.attempts,
        "strengths": profile.strengths,
        "weaknesses": profile.weaknesses,
    })


def cmd_learning_report(args: argparse.Namespace) -> None:
    """Show the latest learning report."""
    run_dir = _get_latest_run_dir()
    if not run_dir:
        _json({"error": "No runs found. Run 'sourcelab demo' or 'sourcelab answer submit' first."})
        return

    report_path = run_dir / "learning_report.json"
    if not report_path.exists():
        _json({"error": f"No learning_report.json found in {run_dir}"})
        return

    report = json.loads(report_path.read_text(encoding="utf-8"))

    # Also show markdown if available
    report_md_path = run_dir / "learning_report.md"
    if report_md_path.exists():
        report["markdown"] = report_md_path.read_text(encoding="utf-8")

    report["run_id"] = run_dir.name
    report["run_dir"] = str(run_dir)
    _json(report)


def cmd_dashboard(args: argparse.Namespace) -> None:
    """Launch the Streamlit dashboard."""
    import shutil
    import subprocess

    streamlit_path = shutil.which("streamlit")
    if streamlit_path is None:
        print("Streamlit is not installed.")
        print("Install with: pip install -e '.[ui]'")
        print("Then run: streamlit run src/sourcelab/ui/dashboard.py")
        return

    if args.launch:
        dashboard_path = Path(__file__).parent / "ui" / "dashboard.py"
        print(f"Launching dashboard: streamlit run {dashboard_path}")
        subprocess.run([streamlit_path, "run", str(dashboard_path)], check=False)
    else:
        print("To launch the dashboard, run:")
        print("  streamlit run src/sourcelab/ui/dashboard.py")
        print()
        print("Or use: sourcelab dashboard --launch")


def cmd_runs_list(args: argparse.Namespace) -> None:
    """List all runs."""
    from sourcelab.ui.run_loader import list_runs
    from sourcelab.ui.terminal import print_run_list

    summaries = list_runs(Path.cwd())
    print_run_list(summaries)


def cmd_runs_latest(args: argparse.Namespace) -> None:
    """Show the latest run summary."""
    from sourcelab.ui.run_loader import get_latest_run
    from sourcelab.ui.terminal import print_run_summary

    summary = get_latest_run(Path.cwd())
    if summary is None:
        print("No runs found. Run 'sourcelab demo' or 'sourcelab lesson create' first.")
        return
    print_run_summary(summary)


def cmd_runs_show(args: argparse.Namespace) -> None:
    """Show a specific run or the latest run."""
    from sourcelab.ui.run_loader import get_latest_run, summarize_run
    from sourcelab.ui.terminal import print_run_summary

    if args.run_id == "latest":
        summary = get_latest_run(Path.cwd())
    else:
        run_dir = Path("artifacts/runs") / args.run_id
        if not run_dir.exists():
            print(f"Run not found: {args.run_id}")
            return
        summary = summarize_run(run_dir)

    if summary is None:
        print("No runs found.")
        return
    print_run_summary(summary)


def cmd_runs_compare(args: argparse.Namespace) -> None:
    """Compare two or more runs."""
    from sourcelab.comparison.run_compare import compare_runs

    run_ids = args.run_ids
    if len(run_ids) < 2:
        print("At least two run IDs are required.", file=sys.stderr)
        sys.exit(1)

    try:
        result = compare_runs(Path.cwd(), run_ids)
    except FileNotFoundError as exc:
        print(f"Run not found: {exc}", file=sys.stderr)
        sys.exit(1)

    _json(result.model_dump(mode="json"))


def cmd_batch_create(args: argparse.Namespace) -> None:
    """Create a batch of lesson runs."""
    from sourcelab.batch.service import create_batch

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    batch_name = args.name or payload.get("batch_name", "")
    items = payload.get("items", [])
    if not batch_name:
        print("batch_name is required (--name or in config).", file=sys.stderr)
        sys.exit(1)
    if not items:
        print("items must not be empty in config.", file=sys.stderr)
        sys.exit(1)

    result = create_batch(Path.cwd(), batch_name, items)
    _json(result)


def cmd_batch_list(args: argparse.Namespace) -> None:
    """List all batches."""
    from sourcelab.batch.service import list_batches

    _json(list_batches(Path.cwd()))


def cmd_batch_show(args: argparse.Namespace) -> None:
    """Show batch detail."""
    from sourcelab.batch.service import get_batch

    try:
        _json(get_batch(Path.cwd(), args.batch_id))
    except FileNotFoundError:
        print(f"Batch not found: {args.batch_id}", file=sys.stderr)
        sys.exit(1)


def cmd_batch_compare(args: argparse.Namespace) -> None:
    """Compare runs in a batch."""
    from sourcelab.batch.service import compare_batch_runs

    try:
        _json(compare_batch_runs(Path.cwd(), args.batch_id))
    except FileNotFoundError:
        print(f"Batch not found: {args.batch_id}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


def _print_answer_compare_table(result: dict) -> None:
    header = (
        f"{'Run ID':<22} {'Topic':<28} {'Att':>3} {'Latest':>7} {'Best':>7} "
        f"{'Rev':>3} {'Cap':>3}  Latest focus"
    )
    print(header)
    print("-" * len(header))
    for row in result.get("per_run", []):
        topic = str(row.get("topic", ""))
        if len(topic) > 26:
            topic = topic[:23] + "..."
        latest = f"{row.get('latest_score', 0):.2%}" if row.get("attempt_count") else "—"
        best = f"{row.get('best_score', 0):.2%}" if row.get("attempt_count") else "—"
        focus = str(row.get("latest_next_task_focus") or "")
        if len(focus) > 40:
            focus = focus[:37] + "..."
        print(
            f"{row.get('run_id', ''):<22} {topic:<28} "
            f"{row.get('attempt_count', 0):>3} {latest:>7} {best:>7} "
            f"{row.get('needs_review_count', 0):>3} {row.get('capped_count', 0):>3}  {focus}"
        )
    recommendation = result.get("recommendation")
    if recommendation:
        print()
        print(recommendation)


def cmd_batch_answers(args: argparse.Namespace) -> None:
    """Compare learner answers for all runs in a batch."""
    from sourcelab.comparison.answer_compare import answer_compare_to_markdown, compare_batch_answers

    try:
        result = compare_batch_answers(Path.cwd(), args.batch_id)
    except FileNotFoundError:
        print(f"Batch not found: {args.batch_id}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    if args.json:
        _json(result.model_dump(mode="json"))
        return
    if args.markdown:
        print(answer_compare_to_markdown(result))
        return
    _print_answer_compare_table(result.model_dump(mode="json"))


def cmd_runs_answers_compare(args: argparse.Namespace) -> None:
    """Compare learner answers across two or more runs."""
    from sourcelab.comparison.answer_compare import answer_compare_to_markdown, compare_run_answers

    run_ids = args.run_ids
    if len(run_ids) < 2:
        print("At least two run IDs are required.", file=sys.stderr)
        sys.exit(1)

    try:
        result = compare_run_answers(Path.cwd(), run_ids)
    except FileNotFoundError as exc:
        print(f"Run not found: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        _json(result.model_dump(mode="json"))
        return
    if args.markdown:
        print(answer_compare_to_markdown(result))
        return
    _print_answer_compare_table(result.model_dump(mode="json"))


def cmd_export(args: argparse.Namespace) -> None:
    """Export a run report."""
    from sourcelab.ui.export import export_run

    try:
        path = export_run(
            project_root=Path.cwd(),
            run_id=args.run_id,
            fmt=args.format,
        )
        print(f"Exported: {path}")
    except FileNotFoundError as e:
        print(f"Error: {e}")


def cmd_index_build(args: argparse.Namespace) -> None:
    """Build a persistent vector index."""
    import json
    from datetime import datetime, timezone

    from sourcelab.retrieval.index import PocketIndex
    from sourcelab.retrieval.schemas import IndexManifest
    from sourcelab.sources.registry import SourceRegistry

    registry = SourceRegistry.bootstrap_demo(Path.cwd())
    index_dir = Path(args.index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)

    # Build index
    index = PocketIndex.from_registry(
        registry,
        dim=args.dim,
        backend_name=args.backend,
        store_name=args.store,
    )

    # Build store and persist
    if args.store == "json":
        index.build_store()

    # Write manifest
    manifest = IndexManifest(
        index_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        created_at=datetime.now(timezone.utc),
        backend=args.backend,
        store=args.store,
        chunk_count=len(index.chunks),
        source_count=len(registry.sources),
        vector_dim=args.dim,
        compression="int8",
        artifacts=["vector_store.json", "index_manifest.json"],
    )

    manifest_path = index_dir / "index_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )

    _json({
        "status": "PASS",
        "backend": args.backend,
        "store": args.store,
        "chunk_count": len(index.chunks),
        "source_count": len(registry.sources),
        "vector_dim": args.dim,
        "index_dir": str(index_dir),
        "manifest_path": str(manifest_path),
    })


def cmd_index_stats(args: argparse.Namespace) -> None:
    """Show index statistics."""
    import json

    index_dir = Path(args.index_dir)
    manifest_path = index_dir / "index_manifest.json"

    if not manifest_path.exists():
        _json({
            "status": "WARN",
            "message": "No index found. Run 'sourcelab index build' first.",
        })
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _json({
        "status": "PASS",
        "index_id": manifest.get("index_id"),
        "backend": manifest.get("backend"),
        "store": manifest.get("store"),
        "chunk_count": manifest.get("chunk_count"),
        "source_count": manifest.get("source_count"),
        "vector_dim": manifest.get("vector_dim"),
        "compression": manifest.get("compression"),
        "artifacts": manifest.get("artifacts", []),
        "index_dir": str(index_dir),
    })


def cmd_index_clear(args: argparse.Namespace) -> None:
    """Clear the persistent index."""
    import shutil

    index_dir = Path(args.index_dir)
    if index_dir.exists():
        shutil.rmtree(index_dir)
        _json({
            "status": "PASS",
            "message": f"Index cleared: {index_dir}",
        })
    else:
        _json({
            "status": "WARN",
            "message": f"Index directory not found: {index_dir}",
        })


def cmd_retrieval_eval(args: argparse.Namespace) -> None:
    """Run retrieval evaluation."""
    from sourcelab.retrieval.evaluation import (
        load_eval_fixtures,
        evaluate_retrieval,
        format_evaluation_report,
    )
    from sourcelab.retrieval.index import PocketIndex
    from sourcelab.sources.registry import SourceRegistry

    registry = SourceRegistry.bootstrap_demo(Path.cwd())
    index = PocketIndex.from_registry(
        registry,
        dim=args.dim,
        backend_name=args.backend,
        store_name=args.store,
    )

    # Create search function
    def search_fn(query: str, top_k: int):
        return index.search(query, top_k=top_k)

    # Load fixtures
    queries = load_eval_fixtures(Path.cwd())
    if not queries:
        _json({
            "status": "WARN",
            "message": "No evaluation fixtures found. Create tests/fixtures/retrieval_eval.json.",
        })
        return

    # Run evaluation
    report = evaluate_retrieval(
        search_fn=search_fn,
        queries=queries,
        top_k=args.top_k,
        backend=args.backend,
        store=args.store,
    )

    formatted = format_evaluation_report(report)
    _json({"status": "PASS", **formatted})


def cmd_models_config(args: argparse.Namespace) -> None:
    """Show current model configuration."""
    from sourcelab.models.config import get_model_config
    config = get_model_config()
    _json(config.model_dump())


def cmd_models_health(args: argparse.Namespace) -> None:
    """Check health of configured model backend."""
    from sourcelab.models.config import get_model_config
    from sourcelab.models.backends import get_backend

    config = get_model_config()
    backend = get_backend(
        config.backend,
        model_name=config.model_name,
        base_url=config.base_url,
        timeout_seconds=config.timeout_seconds,
    )
    health = backend.health_check()
    _json(health.model_dump())


def cmd_models_test(args: argparse.Namespace) -> None:
    """Test a model backend with a sample prompt."""
    from sourcelab.generation.model_router import ModelRouter
    from sourcelab.models.schemas import ModelRequest, ModelRouterConfig

    mode = args.mode or "deterministic"
    backend = args.backend or "deterministic"
    model_name = args.model_name or ""
    base_url = args.model_base_url or ""

    config = ModelRouterConfig(
        mode=mode,
        backend=backend,
        model_name=model_name,
        base_url=base_url,
    )
    router = ModelRouter(config=config)

    request = ModelRequest(
        prompt=args.prompt or "What is post-quantum cryptography?",
        route="general",
    )
    response = router.generate(request)
    _json({
        "text": response.text[:500],
        "backend": response.backend,
        "model_name": response.model_name,
        "route": response.route,
        "latency_ms": response.latency_ms,
        "deterministic_fallback_used": response.deterministic_fallback_used,
        "warnings": response.warnings,
    })


def cmd_source_pack_list(args: argparse.Namespace) -> None:
    """List available source packs."""
    packs = list_source_packs(Path.cwd())
    _json({"packs": packs, "total": len(packs)})


def cmd_source_pack_validate(args: argparse.Namespace) -> None:
    """Validate a source pack."""
    result = validate_source_pack(Path.cwd(), args.pack_name)
    _json(result)


def cmd_source_pack_doctor(args: argparse.Namespace) -> None:
    """Run strengthened source pack validation."""
    result = doctor_source_pack(Path.cwd(), args.pack_name)
    _json(result)


def cmd_source_pack_install(args: argparse.Namespace) -> None:
    """Install a source pack."""
    result = install_source_pack(Path.cwd(), args.pack_name)
    _json(result)


def cmd_source_pack_status(args: argparse.Namespace) -> None:
    """Check source pack installation status."""
    result = source_pack_status(Path.cwd(), args.pack_name)
    _json(result)


def cmd_evals_run(args: argparse.Namespace) -> None:
    """Run golden evals for a source pack."""
    from sourcelab.evals.runner import run_all_packs_evals, run_golden_evals

    if getattr(args, "all_packs", False):
        if args.pack:
            _json({"error": "Use either --pack or --all-packs, not both."})
            return
    elif not args.pack:
        _json({"error": "Provide --pack <name> or --all-packs."})
        return

    eval_types = None
    if args.type:
        eval_types = [args.type]

    if getattr(args, "all_packs", False):
        result = run_all_packs_evals(
            project_root=Path.cwd(),
            eval_types=eval_types,
        )
    else:
        result = run_golden_evals(
            project_root=Path.cwd(),
            pack_name=args.pack,
            eval_types=eval_types,
        )
    _json(result)


def cmd_evals_latest(args: argparse.Namespace) -> None:
    """Show latest eval results."""
    if getattr(args, "all_packs", False):
        if args.pack:
            _json({"error": "Use either --pack or --all-packs, not both."})
            return
        summary_path = Path.cwd() / "artifacts" / "evals" / "all_packs" / "golden_eval_summary.json"
        if not summary_path.exists():
            _json({"error": "No combined eval summary found. Run 'sourcelab evals run --all-packs'."})
            return
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        md_path = summary_path.parent / "golden_eval_summary.md"
        if md_path.exists():
            summary["markdown"] = md_path.read_text(encoding="utf-8")
        _json(summary)
        return

    if not args.pack:
        _json({"error": "Provide --pack <name> or --all-packs."})
        return

    evals_dir = Path.cwd() / "artifacts" / "evals" / args.pack
    if not evals_dir.exists():
        _json({"error": f"No eval results found for pack: {args.pack}"})
        return

    summary_path = evals_dir / "golden_eval_summary.json"
    if not summary_path.exists():
        _json({"error": f"No summary found for pack: {args.pack}"})
        return

    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    # Also show markdown if available
    md_path = evals_dir / "golden_eval_summary.md"
    if md_path.exists():
        summary["markdown"] = md_path.read_text(encoding="utf-8")

    _json(summary)


def cmd_evals_thresholds_show(args: argparse.Namespace) -> None:
    """Show per-pack eval thresholds and compliance against the latest summary."""
    from sourcelab.evals.thresholds import (
        evaluate_against_thresholds,
        load_pack_thresholds,
    )

    project_root = Path.cwd()
    if not args.pack:
        _json({"error": "Provide --pack <name>."})
        return

    thresholds = load_pack_thresholds(project_root, args.pack)
    summary_path = (
        project_root / "artifacts" / "evals" / args.pack / "golden_eval_summary.json"
    )
    summary: dict | None = None
    if summary_path.is_file():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            summary = None

    evaluation = evaluate_against_thresholds(args.pack, summary, thresholds)
    _json(evaluation.to_dict())


def cmd_evals_thresholds_set(args: argparse.Namespace) -> None:
    """Set per-pack eval thresholds in the pack's manifest.json."""
    from sourcelab.evals.thresholds import PackEvalThresholds, write_pack_thresholds

    project_root = Path.cwd()
    if not args.pack:
        _json({"error": "Provide --pack <name>."})
        return

    min_pass_rate = getattr(args, "min_pass_rate", None)
    min_cases = getattr(args, "min_cases", None)
    required_evals = getattr(args, "required_evals", None)

    if min_pass_rate is None and min_cases is None and required_evals is None:
        _json(
            {
                "error": "Provide at least one of --min-pass-rate, --min-cases, --required-evals."
            }
        )
        return

    if min_pass_rate is not None and not (0.0 <= min_pass_rate <= 1.0):
        _json({"error": "--min-pass-rate must be between 0.0 and 1.0"})
        return

    if min_cases is not None and min_cases < 0:
        _json({"error": "--min-cases must be >= 0"})
        return

    # Read existing thresholds to merge
    from sourcelab.evals.thresholds import load_pack_thresholds

    existing = load_pack_thresholds(project_root, args.pack)
    required_evals_list = (
        [item.strip() for item in required_evals.split(",") if item.strip()]
        if required_evals is not None
        else existing.required_evals
    )
    updated = PackEvalThresholds(
        min_pass_rate=(
            float(min_pass_rate) if min_pass_rate is not None else existing.min_pass_rate
        ),
        min_cases=int(min_cases) if min_cases is not None else existing.min_cases,
        required_evals=required_evals_list,
    )

    try:
        manifest_path = write_pack_thresholds(project_root, args.pack, updated)
    except (FileNotFoundError, ValueError) as exc:
        _json({"error": str(exc)})
        return

    _json(
        {
            "status": "ok",
            "pack_name": args.pack,
            "thresholds": updated.to_dict(),
            "manifest_path": str(manifest_path),
        }
    )


# ---------------------------------------------------------------------------
# Local Demo command
# ---------------------------------------------------------------------------

def cmd_local_demo(args: argparse.Namespace) -> None:
    """Run the full local demonstration pipeline."""
    project_root = Path.cwd()
    steps = []
    passed = True

    # 1. Validate source pack
    try:
        from sourcelab.sources.source_pack import validate_source_pack, install_source_pack
        pack_result = validate_source_pack(project_root, "pqc_v1")
        steps.append({"step": "validate_source_pack", "passed": pack_result["valid"], "details": pack_result})
        if not pack_result["valid"]:
            passed = False
    except Exception as e:
        steps.append({"step": "validate_source_pack", "passed": False, "error": str(e)})
        passed = False

    # 2. Install source pack
    try:
        install_result = install_source_pack(project_root, "pqc_v1")
        steps.append({"step": "install_source_pack", "passed": install_result["success"], "details": install_result})
        if not install_result["success"]:
            passed = False
    except Exception as e:
        steps.append({"step": "install_source_pack", "passed": False, "error": str(e)})
        passed = False

    # 3. Validate sources
    try:
        from sourcelab.sources.registry import SourceRegistry
        registry = SourceRegistry.bootstrap_demo(project_root)
        errors = registry.validate()
        source_valid = len(errors) == 0
        steps.append({"step": "validate_sources", "passed": source_valid, "errors": errors})
        if not source_valid:
            passed = False
    except Exception as e:
        steps.append({"step": "validate_sources", "passed": False, "error": str(e)})
        passed = False

    # 4. Run golden evals (before demo pipeline so lesson runs do not become latest)
    golden_pass_rate = 0.0
    try:
        from sourcelab.evals.runner import run_golden_evals
        eval_result = run_golden_evals(project_root=project_root, pack_name="pqc_v1")
        summary = eval_result.get("summary", {})
        golden_pass_rate = summary.get("overall_pass_rate", 0) if summary else 0
        steps.append({"step": "run_golden_evals", "passed": golden_pass_rate >= 0.8, "pass_rate": golden_pass_rate})
        if golden_pass_rate < 0.8:
            passed = False
    except Exception as e:
        steps.append({"step": "run_golden_evals", "passed": False, "error": str(e)})
        golden_pass_rate = 0
        passed = False

    # 5. Run demo pipeline (includes retrieval, generation, verification, learning, proof bundle)
    demo_result = {}
    try:
        from sourcelab.core.pipeline import run_demo_pipeline
        demo_result = run_demo_pipeline(
            topic="post-quantum cryptography migration",
            project_root=project_root,
            source_pack="pqc_v1",
        )
        steps.append({"step": "run_demo_pipeline", "passed": demo_result.get("harness_passed", False), "run_id": demo_result.get("run_id")})
        if not demo_result.get("harness_passed", False):
            passed = False
    except Exception as e:
        steps.append({"step": "run_demo_pipeline", "passed": False, "error": str(e)})
        passed = False

    # 6. Submit strong example answer against the demo run
    try:
        from sourcelab.core.pipeline import run_answer_submit
        answer_result = run_answer_submit(
            topic="post-quantum cryptography migration",
            answer_text=(
                "A safe post-quantum migration plan should start with a cryptographic inventory. "
                "The first step is to identify where public-key cryptography is used, separate immediate "
                "operational risk from long-term confidentiality risk, and avoid claiming that current "
                "quantum computers can break RSA-2048 today without evidence."
            ),
            project_root=project_root,
            run_id=demo_result.get("run_id") or None,
        )
        steps.append({"step": "submit_answer", "passed": "overall_score" in answer_result, "score": answer_result.get("overall_score")})
    except Exception as e:
        steps.append({"step": "submit_answer", "passed": False, "error": str(e)})

    # 7. Export latest report
    try:
        from sourcelab.ui.export import export_run
        export_path = export_run(project_root, run_id="latest", fmt="markdown")
        steps.append({"step": "export_report", "passed": True, "path": str(export_path)})
    except Exception as e:
        steps.append({"step": "export_report", "passed": False, "error": str(e)})

    # 8. Run strict release verification
    try:
        from sourcelab.harness.release_gate import verify_release
        strict_result = verify_release(project_root, strict=True)
        steps.append({"step": "verify_release_strict", "passed": strict_result["status"] == "PASS", "status": strict_result["status"]})
        if strict_result["status"] != "PASS":
            passed = False
    except Exception as e:
        steps.append({"step": "verify_release_strict", "passed": False, "error": str(e)})
        passed = False

    # 9. Write release manifest
    try:
        from sourcelab.release.manifest import build_release_manifest, write_release_manifest
        manifest = build_release_manifest(project_root)
        manifest.pytest_status = "passed" if passed else "failed"
        json_path, md_path = write_release_manifest(manifest, project_root)
        steps.append({"step": "write_release_manifest", "passed": True, "json_path": str(json_path), "md_path": str(md_path)})
    except Exception as e:
        steps.append({"step": "write_release_manifest", "passed": False, "error": str(e)})

    # Build summary
    run_id = demo_result.get("run_id", "")
    topic = demo_result.get("topic", "")
    answer_score = None
    for step in steps:
        if step["step"] == "submit_answer" and "score" in step:
            answer_score = step["score"]

    strict_status = "unknown"
    for step in steps:
        if step["step"] == "verify_release_strict" and "status" in step:
            strict_status = step["status"]

    result = {
        "passed": passed,
        "run_id": run_id,
        "lesson_topic": topic,
        "answer_score": answer_score,
        "retrieval_eval_pass_rate": None,
        "golden_eval_pass_rate": golden_pass_rate,
        "strict_release_status": strict_status,
        "report_paths": {
            "release_manifest": str(project_root / "artifacts" / "release" / "local_v1_release_manifest.json"),
            "release_report": str(project_root / "artifacts" / "release" / "local_v1_release_report.md"),
        },
        "dashboard_command": "sourcelab dashboard --launch",
        "steps": steps,
    }
    _json(result)


# ---------------------------------------------------------------------------
# Release CLI commands
# ---------------------------------------------------------------------------

def cmd_release_check(args: argparse.Namespace) -> None:
    """Run local v1 readiness checks."""
    from sourcelab.release.checklist import run_release_checklist
    result = run_release_checklist(Path.cwd())
    _json(result)


def cmd_release_manifest(args: argparse.Namespace) -> None:
    """Print the local v1 release manifest."""
    manifest_path = Path.cwd() / "artifacts" / "release" / "local_v1_release_manifest.json"
    if not manifest_path.exists():
        _json({"error": "No release manifest found. Run 'sourcelab local-demo' first."})
        return
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    _json(data)


def cmd_release_report(args: argparse.Namespace) -> None:
    """Print or write the release report."""
    md_path = Path.cwd() / "artifacts" / "release" / "local_v1_release_report.md"
    if not md_path.exists():
        _json({"error": "No release report found. Run 'sourcelab local-demo' first."})
        return
    content = md_path.read_text(encoding="utf-8")
    if getattr(args, "output", None):
        Path(args.output).write_text(content, encoding="utf-8")
        print(f"Report written to: {args.output}")
    else:
        print(content)


def cmd_release_bundle(args: argparse.Namespace) -> None:
    """Build the local v1 release artifact bundle."""
    from sourcelab.release.bundle import build_release_bundle

    result = build_release_bundle(Path.cwd())
    _json(result)


def cmd_release_checksums(args: argparse.Namespace) -> None:
    """Write SHA256 checksums for the release bundle."""
    from sourcelab.release.checksums import write_release_checksums

    result = write_release_checksums(Path.cwd())
    _json(result)


def cmd_release_sbom(args: argparse.Namespace) -> None:
    """Write a lightweight SBOM JSON artifact."""
    from sourcelab.release.sbom import write_release_sbom

    result = write_release_sbom(Path.cwd())
    _json(result)


def cmd_release_attest(args: argparse.Namespace) -> None:
    """Write an unsigned release attestation JSON artifact."""
    from sourcelab.release.attest import write_release_attestation

    result = write_release_attestation(Path.cwd())
    _json(result)


def cmd_release_sign(args: argparse.Namespace) -> None:
    """Write a signature plan or optionally sign release checksums."""
    from sourcelab.release.signing import write_signature_plan

    result = write_signature_plan(
        Path.cwd(),
        mode=getattr(args, "mode", "dry-run"),
        key_id=getattr(args, "key_id", None),
    )
    _json(result)


def cmd_release_verify_signature(args: argparse.Namespace) -> None:
    """Verify release signature or record unsigned status."""
    from sourcelab.release.signing import verify_release_signature

    result = verify_release_signature(Path.cwd())
    _json(result)


def cmd_release_publish(args: argparse.Namespace) -> None:
    """Write a publish plan without uploading artifacts."""
    from sourcelab.release.publish import write_publish_plan

    result = write_publish_plan(Path.cwd(), dry_run=getattr(args, "dry_run", True))
    _json(result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SourceLab AI production scaffold CLI")
    sub = parser.add_subparsers(required=True)

    version_cmd = sub.add_parser("version", help="Show package version metadata.")
    version_cmd.set_defaults(func=cmd_version)

    doctor_cmd = sub.add_parser("doctor", help="Run environment readiness checks.")
    doctor_cmd.set_defaults(func=cmd_doctor)

    init_local_cmd = sub.add_parser("init-local", help="Run idempotent first-run local setup.")
    init_local_cmd.set_defaults(func=cmd_init_local)

    demo = sub.add_parser("demo", help="Run the end-to-end source-grounded demo.")
    demo.add_argument("--topic", default="post-quantum cryptography migration")
    demo.add_argument("--model-mode", choices=["deterministic", "local_llm"], default=None, help="Model mode override")
    demo.add_argument("--model-backend", choices=["deterministic", "ollama", "openai_compatible"], default=None, help="Model backend override")
    demo.add_argument("--model-name", default=None, help="Model name override")
    demo.add_argument("--model-base-url", default=None, help="Model base URL override")
    demo.set_defaults(func=cmd_demo)

    status = sub.add_parser("status", help="Show local run status.")
    status.set_defaults(func=cmd_status)

    sources = sub.add_parser("sources", help="Source registry commands.")
    sources_sub = sources.add_subparsers(required=True)

    sources_list = sources_sub.add_parser("list", help="List demo sources.")
    sources_list.set_defaults(func=cmd_sources_list)

    sources_validate = sources_sub.add_parser("validate", help="Validate the source registry.")
    sources_validate.set_defaults(func=cmd_sources_validate)

    sources_export = sources_sub.add_parser("export", help="Export the normalized source registry.")
    sources_export.set_defaults(func=cmd_sources_export)

    sources_approve = sources_sub.add_parser("approve", help="Approve a source.")
    sources_approve.add_argument("source_id", help="Source ID to approve")
    sources_approve.set_defaults(func=cmd_sources_approve)

    sources_reject = sources_sub.add_parser("reject", help="Reject a source.")
    sources_reject.add_argument("source_id", help="Source ID to reject")
    sources_reject.add_argument("--reason", default="", help="Reason for rejection")
    sources_reject.set_defaults(func=cmd_sources_reject)

    sources_archive = sources_sub.add_parser("archive", help="Archive a source.")
    sources_archive.add_argument("source_id", help="Source ID to archive")
    sources_archive.set_defaults(func=cmd_sources_archive)

    sources_pending = sources_sub.add_parser("pending", help="List sources pending review.")
    sources_pending.set_defaults(func=cmd_sources_pending)

    sources_freshness = sources_sub.add_parser("freshness", help="Check source freshness.")
    sources_freshness.set_defaults(func=cmd_sources_freshness)

    sources_quality = sources_sub.add_parser("quality", help="Generate source quality report.")
    sources_quality.set_defaults(func=cmd_sources_quality)

    ingest = sub.add_parser("ingest-local", help="Ingest local markdown/text sources into the registry.")
    ingest.add_argument("folder", help="Path to folder containing source files")
    ingest.add_argument(
        "--trust-tier",
        default="C",
        choices=sorted(VALID_TRUST_TIERS),
        help="Trust tier for ingested sources (default: C)",
    )
    ingest.add_argument("--publisher", default="local", help="Publisher name (default: local)")
    ingest.add_argument("--source-type", default="local_note", help="Source type (default: local_note)")
    ingest.set_defaults(func=cmd_ingest_local)

    ingest_url = sub.add_parser("ingest-url", help="Ingest a source from a URL.")
    ingest_url.add_argument("url", help="URL to ingest")
    ingest_url.add_argument(
        "--trust-tier",
        default="C",
        choices=sorted(VALID_TRUST_TIERS),
        help="Trust tier for ingested source (default: C)",
    )
    ingest_url.add_argument("--publisher", default="web", help="Publisher name (default: web)")
    ingest_url.add_argument("--source-type", default="web_page", help="Source type (default: web_page)")
    ingest_url.set_defaults(func=cmd_ingest_url)

    search = sub.add_parser("search", help="Search approved local sources.")
    search.add_argument("query")
    search.add_argument("--top-k", type=int, default=4)
    search.add_argument(
        "--mode",
        choices=["vector", "keyword", "hybrid"],
        default="vector",
        help="Search mode: vector (default), keyword, or hybrid",
    )
    search.add_argument(
        "--backend",
        choices=["hash", "sentence_transformers"],
        default="hash",
        help="Embedding backend (default: hash)",
    )
    search.add_argument(
        "--store",
        choices=["memory", "json", "faiss"],
        default="memory",
        help="Vector store (default: memory)",
    )
    search.add_argument(
        "--diagnostics",
        action="store_true",
        default=False,
        help="Include detailed diagnostics in output",
    )
    search.set_defaults(func=cmd_search)

    # Lesson subcommand
    lesson = sub.add_parser("lesson", help="Lesson generation commands.")
    lesson_sub = lesson.add_subparsers(required=True)

    lesson_create = lesson_sub.add_parser("create", help="Create a new lesson package.")
    lesson_create.add_argument("--topic", required=True, help="Topic for the lesson")
    lesson_create.add_argument(
        "--difficulty",
        type=int,
        default=3,
        choices=range(1, 6),
        help="Difficulty level 1-5 (default: 3)",
    )
    lesson_create.add_argument(
        "--format",
        choices=[
            "executive_explanation",
            "architecture_review",
            "debugging",
            "hands_on_lab",
            "risk_review",
        ],
        default="architecture_review",
        help="Task format (default: architecture_review)",
    )
    lesson_create.add_argument(
        "--source-pack",
        dest="source_pack",
        default=None,
        help="Source pack to scope retrieval (e.g. pqc_v1)",
    )
    lesson_create.add_argument("--model-mode", choices=["deterministic", "local_llm"], default=None, help="Model mode override")
    lesson_create.add_argument("--model-backend", choices=["deterministic", "ollama", "openai_compatible"], default=None, help="Model backend override")
    lesson_create.add_argument("--model-name", default=None, help="Model name override")
    lesson_create.add_argument("--model-base-url", default=None, help="Model base URL override")
    lesson_create.set_defaults(func=cmd_lesson_create)

    lesson_show = lesson_sub.add_parser("show", help="Show the latest generated lesson.")
    lesson_show.add_argument("--latest", action="store_true", default=True, help="Show the latest lesson")
    lesson_show.set_defaults(func=cmd_lesson_show)

    verify = sub.add_parser("verify-release", help="Run release verification gates.")
    verify.add_argument("--strict", action="store_true", default=False, help="Enable strict mode (golden eval failures are blocking)")
    verify.set_defaults(func=cmd_verify_release)

    # Verify subcommand
    verify = sub.add_parser("verify", help="Verification commands.")
    verify_sub = verify.add_subparsers(required=True)

    verify_latest = verify_sub.add_parser("latest", help="Verify the latest run.")
    verify_latest.set_defaults(func=cmd_verify_latest)

    verify_run = verify_sub.add_parser("run", help="Verify a specific run.")
    verify_run.add_argument("run_id", help="Run ID to verify")
    verify_run.set_defaults(func=cmd_verify_run)

    verify_claims = verify_sub.add_parser("claims", help="View claims from a run.")
    verify_claims.add_argument("--run-id", help="Run ID (default: latest)")
    verify_claims.set_defaults(func=cmd_verify_claims)

    # Review subcommand
    review = sub.add_parser("review", help="Human review commands.")
    review_sub = review.add_subparsers(required=True)

    review_queue = review_sub.add_parser("queue", help="View the human review queue.")
    review_queue.add_argument("--run-id", help="Run ID (default: latest)")
    review_queue.set_defaults(func=cmd_review_queue)

    # Proof subcommand
    proof = sub.add_parser("proof", help="Proof bundle commands.")
    proof_sub = proof.add_subparsers(required=True)

    proof_latest = proof_sub.add_parser("latest", help="View the latest proof bundle.")
    proof_latest.set_defaults(func=cmd_proof_latest)

    proof_run = proof_sub.add_parser("run", help="View a specific proof bundle.")
    proof_run.add_argument("run_id", help="Run ID to view")
    proof_run.set_defaults(func=cmd_proof_run)

    proof_artifacts = proof_sub.add_parser("artifacts", help="List artifacts from a run.")
    proof_artifacts.add_argument("--run-id", help="Run ID (default: latest)")
    proof_artifacts.add_argument("--latest", action="store_true", default=True, help="Use latest run")
    proof_artifacts.set_defaults(func=cmd_proof_artifacts)

    # Harness subcommand
    harness = sub.add_parser("harness", help="Harness validation commands.")
    harness_sub = harness.add_subparsers(required=True)

    harness_latest = harness_sub.add_parser("latest", help="View the latest harness report.")
    harness_latest.set_defaults(func=cmd_harness_latest)

    harness_run = harness_sub.add_parser("run", help="View a specific harness report.")
    harness_run.add_argument("run_id", help="Run ID to view")
    harness_run.set_defaults(func=cmd_harness_run)

    # Answer subcommand
    answer = sub.add_parser("answer", help="Answer submission and scoring commands.")
    answer_sub = answer.add_subparsers(required=True)

    answer_submit = answer_sub.add_parser("submit", help="Submit and score a learner answer.")
    answer_submit.add_argument("--topic", help="Topic for the answer (default: from run package)")
    answer_submit.add_argument("--file", help="Path to a file containing the answer")
    answer_submit.add_argument("--text", help="Answer text directly")
    answer_submit.add_argument("--run-id", "--run", dest="run_id", help="Run ID to score against (default: latest)")
    answer_submit.set_defaults(func=cmd_answer_submit)

    answer_history = answer_sub.add_parser("history", help="List answer attempt history for a run.")
    answer_history.add_argument("--run-id", "--run", dest="run_id", default="latest", help="Run ID (default: latest)")
    answer_history.set_defaults(func=cmd_answer_history)

    answer_show = answer_sub.add_parser("show", help="Show detail for a single answer attempt.")
    answer_show.add_argument("--run-id", "--run", dest="run_id", default="latest", help="Run ID (default: latest)")
    answer_show.add_argument("--attempt", required=True, help="Attempt ID to show")
    answer_show.set_defaults(func=cmd_answer_show)

    answer_diff = answer_sub.add_parser("diff", help="Compare two answer attempts.")
    answer_diff.add_argument("--run-id", "--run", dest="run_id", default="latest", help="Run ID (default: latest)")
    answer_diff.add_argument("--from", dest="from_attempt", required=True, help="Earlier attempt ID")
    answer_diff.add_argument("--to", dest="to_attempt", required=True, help="Later attempt ID")
    answer_diff.set_defaults(func=cmd_answer_diff)

    # Profile subcommand
    profile = sub.add_parser("profile", help="Skill profile commands.")
    profile_sub = profile.add_subparsers(required=True)

    profile_show = profile_sub.add_parser("show", help="Show the current skill profile.")
    profile_show.set_defaults(func=cmd_profile_show)

    profile_topic = profile_sub.add_parser("topic", help="Show mastery for a specific topic.")
    profile_topic.add_argument("topic", help="Topic to check")
    profile_topic.set_defaults(func=cmd_profile_topic)

    # Learning subcommand
    learning = sub.add_parser("learning", help="Learning report commands.")
    learning_sub = learning.add_subparsers(required=True)

    learning_report = learning_sub.add_parser("report", help="Show the latest learning report.")
    learning_report.add_argument("--latest", action="store_true", default=True, help="Show the latest learning report")
    learning_report.set_defaults(func=cmd_learning_report)

    # Dashboard subcommand
    dashboard = sub.add_parser("dashboard", help="Launch the Streamlit dashboard.")
    dashboard.add_argument("--launch", action="store_true", default=False, help="Launch dashboard immediately")
    dashboard.set_defaults(func=cmd_dashboard)

    # Runs subcommand
    runs = sub.add_parser("runs", help="Run explorer commands.")
    runs_sub = runs.add_subparsers(required=True)

    runs_list = runs_sub.add_parser("list", help="List all runs.")
    runs_list.set_defaults(func=cmd_runs_list)

    runs_latest = runs_sub.add_parser("latest", help="Show the latest run summary.")
    runs_latest.set_defaults(func=cmd_runs_latest)

    runs_show = runs_sub.add_parser("show", help="Explore a specific run.")
    runs_show.add_argument("run_id", help="Run ID to explore, or 'latest'")
    runs_show.set_defaults(func=cmd_runs_show)

    runs_compare = runs_sub.add_parser("compare", help="Compare two or more runs.")
    runs_compare.add_argument("run_ids", nargs="+", help="Run IDs to compare (minimum 2)")
    runs_compare.set_defaults(func=cmd_runs_compare)

    runs_answers_compare = runs_sub.add_parser(
        "answers-compare",
        help="Compare learner answer attempts across runs.",
    )
    runs_answers_compare.add_argument("run_ids", nargs="+", help="Run IDs (minimum 2)")
    runs_answers_compare.add_argument("--json", action="store_true", help="Emit JSON instead of table")
    runs_answers_compare.add_argument(
        "--markdown",
        action="store_true",
        help="Emit markdown table and recommendations",
    )
    runs_answers_compare.set_defaults(func=cmd_runs_answers_compare)

    # Batch subcommand
    batch = sub.add_parser("batch", help="Batch run commands.")
    batch_sub = batch.add_subparsers(required=True)

    batch_create = batch_sub.add_parser("create", help="Create a batch of lesson runs.")
    batch_create.add_argument("--name", default="", help="Batch name (or use batch_name in config)")
    batch_create.add_argument(
        "--config",
        required=True,
        help="Path to batch JSON config (e.g. examples/batch_pqc.json)",
    )
    batch_create.set_defaults(func=cmd_batch_create)

    batch_list = batch_sub.add_parser("list", help="List all batches.")
    batch_list.set_defaults(func=cmd_batch_list)

    batch_show = batch_sub.add_parser("show", help="Show batch detail.")
    batch_show.add_argument("batch_id", help="Batch ID")
    batch_show.set_defaults(func=cmd_batch_show)

    batch_compare = batch_sub.add_parser("compare", help="Compare runs in a batch.")
    batch_compare.add_argument("batch_id", help="Batch ID")
    batch_compare.set_defaults(func=cmd_batch_compare)

    batch_answers = batch_sub.add_parser("answers", help="Compare learner answers in a batch.")
    batch_answers.add_argument("batch_id", help="Batch ID")
    batch_answers.add_argument("--json", action="store_true", help="Emit JSON instead of table")
    batch_answers.add_argument(
        "--markdown",
        action="store_true",
        help="Emit markdown table and recommendations",
    )
    batch_answers.set_defaults(func=cmd_batch_answers)

    # Export subcommand
    export = sub.add_parser("export", help="Export run reports.")
    export.add_argument("run_id", help="Run ID to export, or 'latest'")
    export.add_argument(
        "--format",
        choices=["markdown", "html"],
        default="markdown",
        help="Export format (default: markdown)",
    )
    export.set_defaults(func=cmd_export)

    # Index subcommand
    index = sub.add_parser("index", help="Index management commands.")
    index_sub = index.add_subparsers(required=True)

    index_build = index_sub.add_parser("build", help="Build a persistent vector index.")
    index_build.add_argument(
        "--backend",
        choices=["hash", "sentence_transformers"],
        default="hash",
        help="Embedding backend (default: hash)",
    )
    index_build.add_argument(
        "--store",
        choices=["memory", "json", "faiss"],
        default="json",
        help="Vector store (default: json)",
    )
    index_build.add_argument("--dim", type=int, default=128, help="Embedding dimension (default: 128)")
    index_build.add_argument("--index-dir", default="artifacts/index", help="Index directory")
    index_build.set_defaults(func=cmd_index_build)

    index_stats = index_sub.add_parser("stats", help="Show index statistics.")
    index_stats.add_argument("--index-dir", default="artifacts/index", help="Index directory")
    index_stats.set_defaults(func=cmd_index_stats)

    index_clear = index_sub.add_parser("clear", help="Clear the persistent index.")
    index_clear.add_argument("--index-dir", default="artifacts/index", help="Index directory")
    index_clear.set_defaults(func=cmd_index_clear)

    # Retrieval subcommand
    retrieval = sub.add_parser("retrieval", help="Retrieval commands.")
    retrieval_sub = retrieval.add_subparsers(required=True)

    retrieval_eval = retrieval_sub.add_parser("eval", help="Run retrieval evaluation.")
    retrieval_eval.add_argument(
        "--backend",
        choices=["hash", "sentence_transformers"],
        default="hash",
        help="Embedding backend (default: hash)",
    )
    retrieval_eval.add_argument(
        "--store",
        choices=["memory", "json", "faiss"],
        default="memory",
        help="Vector store (default: memory)",
    )
    retrieval_eval.add_argument("--dim", type=int, default=128, help="Embedding dimension (default: 128)")
    retrieval_eval.add_argument("--top-k", type=int, default=3, help="Top-k results (default: 3)")
    retrieval_eval.set_defaults(func=cmd_retrieval_eval)

    # API subcommand
    api = sub.add_parser("api", help="Start the API server or inspect routes.")
    api.add_argument("--serve", action="store_true", default=False, help="Start the API server")
    api.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    api.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    api.add_argument("--reload", action="store_true", default=True, help="Enable auto-reload (default: True)")
    api.add_argument("--no-reload", action="store_false", dest="reload", help="Disable auto-reload")
    api.set_defaults(func=cmd_api)
    api_sub = api.add_subparsers(dest="api_command")
    api_routes = api_sub.add_parser("routes", help="List registered API routes.")
    api_routes.add_argument("--json", action="store_true", default=False, help="Output routes as JSON")
    api_routes.set_defaults(func=cmd_api_routes)

    # Models subcommand
    models = sub.add_parser("models", help="Model router commands.")
    models_sub = models.add_subparsers(required=True)

    models_config = models_sub.add_parser("config", help="Show current model configuration.")
    models_config.set_defaults(func=cmd_models_config)

    models_health = models_sub.add_parser("health", help="Check health of model backend.")
    models_health.set_defaults(func=cmd_models_health)

    models_test = models_sub.add_parser("test", help="Test a model backend.")
    models_test.add_argument("--mode", choices=["deterministic", "local_llm"], default="deterministic", help="Model mode (default: deterministic)")
    models_test.add_argument("--backend", choices=["deterministic", "ollama", "openai_compatible"], default="deterministic", help="Model backend (default: deterministic)")
    models_test.add_argument("--model-name", default="", help="Model name")
    models_test.add_argument("--model-base-url", default="", help="Model base URL")
    models_test.add_argument("--prompt", default="What is post-quantum cryptography?", help="Test prompt")
    models_test.set_defaults(func=cmd_models_test)

    # Source pack subcommand
    source_pack = sub.add_parser("source-pack", help="Source pack commands.")
    source_pack_sub = source_pack.add_subparsers(required=True)

    source_pack_list = source_pack_sub.add_parser("list", help="List available source packs.")
    source_pack_list.set_defaults(func=cmd_source_pack_list)

    source_pack_validate = source_pack_sub.add_parser("validate", help="Validate a source pack.")
    source_pack_validate.add_argument("pack_name", help="Pack name to validate")
    source_pack_validate.set_defaults(func=cmd_source_pack_validate)

    source_pack_doctor = source_pack_sub.add_parser("doctor", help="Run strengthened source pack checks.")
    source_pack_doctor.add_argument("pack_name", help="Pack name to check")
    source_pack_doctor.set_defaults(func=cmd_source_pack_doctor)

    source_pack_install = source_pack_sub.add_parser("install", help="Install a source pack.")
    source_pack_install.add_argument("pack_name", help="Pack name to install")
    source_pack_install.set_defaults(func=cmd_source_pack_install)

    source_pack_status_cmd = source_pack_sub.add_parser("status", help="Check source pack status.")
    source_pack_status_cmd.add_argument("pack_name", help="Pack name to check")
    source_pack_status_cmd.set_defaults(func=cmd_source_pack_status)

    # Evals subcommand
    evals = sub.add_parser("evals", help="Golden evaluation commands.")
    evals_sub = evals.add_subparsers(required=True)

    evals_run = evals_sub.add_parser("run", help="Run golden evals.")
    evals_run.add_argument("--pack", help="Source pack name")
    evals_run.add_argument("--all-packs", action="store_true", default=False, help="Run evals for all curated packs")
    evals_run.add_argument(
        "--type",
        choices=["retrieval", "claims", "answers", "lessons"],
        help="Eval type to run (default: all)",
    )
    evals_run.set_defaults(func=cmd_evals_run)

    evals_latest = evals_sub.add_parser("latest", help="Show latest eval results.")
    evals_latest.add_argument("--pack", help="Source pack name")
    evals_latest.add_argument("--all-packs", action="store_true", default=False, help="Show combined all-packs summary")
    evals_latest.set_defaults(func=cmd_evals_latest)

    evals_thresholds = evals_sub.add_parser("thresholds", help="Per-pack eval threshold commands.")
    evals_thresholds_sub = evals_thresholds.add_subparsers(required=True)

    evals_thresholds_show = evals_thresholds_sub.add_parser(
        "show", help="Show per-pack eval thresholds and compliance."
    )
    evals_thresholds_show.add_argument("--pack", required=True, help="Source pack name")
    evals_thresholds_show.set_defaults(func=cmd_evals_thresholds_show)

    evals_thresholds_set = evals_thresholds_sub.add_parser(
        "set", help="Set per-pack eval thresholds in the pack's manifest.json."
    )
    evals_thresholds_set.add_argument("--pack", required=True, help="Source pack name")
    evals_thresholds_set.add_argument(
        "--min-pass-rate",
        type=float,
        help="Minimum overall pass rate (0.0 to 1.0)",
    )
    evals_thresholds_set.add_argument(
        "--min-cases",
        type=int,
        help="Minimum number of eval cases required",
    )
    evals_thresholds_set.add_argument(
        "--required-evals",
        help="Comma-separated list of required eval names (e.g. retrieval_gold,claim_gold)",
    )
    evals_thresholds_set.set_defaults(func=cmd_evals_thresholds_set)

    # Local demo subcommand
    local_demo = sub.add_parser("local-demo", help="Run the full local demonstration pipeline.")
    local_demo.set_defaults(func=cmd_local_demo)

    # Release subcommand
    release = sub.add_parser("release", help="Release manifest and checklist commands.")
    release_sub = release.add_subparsers(required=True)

    release_check = release_sub.add_parser("check", help="Run local v1 readiness checks.")
    release_check.set_defaults(func=cmd_release_check)

    release_manifest = release_sub.add_parser("manifest", help="Print the local v1 release manifest.")
    release_manifest.set_defaults(func=cmd_release_manifest)

    release_report = release_sub.add_parser("report", help="Print or write the release report.")
    release_report.add_argument("--output", "-o", help="Output file path (default: print to stdout)")
    release_report.set_defaults(func=cmd_release_report)

    release_bundle = release_sub.add_parser("bundle", help="Build the local v1 release artifact bundle.")
    release_bundle.set_defaults(func=cmd_release_bundle)

    release_checksums = release_sub.add_parser("checksums", help="Write SHA256 checksums for release bundle.")
    release_checksums.set_defaults(func=cmd_release_checksums)

    release_sbom = release_sub.add_parser("sbom", help="Write a lightweight SBOM JSON artifact.")
    release_sbom.set_defaults(func=cmd_release_sbom)

    release_attest = release_sub.add_parser("attest", help="Write an unsigned release attestation JSON.")
    release_attest.set_defaults(func=cmd_release_attest)

    release_sign = release_sub.add_parser("sign", help="Write signature plan or optionally sign checksums.")
    release_sign.add_argument(
        "--mode",
        choices=["dry-run", "gpg"],
        default="dry-run",
        help="Signing mode (default: dry-run)",
    )
    release_sign.add_argument("--key-id", default=None, help="GPG key ID for --mode gpg")
    release_sign.set_defaults(func=cmd_release_sign)

    release_verify_sig = release_sub.add_parser(
        "verify-signature",
        help="Verify release signature or record unsigned status.",
    )
    release_verify_sig.set_defaults(func=cmd_release_verify_signature)

    release_publish = release_sub.add_parser("publish", help="Write publish plan without uploading.")
    release_publish.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Dry-run publish planning (default)",
    )
    release_publish.set_defaults(func=cmd_release_publish)

    from sourcelab.library.cli import register_library_subparser

    register_library_subparser(sub)

    from sourcelab.research.cli import register_research_subparser

    register_research_subparser(sub)

    return parser


def cmd_api_routes(args: argparse.Namespace) -> None:
    """List the registered FastAPI routes (path + methods).

    Uses the generated OpenAPI schema so router-mounted routes are
    enumerated reliably regardless of internal route nesting.
    """
    try:
        from sourcelab.api.main import app
    except ImportError:
        app = None

    if app is None:
        print("FastAPI is not installed. Install with: pip install -e '.[api]'")
        return

    routes = []
    spec = app.openapi()
    for path, operations in spec.get("paths", {}).items():
        methods = sorted(
            method.upper()
            for method in operations
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        )
        routes.append({"path": path, "methods": methods})
    routes.sort(key=lambda r: r["path"])

    if getattr(args, "json", False):
        _json({"routes": routes, "total": len(routes)})
        return

    for route in routes:
        methods = ",".join(route["methods"]) if route["methods"] else "-"
        print(f"{methods:<22} {route['path']}")
    print(f"\nTotal routes: {len(routes)}")


def cmd_api(args: argparse.Namespace) -> None:
    """Start the API server."""
    if not getattr(args, "serve", False):
        print("To start the API server, run:")
        print("  sourcelab api --serve")
        print()
        print("Or use: bash scripts/start_api.sh")
        return

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is required for the API server.")
        print("Install with: pip install -e '.[api]'")
        return

    try:
        from sourcelab.api.main import app
    except ImportError:
        print("Error: FastAPI is required for the API server.")
        print("Install with: pip install -e '.[api]'")
        return

    if app is None:
        print("Error: FastAPI is required for the API server.")
        print("Install with: pip install -e '.[api]'")
        return

    print(f"Starting SourceLab API server on {args.host}:{args.port}")
    print(f"API docs available at: http://localhost:{args.port}/docs")
    uvicorn.run(
        "sourcelab.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
