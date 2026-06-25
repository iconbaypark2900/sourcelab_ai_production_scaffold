"""Optional release artifact signing for SourceLab Local v1.2."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sourcelab.release.artifact_names import ATTESTATION_FILENAME, SBOM_FILENAME
from sourcelab.release.bundle import BUNDLE_DIR_NAME, get_release_bundle_status
from sourcelab.version import RELEASE_LABEL, __version__

SIGNATURE_PLAN_FILENAME = "signature_plan.json"
SIGNATURE_FILENAME = "SHA256SUMS.sig"
VERIFICATION_FILENAME = "signature_verification.json"
CHECKSUMS_FILENAME = "SHA256SUMS"


def _release_dir(project_root: Path) -> Path:
    return project_root.resolve() / "artifacts" / "release"


def _artifact_paths(project_root: Path) -> dict[str, str | None]:
    root = project_root.resolve()
    release_dir = _release_dir(root)
    bundle_status = get_release_bundle_status(root)
    bundle_zip = release_dir / f"{BUNDLE_DIR_NAME}.zip"
    checksums = release_dir / CHECKSUMS_FILENAME
    attestation = release_dir / ATTESTATION_FILENAME
    sbom = release_dir / SBOM_FILENAME
    return {
        "bundle_path": bundle_status.get("bundle_zip") or (str(bundle_zip) if bundle_zip.is_file() else None),
        "checksum_path": str(checksums) if checksums.is_file() else None,
        "attestation_path": str(attestation) if attestation.is_file() else None,
        "sbom_path": str(sbom) if sbom.is_file() else None,
    }


def _gpg_available() -> bool:
    return shutil.which("gpg") is not None


def _gpg_sign_command(checksums_path: Path, key_id: str | None) -> list[str]:
    cmd = ["gpg", "--detach-sign", "--armor", "--output", str(checksums_path.with_suffix(checksums_path.suffix + ".sig"))]
    if key_id:
        cmd.extend(["--local-user", key_id])
    cmd.append(str(checksums_path))
    return cmd


def write_signature_plan(
    project_root: Path,
    mode: str = "dry-run",
    key_id: str | None = None,
) -> dict:
    """Write a signature plan or perform optional GPG signing."""
    root = project_root.resolve()
    release_dir = _release_dir(root)
    release_dir.mkdir(parents=True, exist_ok=True)

    artifacts = _artifact_paths(root)
    checksums_path = release_dir / CHECKSUMS_FILENAME
    signature_path = release_dir / SIGNATURE_FILENAME
    plan_path = release_dir / SIGNATURE_PLAN_FILENAME

    required_tool = "gpg" if mode == "gpg" else None
    would_run = None
    if mode == "gpg" and checksums_path.is_file():
        would_run = " ".join(_gpg_sign_command(checksums_path, key_id))

    plan = {
        "version": __version__,
        "release_label": RELEASE_LABEL,
        "release_version": __version__,
        "bundle_path": artifacts["bundle_path"],
        "checksum_path": artifacts["checksum_path"],
        "attestation_path": artifacts["attestation_path"],
        "sbom_path": artifacts["sbom_path"],
        "signing_mode": mode,
        "required_external_tool": required_tool,
        "command_that_would_run": would_run,
        "unsigned": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    signed = False
    sign_error: str | None = None

    if mode == "gpg":
        if not checksums_path.is_file():
            sign_error = f"Checksums file missing: {checksums_path}. Run 'sourcelab release checksums' first."
        elif not _gpg_available():
            sign_error = "gpg not found in PATH; install GPG or use --mode dry-run."
        else:
            try:
                cmd = _gpg_sign_command(checksums_path, key_id)
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                if signature_path.is_file():
                    plan["unsigned"] = False
                    signed = True
                else:
                    sign_error = "GPG signing completed but signature file was not created."
            except subprocess.CalledProcessError as exc:
                stderr = (exc.stderr or exc.stdout or str(exc)).strip()
                sign_error = f"GPG signing failed: {stderr or 'unknown error'}"

    if sign_error:
        plan["sign_error"] = sign_error

    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    return {
        "status": "ok" if not sign_error else "error",
        "signing_mode": mode,
        "unsigned": not signed,
        "signed": signed,
        "signature_plan_path": str(plan_path),
        "signature_path": str(signature_path) if signature_path.is_file() else None,
        "error": sign_error,
        "plan": plan,
    }


def verify_release_signature(project_root: Path) -> dict:
    """Verify release signature or record unsigned status."""
    root = project_root.resolve()
    release_dir = _release_dir(root)
    release_dir.mkdir(parents=True, exist_ok=True)

    checksums_path = release_dir / CHECKSUMS_FILENAME
    signature_path = release_dir / SIGNATURE_FILENAME
    plan_path = release_dir / SIGNATURE_PLAN_FILENAME
    verification_path = release_dir / VERIFICATION_FILENAME

    plan: dict | None = None
    if plan_path.is_file():
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            plan = None

    verification: dict = {
        "version": __version__,
        "release_label": RELEASE_LABEL,
        "checksum_path": str(checksums_path) if checksums_path.is_file() else None,
        "signature_path": str(signature_path) if signature_path.is_file() else None,
        "signature_plan_path": str(plan_path) if plan_path.is_file() else None,
        "unsigned": True,
        "verified": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if not checksums_path.is_file():
        verification["status"] = "missing_checksums"
        verification["message"] = "SHA256SUMS not found. Run 'sourcelab release checksums' first."
    elif not signature_path.is_file():
        verification["status"] = "unsigned"
        verification["message"] = "No signature file present (expected for dry-run or unsigned releases)."
        if plan and plan.get("sign_error"):
            verification["unsigned_reason"] = plan["sign_error"]
        else:
            verification["unsigned_reason"] = "Release was not signed (dry-run or GPG unavailable)."
    elif not _gpg_available():
        verification["status"] = "error"
        verification["message"] = "Signature file present but gpg not available for verification."
        verification["unsigned_reason"] = "gpg not found in PATH"
    else:
        try:
            result = subprocess.run(
                ["gpg", "--verify", str(signature_path), str(checksums_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                verification["status"] = "verified"
                verification["verified"] = True
                verification["unsigned"] = False
                verification["message"] = "Signature verified successfully."
            else:
                verification["status"] = "invalid"
                verification["message"] = (result.stderr or result.stdout or "GPG verification failed").strip()
                verification["unsigned_reason"] = verification["message"]
        except OSError as exc:
            verification["status"] = "error"
            verification["message"] = str(exc)
            verification["unsigned_reason"] = str(exc)

    verification_path.write_text(json.dumps(verification, indent=2), encoding="utf-8")

    return {
        "status": verification.get("status", "unknown"),
        "verified": verification["verified"],
        "unsigned": verification["unsigned"],
        "verification_path": str(verification_path),
        "verification": verification,
    }


def get_signature_status(project_root: Path) -> dict:
    """Return signature plan and verification status for doctor."""
    root = project_root.resolve()
    release_dir = _release_dir(root)
    plan_path = release_dir / SIGNATURE_PLAN_FILENAME
    verification_path = release_dir / VERIFICATION_FILENAME
    signature_path = release_dir / SIGNATURE_FILENAME

    plan_status = "missing"
    if plan_path.is_file():
        plan_status = "present"

    verification_status = "missing"
    if verification_path.is_file():
        try:
            data = json.loads(verification_path.read_text(encoding="utf-8"))
            verification_status = data.get("status", "present")
        except (json.JSONDecodeError, OSError):
            verification_status = "invalid"

    return {
        "signature_plan_status": plan_status,
        "signature_plan_path": str(plan_path) if plan_path.is_file() else None,
        "signature_verification_status": verification_status,
        "signature_verification_path": str(verification_path) if verification_path.is_file() else None,
        "signature_file_present": signature_path.is_file(),
        "signature_path": str(signature_path) if signature_path.is_file() else None,
    }
