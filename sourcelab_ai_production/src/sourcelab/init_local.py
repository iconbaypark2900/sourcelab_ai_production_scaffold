"""First-run setup for SourceLab Local v1."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sourcelab.learning.schemas import SkillProfileV2
from sourcelab.learning.skill_profile import save_profile
from sourcelab.sources.registry import SourceRegistry
from sourcelab.sources.source_pack import install_source_pack, source_pack_status, validate_source_pack
from sourcelab.version import RELEASE_LABEL, __version__, get_artifacts_dir


def _ensure_registry(project_root: Path) -> Path:
    registry_path = project_root / "data" / "source_registry.json"
    if registry_path.exists():
        return registry_path

    registry_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [],
    }
    registry_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return registry_path


def _ensure_example_profile(project_root: Path) -> Path:
    profile = SkillProfileV2(user_id="local_user")
    return save_profile(profile, project_root=project_root)


def run_init_local(project_root: Path | None = None) -> dict:
    """Idempotent first-run setup for SourceLab Local v1."""
    root = (project_root or Path.cwd()).resolve()
    steps: list[dict] = []

    artifact_dirs = [
        get_artifacts_dir(root),
        root / "artifacts" / "runs",
        root / "artifacts" / "evals",
        root / "artifacts" / "release",
        root / "artifacts" / "profiles",
        root / "artifacts" / "index",
    ]
    for directory in artifact_dirs:
        directory.mkdir(parents=True, exist_ok=True)
    steps.append({"step": "create_artifact_directories", "passed": True, "count": len(artifact_dirs)})

    approved_sources = root / "data" / "approved_sources"
    approved_sources.mkdir(parents=True, exist_ok=True)
    steps.append({"step": "create_approved_sources", "passed": True, "path": str(approved_sources)})

    registry_path = _ensure_registry(root)
    steps.append({"step": "ensure_source_registry", "passed": registry_path.exists(), "path": str(registry_path)})

    pack_validation = validate_source_pack(root, "pqc_v1")
    steps.append(
        {
            "step": "validate_pqc_source_pack",
            "passed": pack_validation.get("valid", False),
            "details": pack_validation,
        }
    )

    pack_status = source_pack_status(root, "pqc_v1")
    if not pack_status.get("installed"):
        install_result = install_source_pack(root, "pqc_v1")
        steps.append(
            {
                "step": "install_pqc_source_pack",
                "passed": install_result.get("success", False),
                "details": install_result,
            }
        )
    else:
        steps.append(
            {
                "step": "install_pqc_source_pack",
                "passed": True,
                "message": "already installed",
                "details": pack_status,
            }
        )

    profile_path = _ensure_example_profile(root)
    steps.append({"step": "create_example_profile", "passed": profile_path.exists(), "path": str(profile_path)})

    try:
        registry = SourceRegistry.load_from_json(registry_path)
        validation_errors = registry.validate()
        steps.append(
            {
                "step": "validate_sources",
                "passed": not validation_errors,
                "source_count": len(registry.sources),
                "errors": validation_errors,
            }
        )
    except Exception as exc:
        steps.append({"step": "validate_sources", "passed": False, "error": str(exc)})

    passed = all(step.get("passed", False) for step in steps)
    next_commands = [
        "sourcelab doctor",
        "sourcelab local-demo",
        "sourcelab verify-release --strict",
        "sourcelab dashboard --launch",
        "sourcelab api --serve",
    ]

    return {
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "version": __version__,
        "release_label": RELEASE_LABEL,
        "project_root": str(root),
        "artifacts_directory": str(get_artifacts_dir(root)),
        "steps": steps,
        "next_commands": next_commands,
    }
