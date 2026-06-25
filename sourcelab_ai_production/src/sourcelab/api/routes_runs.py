"""Run routes.

Instruction:
- Map run CLI commands to REST endpoints.
- Use thin service wrappers from services.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Path as PathParam, Query

from sourcelab.api.schemas import (
    ArtifactListResponse,
    ArtifactRowResponse,
    AnswerCompareResponse,
    HarnessReportResponse,
    ProofBundleResponse,
    RunArtifactContentResponse,
    RunComparisonResponse,
    RunListResponse,
    RunSummaryResponse,
)
from sourcelab.api.services import (
    compare_run_ids,
    compare_run_answers,
    get_harness_report,
    get_proof_bundle,
    get_run_artifact_content,
    get_run_artifacts,
    get_run_summary,
    get_latest_run_summary,
    list_all_runs,
)

router = APIRouter()


@router.get("/", response_model=RunListResponse)
def list_runs_endpoint() -> RunListResponse:
    """List all runs."""
    runs = list_all_runs()
    return RunListResponse(
        runs=[RunSummaryResponse(**r) for r in runs],
        total=len(runs),
    )


@router.get("/latest", response_model=RunSummaryResponse)
def get_latest_run_endpoint() -> RunSummaryResponse:
    """Get the latest run summary."""
    run = get_latest_run_summary()
    if run is None:
        return RunSummaryResponse(run_id="", run_dir="", topic="No runs found")
    return RunSummaryResponse(**run)


@router.get("/compare", response_model=RunComparisonResponse)
def compare_runs_endpoint(
    run_ids: str = Query(..., description="Comma-separated run IDs (minimum 2)"),
) -> RunComparisonResponse:
    """Compare two or more runs from artifacts."""
    ids = [part.strip() for part in run_ids.split(",") if part.strip()]
    result = compare_run_ids(ids)
    return RunComparisonResponse(**result)


@router.get("/answers/compare", response_model=AnswerCompareResponse)
def compare_run_answers_endpoint(
    run_ids: str = Query(..., description="Comma-separated run IDs (minimum 2)"),
) -> AnswerCompareResponse:
    """Compare learner answer attempts across two or more runs."""
    ids = [part.strip() for part in run_ids.split(",") if part.strip()]
    result = compare_run_answers(ids)
    return AnswerCompareResponse(**result)


@router.get("/{run_id}", response_model=RunSummaryResponse)
def get_run_by_id(
    run_id: str = PathParam(..., description="Run ID"),
) -> RunSummaryResponse:
    """Get a specific run summary."""
    run = get_run_summary(run_id)
    return RunSummaryResponse(**run)


@router.get("/{run_id}/artifacts", response_model=ArtifactListResponse)
def get_run_artifacts_endpoint(
    run_id: str = PathParam(..., description="Run ID"),
) -> ArtifactListResponse:
    """Get artifacts for a run."""
    artifacts = get_run_artifacts(run_id)
    return ArtifactListResponse(
        artifacts=[ArtifactRowResponse(**a) for a in artifacts],
        total=len(artifacts),
    )


@router.get("/{run_id}/artifacts/{artifact_name}", response_model=RunArtifactContentResponse)
def get_run_artifact_content_endpoint(
    run_id: str = PathParam(..., description="Run ID"),
    artifact_name: str = PathParam(..., description="Artifact file name within the run"),
) -> RunArtifactContentResponse:
    """Get the parsed content of a single artifact for a run (read-only)."""
    result = get_run_artifact_content(run_id, artifact_name)
    return RunArtifactContentResponse(**result)


@router.get("/{run_id}/proof", response_model=ProofBundleResponse)
def get_proof_bundle_endpoint(
    run_id: str = PathParam(..., description="Run ID"),
) -> ProofBundleResponse:
    """Get proof bundle for a run."""
    result = get_proof_bundle(run_id)
    return ProofBundleResponse(**result)


@router.get("/latest/proof", response_model=ProofBundleResponse)
def get_latest_proof_bundle_endpoint() -> ProofBundleResponse:
    """Get proof bundle for the latest run."""
    result = get_proof_bundle()
    return ProofBundleResponse(**result)


@router.get("/{run_id}/harness", response_model=HarnessReportResponse)
def get_harness_report_endpoint(
    run_id: str = PathParam(..., description="Run ID"),
) -> HarnessReportResponse:
    """Get harness report for a run."""
    result = get_harness_report(run_id)
    return HarnessReportResponse(**result)


@router.get("/latest/harness", response_model=HarnessReportResponse)
def get_latest_harness_report_endpoint() -> HarnessReportResponse:
    """Get harness report for the latest run."""
    result = get_harness_report()
    return HarnessReportResponse(**result)
