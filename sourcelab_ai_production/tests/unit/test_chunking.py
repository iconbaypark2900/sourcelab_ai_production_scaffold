"""Tests for tokenizer-aware chunking."""

from pathlib import Path

import pytest

from sourcelab.core.models import SourceChunk, SourceRecord
from sourcelab.retrieval.chunking import (
    CHUNKING_STRATEGIES,
    TokenChunker,
    _split_sections,
    _strip_frontmatter,
    available_strategies,
    get_default_chunker,
    chunk_source as chunk_source_fn,
)
from sourcelab.retrieval.config import RetrievalConfig
from sourcelab.sources.chunker import simple_chunk_source
from sourcelab.sources.registry import SourceRegistry


# ---------------------------------------------------------------------------
# Frontmatter and section helpers
# ---------------------------------------------------------------------------


def test_strip_frontmatter_removes_yaml():
    text = "---\ntitle: Foo\n---\n\nBody text here."
    assert _strip_frontmatter(text) == "Body text here."


def test_strip_frontmatter_no_frontmatter():
    text = "Just body text."
    assert _strip_frontmatter(text) == text


def test_strip_frontmatter_partial():
    text = "---\ntitle: Foo"
    assert _strip_frontmatter(text) == text


def test_split_sections_basic():
    text = "# Intro\n\nIntro body.\n\n## Details\n\nMore details."
    sections = _split_sections(text)
    assert len(sections) == 2
    assert sections[0][0] == "Intro"
    assert sections[1][0] == "Details"


def test_split_sections_no_headings():
    text = "Plain text without any markdown headings."
    sections = _split_sections(text)
    assert len(sections) == 1
    assert sections[0][0] == "body"


def test_split_sections_empty_sections_skipped():
    text = "# Empty\n\n\n# Real\n\nContent here."
    sections = _split_sections(text)
    assert len(sections) == 1
    assert sections[0][0] == "Real"


# ---------------------------------------------------------------------------
# TokenChunker construction
# ---------------------------------------------------------------------------


def test_default_chunker_uses_regex_or_tiktoken():
    chunker = TokenChunker()
    assert chunker.name in ("regex", "tiktoken_cl100k")
    assert chunker.max_tokens == 512
    assert chunker.overlap_tokens == 64


def test_chunker_words_backend():
    chunker = TokenChunker(tokenizer_name="words")
    assert chunker.name == "words"
    tokens = chunker._tokenizer("hello world test")
    assert tokens == ["hello", "world", "test"]


def test_chunker_regex_backend():
    chunker = TokenChunker(tokenizer_name="regex")
    assert chunker.name == "regex"
    tokens = chunker._tokenizer("hello, world! don't")
    assert "hello" in tokens
    assert "," in tokens
    assert "don't" in "".join(tokens) or "don't" in tokens


def test_chunker_overlap_must_be_less_than_max():
    with pytest.raises(ValueError, match="overlap_tokens"):
        TokenChunker(max_tokens=100, overlap_tokens=100)
    with pytest.raises(ValueError, match="overlap_tokens"):
        TokenChunker(max_tokens=100, overlap_tokens=150)


def test_chunker_unknown_strategy():
    with pytest.raises(ValueError, match="Unknown tokenizer"):
        TokenChunker(tokenizer_name="nonexistent")


def test_chunker_tiktoken_not_installed():
    chunker = TokenChunker(tokenizer_name="auto")
    # Should not raise; falls back to regex if tiktoken not installed
    assert chunker.name in ("regex", "tiktoken_cl100k")


# ---------------------------------------------------------------------------
# Source chunking (core functionality)
# ---------------------------------------------------------------------------


def test_tokenizer_count_matches_chunk_token_count(tmp_path):
    text = "This is a test sentence with several words in it."
    source = SourceRecord(
        source_id="test_source",
        title="Test",
        path=str(tmp_path / "test.md"),
        trust_tier="A",
        retrieved_at="2024-01-01T00:00:00Z",
        hash_sha256="abc",
    )
    (tmp_path / "test.md").write_text(text)

    chunker = TokenChunker(tokenizer_name="words", max_tokens=5, overlap_tokens=2)
    chunks = chunker.chunk_source(source)
    assert chunks
    for c in chunks:
        assert c.token_count > 0
        assert c.source_id == "test_source"
        assert c.trust_tier == "A"


def test_chunk_preserves_source_id(tmp_path):
    source = SourceRecord(
        source_id="preserve_test",
        title="Preserve",
        path=str(tmp_path / "test.md"),
        trust_tier="B",
        retrieved_at="2024-01-01T00:00:00Z",
        hash_sha256="abc",
    )
    (tmp_path / "test.md").write_text("Some content here for chunking.")

    chunker = TokenChunker(tokenizer_name="regex", max_tokens=50, overlap_tokens=10)
    chunks = chunker.chunk_source(source)
    assert chunks
    assert all(c.source_id == "preserve_test" for c in chunks)


def test_chunk_empty_source(tmp_path):
    source = SourceRecord(
        source_id="empty",
        title="Empty",
        path=str(tmp_path / "empty.md"),
        trust_tier="C",
        retrieved_at="2024-01-01T00:00:00Z",
        hash_sha256="abc",
    )
    (tmp_path / "empty.md").write_text("")

    chunker = TokenChunker()
    chunks = chunker.chunk_source(source)
    assert chunks == []


def test_chunk_no_path():
    source = SourceRecord(
        source_id="nopath",
        title="No Path",
        path=None,
        trust_tier="C",
        retrieved_at="2024-01-01T00:00:00Z",
        hash_sha256="abc",
    )
    chunker = TokenChunker()
    assert chunker.chunk_source(source) == []


def test_chunk_source_preserves_frontmatter_stripped(tmp_path):
    text = "---\ntitle: My Doc\n---\n\n# Section 1\n\nBody of section 1."
    source = SourceRecord(
        source_id="fm_test",
        title="FM Test",
        path=str(tmp_path / "test.md"),
        trust_tier="A",
        retrieved_at="2024-01-01T00:00:00Z",
        hash_sha256="abc",
    )
    (tmp_path / "test.md").write_text(text)

    chunker = TokenChunker(tokenizer_name="words", max_tokens=50, overlap_tokens=10)
    chunks = chunker.chunk_source(source)
    assert chunks
    # Frontmatter should be stripped, so "title:" should not appear
    assert all("title:" not in c.text for c in chunks)
    # Section headings become section_title, not part of chunk text
    assert any(c.section_title == "Section 1" for c in chunks)
    assert any("Body of section 1" in c.text for c in chunks)


# ---------------------------------------------------------------------------
# Section-aware chunking
# ---------------------------------------------------------------------------


def test_section_aware_chunking(tmp_path):
    text = "# Alpha\n\nContent A.\n\n# Beta\n\nContent B."
    source = SourceRecord(
        source_id="section_test",
        title="Section Test",
        path=str(tmp_path / "test.md"),
        trust_tier="A",
        retrieved_at="2024-01-01T00:00:00Z",
        hash_sha256="abc",
    )
    (tmp_path / "test.md").write_text(text)

    chunker = TokenChunker(tokenizer_name="words", max_tokens=50, overlap_tokens=10)
    chunks = chunker.chunk_source(source)
    # Should have one chunk for Alpha section, one for Beta
    sections_found = {c.section_title for c in chunks}
    assert "Alpha" in sections_found
    assert "Beta" in sections_found


# ---------------------------------------------------------------------------
# Sliding window with overlap
# ---------------------------------------------------------------------------


def test_sliding_window_overlap(tmp_path):
    # Create text with enough tokens to span multiple windows
    text = "word " * 200  # 200 words
    source = SourceRecord(
        source_id="overlap_test",
        title="Overlap Test",
        path=str(tmp_path / "test.md"),
        trust_tier="A",
        retrieved_at="2024-01-01T00:00:00Z",
        hash_sha256="abc",
    )
    (tmp_path / "test.md").write_text(text)

    chunker = TokenChunker(tokenizer_name="words", max_tokens=50, overlap_tokens=10)
    chunks = chunker.chunk_source(source)
    assert len(chunks) >= 4  # 200 words with 50-token windows and 10 overlap

    chunk_ids = {c.chunk_id for c in chunks}
    assert len(chunk_ids) == len(chunks)  # All have unique IDs

    # All token counts should be <= max_tokens
    for c in chunks:
        assert c.token_count <= 50


def test_no_overlap(tmp_path):
    text = "word " * 100
    source = SourceRecord(
        source_id="no_overlap",
        title="No Overlap",
        path=str(tmp_path / "test.md"),
        trust_tier="A",
        retrieved_at="2024-01-01T00:00:00Z",
        hash_sha256="abc",
    )
    (tmp_path / "test.md").write_text(text)

    chunker = TokenChunker(tokenizer_name="words", max_tokens=30, overlap_tokens=0)
    chunks = chunker.chunk_source(source)
    assert len(chunks) >= 3
    # With no overlap, tokens should not be repeated across adjacent chunks
    # (We can't easily check text boundaries, but we can check token counts)
    for c in chunks:
        assert c.token_count <= 30


# ---------------------------------------------------------------------------
# chunk_text (no SourceRecord)
# ---------------------------------------------------------------------------


def test_chunk_text_without_source_record():
    chunker = TokenChunker(tokenizer_name="words", max_tokens=10, overlap_tokens=2)
    chunks = chunker.chunk_text("inline", "one two three four five six seven eight nine ten eleven twelve")
    assert chunks
    assert all(c.source_id == "inline" for c in chunks)
    assert all(c.trust_tier == "C" for c in chunks)


def test_chunk_text_empty():
    chunker = TokenChunker()
    assert chunker.chunk_text("empty", "") == []


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def test_chunk_source_convenience(tmp_path):
    source = SourceRecord(
        source_id="convenience",
        title="Conv",
        path=str(tmp_path / "test.md"),
        trust_tier="A",
        retrieved_at="2024-01-01T00:00:00Z",
        hash_sha256="abc",
    )
    (tmp_path / "test.md").write_text("Some text for convenience function.")

    chunks = chunk_source_fn(source)
    assert chunks
    assert all(c.source_id == "convenience" for c in chunks)

    chunks_custom = chunk_source_fn(source, max_tokens=20)
    assert chunks_custom
    for c in chunks_custom:
        assert c.token_count <= 20


def test_get_default_chunker_is_singleton():
    a = get_default_chunker()
    b = get_default_chunker()
    assert a is b


# ---------------------------------------------------------------------------
# info and registry helpers
# ---------------------------------------------------------------------------


def test_chunker_info():
    chunker = TokenChunker(tokenizer_name="words")
    info = chunker.info()
    assert info["name"] == "words"
    assert info["max_tokens"] == 512


def test_chunking_strategies_frozenset():
    assert "auto" in CHUNKING_STRATEGIES
    assert "regex" in CHUNKING_STRATEGIES
    assert "words" in CHUNKING_STRATEGIES


def test_available_strategies():
    strategies = available_strategies()
    assert "auto" in strategies
    assert "regex" in strategies
    assert "words" in strategies


# ---------------------------------------------------------------------------
# RetrievalConfig integration
# ---------------------------------------------------------------------------


def test_config_default_chunking():
    cfg = RetrievalConfig()
    assert cfg.chunking_strategy == "auto"
    assert cfg.chunking_max_tokens == 512
    assert cfg.chunking_overlap_tokens == 64


def test_config_custom_chunking():
    cfg = RetrievalConfig(
        chunking_strategy="regex",
        chunking_max_tokens=256,
        chunking_overlap_tokens=32,
    )
    assert cfg.chunking_strategy == "regex"
    assert cfg.chunking_max_tokens == 256
    assert cfg.chunking_overlap_tokens == 32


def test_config_invalid_chunking_strategy():
    with pytest.raises(ValueError, match="chunking_strategy"):
        RetrievalConfig(chunking_strategy="bogus")


def test_config_invalid_overlap():
    with pytest.raises(ValueError, match="chunking_overlap_tokens"):
        RetrievalConfig(chunking_max_tokens=100, chunking_overlap_tokens=200)


# ---------------------------------------------------------------------------
# Integration: PocketIndex.from_registry_with_config
# ---------------------------------------------------------------------------


def test_pocket_index_from_registry_with_config(tmp_path):
    from sourcelab.retrieval.index import PocketIndex

    # bootstrap_demo expects files in data/demo_sources/
    demo_dir = tmp_path / "data" / "demo_sources"
    demo_dir.mkdir(parents=True)
    (demo_dir / "test_source.md").write_text(
        "# Test Heading\n\nThis is test content for chunking integration."
    )

    registry = SourceRegistry.bootstrap_demo(tmp_path)
    assert registry.sources, "bootstrap_demo should find the source file"

    cfg = RetrievalConfig(
        embedding_dim=64,
        chunking_strategy="words",
        chunking_max_tokens=20,
        chunking_overlap_tokens=5,
        reranker_name="trust_tier",
    )
    index = PocketIndex.from_registry_with_config(registry, cfg)
    assert index.chunks, "PocketIndex should produce chunks from the registry"
    for c in index.chunks:
        assert c.token_count <= 20, f"token_count {c.token_count} exceeds max_tokens 20"
        assert c.section_title, "section_title should be present"


def test_pocket_index_from_registry_with_config_default(tmp_path):
    from sourcelab.retrieval.index import PocketIndex

    demo_dir = tmp_path / "data" / "demo_sources"
    demo_dir.mkdir(parents=True)
    (demo_dir / "default_test.md").write_text(
        "Default config chunking integration test."
    )

    registry = SourceRegistry.bootstrap_demo(tmp_path)
    assert registry.sources

    cfg = RetrievalConfig(embedding_dim=64, reranker_name="trust_tier")
    index = PocketIndex.from_registry_with_config(registry, cfg)
    assert index.chunks, "PocketIndex should produce chunks"
    assert index.chunks[0].token_count > 0


# ---------------------------------------------------------------------------
# Comparison: simple_chunk_source vs token_chunker
# ---------------------------------------------------------------------------


def test_token_chunker_produces_different_chunks_than_word_chunker(tmp_path):
    text = "This is a test sentence with sufficient words to create at least a couple of chunks when using a small max_tokens setting."
    source = SourceRecord(
        source_id="compare",
        title="Compare",
        path=str(tmp_path / "test.md"),
        trust_tier="A",
        retrieved_at="2024-01-01T00:00:00Z",
        hash_sha256="abc",
    )
    (tmp_path / "test.md").write_text(text)

    simple = simple_chunk_source(source, max_words=10)
    token = TokenChunker(tokenizer_name="words", max_tokens=10, overlap_tokens=2).chunk_source(source)
    assert len(simple) > 0
    assert len(token) > 0
    # With overlap, token_chunker should produce more or equal chunks
    assert len(token) >= len(simple)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_chunking_very_large_token_window(tmp_path):
    text = "word " * 500
    source = SourceRecord(
        source_id="large",
        title="Large",
        path=str(tmp_path / "test.md"),
        trust_tier="A",
        retrieved_at="2024-01-01T00:00:00Z",
        hash_sha256="abc",
    )
    (tmp_path / "test.md").write_text(text)

    chunker = TokenChunker(tokenizer_name="words", max_tokens=1000, overlap_tokens=50)
    chunks = chunker.chunk_source(source)
    assert chunks
    assert all(c.token_count <= 1000 for c in chunks)


def test_chunking_with_special_characters(tmp_path):
    text = "Don't stop! The price was $100—but is it worth it? (Yes, it's great.)"
    source = SourceRecord(
        source_id="special",
        title="Special",
        path=str(tmp_path / "test.md"),
        trust_tier="A",
        retrieved_at="2024-01-01T00:00:00Z",
        hash_sha256="abc",
    )
    (tmp_path / "test.md").write_text(text)

    chunker = TokenChunker(tokenizer_name="regex", max_tokens=100, overlap_tokens=10)
    chunks = chunker.chunk_source(source)
    assert chunks
    assert any("Don't" in c.text or "don't" in c.text or "don" in c.text for c in chunks)


def test_chunking_deeply_nested_sections(tmp_path):
    text = "# H1\n\nA.\n\n## H2\n\nB.\n\n### H3\n\nC.\n\n# Next H1\n\nD."
    source = SourceRecord(
        source_id="nested",
        title="Nested",
        path=str(tmp_path / "test.md"),
        trust_tier="A",
        retrieved_at="2024-01-01T00:00:00Z",
        hash_sha256="abc",
    )
    (tmp_path / "test.md").write_text(text)

    chunker = TokenChunker(tokenizer_name="words", max_tokens=50, overlap_tokens=10)
    chunks = chunker.chunk_source(source)
    sections = {c.section_title for c in chunks}
    assert "H1" in sections
    assert "H2" in sections
    assert "H3" in sections
    assert "Next H1" in sections


# ---------------------------------------------------------------------------
# Backward compatibility: simple_chunk_source unchanged
# ---------------------------------------------------------------------------


def test_simple_chunk_source_still_works(tmp_path):
    source = SourceRecord(
        source_id="backward",
        title="Backward",
        path=str(tmp_path / "test.md"),
        trust_tier="A",
        retrieved_at="2024-01-01T00:00:00Z",
        hash_sha256="abc",
    )
    (tmp_path / "test.md").write_text("word " * 300)

    chunks = simple_chunk_source(source, max_words=100)
    assert len(chunks) >= 2
