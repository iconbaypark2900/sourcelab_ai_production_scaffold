"""Filesystem layout helpers for the SourceLab library pipeline."""

from __future__ import annotations

from pathlib import Path

RAW_ORIGINS = (
    "local_docs",
    "arxiv",
    "pubmed",
    "nvd",
    "sec",
    "nasa",
    "govinfo",
    "github",
)

SILVER_SUBDIRS = ("source_cards", "chunks", "manifests", "dedupe", "quality")
PROMOTION_SUBDIRS = ("candidates", "reports")


def library_root(project_root: Path) -> Path:
    return project_root / "data" / "library"


def ensure_library_layout(project_root: Path) -> Path:
    """Create library directory tree with .gitkeep placeholders."""
    root = library_root(project_root)
    for origin in RAW_ORIGINS:
        _ensure_dir(root / "raw" / origin)
    for sub in SILVER_SUBDIRS:
        _ensure_dir(root / "silver" / sub)
    for sub in PROMOTION_SUBDIRS:
        _ensure_dir(root / "promotion" / sub)
    return root


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    gitkeep = path / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("", encoding="utf-8")
