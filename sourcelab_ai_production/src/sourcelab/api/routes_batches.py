"""Batch run routes."""

from __future__ import annotations

from fastapi import APIRouter, Path as PathParam
from fastapi.responses import PlainTextResponse

from sourcelab.api.schemas import (
    BatchDetailResponse,
    BatchListResponse,
    BatchListItemResponse,
    BatchReportResponse,
    AnswerCompareResponse,
    RunComparisonResponse,
)
from sourcelab.api.services import (
    compare_batch,
    compare_batch_answers,
    get_batch_comparison_report,
    get_batch_detail,
    list_all_batches,
)

router = APIRouter()


@router.get("/", response_model=BatchListResponse)
def list_batches_endpoint() -> BatchListResponse:
    """List all batch runs."""
    batches = list_all_batches()
    return BatchListResponse(
        batches=[BatchListItemResponse(**b) for b in batches],
        total=len(batches),
    )


@router.get("/{batch_id}", response_model=BatchDetailResponse)
def get_batch_endpoint(
    batch_id: str = PathParam(..., description="Batch ID"),
) -> BatchDetailResponse:
    """Get batch detail."""
    result = get_batch_detail(batch_id)
    return BatchDetailResponse(**result)


@router.get("/{batch_id}/compare", response_model=RunComparisonResponse)
def compare_batch_endpoint(
    batch_id: str = PathParam(..., description="Batch ID"),
) -> RunComparisonResponse:
    """Compare all runs in a batch."""
    result = compare_batch(batch_id)
    return RunComparisonResponse(**result)


@router.get("/{batch_id}/answers/compare", response_model=AnswerCompareResponse)
def compare_batch_answers_endpoint(
    batch_id: str = PathParam(..., description="Batch ID"),
) -> AnswerCompareResponse:
    """Compare learner answer attempts for all runs in a batch."""
    result = compare_batch_answers(batch_id)
    return AnswerCompareResponse(**result)


@router.get("/{batch_id}/report", response_model=BatchReportResponse)
def get_batch_report_endpoint(
    batch_id: str = PathParam(..., description="Batch ID"),
) -> BatchReportResponse:
    """Get batch comparison report (JSON + markdown)."""
    result = get_batch_comparison_report(batch_id)
    return BatchReportResponse(**result)


@router.get("/{batch_id}/report/download")
def download_batch_report_markdown(
    batch_id: str = PathParam(..., description="Batch ID"),
) -> PlainTextResponse:
    """Download comparison report as markdown."""
    result = get_batch_comparison_report(batch_id)
    return PlainTextResponse(
        content=result.get("comparison_report_md", ""),
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="batch_{batch_id}_comparison.md"',
        },
    )
