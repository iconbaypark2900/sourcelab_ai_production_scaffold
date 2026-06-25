"""Environment and readiness checks for SourceLab Local v1."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

from sourcelab.version import RELEASE_LABEL, __version__, get_artifacts_dir, version_info

OPTIONAL_EXTRAS = ("api", "ui", "ingest", "retrieval", "models")
DEPENDENCY_LOCK_REL_PATH = Path("requirements") / "lock-local-v1.txt"


def _extra_installed(extra: str) -> bool:
    """Return True when an optional extra appears importable."""
    checks: dict[str, tuple[str, ...]] = {
        "api": ("fastapi", "uvicorn"),
        "ui": ("streamlit",),
        "ingest": ("pypdf", "bs4", "requests"),
        "retrieval": ("sentence_transformers", "faiss"),
        "models": ("httpx",),
    }
    modules = checks.get(extra, ())
    return all(importlib.util.find_spec(module) is not None for module in modules)


def _check_writable(path: Path) -> bool:
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _manifest_status(project_root: Path) -> dict:
    manifest_path = project_root / "artifacts" / "release" / "local_v1_release_manifest.json"
    if not manifest_path.exists():
        return {"status": "missing", "path": str(manifest_path)}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {
            "status": "present",
            "path": str(manifest_path),
            "version": data.get("version", "unknown"),
            "strict_release_status": data.get("strict_release_status", "unknown"),
            "golden_eval_status": data.get("golden_eval_status", "unknown"),
        }
    except (json.JSONDecodeError, OSError) as exc:
        return {"status": "invalid", "path": str(manifest_path), "error": str(exc)}


def _golden_eval_status(project_root: Path) -> dict:
    evals_dir = project_root / "artifacts" / "evals"
    if not evals_dir.exists():
        return {"status": "missing", "message": "no eval artifacts"}
    for pack_dir in sorted(evals_dir.iterdir()):
        if not pack_dir.is_dir():
            continue
        summary_path = pack_dir / "golden_eval_summary.json"
        if not summary_path.exists():
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            rate = summary.get("overall_pass_rate", 0)
            return {
                "status": "PASS" if rate >= 0.8 else "FAIL",
                "pack": pack_dir.name,
                "pass_rate": rate,
                "total_passed": summary.get("total_passed", 0),
                "total_cases": summary.get("total_cases", 0),
            }
        except (json.JSONDecodeError, OSError):
            continue
    return {"status": "missing", "message": "no golden eval summary found"}


def _recommended_next_command(
    root: Path,
    manifest: dict,
    bundle_status: dict,
    golden_eval: dict,
) -> str:
    if manifest.get("status") != "present":
        return "sourcelab local-demo"
    if manifest.get("strict_release_status") != "PASS":
        return "sourcelab verify-release --strict"
    if golden_eval.get("status") not in {"PASS", "unknown"}:
        return "sourcelab evals run --pack pqc_v1"
    if bundle_status.get("status") != "present":
        return "sourcelab release bundle"
    return "make ga-check"


def get_optional_extras_status() -> dict[str, bool]:
    """Return install status for optional package extras."""
    return {extra: _extra_installed(extra) for extra in OPTIONAL_EXTRAS}


def _lock_drift_status(project_root: Path) -> dict:
    """Compare committed lock file to generated content (ignoring header lines)."""
    lock_path = project_root / DEPENDENCY_LOCK_REL_PATH
    if not lock_path.is_file():
        return {"status": "missing", "path": str(lock_path), "drift_detected": True}

    try:
        import subprocess

        result = subprocess.run(
            ["bash", "scripts/freeze_requirements.sh", "--check"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            check=False,
        )
        drift_detected = result.returncode != 0
        return {
            "status": "drift" if drift_detected else "ok",
            "path": str(lock_path),
            "drift_detected": drift_detected,
            "message": (result.stderr or result.stdout or "").strip() or None,
        }
    except OSError as exc:
        return {
            "status": "unknown",
            "path": str(lock_path),
            "drift_detected": None,
            "error": str(exc),
        }


def _multi_pack_status(project_root: Path) -> dict:
    from sourcelab.sources.source_pack import list_source_packs

    packs = [
        p["pack_name"]
        for p in list_source_packs(project_root)
        if p.get("pack_name") not in {"TEMPLATE"}
    ]
    evals_dir = project_root / "artifacts" / "evals"
    evaluated = []
    if evals_dir.exists():
        for pack_name in packs:
            summary = evals_dir / pack_name / "golden_eval_summary.json"
            if summary.is_file():
                evaluated.append(pack_name)
    all_packs_summary = evals_dir / "all_packs" / "golden_eval_summary.json"
    return {
        "available_packs": packs,
        "evaluated_packs": evaluated,
        "all_packs_summary_present": all_packs_summary.is_file(),
        "all_packs_summary_path": str(all_packs_summary) if all_packs_summary.is_file() else None,
    }


def _artifact_file_status(project_root: Path, rel_path: str) -> dict:
    path = project_root / rel_path
    if not path.is_file():
        return {"status": "missing", "path": str(path)}
    return {"status": "present", "path": str(path)}


def run_doctor(project_root: Path | None = None) -> dict:
    """Run local environment readiness checks and return JSON-serializable report."""
    root = (project_root or Path.cwd()).resolve()
    artifacts_dir = get_artifacts_dir(root)
    registry_path = root / "data" / "source_registry.json"
    pqc_pack_dir = root / "data" / "source_packs" / "pqc_v1"

    checks: list[dict] = []

    py_ok = sys.version_info >= (3, 10)
    checks.append(
        {
            "name": "python_version",
            "passed": py_ok,
            "message": f"Python {sys.version.split()[0]}",
        }
    )

    package_ok = importlib.util.find_spec("sourcelab") is not None
    checks.append(
        {
            "name": "package_import",
            "passed": package_ok,
            "message": f"sourcelab {__version__}" if package_ok else "sourcelab not importable",
        }
    )

    checks.append(
        {
            "name": "project_root",
            "passed": (root / "pyproject.toml").exists(),
            "message": str(root),
        }
    )

    writable = _check_writable(artifacts_dir)
    checks.append(
        {
            "name": "artifacts_directory_writable",
            "passed": writable,
            "message": str(artifacts_dir),
        }
    )

    registry_ok = registry_path.exists()
    checks.append(
        {
            "name": "source_registry",
            "passed": registry_ok,
            "message": str(registry_path) if registry_ok else "source registry missing",
        }
    )

    pqc_ok = pqc_pack_dir.exists() and (pqc_pack_dir / "manifest.json").exists()
    checks.append(
        {
            "name": "pqc_source_pack",
            "passed": pqc_ok,
            "message": str(pqc_pack_dir) if pqc_ok else "pqc_v1 pack missing",
        }
    )

    extras_status = {extra: _extra_installed(extra) for extra in OPTIONAL_EXTRAS}
    checks.append(
        {
            "name": "optional_extras",
            "passed": extras_status.get("api", False) and extras_status.get("ui", False),
            "message": "optional extras status",
            "details": extras_status,
        }
    )

    docker_available = shutil.which("docker") is not None
    checks.append(
        {
            "name": "docker_available",
            "passed": docker_available,
            "message": "docker CLI available" if docker_available else "docker not found in PATH",
        }
    )

    make_available = shutil.which("make") is not None
    checks.append(
        {
            "name": "make_available",
            "passed": make_available,
            "message": "make available" if make_available else "make not found in PATH",
        }
    )

    dashboard_available = shutil.which("streamlit") is not None and extras_status.get("ui", False)
    checks.append(
        {
            "name": "dashboard_launch",
            "passed": dashboard_available,
            "message": "streamlit available" if dashboard_available else "install ui extra: pip install -e '.[ui]'",
        }
    )

    api_available = extras_status.get("api", False)
    checks.append(
        {
            "name": "api_launch",
            "passed": api_available,
            "message": "fastapi/uvicorn available" if api_available else "install api extra: pip install -e '.[api]'",
        }
    )

    try:
        from sourcelab.models.config import get_model_config

        model_config = get_model_config()
        model_status = {
            "mode": model_config.mode,
            "backend": model_config.backend,
            "model_name": model_config.model_name or "(default)",
            "base_url": model_config.base_url or "(none)",
        }
        checks.append(
            {
                "name": "local_model_config",
                "passed": True,
                "message": f"{model_config.mode}/{model_config.backend}",
                "details": model_status,
            }
        )
    except Exception as exc:
        model_status = {}
        checks.append(
            {
                "name": "local_model_config",
                "passed": False,
                "message": str(exc),
            }
        )

    manifest = _manifest_status(root)
    checks.append(
        {
            "name": "release_manifest",
            "passed": manifest.get("status") == "present",
            "message": manifest.get("status", "unknown"),
            "details": manifest,
        }
    )

    from sourcelab.release.bundle import get_release_bundle_status

    bundle_status = get_release_bundle_status(root)
    checks.append(
        {
            "name": "release_bundle",
            "passed": bundle_status.get("status") == "present",
            "message": bundle_status.get("status", "unknown"),
            "details": bundle_status,
        }
    )

    strict_release_status = manifest.get("strict_release_status", "unknown")
    checks.append(
        {
            "name": "strict_release_status",
            "passed": strict_release_status == "PASS",
            "message": strict_release_status,
        }
    )

    golden_eval = _golden_eval_status(root)
    checks.append(
        {
            "name": "golden_eval_status",
            "passed": golden_eval.get("status") in {"PASS", "unknown"},
            "message": golden_eval.get("status", "unknown"),
            "details": golden_eval,
        }
    )

    dependency_lock_path = root / DEPENDENCY_LOCK_REL_PATH
    dependency_lock_exists = dependency_lock_path.is_file()
    lock_drift = _lock_drift_status(root)
    checks.append(
        {
            "name": "dependency_lock",
            "passed": dependency_lock_exists,
            "message": "present" if dependency_lock_exists else "missing",
            "details": {
                "dependency_lock_exists": dependency_lock_exists,
                "dependency_lock_path": str(dependency_lock_path),
            },
        }
    )
    checks.append(
        {
            "name": "dependency_lock_drift",
            "passed": lock_drift.get("drift_detected") is False,
            "message": lock_drift.get("status", "unknown"),
            "details": lock_drift,
        }
    )

    from sourcelab.release.signing import get_signature_status
    from sourcelab.release.publish import get_publish_plan_status
    from sourcelab.release.artifact_names import ATTESTATION_FILENAME, SBOM_FILENAME

    signature_status = get_signature_status(root)
    publish_status = get_publish_plan_status(root)
    sbom_status = _artifact_file_status(root, f"artifacts/release/{SBOM_FILENAME}")
    attestation_status = _artifact_file_status(root, f"artifacts/release/{ATTESTATION_FILENAME}")
    multi_pack = _multi_pack_status(root)

    checks.extend([
        {
            "name": "signature_plan_status",
            "passed": signature_status.get("signature_plan_status") == "present",
            "message": signature_status.get("signature_plan_status", "missing"),
            "details": signature_status,
        },
        {
            "name": "signature_verification_status",
            "passed": signature_status.get("signature_verification_status") in {"present", "unsigned", "verified"},
            "message": signature_status.get("signature_verification_status", "missing"),
            "details": signature_status,
        },
        {
            "name": "publish_plan_status",
            "passed": publish_status.get("status") == "present",
            "message": publish_status.get("status", "missing"),
            "details": publish_status,
        },
        {
            "name": "sbom_status",
            "passed": sbom_status.get("status") == "present",
            "message": sbom_status.get("status", "missing"),
            "details": sbom_status,
        },
        {
            "name": "attestation_status",
            "passed": attestation_status.get("status") == "present",
            "message": attestation_status.get("status", "missing"),
            "details": attestation_status,
        },
        {
            "name": "multi_pack_status",
            "passed": len(multi_pack.get("available_packs", [])) >= 1,
            "message": f"{len(multi_pack.get('evaluated_packs', []))}/{len(multi_pack.get('available_packs', []))} packs evaluated",
            "details": multi_pack,
        },
    ])

    recommended_next_command = _recommended_next_command(root, manifest, bundle_status, golden_eval)

    blocking = [c for c in checks if not c["passed"] and c["name"] in {
        "python_version",
        "package_import",
        "project_root",
        "artifacts_directory_writable",
        "pqc_source_pack",
    }]
    status = "PASS" if not blocking else "FAIL"

    return {
        "status": status,
        "release_label": RELEASE_LABEL,
        "version": __version__,
        **version_info(root),
        "checks": checks,
        "optional_extras": extras_status,
        "release_manifest": manifest,
        "release_bundle": bundle_status,
        "strict_release_status": strict_release_status,
        "golden_eval_status": golden_eval.get("status", "unknown"),
        "golden_eval": golden_eval,
        "docker_available": docker_available,
        "make_available": make_available,
        "dashboard_available": dashboard_available,
        "api_available": api_available,
        "model_backend_mode": model_status.get("mode", "unknown") if model_status else "unknown",
        "recommended_next_command": recommended_next_command,
        "dependency_lock_exists": dependency_lock_exists,
        "dependency_lock_path": str(dependency_lock_path),
        "dependency_lock_drift": lock_drift,
        "signature_status": signature_status,
        "publish_plan_status": publish_status,
        "sbom_status": sbom_status,
        "attestation_status": attestation_status,
        "multi_pack_status": multi_pack,
        "blocking": [c["name"] for c in blocking],
    }
