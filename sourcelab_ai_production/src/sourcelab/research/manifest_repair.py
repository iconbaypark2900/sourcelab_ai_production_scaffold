"""Safe manifest repair hook for guided gap-closure orchestration."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_manifest_repair(project_root: Path) -> tuple[list[str], int, str]:
    """Run bootstrap manifest repair without overwriting source markdown bodies."""
    script = project_root / "scripts" / "bootstrap_sourcelab_source_packs.py"
    if not script.exists():
        return [f"bootstrap script not found: {script}"], 1, ""

    result = subprocess.run(
        [sys.executable, str(script), "--repair-manifests"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [line for line in (result.stdout or "").splitlines() if line.strip()]
    if result.stderr:
        lines.extend(line for line in result.stderr.splitlines() if line.strip())
    combined = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    return lines, result.returncode, combined.strip()
