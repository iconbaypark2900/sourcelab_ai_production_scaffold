"""Source chunker.

Instruction:
- Chunking must preserve source IDs and trust tiers.
- Never create a chunk without linking back to SourceRecord.
- Production should add tokenizer-aware chunking and section extraction.
"""

from __future__ import annotations

from pathlib import Path

from sourcelab.core.models import SourceChunk, SourceRecord


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter from markdown source files."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].lstrip("\n")
    return text


def simple_chunk_source(source: SourceRecord, max_words: int = 120) -> list[SourceChunk]:
    """Split a source file into small word chunks."""
    if not source.path:
        return []

    text = _strip_frontmatter(Path(source.path).read_text(encoding="utf-8", errors="ignore"))
    words = text.split()
    chunks: list[SourceChunk] = []

    for i in range(0, len(words), max_words):
        chunk_words = words[i : i + max_words]
        chunk_text = " ".join(chunk_words)
        if not chunk_text.strip():
            continue

        chunks.append(
            SourceChunk(
                chunk_id=f"{source.source_id}::chunk-{len(chunks):03d}",
                source_id=source.source_id,
                text=chunk_text,
                section_title="body",
                trust_tier=source.trust_tier,
                token_count=len(chunk_words),
            )
        )
    return chunks
