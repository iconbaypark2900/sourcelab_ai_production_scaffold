"""Lightweight SBOM export for SourceLab Local v1 release artifacts."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from sourcelab.release.artifact_names import SBOM_FILENAME
from sourcelab.version import __version__
PROJECT_DIST_NAME = "sourcelab-ai"


def _collect_installed_packages() -> list[dict[str, str]]:
    packages: list[dict[str, str]] = []
    for dist in sorted(metadata.distributions(), key=lambda d: (d.metadata.get("Name") or "").lower()):
        name = dist.metadata.get("Name")
        if not name:
            continue
        packages.append({"name": name, "version": dist.version})
    return packages


def write_release_sbom(project_root: Path) -> dict:
    """Write a lightweight SBOM JSON from the active Python environment."""
    root = project_root.resolve()
    release_dir = root / "artifacts" / "release"
    release_dir.mkdir(parents=True, exist_ok=True)
    sbom_path = release_dir / SBOM_FILENAME

    try:
        project_dist = metadata.distribution(PROJECT_DIST_NAME)
        project_name = project_dist.metadata.get("Name", PROJECT_DIST_NAME)
        project_version = project_dist.version
    except metadata.PackageNotFoundError as exc:
        return {
            "status": "error",
            "sbom_path": str(sbom_path),
            "error": (
                f"Could not read installed package metadata for '{PROJECT_DIST_NAME}'. "
                "Install the project in editable mode first: pip install -e '.[dev,api,ui,ingest,retrieval,models]'"
            ),
            "detail": str(exc),
        }
    except Exception as exc:
        return {
            "status": "error",
            "sbom_path": str(sbom_path),
            "error": "Installed package metadata is unreadable.",
            "detail": str(exc),
        }

    sbom = {
        "name": project_name,
        "version": project_version,
        "source": "python environment",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_version": __version__,
        "python_version": sys.version.split()[0],
        "packages": _collect_installed_packages(),
    }
    sbom_path.write_text(json.dumps(sbom, indent=2), encoding="utf-8")

    return {
        "status": "ok",
        "sbom_path": str(sbom_path),
        "package_count": len(sbom["packages"]),
        "project_version": __version__,
    }
