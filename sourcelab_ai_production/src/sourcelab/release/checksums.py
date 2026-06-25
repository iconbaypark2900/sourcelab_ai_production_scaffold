"""SHA256 checksum generation for release artifacts."""

from __future__ import annotations

from pathlib import Path

from sourcelab.release.artifact_names import (
    ATTESTATION_FILENAME,
    MANIFEST_FILENAME,
    REPORT_FILENAME,
    SBOM_FILENAME,
)
from sourcelab.release.bundle import BUNDLE_DIR_NAME
from sourcelab.release.hash_util import sha256_file


def write_release_checksums(project_root: Path) -> dict:
    """Write SHA256SUMS for release bundle and related release artifacts."""
    root = project_root.resolve()
    release_dir = root / "artifacts" / "release"
    release_dir.mkdir(parents=True, exist_ok=True)

    bundle_dir = release_dir / BUNDLE_DIR_NAME
    bundle_zip = release_dir / f"{BUNDLE_DIR_NAME}.zip"
    sums_path = release_dir / "SHA256SUMS"

    entries: list[tuple[str, str]] = []

    if bundle_dir.is_dir():
        for file_path in sorted(bundle_dir.rglob("*")):
            if file_path.is_file():
                rel = file_path.relative_to(release_dir)
                entries.append((sha256_file(file_path), str(rel)))

    if bundle_zip.is_file():
        rel = bundle_zip.relative_to(release_dir)
        entries.append((sha256_file(bundle_zip), str(rel)))

    for filename in (MANIFEST_FILENAME, REPORT_FILENAME, SBOM_FILENAME, ATTESTATION_FILENAME):
        artifact_path = release_dir / filename
        if artifact_path.is_file():
            rel = artifact_path.relative_to(release_dir)
            entries.append((sha256_file(artifact_path), str(rel)))

    lines = [f"{digest}  {name}" for digest, name in entries]
    sums_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    return {
        "status": "ok" if entries else "empty",
        "checksums_path": str(sums_path),
        "entry_count": len(entries),
        "entries": [{"sha256": d, "path": n} for d, n in entries],
    }
