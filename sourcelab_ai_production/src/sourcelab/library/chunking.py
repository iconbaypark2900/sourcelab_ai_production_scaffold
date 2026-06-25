"""Chunk silver source cards for retrieval-ready storage."""

from __future__ import annotations

import re
from pathlib import Path

from sourcelab.library.io import save_model
from sourcelab.library.paths import library_root
from sourcelab.library.schemas import SourceCard, SourceChunk

DEFAULT_MAX_CHARS = 1200


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].lstrip("\n")
    return text


def _split_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_title = "body"
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("#"):
            if current_lines:
                sections.append((current_title, "\n".join(current_lines).strip()))
                current_lines = []
            current_title = re.sub(r"^#+\s*", "", line).strip() or "section"
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_title, "\n".join(current_lines).strip()))
    return [(title, body) for title, body in sections if body.strip()]


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


def chunk_text(
    source_id: str,
    text: str,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[SourceChunk]:
    """Split text into section-aware chunks."""
    cleaned = _strip_frontmatter(text)
    sections = _split_sections(cleaned) or [("body", cleaned)]
    chunks: list[SourceChunk] = []
    cursor = 0

    for section_title, section_text in sections:
        start = cleaned.find(section_text, cursor)
        if start < 0:
            start = cursor
        for offset in range(0, len(section_text), max_chars):
            piece = section_text[offset : offset + max_chars].strip()
            if not piece:
                continue
            piece_start = start + offset
            piece_end = piece_start + len(piece)
            chunks.append(
                SourceChunk(
                    chunk_id=f"{source_id}::chunk-{len(chunks):03d}",
                    source_id=source_id,
                    text=piece,
                    section=section_title,
                    start_char=piece_start,
                    end_char=piece_end,
                    token_estimate=_estimate_tokens(piece),
                    metadata={"section": section_title},
                )
            )
        cursor = start + len(section_text)

    return chunks


def chunk_source_card(project_root: Path, card: SourceCard, max_chars: int = DEFAULT_MAX_CHARS) -> list[Path]:
    """Write chunk artifacts for a source card."""
    raw_path = project_root / card.raw_path
    text = raw_path.read_text(encoding="utf-8", errors="ignore") if raw_path.exists() else card.summary
    chunks = chunk_text(card.source_id, text, max_chars=max_chars)
    chunks_dir = library_root(project_root) / "silver" / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for chunk in chunks:
        path = chunks_dir / f"{chunk.chunk_id.replace('::', '__')}.json"
        save_model(path, chunk)
        written.append(path)
    return written
