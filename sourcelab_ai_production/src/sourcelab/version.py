"""SourceLab version and release metadata."""

from __future__ import annotations

import sys
from pathlib import Path

__version__ = "1.0.2"
RELEASE_LABEL = "SourceLab Local v1.0.2"


def get_artifacts_dir(project_root: Path | None = None) -> Path:
    """Return the artifacts directory for the project."""
    root = project_root or Path.cwd()
    return root / "artifacts"


def version_info(project_root: Path | None = None) -> dict[str, str]:
    """Return version metadata shared by CLI and API."""
    root = project_root or Path.cwd()
    artifacts_dir = get_artifacts_dir(root)
    return {
        "version": __version__,
        "release_label": RELEASE_LABEL,
        "python_version": sys.version.split()[0],
        "project_root": str(root.resolve()),
        "artifacts_directory": str(artifacts_dir.resolve()),
        "api_version": "v1",
    }
