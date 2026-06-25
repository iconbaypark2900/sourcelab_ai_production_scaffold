"""Release publish dry-run planning for SourceLab Local v1.2."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sourcelab.release.artifact_names import ATTESTATION_FILENAME, MANIFEST_FILENAME, REPORT_FILENAME, SBOM_FILENAME
from sourcelab.release.bundle import BUNDLE_DIR_NAME
from sourcelab.release.signing import SIGNATURE_FILENAME, SIGNATURE_PLAN_FILENAME
from sourcelab.version import RELEASE_LABEL, __version__

PUBLISH_PLAN_FILENAME = "publish_plan.json"


def _release_dir(project_root: Path) -> Path:
    return project_root.resolve() / "artifacts" / "release"


def _release_notes_candidates(project_root: Path) -> list[Path]:
    root = project_root.resolve()
    candidates = [
        root / "RELEASE_NOTES_LOCAL_V1_GA.md",
        root / "RELEASE_NOTES_LOCAL_V1_RC.md",
        root / "CHANGELOG.md",
    ]
    return [p for p in candidates if p.is_file()]


def write_publish_plan(project_root: Path, dry_run: bool = True) -> dict:
    """Write a publish plan without uploading artifacts."""
    root = project_root.resolve()
    release_dir = _release_dir(root)
    release_dir.mkdir(parents=True, exist_ok=True)
    plan_path = release_dir / PUBLISH_PLAN_FILENAME

    bundle_zip = release_dir / f"{BUNDLE_DIR_NAME}.zip"
    checksums = release_dir / "SHA256SUMS"
    sbom = release_dir / SBOM_FILENAME
    attestation = release_dir / ATTESTATION_FILENAME
    signature = release_dir / SIGNATURE_FILENAME
    manifest = release_dir / MANIFEST_FILENAME
    report = release_dir / REPORT_FILENAME
    signature_plan = release_dir / SIGNATURE_PLAN_FILENAME

    release_notes = _release_notes_candidates(root)
    primary_notes = release_notes[0] if release_notes else None

    files_to_publish: list[dict] = []
    for path, role in (
        (bundle_zip, "bundle_zip"),
        (checksums, "checksums"),
        (sbom, "sbom"),
        (attestation, "attestation"),
        (signature, "signature"),
        (manifest, "release_manifest"),
        (report, "release_report"),
        (signature_plan, "signature_plan"),
    ):
        entry = {
            "role": role,
            "path": str(path),
            "present": path.is_file(),
        }
        if path.is_file():
            entry["size_bytes"] = path.stat().st_size
        files_to_publish.append(entry)

    for notes_path in release_notes:
        files_to_publish.append({
            "role": "release_notes",
            "path": str(notes_path),
            "present": True,
            "size_bytes": notes_path.stat().st_size,
        })

    warnings: list[str] = []
    if not bundle_zip.is_file():
        warnings.append("Bundle zip missing. Run 'sourcelab release bundle'.")
    if not checksums.is_file():
        warnings.append("SHA256SUMS missing. Run 'sourcelab release checksums'.")
    if not sbom.is_file():
        warnings.append("SBOM missing. Run 'sourcelab release sbom'.")
    if not attestation.is_file():
        warnings.append("Attestation missing. Run 'sourcelab release attest'.")
    if not signature.is_file():
        warnings.append("Signature missing (expected for unsigned/dry-run releases).")
    if not primary_notes:
        warnings.append("No release notes file found.")

    tag = f"local-v1-{__version__}"
    title = f"SourceLab Local {RELEASE_LABEL} ({__version__})"

    plan = {
        "version": __version__,
        "release_label": RELEASE_LABEL,
        "dry_run": dry_run,
        "upload_performed": False,
        "files_to_publish": files_to_publish,
        "bundle_zip": str(bundle_zip) if bundle_zip.is_file() else None,
        "sha256sums_path": str(checksums) if checksums.is_file() else None,
        "sbom_path": str(sbom) if sbom.is_file() else None,
        "attestation_path": str(attestation) if attestation.is_file() else None,
        "signature_path": str(signature) if signature.is_file() else None,
        "release_notes_paths": [str(p) for p in release_notes],
        "suggested_github_title": title,
        "suggested_github_tag": tag,
        "warnings": warnings,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    return {
        "status": "ok",
        "dry_run": dry_run,
        "publish_plan_path": str(plan_path),
        "warning_count": len(warnings),
        "warnings": warnings,
        "suggested_github_title": title,
        "suggested_github_tag": tag,
    }


def get_publish_plan_status(project_root: Path) -> dict:
    """Return publish plan status for doctor."""
    plan_path = _release_dir(project_root) / PUBLISH_PLAN_FILENAME
    if not plan_path.is_file():
        return {"status": "missing", "path": str(plan_path)}
    try:
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        return {
            "status": "present",
            "path": str(plan_path),
            "warning_count": len(data.get("warnings", [])),
            "dry_run": data.get("dry_run", True),
        }
    except (json.JSONDecodeError, OSError) as exc:
        return {"status": "invalid", "path": str(plan_path), "error": str(exc)}
