"""Lesson routes.

Instruction:
- Map lesson CLI commands to REST endpoints.
- Use thin service wrappers from services.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Path as PathParam

from sourcelab.api.schemas import (
    BatchCreateRequest,
    BatchCreateResponse,
    BatchFailureResponse,
    BatchRunResultResponse,
    LessonCreateRequest,
    LessonCreateResponse,
    LessonShowResponse,
)
from sourcelab.api.services import create_batch_runs, create_lesson, show_lesson

router = APIRouter()


@router.post("/", response_model=LessonCreateResponse)
def create_lesson_endpoint(request: LessonCreateRequest) -> LessonCreateResponse:
    """Create a lesson package."""
    result = create_lesson(
        topic=request.topic,
        source_pack=request.source_pack,
        level=request.level,
        source_policy=request.source_policy,
        difficulty=request.difficulty,
        task_format=request.task_format,
        retrieval_mode=request.retrieval_mode,
        audience=request.audience,
        model_mode=request.model_mode,
        model_backend=request.model_backend,
        model_name=request.model_name,
        model_base_url=request.model_base_url,
    )
    return LessonCreateResponse(**result)


@router.post("/batch", response_model=BatchCreateResponse)
def create_batch_endpoint(request: BatchCreateRequest) -> BatchCreateResponse:
    """Create multiple lesson runs synchronously."""
    items = [item.model_dump() for item in request.items]
    result = create_batch_runs(batch_name=request.batch_name, items=items)
    return BatchCreateResponse(
        batch_id=result["batch_id"],
        batch_name=result["batch_name"],
        status=result["status"],
        created_at=result["created_at"],
        runs=[BatchRunResultResponse(**r) for r in result["runs"]],
        failures=[BatchFailureResponse(**f) for f in result["failures"]],
    )


@router.get("/{run_id}", response_model=LessonShowResponse)
def show_lesson_by_run_id(
    run_id: str = PathParam(..., description="Run ID"),
) -> LessonShowResponse:
    """Show a lesson package by run ID."""
    result = show_lesson(run_id)
    return LessonShowResponse(**result)


@router.get("/", response_model=LessonShowResponse)
def show_latest_lesson() -> LessonShowResponse:
    """Show the latest lesson package."""
    result = show_lesson()
    return LessonShowResponse(**result)
