"""Release artifact bundle for SourceLab Local v1.

Instruction:
- Builds a distributable bundle under artifacts/release/sourcelab_local_v1_ga_bundle/
- Creates artifacts/release/sourcelab_local_v1_ga_bundle.zip
- Excludes .venv, caches, and oversized artifacts.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from sourcelab.harness.release_gate import _find_latest_run
from sourcelab.version import RELEASE_LABEL, __version__, version_info

BUNDLE_DIR_NAME = "sourcelab_local_v1_ga_bundle"
BUNDLE_DIR_NAME_LEGACY = "sourcelab_local_v1_rc_bundle"
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MiB per file
EXCLUDED_DIR_NAMES = {
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".so", ".whl"}


def _should_skip_path(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDED_DIR_NAMES:
            return True
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    if path.is_file():
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                return True
        except OSError:
            return True
    return False


def _copy_into_bundle(src: Path, bundle_root: Path, rel_dest: str, included: list[str]) -> None:
    if not src.exists() or not src.is_file():
        return
    if _should_skip_path(src):
        return
    dest = bundle_root / rel_dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    included.append(rel_dest)


def _latest_export_files(exports_dir: Path) -> list[Path]:
    if not exports_dir.exists():
        return []
    files = sorted(
        [p for p in exports_dir.iterdir() if p.is_file() and p.suffix in {".md", ".html"}],
        key=lambda p: p.stat().st_mtime,
    )
    if not files:
        return []
    latest_ts = files[-1].stat().st_mtime
    return [p for p in files if p.stat().st_mtime == latest_ts or p.name.startswith("report_")]


def _find_golden_eval_dir(project_root: Path) -> Path | None:
    evals_dir = project_root / "artifacts" / "evals"
    if not evals_dir.exists():
        return None
    for pack_dir in sorted(evals_dir.iterdir()):
        if pack_dir.is_dir() and (pack_dir / "golden_eval_summary.json").exists():
            return pack_dir
    return None


def build_release_bundle(project_root: Path) -> dict:
    """Build the local v1 release bundle directory and zip archive."""
    root = project_root.resolve()
    release_dir = root / "artifacts" / "release"
    release_dir.mkdir(parents=True, exist_ok=True)

    bundle_root = release_dir / BUNDLE_DIR_NAME
    if bundle_root.exists():
        shutil.rmtree(bundle_root)
    bundle_root.mkdir(parents=True)

    included: list[str] = []
    missing: list[str] = []

    def require_copy(src: Path, rel_dest: str) -> None:
        if src.exists():
            _copy_into_bundle(src, bundle_root, rel_dest, included)
        else:
            missing.append(rel_dest)

    # Release manifest and report
    require_copy(
        release_dir / "local_v1_release_manifest.json",
        "release/local_v1_release_manifest.json",
    )
    require_copy(
        release_dir / "local_v1_release_report.md",
        "release/local_v1_release_report.md",
    )

    # Version metadata
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **version_info(root),
    }
    version_path = bundle_root / "version_metadata.json"
    version_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    included.append("version_metadata.json")

    # Doctor report
    from sourcelab.doctor import run_doctor

    doctor_report = run_doctor(root)
    doctor_path = bundle_root / "doctor_report.json"
    doctor_path.write_text(json.dumps(doctor_report, indent=2, default=str), encoding="utf-8")
    included.append("doctor_report.json")

    # Latest run artifacts
    latest_run = _find_latest_run(root)
    if latest_run is not None:
        for name in ("proof_summary.json", "harness_report.json", "run_manifest.json"):
            src = latest_run / name
            if src.exists():
                _copy_into_bundle(src, bundle_root, f"runs/latest/{name}", included)
            else:
                missing.append(f"runs/latest/{name}")
    else:
        missing.append("runs/latest/")

    # Golden eval summaries
    golden_dir = _find_golden_eval_dir(root)
    if golden_dir is not None:
        for name in ("golden_eval_summary.json", "golden_eval_summary.md"):
            src = golden_dir / name
            if src.exists():
                _copy_into_bundle(
                    src,
                    bundle_root,
                    f"evals/{golden_dir.name}/{name}",
                    included,
                )
    else:
        missing.append("evals/golden_eval_summary.json")

    # Latest exports
    exports_dir = root / "artifacts" / "exports"
    export_files = _latest_export_files(exports_dir)
    if export_files:
        for export_file in export_files[-2:]:
            rel = f"exports/{export_file.name}"
            _copy_into_bundle(export_file, bundle_root, rel, included)
    else:
        missing.append("exports/latest_report")

    # Documentation
    doc_files = [
        (root / "README.md", "docs/README.md"),
        (root / "RELEASE_NOTES_LOCAL_V1_RC.md", "docs/RELEASE_NOTES_LOCAL_V1_RC.md"),
        (root / "RELEASE_NOTES_LOCAL_V1_GA.md", "docs/RELEASE_NOTES_LOCAL_V1_GA.md"),
        (root / "docs" / "demo" / "LOCAL_V1_WALKTHROUGH.md", "docs/LOCAL_V1_WALKTHROUGH.md"),
        (root / "CHANGELOG.md", "docs/CHANGELOG.md"),
    ]
    for src, rel in doc_files:
        require_copy(src, rel)

    # Bundle manifest
    bundle_manifest = {
        "bundle_name": BUNDLE_DIR_NAME,
        "version": __version__,
        "release_label": RELEASE_LABEL,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "included_files": sorted(included),
        "missing_optional": missing,
        "latest_run_id": latest_run.name if latest_run else None,
    }
    manifest_out = bundle_root / "bundle_manifest.json"
    manifest_out.write_text(json.dumps(bundle_manifest, indent=2), encoding="utf-8")
    included.append("bundle_manifest.json")

    # Zip archive
    zip_path = release_dir / f"{BUNDLE_DIR_NAME}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(bundle_root.rglob("*")):
            if file_path.is_file():
                arcname = f"{BUNDLE_DIR_NAME}/{file_path.relative_to(bundle_root)}"
                zf.write(file_path, arcname)

    return {
        "status": "ok",
        "bundle_dir": str(bundle_root),
        "bundle_zip": str(zip_path),
        "file_count": len(included),
        "included_files": sorted(included),
        "missing_optional": missing,
        "latest_run_id": latest_run.name if latest_run else None,
    }


def get_release_bundle_status(project_root: Path) -> dict:
    """Return bundle directory/zip presence for doctor and dashboard."""
    release_dir = project_root / "artifacts" / "release"
    bundle_dir = release_dir / BUNDLE_DIR_NAME
    bundle_zip = release_dir / f"{BUNDLE_DIR_NAME}.zip"
    if bundle_dir.is_dir() and bundle_zip.is_file():
        return {
            "status": "present",
            "bundle_dir": str(bundle_dir),
            "bundle_zip": str(bundle_zip),
            "bundle_name": BUNDLE_DIR_NAME,
        }
    if bundle_dir.is_dir() or bundle_zip.is_file():
        return {
            "status": "partial",
            "bundle_dir": str(bundle_dir) if bundle_dir.is_dir() else None,
            "bundle_zip": str(bundle_zip) if bundle_zip.is_file() else None,
            "bundle_name": BUNDLE_DIR_NAME,
        }

    legacy_dir = release_dir / BUNDLE_DIR_NAME_LEGACY
    legacy_zip = release_dir / f"{BUNDLE_DIR_NAME_LEGACY}.zip"
    if legacy_dir.is_dir() or legacy_zip.is_file():
        return {
            "status": "legacy",
            "bundle_dir": str(legacy_dir) if legacy_dir.is_dir() else None,
            "bundle_zip": str(legacy_zip) if legacy_zip.is_file() else None,
            "bundle_name": BUNDLE_DIR_NAME_LEGACY,
            "migration_warning": (
                f"Legacy bundle name '{BUNDLE_DIR_NAME_LEGACY}' detected. "
                f"Re-run 'sourcelab release bundle' to produce '{BUNDLE_DIR_NAME}'."
            ),
        }

    return {
        "status": "missing",
        "bundle_dir": str(bundle_dir),
        "bundle_zip": str(bundle_zip),
        "bundle_name": BUNDLE_DIR_NAME,
    }
