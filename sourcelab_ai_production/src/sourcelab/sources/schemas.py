"""Source ingestion schemas for SourceLab AI.

Instruction:
- Pydantic schemas for ingestion requests, results, approval, and quality reports.
- Used by ingest_local, ingest_url, freshness, and quality modules.
- All ingestion must produce structured results for auditing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class IngestionRequest(BaseModel):
    """Request to ingest a source."""

    source_id: str
    title: str
    path: str | None = None
    url: str | None = None
    publisher: str = "local"
    source_type: str = "local_note"
    trust_tier: Literal["A", "B", "C", "D", "E"] = "C"
    retrieved_at: datetime | None = None
    hash_sha256: str = ""
    content_type: str = ""


class IngestedFile(BaseModel):
    """A single ingested file record."""

    source_id: str
    title: str
    path: str
    original_path: str | None = None
    publisher: str = "local"
    source_type: str = "local_note"
    trust_tier: Literal["A", "B", "C", "D", "E"] = "C"
    status: Literal["active", "pending_review", "rejected", "stale", "archived"] = "active"
    approval_status: Literal["approved", "needs_review", "rejected"] = "approved"
    retrieved_at: datetime
    last_checked_at: datetime | None = None
    hash_sha256: str
    content_type: str = "text/plain"
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class URLIngestionRecord(BaseModel):
    """Record for URL-based ingestion."""

    source_id: str
    title: str
    url: str
    path: str
    publisher: str = "local"
    source_type: str = "web_page"
    trust_tier: Literal["A", "B", "C", "D", "E"] = "C"
    status: Literal["active", "pending_review", "rejected", "stale", "archived"] = "active"
    approval_status: Literal["approved", "needs_review", "rejected"] = "approved"
    retrieved_at: datetime
    last_checked_at: datetime | None = None
    hash_sha256: str
    content_type: str = "text/plain"
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class SourceApprovalRecord(BaseModel):
    """Record for source approval workflow."""

    source_id: str
    approval_status: Literal["approved", "needs_review", "rejected"] = "needs_review"
    reason: str = ""
    reviewed_at: datetime | None = None
    reviewer: str = ""


class FreshnessCheckResult(BaseModel):
    """Result of a freshness check for a source."""

    source_id: str
    title: str
    retrieved_at: datetime | None = None
    last_checked_at: datetime | None = None
    age_days: int | None = None
    freshness_status: Literal["fresh", "aging", "stale", "unknown"] = "unknown"
    warnings: list[str] = Field(default_factory=list)


class SourceQualityReport(BaseModel):
    """Quality report for the source registry."""

    total_sources: int = 0
    active_sources: int = 0
    pending_review_sources: int = 0
    rejected_sources: int = 0
    archived_sources: int = 0
    stale_sources: int = 0
    low_trust_sources: int = 0
    missing_metadata: list[str] = Field(default_factory=list)
    duplicate_hashes: list[str] = Field(default_factory=list)
    empty_content_sources: list[str] = Field(default_factory=list)
    missing_path_or_url: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class IngestionResult(BaseModel):
    """Result of an ingestion operation."""

    status: Literal["PASS", "FAIL", "WARN"] = "PASS"
    folder: str = ""
    total_files_found: int = 0
    ingested: int = 0
    updated: int = 0
    skipped: int = 0
    files_ingested: list[str] = Field(default_factory=list)
    files_updated: list[str] = Field(default_factory=list)
    files_skipped: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    registry_path: str = ""
    total_sources_in_registry: int = 0
