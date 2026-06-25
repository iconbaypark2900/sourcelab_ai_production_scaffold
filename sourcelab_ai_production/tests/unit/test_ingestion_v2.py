"""Tests for source ingestion v2: PDF, URL, approval, freshness, and quality."""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from sourcelab.core.models import SourceRecord
from sourcelab.sources.registry import SourceRegistry, normalize_source_id
from sourcelab.sources.schemas import (
    IngestionRequest,
    IngestionResult,
    IngestedFile,
    URLIngestionRecord,
    SourceApprovalRecord,
    FreshnessCheckResult,
    SourceQualityReport,
)
from sourcelab.sources.ingest_local import (
    discover_local_files,
    extract_pdf_text,
    save_extracted_text,
    SUPPORTED_EXTENSIONS,
)
from sourcelab.sources.ingest_url import (
    fetch_url_content,
    parse_html_to_text,
    save_url_content,
    ingest_url_source,
)
from sourcelab.sources.freshness import (
    check_source_freshness,
    check_all_sources_freshness,
    format_freshness_report,
    FRESH_THRESHOLD,
    AGING_THRESHOLD,
)
from sourcelab.sources.quality import (
    generate_quality_report,
    format_quality_report,
)


# --- Schema tests ---


def test_ingestion_request_schema():
    """IngestionRequest schema validates with required fields."""
    request = IngestionRequest(
        source_id="test_source",
        title="Test Source",
        trust_tier="C",
    )
    assert request.source_id == "test_source"
    assert request.trust_tier == "C"


def test_ingestion_result_schema():
    """IngestionResult schema validates with required fields."""
    result = IngestionResult(status="PASS", ingested=5)
    assert result.status == "PASS"
    assert result.ingested == 5


def test_ingested_file_schema():
    """IngestedFile schema validates with required fields."""
    now = datetime.now(timezone.utc)
    file = IngestedFile(
        source_id="test",
        title="Test",
        path="/path/to/file.md",
        retrieved_at=now,
        hash_sha256="abc123",
    )
    assert file.source_id == "test"
    assert file.status == "active"
    assert file.approval_status == "approved"


def test_url_ingestion_record_schema():
    """URLIngestionRecord schema validates with required fields."""
    now = datetime.now(timezone.utc)
    record = URLIngestionRecord(
        source_id="test",
        title="Test",
        url="https://example.com",
        path="/path/to/file.txt",
        retrieved_at=now,
        hash_sha256="abc123",
    )
    assert record.url == "https://example.com"


def test_source_approval_record_schema():
    """SourceApprovalRecord schema validates with required fields."""
    record = SourceApprovalRecord(
        source_id="test",
        approval_status="approved",
        reason="Looks good",
    )
    assert record.approval_status == "approved"


def test_freshness_check_result_schema():
    """FreshnessCheckResult schema validates with required fields."""
    result = FreshnessCheckResult(
        source_id="test",
        title="Test",
        age_days=30,
        freshness_status="fresh",
    )
    assert result.freshness_status == "fresh"


def test_source_quality_report_schema():
    """SourceQualityReport schema validates with required fields."""
    report = SourceQualityReport(total_sources=10, active_sources=8)
    assert report.total_sources == 10
    assert report.active_sources == 8


# --- Local ingestion tests ---


def test_discover_local_files(tmp_path):
    """discover_local_files finds .md, .txt, and .pdf files."""
    (tmp_path / "doc.md").write_text("Markdown", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("Text", encoding="utf-8")
    (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    (tmp_path / "data.json").write_text("{}", encoding="utf-8")

    files = discover_local_files(tmp_path)
    names = [f.name for f in files]
    assert "doc.md" in names
    assert "notes.txt" in names
    assert "paper.pdf" in names
    assert "image.png" not in names
    assert "data.json" not in names


def test_extract_pdf_text_missing_dependency(tmp_path):
    """extract_pdf_text returns error when pypdf is not installed."""
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake content")

    with patch.dict("sys.modules", {"pypdf": None}):
        text, error = extract_pdf_text(pdf_path)
        assert text == ""
        assert "pypdf not installed" in error


def test_save_extracted_text(tmp_path):
    """save_extracted_text saves text to extracted directory."""
    text = "Extracted content from PDF"
    source_id = "test_pdf"
    project_root = tmp_path

    path = save_extracted_text(text, source_id, project_root)
    assert path.exists()
    assert path.read_text(encoding="utf-8") == text
    assert "extracted" in str(path)
    assert path.name == "test_pdf.txt"


def test_supported_extensions_includes_pdf():
    """SUPPORTED_EXTENSIONS includes .pdf."""
    assert ".pdf" in SUPPORTED_EXTENSIONS
    assert ".md" in SUPPORTED_EXTENSIONS
    assert ".txt" in SUPPORTED_EXTENSIONS


# --- URL ingestion tests ---


def test_fetch_url_content_missing_dependency():
    """fetch_url_content returns error when requests is not installed."""
    with patch.dict("sys.modules", {"requests": None}):
        text, content_type, error = fetch_url_content("https://example.com")
        assert text == ""
        assert "requests not installed" in error


def test_parse_html_to_text_missing_dependency():
    """parse_html_to_text returns error when beautifulsoup4 is not installed."""
    with patch.dict("sys.modules", {"bs4": None}):
        text, error = parse_html_to_text("<html><body>Hello</body></html>")
        assert text == ""
        assert "beautifulsoup4 not installed" in error


def test_parse_html_to_text():
    """parse_html_to_text extracts text from HTML."""
    try:
        import bs4  # noqa: F401
    except ImportError:
        pytest.skip("beautifulsoup4 not installed")

    html = "<html><head><title>Test</title></head><body><p>Hello World</p></body></html>"
    text, error = parse_html_to_text(html)
    assert error is None
    assert "Hello World" in text


def test_save_url_content(tmp_path):
    """save_url_content saves text to web directory."""
    text = "Web content"
    source_id = "url_test"
    project_root = tmp_path

    path = save_url_content(text, source_id, project_root)
    assert path.exists()
    assert path.read_text(encoding="utf-8") == text
    assert "web" in str(path)


def test_ingest_url_source_missing_deps(tmp_path):
    """ingest_url_source returns None when dependencies are missing."""
    with patch.dict("sys.modules", {"requests": None}):
        result = ingest_url_source(
            url="https://example.com",
            trust_tier="C",
            publisher="test",
            source_type="web_page",
            project_root=tmp_path,
        )
        assert result is None


# --- Approval workflow tests ---


def test_approve_source():
    """approve_source changes source status to active and approved."""
    source = SourceRecord(
        source_id="test",
        title="Test",
        retrieved_at=datetime.now(timezone.utc),
        hash_sha256="abc123",
        status="pending_review",
        approval_status="needs_review",
    )
    registry = SourceRegistry(sources=[source])

    result = registry.approve_source("test")
    assert result is True
    assert source.status == "active"
    assert source.approval_status == "approved"


def test_approve_source_not_found():
    """approve_source returns False when source not found."""
    registry = SourceRegistry(sources=[])
    result = registry.approve_source("nonexistent")
    assert result is False


def test_reject_source():
    """reject_source changes source status to rejected."""
    source = SourceRecord(
        source_id="test",
        title="Test",
        retrieved_at=datetime.now(timezone.utc),
        hash_sha256="abc123",
    )
    registry = SourceRegistry(sources=[source])

    result = registry.reject_source("test", "Low quality")
    assert result is True
    assert source.status == "rejected"
    assert source.approval_status == "rejected"


def test_reject_source_not_found():
    """reject_source returns False when source not found."""
    registry = SourceRegistry(sources=[])
    result = registry.reject_source("nonexistent")
    assert result is False


def test_archive_source():
    """archive_source changes source status to archived."""
    source = SourceRecord(
        source_id="test",
        title="Test",
        retrieved_at=datetime.now(timezone.utc),
        hash_sha256="abc123",
    )
    registry = SourceRegistry(sources=[source])

    result = registry.archive_source("test")
    assert result is True
    assert source.status == "archived"


def test_archive_source_not_found():
    """archive_source returns False when source not found."""
    registry = SourceRegistry(sources=[])
    result = registry.archive_source("nonexistent")
    assert result is False


def test_get_pending_sources():
    """get_pending_sources returns sources with pending_review status."""
    sources = [
        SourceRecord(
            source_id="active",
            title="Active",
            retrieved_at=datetime.now(timezone.utc),
            hash_sha256="abc",
            status="active",
        ),
        SourceRecord(
            source_id="pending",
            title="Pending",
            retrieved_at=datetime.now(timezone.utc),
            hash_sha256="def",
            status="pending_review",
        ),
    ]
    registry = SourceRegistry(sources=sources)

    pending = registry.get_pending_sources()
    assert len(pending) == 1
    assert pending[0].source_id == "pending"


def test_get_active_approved_sources():
    """get_active_approved_sources returns only active and approved sources."""
    sources = [
        SourceRecord(
            source_id="active_approved",
            title="Active Approved",
            retrieved_at=datetime.now(timezone.utc),
            hash_sha256="abc",
            status="active",
            approval_status="approved",
        ),
        SourceRecord(
            source_id="active_rejected",
            title="Active Rejected",
            retrieved_at=datetime.now(timezone.utc),
            hash_sha256="def",
            status="active",
            approval_status="rejected",
        ),
        SourceRecord(
            source_id="pending",
            title="Pending",
            retrieved_at=datetime.now(timezone.utc),
            hash_sha256="ghi",
            status="pending_review",
        ),
    ]
    registry = SourceRegistry(sources=sources)

    active = registry.get_active_approved_sources()
    assert len(active) == 1
    assert active[0].source_id == "active_approved"


def test_filter_for_retrieval():
    """filter_for_retrieval excludes rejected sources by default."""
    sources = [
        SourceRecord(
            source_id="active",
            title="Active",
            retrieved_at=datetime.now(timezone.utc),
            hash_sha256="abc",
            status="active",
            approval_status="approved",
        ),
        SourceRecord(
            source_id="rejected",
            title="Rejected",
            retrieved_at=datetime.now(timezone.utc),
            hash_sha256="def",
            status="rejected",
            approval_status="rejected",
        ),
        SourceRecord(
            source_id="pending",
            title="Pending",
            retrieved_at=datetime.now(timezone.utc),
            hash_sha256="ghi",
            status="pending_review",
        ),
    ]
    registry = SourceRegistry(sources=sources)

    # Default: exclude pending and rejected
    filtered = registry.filter_for_retrieval()
    assert len(filtered) == 1
    assert filtered[0].source_id == "active"

    # Include pending
    filtered = registry.filter_for_retrieval(include_pending=True)
    assert len(filtered) == 2
    source_ids = {s.source_id for s in filtered}
    assert "active" in source_ids
    assert "pending" in source_ids


# --- Freshness tests ---


def test_check_source_freshness_fresh():
    """check_source_freshness classifies recent sources as fresh."""
    source = SourceRecord(
        source_id="test",
        title="Test",
        retrieved_at=datetime.now(timezone.utc) - timedelta(days=30),
        hash_sha256="abc123",
    )

    result = check_source_freshness(source)
    assert result.freshness_status == "fresh"
    assert result.age_days == 30
    assert len(result.warnings) == 0


def test_check_source_freshness_aging():
    """check_source_freshness classifies medium-age sources as aging."""
    source = SourceRecord(
        source_id="test",
        title="Test",
        retrieved_at=datetime.now(timezone.utc) - timedelta(days=120),
        hash_sha256="abc123",
    )

    result = check_source_freshness(source)
    assert result.freshness_status == "aging"
    assert result.age_days == 120
    assert len(result.warnings) > 0


def test_check_source_freshness_stale():
    """check_source_freshness classifies old sources as stale."""
    source = SourceRecord(
        source_id="test",
        title="Test",
        retrieved_at=datetime.now(timezone.utc) - timedelta(days=200),
        hash_sha256="abc123",
    )

    result = check_source_freshness(source)
    assert result.freshness_status == "stale"
    assert result.age_days == 200
    assert len(result.warnings) > 0


def test_check_source_freshness_unknown():
    """check_source_freshness returns unknown when no retrieved_at."""
    source = SourceRecord(
        source_id="test",
        title="Test",
        retrieved_at=datetime.now(timezone.utc),
        hash_sha256="abc123",
    )
    source.retrieved_at = None

    result = check_source_freshness(source)
    assert result.freshness_status == "unknown"
    assert "No retrieved_at date" in result.warnings


def test_check_all_sources_freshness():
    """check_all_sources_freshness returns results for all sources."""
    sources = [
        SourceRecord(
            source_id="fresh",
            title="Fresh",
            retrieved_at=datetime.now(timezone.utc) - timedelta(days=10),
            hash_sha256="abc",
        ),
        SourceRecord(
            source_id="stale",
            title="Stale",
            retrieved_at=datetime.now(timezone.utc) - timedelta(days=200),
            hash_sha256="def",
        ),
    ]

    results = check_all_sources_freshness(sources)
    assert len(results) == 2
    statuses = {r.freshness_status for r in results}
    assert "fresh" in statuses
    assert "stale" in statuses


def test_format_freshness_report():
    """format_freshness_report returns a formatted report."""
    results = [
        FreshnessCheckResult(source_id="a", title="A", freshness_status="fresh"),
        FreshnessCheckResult(source_id="b", title="B", freshness_status="stale"),
    ]

    report = format_freshness_report(results)
    assert report["total_sources"] == 2
    assert report["fresh_count"] == 1
    assert report["stale_count"] == 1
    assert len(report["details"]) == 2


# --- Quality tests ---


def test_generate_quality_report():
    """generate_quality_report detects issues in source registry."""
    sources = [
        SourceRecord(
            source_id="good",
            title="Good Source",
            publisher="Publisher",
            source_type="document",
            retrieved_at=datetime.now(timezone.utc),
            hash_sha256="abc123",
            status="active",
        ),
        SourceRecord(
            source_id="low_trust",
            title="Low Trust",
            publisher="Publisher",
            source_type="document",
            trust_tier="E",
            retrieved_at=datetime.now(timezone.utc),
            hash_sha256="def456",
            status="active",
        ),
        SourceRecord(
            source_id="no_publisher",
            title="No Publisher",
            retrieved_at=datetime.now(timezone.utc),
            hash_sha256="ghi789",
            status="active",
        ),
    ]

    report = generate_quality_report(sources)
    assert report.total_sources == 3
    assert report.active_sources == 3
    assert report.low_trust_sources == 1
    assert len(report.missing_metadata) > 0


def test_generate_quality_report_duplicate_hashes():
    """generate_quality_report detects duplicate hashes."""
    sources = [
        SourceRecord(
            source_id="a",
            title="A",
            retrieved_at=datetime.now(timezone.utc),
            hash_sha256="same_hash",
        ),
        SourceRecord(
            source_id="b",
            title="B",
            retrieved_at=datetime.now(timezone.utc),
            hash_sha256="same_hash",
        ),
    ]

    report = generate_quality_report(sources)
    assert len(report.duplicate_hashes) > 0


def test_generate_quality_report_missing_path_or_url():
    """generate_quality_report detects missing path and URL."""
    source = SourceRecord(
        source_id="no_path",
        title="No Path",
        retrieved_at=datetime.now(timezone.utc),
        hash_sha256="abc",
    )
    # source.path is None by default

    report = generate_quality_report([source])
    assert "no_path" in report.missing_path_or_url


def test_format_quality_report():
    """format_quality_report returns a formatted report."""
    report = SourceQualityReport(
        total_sources=10,
        active_sources=8,
        pending_review_sources=1,
        stale_sources=1,
    )

    formatted = format_quality_report(report)
    assert formatted["total_sources"] == 10
    assert formatted["active_sources"] == 8
    assert formatted["pending_review_sources"] == 1
    assert formatted["stale_sources"] == 1


# --- Retrieval filtering tests ---


def test_pending_sources_excluded_from_default_retrieval():
    """Pending sources are excluded from default retrieval."""
    sources = [
        SourceRecord(
            source_id="active",
            title="Active",
            retrieved_at=datetime.now(timezone.utc),
            hash_sha256="abc",
            status="active",
            approval_status="approved",
        ),
        SourceRecord(
            source_id="pending",
            title="Pending",
            retrieved_at=datetime.now(timezone.utc),
            hash_sha256="def",
            status="pending_review",
            approval_status="needs_review",
        ),
    ]
    registry = SourceRegistry(sources=sources)

    filtered = registry.filter_for_retrieval()
    source_ids = {s.source_id for s in filtered}
    assert "active" in source_ids
    assert "pending" not in source_ids


def test_rejected_sources_excluded_from_retrieval():
    """Rejected sources are excluded from retrieval."""
    sources = [
        SourceRecord(
            source_id="active",
            title="Active",
            retrieved_at=datetime.now(timezone.utc),
            hash_sha256="abc",
            status="active",
            approval_status="approved",
        ),
        SourceRecord(
            source_id="rejected",
            title="Rejected",
            retrieved_at=datetime.now(timezone.utc),
            hash_sha256="def",
            status="rejected",
            approval_status="rejected",
        ),
    ]
    registry = SourceRegistry(sources=sources)

    filtered = registry.filter_for_retrieval()
    source_ids = {s.source_id for s in filtered}
    assert "active" in source_ids
    assert "rejected" not in source_ids
