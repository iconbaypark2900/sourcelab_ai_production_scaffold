"""Retrieval routes.

Instruction:
- Map retrieval CLI commands to REST endpoints.
- Use thin service wrappers from services.py.
"""

from __future__ import annotations

from fastapi import APIRouter

from sourcelab.api.schemas import (
    IndexBuildResponse,
    RetrievalDiagnosticsResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from sourcelab.api.services import build_index, get_retrieval_diagnostics, search_sources

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    """Search sources using hybrid search."""
    result = search_sources(
        query=request.query,
        top_k=request.top_k,
        mode=request.mode,
    )
    return SearchResponse(
        query=result["query"],
        mode=result["mode"],
        results=[SearchResultItem(**r) for r in result["results"]],
        total=result["total"],
    )


@router.post("/index", response_model=IndexBuildResponse)
def build_search_index() -> IndexBuildResponse:
    """Build search index from registry."""
    result = build_index()
    return IndexBuildResponse(**result)


@router.get("/diagnostics", response_model=RetrievalDiagnosticsResponse)
def retrieval_diagnostics() -> RetrievalDiagnosticsResponse:
    """Get retrieval diagnostics from the latest run."""
    result = get_retrieval_diagnostics()
    return RetrievalDiagnosticsResponse(**result)
