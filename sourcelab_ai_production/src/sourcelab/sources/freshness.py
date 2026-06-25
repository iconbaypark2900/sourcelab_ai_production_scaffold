"""Source freshness checks for SourceLab AI.

Instruction:
- Check source freshness based on retrieved_at and last_checked_at dates.
- Classify sources as fresh, aging, or stale based on age thresholds.
- Default thresholds: fresh <= 90 days, aging 91-180 days, stale > 180 days.
- Used by CLI command and dashboard.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sourcelab.core.models import SourceRecord
from sourcelab.sources.schemas import FreshnessCheckResult

# Default thresholds in days
FRESH_THRESHOLD = 90
AGING_THRESHOLD = 180


def check_source_freshness(
    source: SourceRecord,
    now: datetime | None = None,
    fresh_threshold: int = FRESH_THRESHOLD,
    aging_threshold: int = AGING_THRESHOLD,
) -> FreshnessCheckResult:
    """Check freshness of a single source.

    Args:
        source: The source record to check.
        now: Current datetime (for testing). If None, uses UTC now.
        fresh_threshold: Max days for 'fresh' status.
        aging_threshold: Max days for 'aging' status (stale is > aging_threshold).

    Returns:
        FreshnessCheckResult with age and status.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    result = FreshnessCheckResult(
        source_id=source.source_id,
        title=source.title,
        retrieved_at=source.retrieved_at,
        last_checked_at=source.last_checked_at,
    )

    if source.retrieved_at is None:
        result.freshness_status = "unknown"
        result.warnings.append("No retrieved_at date")
        return result

    # Calculate age
    retrieved_at = source.retrieved_at
    if retrieved_at.tzinfo is None:
        retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)

    age_delta = now - retrieved_at
    result.age_days = age_delta.days

    # Classify freshness
    if result.age_days <= fresh_threshold:
        result.freshness_status = "fresh"
    elif result.age_days <= aging_threshold:
        result.freshness_status = "aging"
        result.warnings.append(f"Source is {result.age_days} days old (aging)")
    else:
        result.freshness_status = "stale"
        result.warnings.append(f"Source is {result.age_days} days old (stale)")

    return result


def check_all_sources_freshness(
    sources: list[SourceRecord],
    now: datetime | None = None,
) -> list[FreshnessCheckResult]:
    """Check freshness of all sources.

    Args:
        sources: List of source records.
        now: Current datetime (for testing).

    Returns:
        List of FreshnessCheckResult for each source.
    """
    return [check_source_freshness(source, now) for source in sources]


def format_freshness_report(results: list[FreshnessCheckResult]) -> dict:
    """Format freshness check results into a report.

    Args:
        results: List of FreshnessCheckResult.

    Returns:
        Dictionary with summary and details.
    """
    fresh_count = sum(1 for r in results if r.freshness_status == "fresh")
    aging_count = sum(1 for r in results if r.freshness_status == "aging")
    stale_count = sum(1 for r in results if r.freshness_status == "stale")
    unknown_count = sum(1 for r in results if r.freshness_status == "unknown")

    return {
        "total_sources": len(results),
        "fresh_count": fresh_count,
        "aging_count": aging_count,
        "stale_count": stale_count,
        "unknown_count": unknown_count,
        "details": [r.model_dump() for r in results],
    }
