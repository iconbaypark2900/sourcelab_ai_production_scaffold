"""Source routes.

Instruction:
- Map source CLI commands to REST endpoints.
- Use thin service wrappers from services.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Path as PathParam

from sourcelab.api.schemas import (
    SourceActionRequest,
    SourceActionResponse,
    SourceIngestRequest,
    SourceIngestResponse,
    SourceListResponse,
    SourceResponse,
    SourceValidationResponse,
)
from sourcelab.api.services import (
    approve_source,
    archive_source,
    get_source,
    list_sources,
    reject_source,
    validate_sources,
)

router = APIRouter()


@router.get("/", response_model=SourceListResponse)
def list_all_sources() -> SourceListResponse:
    """List all sources in the registry."""
    sources = list_sources()
    return SourceListResponse(
        sources=[SourceResponse(**s) for s in sources],
        total=len(sources),
    )


@router.get("/validate", response_model=SourceValidationResponse)
def validate_all_sources() -> SourceValidationResponse:
    """Validate all sources in the registry."""
    result = validate_sources()
    return SourceValidationResponse(**result)


@router.get("/{source_id}", response_model=SourceResponse)
def get_source_by_id(
    source_id: str = PathParam(..., description="Source ID"),
) -> SourceResponse:
    """Get a specific source by ID."""
    source = get_source(source_id)
    return SourceResponse(**source)


@router.post("/{source_id}/approve", response_model=SourceActionResponse)
def approve_source_by_id(
    source_id: str = PathParam(..., description="Source ID"),
) -> SourceActionResponse:
    """Approve a source."""
    result = approve_source(source_id)
    return SourceActionResponse(**result)


@router.post("/{source_id}/reject", response_model=SourceActionResponse)
def reject_source_by_id(
    source_id: str = PathParam(..., description="Source ID"),
    request: SourceActionRequest = SourceActionRequest(),
) -> SourceActionResponse:
    """Reject a source."""
    result = reject_source(source_id, reason=request.reason)
    return SourceActionResponse(**result)


@router.post("/{source_id}/archive", response_model=SourceActionResponse)
def archive_source_by_id(
    source_id: str = PathParam(..., description="Source ID"),
) -> SourceActionResponse:
    """Archive a source."""
    result = archive_source(source_id)
    return SourceActionResponse(**result)


@router.post("/ingest", response_model=SourceIngestResponse)
def ingest_source(request: SourceIngestRequest) -> SourceIngestResponse:
    """Ingest a source file."""
    # This is a placeholder - full implementation would use SourceIngestor
    return SourceIngestResponse(
        source_id=request.source_id,
        status="pending",
        message=f"Source '{request.source_id}' ingestion queued",
    )
