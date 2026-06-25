"""Tokenizer-aware chunking for retrieval.

Instruction:
- Provides section-aware, token-aware chunking with configurable backends.
- Supports sliding window with overlap for coherent chunk boundaries.
- Default regex backend is deterministic with zero external dependencies.
- Optional tiktoken backend provides OpenAI-compatible tokenization.
- All chunkers produce SourceChunk models with accurate token_count.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from sourcelab.core.models import SourceChunk, SourceRecord


# GPT-2 / tiktoken-compatible regex pattern.
# Uses Unicode-safe character classes (works on Python 3.12 without \p{L}).
_GPT2_REGEX = re.compile(
    r"""'s|'t|'re|'ve|'m|'ll|'d| ?[^\W\d_]+| ?\d+| ?[^\s\w]+|\s+(?!\S)|\s+""",
    re.UNICODE,
)

_SECTION_HEADING = re.compile(r"^#+\s+")


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter from markdown source files."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].lstrip("\n")
    return text


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split text into markdown sections with their headings."""
    sections: list[tuple[str, str]] = []
    current_title = "body"
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("#"):
            if current_lines:
                sections.append((current_title, "\n".join(current_lines).strip()))
                current_lines = []
            current_title = _SECTION_HEADING.sub("", line).strip() or "section"
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_title, "\n".join(current_lines).strip()))
    return [(title, body) for title, body in sections if body.strip()]


# --- Tokenizer backends ---


def _tokenize_words(text: str) -> list[str]:
    return text.split()


def _tokenize_regex(text: str) -> list[str]:
    return [m.group() for m in _GPT2_REGEX.finditer(text)]


_TOKENIZERS: dict[str, Callable[[str], list[str]]] = {
    "words": _tokenize_words,
    "regex": _tokenize_regex,
}


def _try_load_tiktoken(encoding: str = "cl100k_base") -> Callable[[str], list[int]] | None:
    try:
        import tiktoken

        enc = tiktoken.get_encoding(encoding)
        return enc.encode
    except ImportError:
        return None


# --- Main chunker ---


class TokenChunker:
    """Section-aware chunker with configurable tokenizer and sliding window.

    The chunker strips frontmatter, splits on markdown headings, then
    applies a sliding window of ``max_tokens`` with ``overlap_tokens``
    overlap within each section.  Every chunk carries an accurate
    ``token_count``.

    Supported tokenizer backends via ``tokenizer_name``:
    - ``"auto"`` - try tiktoken cl100k_base, fall back to regex
    - ``"regex"`` - GPT-2-style regex (deterministic, zero deps)
    - ``"words"`` - simple whitespace split (backward compatible)
    - ``"tiktoken_cl100k"`` - OpenAI cl100k_base (requires ``tiktoken``)
    """

    def __init__(
        self,
        tokenizer_name: str = "auto",
        max_tokens: int = 512,
        overlap_tokens: int = 64,
    ):
        if overlap_tokens >= max_tokens:
            raise ValueError(
                f"overlap_tokens ({overlap_tokens}) must be < max_tokens ({max_tokens})"
            )
        self._max_tokens = max_tokens
        self._overlap_tokens = overlap_tokens

        if tokenizer_name == "auto":
            tik = _try_load_tiktoken()
            if tik is not None:
                self._tokenizer = tik
                self._resolved_name = "tiktoken_cl100k"
            else:
                self._tokenizer = _tokenize_regex
                self._resolved_name = "regex"
        elif tokenizer_name == "tiktoken_cl100k":
            tik = _try_load_tiktoken()
            if tik is None:
                raise ImportError(
                    "tiktoken is not installed. Install it with: pip install tiktoken"
                )
            self._tokenizer = tik
            self._resolved_name = tokenizer_name
        elif tokenizer_name in _TOKENIZERS:
            self._tokenizer = _TOKENIZERS[tokenizer_name]
            self._resolved_name = tokenizer_name
        else:
            raise ValueError(
                f"Unknown tokenizer: {tokenizer_name}. "
                f"Available: auto, words, regex, tiktoken_cl100k"
            )

    @property
    def name(self) -> str:
        return self._resolved_name

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    @property
    def overlap_tokens(self) -> int:
        return self._overlap_tokens

    def count(self, text: str) -> int:
        return len(self._tokenizer(text))

    def _decode_tokens(self, tokens: list[str] | list[int]) -> str:
        if self._resolved_name == "tiktoken_cl100k":
            import tiktoken

            enc = tiktoken.get_encoding("cl100k_base")
            return enc.decode(tokens)
        elif self._resolved_name == "regex":
            return "".join(tokens)
        else:
            return " ".join(tokens)

    def _chunk_section_text(
        self,
        text: str,
        source_id: str,
        section_title: str,
        trust_tier: str,
    ) -> list[SourceChunk]:
        tokens = self._tokenizer(text)
        if not tokens:
            return []
        chunks: list[SourceChunk] = []
        start = 0
        while start < len(tokens):
            end = min(start + self._max_tokens, len(tokens))
            piece = self._decode_tokens(tokens[start:end]).strip()
            if piece:
                chunks.append(
                    SourceChunk(
                        chunk_id=f"{source_id}::chunk-{len(chunks):03d}",
                        source_id=source_id,
                        text=piece,
                        section_title=section_title,
                        trust_tier=trust_tier,
                        token_count=end - start,
                    )
                )
            if end >= len(tokens):
                break
            start = end - self._overlap_tokens
        return chunks

    def chunk_source(self, source: SourceRecord) -> list[SourceChunk]:
        """Chunk a source record into token-aware, section-preserving chunks."""
        if not source.path:
            return []
        text = _strip_frontmatter(
            Path(source.path).read_text(encoding="utf-8", errors="ignore")
        )
        sections = _split_sections(text) or [("body", text)]
        chunks: list[SourceChunk] = []
        for section_title, section_text in sections:
            if not section_text.strip():
                continue
            chunks.extend(
                self._chunk_section_text(
                    section_text, source.source_id, section_title, source.trust_tier
                )
            )
        return chunks

    def chunk_text(
        self,
        source_id: str,
        text: str,
        trust_tier: str = "C",
    ) -> list[SourceChunk]:
        """Chunk arbitrary text without a SourceRecord."""
        cleaned = _strip_frontmatter(text)
        sections = _split_sections(cleaned) or [("body", cleaned)]
        chunks: list[SourceChunk] = []
        for section_title, section_text in sections:
            if not section_text.strip():
                continue
            chunks.extend(
                self._chunk_section_text(
                    section_text, source_id, section_title, trust_tier
                )
            )
        return chunks

    def info(self) -> dict:
        return {
            "name": self._resolved_name,
            "max_tokens": self._max_tokens,
            "overlap_tokens": self._overlap_tokens,
        }


# --- Default chunker instance and convenience wrapper ---

_DEFAULT_CHUNKER: TokenChunker | None = None


def get_default_chunker() -> TokenChunker:
    global _DEFAULT_CHUNKER
    if _DEFAULT_CHUNKER is None:
        _DEFAULT_CHUNKER = TokenChunker()
    return _DEFAULT_CHUNKER


def chunk_source(source: SourceRecord, max_tokens: int | None = None) -> list[SourceChunk]:
    chunker = get_default_chunker()
    if max_tokens is not None:
        overlap = min(chunker.overlap_tokens, max_tokens // 4)
        chunker = TokenChunker(max_tokens=max_tokens, overlap_tokens=overlap)
    return chunker.chunk_source(source)


# --- Strategy registry helpers ---

CHUNKING_STRATEGIES = frozenset({"auto", "regex", "words", "tiktoken_cl100k"})


def available_strategies() -> list[str]:
    available = ["auto", "regex", "words"]
    if _try_load_tiktoken() is not None:
        available.append("tiktoken_cl100k")
    return available
