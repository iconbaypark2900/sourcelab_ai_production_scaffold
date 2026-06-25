"""Release dashboard summary helpers (no Streamlit dependency)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from sourcelab.harness.release_gate import _find_latest_run
from sourcelab.release.bundle import get_release_bundle_status
from sourcelab.ui.run_loader import get_latest_run, list_runs, summarize_run
from sourcelab.version import RELEASE_LABEL, __version__


def load_release_dashboard_summary(project_root: Path) -> dict:
    """Load release overview data for dashboard and tests."""
    root = project_root.resolve()
    manifest_path = root / "artifacts" / "release" / "local_v1_release_manifest.json"
    manifest_data: dict | None = None
    if manifest_path.exists():
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            manifest_data = None

    bundle_status = get_release_bundle_status(root)

    latest_run = get_latest_run(root)
    run_summary = None
    if latest_run is not None:
        run_summary = summarize_run(latest_run)

    golden_eval: dict | None = None
    evals_dir = root / "artifacts" / "evals"
    if evals_dir.exists():
        for pack_dir in sorted(evals_dir.iterdir()):
            summary_path = pack_dir / "golden_eval_summary.json"
            if pack_dir.is_dir() and summary_path.exists():
                try:
                    golden_eval = json.loads(summary_path.read_text(encoding="utf-8"))
                    golden_eval["pack"] = pack_dir.name
                    break
                except (json.JSONDecodeError, OSError):
                    continue

    exports_dir = root / "artifacts" / "exports"
    latest_export: str | None = None
    if exports_dir.exists():
        export_files = sorted(
            [p for p in exports_dir.iterdir() if p.is_file()],
            key=lambda p: p.stat().st_mtime,
        )
        if export_files:
            latest_export = str(export_files[-1])

    strict_status = "unknown"
    golden_status = "unknown"
    if manifest_data:
        strict_status = manifest_data.get("strict_release_status", "unknown")
        golden_status = manifest_data.get("golden_eval_status", "unknown")

    release_healthy = (
        strict_status == "PASS"
        and golden_status in {"PASS", "unknown"}
        and bundle_status.get("status") in {"present", "missing"}
    )

    next_steps: list[str] = []
    if bundle_status.get("status") != "present":
        next_steps.append("sourcelab release bundle")
    if strict_status != "PASS":
        next_steps.append("sourcelab verify-release --strict")
    if not latest_run:
        next_steps.append("sourcelab local-demo")
    elif not latest_export:
        next_steps.append("sourcelab export latest --format markdown")
    if not next_steps:
        next_steps.append("make ga-check")

    return {
        "version": __version__,
        "release_label": RELEASE_LABEL,
        "release_healthy": release_healthy,
        "strict_release_status": strict_status,
        "golden_eval_status": golden_status,
        "golden_eval": golden_eval,
        "bundle_status": bundle_status,
        "manifest": manifest_data,
        "latest_run": asdict(run_summary) if run_summary else None,
        "latest_export_path": latest_export,
        "recommended_next_commands": next_steps,
    }
