"""Evaluation routes.

Instruction:
- Map eval CLI commands to REST endpoints.
- Run golden evals and show latest results.
- Show per-pack eval history for trend tracking.
- Show per-pack eval thresholds and compliance.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from sourcelab.api.schemas import (
    EvalsHistoryResponse,
    EvalsLatestResponse,
    EvalsRunRequest,
    EvalsRunResponse,
    GoldenEvalSummaryResponse,
    PackThresholdResponse,
)
from sourcelab.api.services import (
    evals_history_api,
    evals_latest_api,
    evals_thresholds_api,
    run_evals_api,
)

router = APIRouter()


@router.post("/run", response_model=EvalsRunResponse)
def run_evals(request: EvalsRunRequest) -> EvalsRunResponse:
    """Run golden evals for a source pack."""
    result = run_evals_api(
        pack_name=request.pack_name,
        eval_type=request.eval_type,
    )
    return EvalsRunResponse(**result)


@router.get("/latest/{pack_name}", response_model=EvalsLatestResponse)
def evals_latest(pack_name: str) -> EvalsLatestResponse:
    """Show latest eval results for a source pack."""
    result = evals_latest_api(pack_name)
    return EvalsLatestResponse(**result)


@router.get("/history/{pack_name}", response_model=EvalsHistoryResponse)
def evals_history(
    pack_name: str,
    limit: int = Query(50, ge=1, le=500),
) -> EvalsHistoryResponse:
    """Return eval history (newest first) for a source pack."""
    result = evals_history_api(pack_name, limit=limit)
    return EvalsHistoryResponse(**result)


@router.get("/thresholds/{pack_name}", response_model=PackThresholdResponse)
def evals_thresholds(pack_name: str) -> PackThresholdResponse:
    """Return per-pack eval thresholds and compliance against the latest summary."""
    result = evals_thresholds_api(pack_name)
    return PackThresholdResponse(**result)
