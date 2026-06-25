"""Signature-ready release attestation for SourceLab Local v1."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sourcelab.release.artifact_names import ATTESTATION_FILENAME, SBOM_FILENAME
from sourcelab.release.bundle import BUNDLE_DIR_NAME, get_release_bundle_status
from sourcelab.release.hash_util import sha256_file
from sourcelab.release.signing import get_signature_status
from sourcelab.version import RELEASE_LABEL, __version__

DEPENDENCY_LOCK_REL_PATH = Path("requirements") / "lock-local-v1.txt"
CI_WORKFLOW_REL_PATH = Path(".github") / "workflows" / "local-v1-release.yml"


def _read_manifest_field(project_root: Path, field: str, default: object = None) -> object:
    manifest_path = project_root / "artifacts" / "release" / "local_v1_release_manifest.json"
    if not manifest_path.exists():
        return default
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return data.get(field, default)
    except (json.JSONDecodeError, OSError):
        return default


def _source_pack_summary(project_root: Path) -> list[dict]:
    from sourcelab.sources.source_pack import list_source_packs, source_pack_status

    summary = []
    for pack in list_source_packs(project_root):
        pack_name = pack.get("pack_name", "")
        if pack_name == "TEMPLATE":
            continue
        status = source_pack_status(project_root, pack_name)
        summary.append({
            "pack_name": pack_name,
            "version": pack.get("version"),
            "source_count": pack.get("source_count", 0),
            "eval_count": pack.get("eval_count", 0),
            "installed": status.get("installed", False),
            "installed_count": status.get("installed_count", 0),
        })
    return summary


def _golden_eval_summary_path(project_root: Path) -> str | None:
    evals_dir = project_root / "artifacts" / "evals"
    pqc_summary = evals_dir / "pqc_v1" / "golden_eval_summary.json"
    if pqc_summary.is_file():
        return str(pqc_summary)
    all_packs_summary = evals_dir / "all_packs" / "golden_eval_summary.json"
    if all_packs_summary.is_file():
        return str(all_packs_summary)
    if evals_dir.exists():
        for pack_dir in sorted(evals_dir.iterdir()):
            if not pack_dir.is_dir():
                continue
            candidate = pack_dir / "golden_eval_summary.json"
            if candidate.is_file():
                return str(candidate)
    return None


def write_release_attestation(project_root: Path) -> dict:
    """Write an unsigned release attestation JSON artifact."""
    root = project_root.resolve()
    release_dir = root / "artifacts" / "release"
    release_dir.mkdir(parents=True, exist_ok=True)
    attestation_path = release_dir / ATTESTATION_FILENAME

    bundle_status = get_release_bundle_status(root)
    bundle_zip_path = release_dir / f"{BUNDLE_DIR_NAME}.zip"
    checksums_path = release_dir / "SHA256SUMS"
    sbom_path = release_dir / SBOM_FILENAME

    bundle_sha256: str | None = None
    bundle_zip_sha256: str | None = None
    if bundle_zip_path.is_file():
        bundle_sha256 = sha256_file(bundle_zip_path)
        bundle_zip_sha256 = bundle_sha256

    checksums_sha256: str | None = None
    if checksums_path.is_file():
        checksums_sha256 = sha256_file(checksums_path)

    sbom_sha256: str | None = None
    if sbom_path.is_file():
        sbom_sha256 = sha256_file(sbom_path)

    signature_info = get_signature_status(root)
    signature_status = signature_info.get("signature_verification_status", "missing")
    unsigned = True
    unsigned_reason = "Release signing not performed (dry-run default)."
    if signature_info.get("signature_file_present"):
        unsigned = False
        unsigned_reason = None
    elif signature_info.get("signature_plan_status") == "present":
        plan_path = signature_info.get("signature_plan_path")
        if plan_path:
            try:
                plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
                if plan.get("sign_error"):
                    unsigned_reason = plan["sign_error"]
            except (json.JSONDecodeError, OSError):
                pass

    golden_eval_pass_rate = _read_manifest_field(root, "golden_eval_pass_rate")
    test_status = _read_manifest_field(root, "pytest_status")
    if test_status is None:
        test_count = _read_manifest_field(root, "test_count", 0)
        test_status = "available" if test_count else "unknown"

    lock_file_path = root / DEPENDENCY_LOCK_REL_PATH
    ci_workflow_path = root / CI_WORKFLOW_REL_PATH

    attestation = {
        "version": __version__,
        "release_label": RELEASE_LABEL,
        "bundle_path": bundle_status.get("bundle_zip") or str(bundle_zip_path),
        "bundle_sha256": bundle_sha256,
        "bundle_zip_sha256": bundle_zip_sha256,
        "checksum_file_path": str(checksums_path) if checksums_path.exists() else None,
        "checksums_sha256": checksums_sha256,
        "sbom_path": str(sbom_path) if sbom_path.exists() else None,
        "sbom_sha256": sbom_sha256,
        "source_pack_summary": _source_pack_summary(root),
        "golden_eval_summary_path": _golden_eval_summary_path(root),
        "ci_workflow_path": str(ci_workflow_path) if ci_workflow_path.exists() else None,
        "lock_file_path": str(lock_file_path) if lock_file_path.exists() else None,
        "signature_status": signature_status,
        "unsigned_reason": unsigned_reason,
        "strict_release_status": _read_manifest_field(root, "strict_release_status", "unknown"),
        "golden_eval_pass_rate": golden_eval_pass_rate,
        "test_status": test_status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "unsigned": unsigned,
    }
    attestation_path.write_text(json.dumps(attestation, indent=2), encoding="utf-8")

    return {
        "status": "ok",
        "attestation_path": str(attestation_path),
        "unsigned": unsigned,
        "bundle_sha256": bundle_sha256,
        "checksums_sha256": checksums_sha256,
        "sbom_sha256": sbom_sha256,
    }
