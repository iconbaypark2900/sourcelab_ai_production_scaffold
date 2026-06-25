"""Local documentation collector for the SourceLab library pipeline."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from sourcelab.library.io import save_json, sha256_text, utc_now
from sourcelab.library.paths import ensure_library_layout, library_root
from sourcelab.library.schemas import LibraryBuildReport, RawSourceRecord
from sourcelab.sources.registry import normalize_source_id

LOCAL_DOC_GLOBS = (
    "README.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "docs/**/*.md",
    "apps/web/README.md",
)

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "node_modules",
    "artifacts",
    "__pycache__",
    ".pytest_cache",
    ".next",
    "dist",
    "build",
}


def _should_skip(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def discover_local_docs(root: Path) -> list[Path]:
    """Discover markdown documentation files under a project root."""
    root = root.resolve()
    found: set[Path] = set()
    for pattern in LOCAL_DOC_GLOBS:
        for candidate in root.glob(pattern):
            if candidate.is_file() and not _should_skip(candidate.relative_to(root)):
                found.add(candidate.resolve())
    return sorted(found)


def _extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def _extract_summary(text: str, max_chars: int = 400) -> str:
    body = text
    if body.startswith("---"):
        parts = body.split("---", 2)
        if len(parts) >= 3:
            body = parts[2]
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    for paragraph in paragraphs:
        if paragraph.startswith("#"):
            continue
        cleaned = re.sub(r"[#*`>\[\]]", "", paragraph).strip()
        if len(cleaned) > 40:
            return cleaned[:max_chars]
    return ""


def _extract_key_terms(text: str, limit: int = 12) -> list[str]:
    words = re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{2,}\b", text.lower())
    stop = {
        "the", "and", "for", "with", "this", "that", "from", "are", "was", "were",
        "have", "has", "not", "you", "your", "use", "using", "into", "when", "will",
    }
    counts: dict[str, int] = {}
    for word in words:
        if word in stop:
            continue
        counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, _ in ranked[:limit]]


def collect_local_docs(
    project_root: Path,
    scan_path: Path,
    domain: str,
) -> LibraryBuildReport:
    """Collect local markdown docs into bronze raw records."""
    ensure_library_layout(project_root)
    lib_root = library_root(project_root)
    raw_dir = lib_root / "raw" / "local_docs"
    raw_dir.mkdir(parents=True, exist_ok=True)

    docs = discover_local_docs(scan_path)
    records: list[RawSourceRecord] = []
    retrieved_at = utc_now()

    for doc_path in docs:
        rel = doc_path.relative_to(scan_path.resolve())
        text = doc_path.read_text(encoding="utf-8", errors="ignore")
        checksum = sha256_text(text)
        stem = normalize_source_id(doc_path.stem if doc_path.stem != "README" else f"{rel.parent.name}_readme")
        if stem == "readme" or stem.endswith("_readme"):
            pass
        record_id = normalize_source_id(f"local_{stem}")
        content_name = f"{record_id}.md"
        content_path = raw_dir / content_name
        if not content_path.exists() or sha256_text(content_path.read_text(encoding="utf-8")) != checksum:
            content_path.write_text(text, encoding="utf-8")

        meta_path = raw_dir / f"{record_id}.json"
        record = RawSourceRecord(
            record_id=record_id,
            origin="local_docs",
            external_id=str(rel),
            title=_extract_title(text, fallback=doc_path.stem.replace("_", " ").title()),
            url=None,
            publisher="local_project",
            authors=[],
            published_at=None,
            retrieved_at=retrieved_at,
            license="project_internal",
            source_type="local_markdown",
            domain_tags=[domain],
            topic_tags=_extract_key_terms(text, limit=6),
            summary=_extract_summary(text),
            key_terms=_extract_key_terms(text),
            raw_path=str(content_path.relative_to(project_root)),
            checksum=checksum,
            metadata={"relative_path": str(rel)},
        )
        save_json(meta_path, record.model_dump(mode="json"))
        records.append(record)

    return LibraryBuildReport(
        generated_at=retrieved_at,
        stage="collect-local",
        status="ok",
        message=f"Collected {len(records)} local docs from {scan_path}",
        counts={"raw_records": len(records)},
    )
