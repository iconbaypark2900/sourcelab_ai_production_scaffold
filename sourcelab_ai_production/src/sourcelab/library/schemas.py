"""Pydantic schemas for the SourceLab Library Builder pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RawSourceRecord(BaseModel):
    """Bronze-layer record from a metadata-first collector."""

    record_id: str
    origin: str
    external_id: str | None = None
    title: str
    url: str | None = None
    publisher: str = "unknown"
    authors: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    retrieved_at: datetime
    license: str = "unknown"
    source_type: str = "document"
    domain_tags: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    summary: str = ""
    key_terms: list[str] = Field(default_factory=list)
    raw_path: str
    checksum: str
    metadata: dict = Field(default_factory=dict)


class SourceCard(BaseModel):
    """Silver-layer normalized source card."""

    source_id: str
    origin: str
    title: str
    url: str | None = None
    publisher: str = "unknown"
    authors: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    retrieved_at: datetime
    license: str = "unknown"
    source_type: str = "document"
    trust_tier: Literal["A", "B", "C", "D", "E"] = "C"
    domain_tags: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    summary: str = ""
    key_terms: list[str] = Field(default_factory=list)
    raw_path: str
    chunk_paths: list[str] = Field(default_factory=list)
    checksum: str
    quality_score: float | None = None
    external_id: str | None = None


class SourceChunk(BaseModel):
    """Silver-layer text chunk linked to a source card."""

    chunk_id: str
    source_id: str
    text: str
    section: str = "body"
    start_char: int = 0
    end_char: int = 0
    token_estimate: int = 0
    metadata: dict = Field(default_factory=dict)


class LibraryManifest(BaseModel):
    """Silver-layer manifest summarizing library build state."""

    built_at: datetime
    raw_record_count: int = 0
    source_card_count: int = 0
    chunk_count: int = 0
    origins: dict[str, int] = Field(default_factory=dict)
    domain_tags: dict[str, int] = Field(default_factory=dict)


class DedupeCluster(BaseModel):
    """Group of source cards considered duplicates."""

    cluster_id: str
    canonical_source_id: str
    duplicate_source_ids: list[str] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)


class DedupeReport(BaseModel):
    """Silver-layer deduplication report."""

    generated_at: datetime
    total_cards: int = 0
    unique_cards: int = 0
    duplicate_clusters: list[DedupeCluster] = Field(default_factory=list)
    checksum_matches: int = 0
    url_matches: int = 0
    external_id_matches: int = 0
    title_similarity_matches: int = 0


class SourceQualityEntry(BaseModel):
    """Per-source quality scoring entry."""

    source_id: str
    quality_score: float
    factors: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class SourceQualityReport(BaseModel):
    """Silver-layer quality report."""

    generated_at: datetime
    total_sources: int = 0
    average_score: float = 0.0
    entries: list[SourceQualityEntry] = Field(default_factory=list)


class PromotionCandidate(BaseModel):
    """Gold-layer candidate for source pack promotion."""

    source_id: str
    title: str
    domain_tags: list[str] = Field(default_factory=list)
    quality_score: float = 0.0
    target_pack: str
    proposed_filename: str
    status: Literal["proposed", "promoted", "skipped"] = "proposed"
    reason: str = ""


class LibraryBuildReport(BaseModel):
    """Summary report for a library build or promotion run."""

    generated_at: datetime
    stage: str
    status: Literal["ok", "dry_run", "skipped", "error"] = "ok"
    message: str = ""
    counts: dict[str, int] = Field(default_factory=dict)
    candidates: list[PromotionCandidate] = Field(default_factory=list)


class SourceExpansionSuggestion(BaseModel):
    """Suggestion to expand sources when a run has thin evidence."""

    suggestion_id: str
    reason: str
    collector: str
    query_hint: str = ""
    domain_tags: list[str] = Field(default_factory=list)
    priority: Literal["low", "medium", "high"] = "medium"


class SourceExpansionSuggestions(BaseModel):
    """Run artifact listing source expansion suggestions."""

    run_id: str
    generated_at: datetime
    thin_evidence: bool = False
    triggers: list[str] = Field(default_factory=list)
    suggestions: list[SourceExpansionSuggestion] = Field(default_factory=list)
