"""Source quality reports for SourceLab AI.

Instruction:
- Generate quality reports for the source registry.
- Detect missing metadata, low-trust sources, stale sources, pending review sources, etc.
- Used by CLI command and dashboard.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sourcelab.core.models import SourceRecord
from sourcelab.sources.schemas import SourceQualityReport
from sourcelab.sources.freshness import check_source_freshness


def generate_quality_report(
    sources: list[SourceRecord],
    now: datetime | None = None,
) -> SourceQualityReport:
    """Generate a quality report for the source registry.

    Args:
        sources: List of source records.
        now: Current datetime (for testing).

    Returns:
        SourceQualityReport with all quality metrics.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    report = SourceQualityReport(total_sources=len(sources))

    # Track hashes for duplicate detection
    hash_counts: dict[str, list[str]] = {}

    for source in sources:
        # Status counts
        if source.status == "active":
            report.active_sources += 1
        elif source.status == "pending_review":
            report.pending_review_sources += 1
        elif source.status == "rejected":
            report.rejected_sources += 1
        elif source.status == "archived":
            report.archived_sources += 1

        # Low trust sources (D or E)
        if source.trust_tier in ("D", "E"):
            report.low_trust_sources += 1

        # Stale sources
        freshness = check_source_freshness(source, now)
        if freshness.freshness_status == "stale":
            report.stale_sources += 1

        # Missing metadata
        if not source.title:
            report.missing_metadata.append(f"{source.source_id}: missing title")
        if not source.publisher or source.publisher == "local":
            report.missing_metadata.append(f"{source.source_id}: missing publisher")
        if not source.source_type or source.source_type == "local_note":
            report.missing_metadata.append(f"{source.source_id}: missing source_type")

        # Duplicate hashes
        if source.hash_sha256:
            if source.hash_sha256 not in hash_counts:
                hash_counts[source.hash_sha256] = []
            hash_counts[source.hash_sha256].append(source.source_id)

        # Empty content (no path or URL)
        if not source.path and not source.url:
            report.missing_path_or_url.append(source.source_id)

        # Check for warnings from freshness
        report.warnings.extend(freshness.warnings)

    # Find duplicate hashes
    for hash_val, source_ids in hash_counts.items():
        if len(source_ids) > 1:
            report.duplicate_hashes.append(
                f"Hash {hash_val[:16]}... shared by: {', '.join(source_ids)}"
            )

    return report


def format_quality_report(report: SourceQualityReport) -> dict:
    """Format quality report for display.

    Args:
        report: SourceQualityReport.

    Returns:
        Dictionary with all report data.
    """
    return {
        "total_sources": report.total_sources,
        "active_sources": report.active_sources,
        "pending_review_sources": report.pending_review_sources,
        "rejected_sources": report.rejected_sources,
        "archived_sources": report.archived_sources,
        "stale_sources": report.stale_sources,
        "low_trust_sources": report.low_trust_sources,
        "missing_metadata": report.missing_metadata,
        "duplicate_hashes": report.duplicate_hashes,
        "empty_content_sources": report.empty_content_sources,
        "missing_path_or_url": report.missing_path_or_url,
        "warnings": report.warnings,
    }
