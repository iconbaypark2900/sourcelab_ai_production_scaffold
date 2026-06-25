"""Source pack routes.

Instruction:
- Map source pack CLI commands to REST endpoints.
- List, validate, install, and check status of source packs.
"""

from __future__ import annotations

from fastapi import APIRouter, Path as PathParam

from sourcelab.api.schemas import (
    SourcePackListResponse,
    SourcePackInfo,
    SourcePackValidationResponse,
    SourcePackInstallRequest,
    SourcePackInstallResponse,
    SourcePackStatusResponse,
)
from sourcelab.api.services import (
    list_source_packs_api,
    validate_source_pack_api,
    install_source_pack_api,
    source_pack_status_api,
)

router = APIRouter()


@router.get("/", response_model=SourcePackListResponse)
def list_source_packs() -> SourcePackListResponse:
    """List available source packs."""
    result = list_source_packs_api()
    return SourcePackListResponse(**result)


@router.get("/{pack_name}/validate", response_model=SourcePackValidationResponse)
def validate_source_pack(pack_name: str = PathParam(...)) -> SourcePackValidationResponse:
    """Validate a source pack's structure and content."""
    result = validate_source_pack_api(pack_name)
    return SourcePackValidationResponse(**result)


@router.post("/{pack_name}/install", response_model=SourcePackInstallResponse)
def install_source_pack(
    pack_name: str = PathParam(...),
) -> SourcePackInstallResponse:
    """Install a source pack into the source registry."""
    result = install_source_pack_api(pack_name)
    return SourcePackInstallResponse(**result)


@router.get("/{pack_name}/status", response_model=SourcePackStatusResponse)
def source_pack_status(pack_name: str = PathParam(...)) -> SourcePackStatusResponse:
    """Check source pack installation status."""
    result = source_pack_status_api(pack_name)
    return SourcePackStatusResponse(**result)
