"""Release manifest schemas for SourceLab AI.

Instruction:
- Pydantic schemas for the local v1 release manifest.
- Captures all release readiness information in a single artifact.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ReleaseManifest(BaseModel):
    """Local v1 release manifest artifact."""

    version: str = "1.0.0"
    release_label: str = "SourceLab Local v1.0 GA"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    project_name: str = "SourceLab AI"

    # Test status
    test_count: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    pytest_status: str = ""

    # Strict release status
    strict_release_status: str = "unknown"
    strict_release_blocking: list[str] = Field(default_factory=list)
    strict_release_warnings: list[str] = Field(default_factory=list)

    # Golden eval status
    golden_eval_pass_rate: float | None = None
    golden_eval_total_cases: int = 0
    golden_eval_passed_cases: int = 0
    golden_eval_status: str = "unknown"
    golden_eval_packs: list[dict[str, Any]] = Field(default_factory=list)

    # Source pack status
    pqc_pack_installed: bool = False
    pqc_pack_source_count: int = 0
    source_validation_status: str = "unknown"

    # Latest demo run
    latest_run_id: str | None = None
    latest_run_topic: str = ""
    latest_run_harness_passed: bool | None = None
    latest_run_answer_score: float | None = None

    # Proof bundle status
    proof_bundle_status: str = "unknown"
    proof_bundle_artifact_count: int = 0

    # Harness status
    harness_status: str = "unknown"
    harness_artifact_count: int = 0

    # Model mode
    model_mode: str = "deterministic"
    model_backend: str = "deterministic"

    # API availability
    api_available: bool = True
    api_routes: list[str] = Field(default_factory=list)

    # Dashboard
    dashboard_launch_command: str = "sourcelab dashboard --launch"

    # Retrieval eval
    retrieval_eval_pass_rate: float | None = None
    retrieval_eval_status: str = "unknown"

    # Known limitations
    known_limitations: list[str] = Field(default_factory=list)

    # Blocking issues
    blocking_issues: list[str] = Field(default_factory=list)

    # Warnings
    warnings: list[str] = Field(default_factory=list)

    # Local v1 packaging status
    doctor_status: str = "unknown"
    init_local_status: str = "unknown"
    smoke_status: str = "unknown"
    package_extras: dict[str, bool] = Field(default_factory=dict)
    docker_available: bool = False
    docker_note: str = ""
    demo_scripts: list[str] = Field(default_factory=list)
    release_notes_path: str = "RELEASE_NOTES_LOCAL_V1_GA.md"
    changelog_path: str = "CHANGELOG.md"
