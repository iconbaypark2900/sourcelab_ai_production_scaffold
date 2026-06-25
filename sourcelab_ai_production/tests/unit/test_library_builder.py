"""Tests for SourceLab Library Builder v1."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sourcelab.library.chunking import chunk_text
from sourcelab.library.collectors.arxiv import _parse_arxiv_feed, collect_arxiv
from sourcelab.library.collectors.local_docs import collect_local_docs, discover_local_docs
from sourcelab.library.collectors.nvd import _parse_nvd_response, collect_nvd
from sourcelab.library.collectors.pubmed import _parse_pubmed_xml, collect_pubmed
from sourcelab.library.dedupe import build_dedupe_report, dedupe_library
from sourcelab.library.expansion import (
    build_expansion_suggestions,
    detect_thin_evidence,
    maybe_write_source_expansion_suggestions,
)
from sourcelab.library.normalize import normalize_library
from sourcelab.library.paths import ensure_library_layout
from sourcelab.library.promote import promote_library
from sourcelab.library.quality import quality_library, score_source_card
from sourcelab.library.schemas import (
    DedupeReport,
    LibraryBuildReport,
    LibraryManifest,
    PromotionCandidate,
    RawSourceRecord,
    SourceCard,
    SourceChunk,
    SourceExpansionSuggestions,
    SourceQualityReport,
)
from sourcelab.library.stats import library_stats


SAMPLE_ARXIV_XML = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1234.5678v1</id>
    <title>Sample Paper Title</title>
    <summary>Sample abstract text for testing.</summary>
    <published>2024-01-02T00:00:00Z</published>
    <author><name>Ada Lovelace</name></author>
    <link rel="alternate" href="http://arxiv.org/abs/1234.5678"/>
  </entry>
</feed>"""

SAMPLE_PUBMED_XML = """
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID Version="1">999999</PMID>
      <Article>
        <ArticleTitle>Sample PubMed Article</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">Background details.</AbstractText>
          <AbstractText>Main abstract.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author><LastName>Curie</LastName><ForeName>Marie</ForeName></Author>
        </AuthorList>
        <Journal><JournalIssue><PubDate><Year>2023</Year></PubDate></JournalIssue></Journal>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""

SAMPLE_NVD_JSON = {
    "vulnerabilities": [
        {
            "cve": {
                "id": "CVE-2024-1234",
                "published": "2024-03-01T00:00:00.000",
                "descriptions": [{"lang": "en", "value": "Sample CVE description."}],
            }
        }
    ]
}


@pytest.fixture
def library_project(tmp_path: Path) -> Path:
    (tmp_path / "README.md").write_text("# Demo\n\nLocal docs summary for library tests.", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Guide\n\nDetailed guide content.", encoding="utf-8")
    ensure_library_layout(tmp_path)
    return tmp_path


def test_schema_validation_roundtrip():
    now = datetime.now(timezone.utc)
    raw = RawSourceRecord(
        record_id="demo_raw",
        origin="local_docs",
        title="Demo",
        retrieved_at=now,
        raw_path="data/library/raw/local_docs/demo.md",
        checksum="abc",
    )
    card = SourceCard(
        source_id="demo_raw",
        origin="local_docs",
        title="Demo",
        retrieved_at=now,
        raw_path=raw.raw_path,
        checksum="abc",
    )
    chunk = SourceChunk(
        chunk_id="demo_raw::chunk-000",
        source_id="demo_raw",
        text="hello",
        section="body",
        start_char=0,
        end_char=5,
        token_estimate=1,
    )
    assert RawSourceRecord.model_validate(raw.model_dump()).record_id == "demo_raw"
    assert SourceCard.model_validate(card.model_dump()).source_id == "demo_raw"
    assert SourceChunk.model_validate(chunk.model_dump()).chunk_id.endswith("000")


def test_discover_and_collect_local_docs(library_project: Path):
    docs = discover_local_docs(library_project)
    assert len(docs) >= 2
    report = collect_local_docs(library_project, library_project, domain="user_project_library")
    assert report.counts["raw_records"] >= 2


def test_arxiv_parser_and_collect_mock(library_project: Path):
    parsed = _parse_arxiv_feed(SAMPLE_ARXIV_XML)
    assert parsed[0]["arxiv_id"] == "1234.5678v1"
    assert "Sample Paper" in parsed[0]["title"]

    def fake_fetcher(url: str) -> str:
        assert "export.arxiv.org" in url
        return SAMPLE_ARXIV_XML

    report = collect_arxiv(
        library_project,
        query="sample",
        domain="research",
        max_results=1,
        delay_seconds=0,
        fetcher=fake_fetcher,
    )
    assert report.counts["raw_records"] == 1


def test_pubmed_parser_and_collect_mock(library_project: Path):
    parsed = _parse_pubmed_xml(SAMPLE_PUBMED_XML)
    assert parsed[0]["pmid"] == "999999"
    assert parsed[0]["authors"][0] == "Marie Curie"

    calls: list[str] = []

    def fake_fetcher(url: str) -> str:
        calls.append(url)
        if "esearch" in url:
            return json.dumps({"esearchresult": {"idlist": ["999999"]}})
        return SAMPLE_PUBMED_XML

    report = collect_pubmed(
        library_project,
        query="sample",
        domain="research",
        max_results=1,
        delay_seconds=0,
        fetcher=fake_fetcher,
    )
    assert report.counts["raw_records"] == 1
    assert len(calls) == 2


def test_nvd_parser_and_collect_mock(library_project: Path):
    parsed = _parse_nvd_response(SAMPLE_NVD_JSON)
    assert parsed[0]["cve_id"] == "CVE-2024-1234"

    report = collect_nvd(
        library_project,
        domain="security",
        keyword="sample",
        max_results=1,
        delay_seconds=0,
        fetcher=lambda url: json.dumps(SAMPLE_NVD_JSON),
    )
    assert report.counts["raw_records"] == 1


def test_chunking_sections():
    text = "# Intro\n\nIntro body.\n\n## Details\n\nMore details here."
    chunks = chunk_text("demo", text, max_chars=40)
    assert len(chunks) >= 2
    assert chunks[0].section in {"Intro", "body", "Details"}


def test_dedupe_checksum_and_title():
    now = datetime.now(timezone.utc)
    cards = [
        SourceCard(
            source_id="a",
            origin="local_docs",
            title="Same Title",
            retrieved_at=now,
            raw_path="x",
            checksum="same",
        ),
        SourceCard(
            source_id="b",
            origin="local_docs",
            title="Same Title",
            retrieved_at=now,
            raw_path="y",
            checksum="same",
        ),
    ]
    report = build_dedupe_report(cards)
    assert report.total_cards == 2
    assert report.unique_cards == 1
    assert report.checksum_matches >= 1


def test_quality_scoring():
    now = datetime.now(timezone.utc)
    card = SourceCard(
        source_id="quality_demo",
        origin="local_docs",
        title="Quality Demo Title",
        retrieved_at=now,
        raw_path="x",
        checksum="abc",
        summary="A sufficiently long summary for quality scoring in library builder tests.",
        key_terms=["alpha", "beta", "gamma"],
        chunk_paths=["data/library/silver/chunks/a.json"],
        trust_tier="B",
        url="https://example.com/doc",
    )
    entry = score_source_card(card)
    assert entry.quality_score >= 0.55


def test_pipeline_normalize_dedupe_quality_stats(library_project: Path):
    collect_local_docs(library_project, library_project, domain="user_project_library")
    normalize_library(library_project)
    dedupe_report = dedupe_library(library_project)
    quality_report = quality_library(library_project)
    stats = library_stats(library_project)

    assert dedupe_report.counts["total_cards"] >= 2
    assert quality_report.counts["sources_scored"] >= 2
    assert stats["silver"]["source_cards"] >= 2


def test_promote_dry_run(library_project: Path):
    collect_local_docs(library_project, library_project, domain="user_project_library")
    normalize_library(library_project)
    quality_library(library_project)
    report = promote_library(
        library_project,
        domain="user_project_library",
        target_pack="agentic_engineering_v1",
        min_quality=0.4,
        dry_run=True,
        force=False,
    )
    assert report.status == "dry_run"
    assert report.counts["candidates"] >= 1
    proposal_dir = library_project / "data/library/promotion/candidates/agentic_engineering_v1"
    assert proposal_dir.exists()
    assert any(proposal_dir.glob("*.md"))


def test_expansion_suggestions_on_thin_evidence(tmp_path: Path):
    run_dir = tmp_path / "artifacts" / "runs" / "run_test"
    run_dir.mkdir(parents=True)
    (run_dir / "retrieved_chunks.json").write_text("[]", encoding="utf-8")
    (run_dir / "source_registry_snapshot.json").write_text("[]", encoding="utf-8")
    (run_dir / "source_grounding_review.json").write_text(
        json.dumps({"source_grounding_score": 0.1}),
        encoding="utf-8",
    )

    thin, triggers = detect_thin_evidence(run_dir)
    assert thin is True
    assert triggers

    payload = maybe_write_source_expansion_suggestions(tmp_path, run_dir, "agentic engineering")
    assert payload is not None
    assert (run_dir / "source_expansion_suggestions.json").exists()
    loaded = SourceExpansionSuggestions.model_validate(
        json.loads((run_dir / "source_expansion_suggestions.json").read_text(encoding="utf-8"))
    )
    assert loaded.thin_evidence is True
    assert len(loaded.suggestions) >= 3


def test_expansion_suggestions_skipped_when_evidence_ok(tmp_path: Path):
    run_dir = tmp_path / "artifacts" / "runs" / "run_ok"
    run_dir.mkdir(parents=True)
    chunks = [{"chunk_id": "a", "source_id": "s1"}, {"chunk_id": "b", "source_id": "s2"}]
    (run_dir / "retrieved_chunks.json").write_text(json.dumps(chunks), encoding="utf-8")
    (run_dir / "source_registry_snapshot.json").write_text(json.dumps(chunks), encoding="utf-8")
    (run_dir / "source_grounding_review.json").write_text(
        json.dumps({"source_grounding_score": 0.9}),
        encoding="utf-8",
    )
    assert maybe_write_source_expansion_suggestions(tmp_path, run_dir, "topic") is None
