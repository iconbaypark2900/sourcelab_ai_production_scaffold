"""Learning routes.

Instruction:
- Map learning CLI commands to REST endpoints.
- Use thin service wrappers from services.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Path as PathParam, Query

from sourcelab.api.schemas import (
    AnswerAttemptDetailResponse,
    AnswerDiffResponse,
    AnswerHistoryResponse,
    AnswerSubmitRequest,
    AnswerSubmitResponse,
    CurriculumResponse,
    LearningReportResponse,
    NextTaskResponse,
    ProfileShowResponse,
)
from sourcelab.api.services import (
    get_answer_attempt,
    get_answer_diff,
    get_answer_history,
    get_curriculum,
    get_learning_report,
    get_next_task,
    get_skill_profile,
    submit_answer,
)

router = APIRouter()


@router.post("/answers", response_model=AnswerSubmitResponse)
def submit_answer_endpoint(request: AnswerSubmitRequest) -> AnswerSubmitResponse:
    """Submit an answer for scoring against a run.

    ``run_id`` may be "latest" (or null) and is resolved to a concrete run id.
    ``topic`` is optional (resolved from the run manifest). ``user_id`` is
    accepted but local mode always uses the single ``local_user`` profile.
    """
    result = submit_answer(
        answer_text=request.answer_text,
        run_id=request.run_id,
        topic=request.topic,
    )
    return AnswerSubmitResponse(**result)


@router.get("/answers/{run_id}", response_model=AnswerHistoryResponse)
def get_answer_history_endpoint(
    run_id: str = PathParam(..., description="Run ID or 'latest'"),
) -> AnswerHistoryResponse:
    """List immutable answer attempts for a run."""
    result = get_answer_history(run_id)
    return AnswerHistoryResponse(**result)


@router.get("/answers/{run_id}/diff", response_model=AnswerDiffResponse)
def get_answer_diff_endpoint(
    run_id: str = PathParam(..., description="Run ID or 'latest'"),
    from_attempt: str = Query(..., alias="from_attempt", description="Earlier attempt id"),
    to_attempt: str = Query(..., alias="to_attempt", description="Later attempt id"),
) -> AnswerDiffResponse:
    """Compute score and content deltas between two answer attempts."""
    result = get_answer_diff(run_id, from_attempt, to_attempt)
    return AnswerDiffResponse(**result)


@router.get("/answers/{run_id}/{attempt_id}", response_model=AnswerAttemptDetailResponse)
def get_answer_attempt_endpoint(
    run_id: str = PathParam(..., description="Run ID or 'latest'"),
    attempt_id: str = PathParam(..., description="Attempt ID"),
) -> AnswerAttemptDetailResponse:
    """Load full detail for a single answer attempt."""
    result = get_answer_attempt(run_id, attempt_id)
    return AnswerAttemptDetailResponse(**result)


@router.get("/profile", response_model=ProfileShowResponse)
def get_profile_endpoint(
    topic: str | None = Query(None, description="Filter by topic"),
) -> ProfileShowResponse:
    """Get skill profile."""
    result = get_skill_profile(topic)
    return ProfileShowResponse(**result)


@router.get("/profile/{topic}", response_model=ProfileShowResponse)
def get_profile_by_topic_endpoint(
    topic: str = PathParam(..., description="Topic"),
) -> ProfileShowResponse:
    """Get skill profile for a specific topic."""
    result = get_skill_profile(topic)
    return ProfileShowResponse(**result)


@router.get("/curriculum", response_model=CurriculumResponse)
def get_curriculum_endpoint() -> CurriculumResponse:
    """Get full curriculum overview with profile, latest report, and next task."""
    result = get_curriculum()
    return CurriculumResponse(**result)


@router.get("/reports/{run_id}", response_model=LearningReportResponse)
def get_learning_report_endpoint(
    run_id: str = PathParam(..., description="Run ID"),
) -> LearningReportResponse:
    """Get learning report for a run."""
    result = get_learning_report(run_id)
    return LearningReportResponse(**result)


@router.get("/reports/latest", response_model=LearningReportResponse)
def get_latest_learning_report_endpoint() -> LearningReportResponse:
    """Get learning report for the latest run."""
    result = get_learning_report()
    return LearningReportResponse(**result)


@router.get("/next-task/{run_id}", response_model=NextTaskResponse)
def get_next_task_endpoint(
    run_id: str = PathParam(..., description="Run ID"),
) -> NextTaskResponse:
    """Get next task recommendation for a run."""
    result = get_next_task(run_id)
    return NextTaskResponse(**result)


@router.get("/next-task/latest", response_model=NextTaskResponse)
def get_latest_next_task_endpoint() -> NextTaskResponse:
    """Get next task recommendation for the latest run."""
    result = get_next_task()
    return NextTaskResponse(**result)
