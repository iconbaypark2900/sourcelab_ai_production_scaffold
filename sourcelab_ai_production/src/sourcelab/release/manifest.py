"""Release manifest builder for SourceLab AI.

Instruction:
- Builds the local v1 release manifest from current project state.
- Writes artifacts/release/local_v1_release_manifest.json
- Writes artifacts/release/local_v1_release_report.md
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sourcelab.release.schemas import ReleaseManifest
from sourcelab.version import RELEASE_LABEL, __version__


def build_release_manifest(project_root: Path) -> ReleaseManifest:
    """Build the local v1 release manifest from current project state."""
    from sourcelab.doctor import get_optional_extras_status, run_doctor
    from sourcelab.init_local import run_init_local
    from sourcelab.sources.source_pack import source_pack_status
    from sourcelab.harness.release_gate import _find_latest_run
    from sourcelab.ui.run_loader import load_json_artifact

    manifest = ReleaseManifest(version=__version__, release_label=RELEASE_LABEL)

    # 1. Test count
    tests_dir = project_root / "tests"
    if tests_dir.exists():
        test_files = list(tests_dir.glob("**/test_*.py"))
        manifest.test_count = len(test_files)

    # 2. Source pack status
    pack_status = source_pack_status(project_root, "pqc_v1")
    manifest.pqc_pack_installed = pack_status.get("installed", False)
    manifest.pqc_pack_source_count = pack_status.get("installed_count", 0)

    # 3. Source validation
    from sourcelab.sources.registry import SourceRegistry
    registry_path = project_root / "data" / "source_registry.json"
    if registry_path.exists():
        try:
            registry = SourceRegistry.load_from_json(registry_path)
            errors = registry.validate()
            manifest.source_validation_status = "PASS" if not errors else "FAIL"
        except Exception:
            manifest.source_validation_status = "unknown"
    else:
        manifest.source_validation_status = "no_registry"

    # 4. Latest run info
    latest_run = _find_latest_run(project_root)
    if latest_run is not None:
        manifest.latest_run_id = latest_run.name

        run_manifest = load_json_artifact(latest_run, "run_manifest.json")
        if run_manifest and isinstance(run_manifest, dict):
            manifest.latest_run_topic = run_manifest.get("topic", "")

        harness_report = load_json_artifact(latest_run, "harness_report.json")
        if harness_report and isinstance(harness_report, dict):
            manifest.latest_run_harness_passed = harness_report.get("passed")
            manifest.harness_artifact_count = harness_report.get("artifact_count", 0)
            manifest.harness_status = "PASS" if harness_report.get("passed") else "FAIL"

        proof_summary = load_json_artifact(latest_run, "proof_summary.json")
        if proof_summary and isinstance(proof_summary, dict):
            manifest.latest_run_answer_score = proof_summary.get("answer_score")
            manifest.proof_bundle_status = proof_summary.get("release_gate_status", "unknown")

        # Artifact count
        artifact_files = [
            f for f in latest_run.iterdir()
            if f.is_file() and f.suffix in [".json", ".md", ".txt"]
        ]
        manifest.proof_bundle_artifact_count = len(artifact_files)

    # 5. Golden eval status
    evals_dir = project_root / "artifacts" / "evals"
    if evals_dir.exists():
        total_cases = 0
        total_passed = 0
        for pack_dir in evals_dir.iterdir():
            if not pack_dir.is_dir():
                continue
            summary_path = pack_dir / "golden_eval_summary.json"
            if not summary_path.exists():
                continue
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                pack_cases = summary.get("total_cases", 0)
                pack_passed = summary.get("total_passed", 0)
                total_cases += pack_cases
                total_passed += pack_passed
                manifest.golden_eval_packs.append({
                    "pack": pack_dir.name,
                    "pass_rate": summary.get("overall_pass_rate", 0),
                    "total_cases": pack_cases,
                    "total_passed": pack_passed,
                })
            except (json.JSONDecodeError, KeyError):
                continue

        manifest.golden_eval_total_cases = total_cases
        manifest.golden_eval_passed_cases = total_passed
        manifest.golden_eval_pass_rate = total_passed / total_cases if total_cases > 0 else None
        manifest.golden_eval_status = (
            "PASS" if manifest.golden_eval_pass_rate is not None and manifest.golden_eval_pass_rate >= 0.8
            else "FAIL" if manifest.golden_eval_pass_rate is not None
            else "unknown"
        )

    # 6. Retrieval eval
    retrieval_eval_path = project_root / "artifacts" / "evals" / "retrieval_eval.json"
    if retrieval_eval_path.exists():
        try:
            retrieval_data = json.loads(retrieval_eval_path.read_text(encoding="utf-8"))
            manifest.retrieval_eval_pass_rate = retrieval_data.get("pass_rate")
            manifest.retrieval_eval_status = (
                "PASS" if manifest.retrieval_eval_pass_rate is not None and manifest.retrieval_eval_pass_rate >= 0.8
                else "FAIL"
            )
        except (json.JSONDecodeError, KeyError):
            pass

    # 7. API routes
    try:
        from sourcelab.api.main import app
        if app is not None:
            manifest.api_available = True
            manifest.api_routes = [
                route.path for route in app.routes
                if hasattr(route, "path")
            ]
        else:
            manifest.api_available = False
    except Exception:
        manifest.api_available = False

    # 8. Known limitations
    manifest.known_limitations = [
        "Deterministic fallback used for generation (no live LLM required)",
        "Hashed embeddings instead of neural embeddings",
        "int8 compression instead of full TurboQuant",
        "Heuristic scoring instead of LLM judge",
        "No authentication or multi-user support",
        "No persistent database storage",
        "No live web search capability",
    ]

    # 9. Strict release check
    from sourcelab.harness.release_gate import verify_release
    strict_report = verify_release(project_root, strict=True)
    manifest.strict_release_status = strict_report["status"]
    manifest.strict_release_blocking = strict_report["blocking_failures"]
    manifest.strict_release_warnings = strict_report["warnings"]

    # 10. Local v1 packaging status
    doctor_report = run_doctor(project_root)
    manifest.doctor_status = doctor_report.get("status", "unknown")
    init_report = run_init_local(project_root)
    manifest.init_local_status = init_report.get("status", "unknown")
    manifest.package_extras = get_optional_extras_status()

    smoke_test_path = project_root / "tests" / "integration" / "test_local_v1_smoke.py"
    manifest.smoke_status = "available" if smoke_test_path.exists() else "missing"

    dockerfile = project_root / "Dockerfile"
    compose_file = project_root / "docker-compose.yml"
    manifest.docker_available = dockerfile.exists() and compose_file.exists()
    manifest.docker_note = (
        "docker compose up sourcelab-api exposes FastAPI on port 8000"
        if manifest.docker_available
        else "Docker packaging not present"
    )

    manifest.demo_scripts = [
        "scripts/local_v1_demo.sh",
        "scripts/local_v1_smoke.sh",
        "scripts/start_api.sh",
        "scripts/start_dashboard.sh",
    ]
    manifest.release_notes_path = "RELEASE_NOTES_LOCAL_V1_GA.md"
    manifest.changelog_path = "CHANGELOG.md"

    return manifest


def write_release_manifest(manifest: ReleaseManifest, project_root: Path) -> tuple[Path, Path]:
    """Write release manifest JSON and markdown report."""
    release_dir = project_root / "artifacts" / "release"
    release_dir.mkdir(parents=True, exist_ok=True)

    # Write JSON manifest
    json_path = release_dir / "local_v1_release_manifest.json"
    json_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )

    # Write markdown report
    md_path = release_dir / "local_v1_release_report.md"
    md_content = _generate_release_report(manifest)
    md_path.write_text(md_content, encoding="utf-8")

    return json_path, md_path


def _generate_release_report(manifest: ReleaseManifest) -> str:
    """Generate a markdown release report."""
    lines = [
        f"# SourceLab AI Local v1 Release Report",
        "",
        f"**Version:** {manifest.version}",
        f"**Release Label:** {manifest.release_label}",
        f"**Created:** {manifest.created_at.isoformat()}",
        f"**Project:** {manifest.project_name}",
        "",
        "## Status Summary",
        "",
        f"- **Strict Release Status:** {manifest.strict_release_status}",
        f"- **Golden Eval Status:** {manifest.golden_eval_status}",
        f"- **Harness Status:** {manifest.harness_status}",
        f"- **Source Pack Installed:** {'Yes' if manifest.pqc_pack_installed else 'No'}",
        f"- **Source Validation:** {manifest.source_validation_status}",
        f"- **Doctor Status:** {manifest.doctor_status}",
        f"- **Init Local Status:** {manifest.init_local_status}",
        f"- **Smoke Tests:** {manifest.smoke_status}",
        "",
        "## Package Extras",
        "",
    ]

    for extra, installed in sorted(manifest.package_extras.items()):
        lines.append(f"- **{extra}:** {'installed' if installed else 'missing'}")

    lines.extend([
        "",
        f"- **Docker:** {manifest.docker_note}",
        "",
        "## Demo Scripts",
        "",
    ])

    for script in manifest.demo_scripts:
        lines.append(f"- `{script}`")

    lines.extend([
        "",
        f"- **Release Notes:** `{manifest.release_notes_path}`",
        f"- **Changelog:** `{manifest.changelog_path}`",
        "",
        "## Test Status",
        "",
        f"- **Test Files:** {manifest.test_count}",
        f"- **Pytest Status:** {manifest.pytest_status or 'not run'}",
        "",
        "## Latest Demo Run",
        "",
    ])

    if manifest.latest_run_id:
        lines.extend([
            f"- **Run ID:** {manifest.latest_run_id}",
            f"- **Topic:** {manifest.latest_run_topic or '(not set)'}",
            f"- **Harness Passed:** {manifest.latest_run_harness_passed}",
            f"- **Answer Score:** {manifest.latest_run_answer_score:.2f}" if manifest.latest_run_answer_score is not None else "- **Answer Score:** N/A",
            f"- **Artifact Count:** {manifest.proof_bundle_artifact_count}",
        ])
    else:
        lines.append("- No runs found.")

    lines.extend([
        "",
        "## Golden Eval Results",
        "",
    ])

    if manifest.golden_eval_packs:
        for pack in manifest.golden_eval_packs:
            lines.append(f"- **{pack['pack']}:** {pack['pass_rate']:.1%} ({pack['total_passed']}/{pack['total_cases']})")
    else:
        lines.append("- No golden eval results found.")

    lines.extend([
        "",
        "## Strict Release Blocking Issues",
        "",
    ])

    if manifest.strict_release_blocking:
        for issue in manifest.strict_release_blocking:
            lines.append(f"- {issue}")
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Strict Release Warnings",
        "",
    ])

    if manifest.strict_release_warnings:
        for warning in manifest.strict_release_warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Known Limitations",
        "",
    ])

    for limitation in manifest.known_limitations:
        lines.append(f"- {limitation}")

    lines.extend([
        "",
        "## Commands to Reproduce",
        "",
        "```bash",
        "# Run full local demo",
        "sourcelab local-demo",
        "",
        "# Run strict release verification",
        "sourcelab verify-release --strict",
        "",
        "# First-run setup",
        "sourcelab init-local",
        "",
        "# Environment checks",
        "sourcelab doctor",
        "",
        "# One-command demo",
        "bash scripts/local_v1_demo.sh",
        "",
        "# Check release readiness",
        "sourcelab release check",
        "",
        "# View release manifest",
        "sourcelab release manifest",
        "",
        "# View release report",
        "sourcelab release report",
        "",
        "# Build release bundle",
        "sourcelab release bundle",
        "",
        "# Generate release checksums",
        "sourcelab release checksums",
        "",
        "# Export SBOM and attestation",
        "sourcelab release sbom",
        "sourcelab release attest",
        "",
        "# Launch dashboard",
        f"{manifest.dashboard_launch_command}",
        "",
        "# Start API server",
        "sourcelab api --serve",
        "```",
        "",
    ])

    return "\n".join(lines)
