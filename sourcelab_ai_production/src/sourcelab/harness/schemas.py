"""Harness schemas for Proof Bundle v2.

Instruction:
- These schemas define the complete harness and proof bundle output.
- Every field must be serializable to JSON for the proof bundle.
- Keep schemas explicit so the harness can validate them.
- RunManifest records every artifact produced by a run.
- HarnessReport includes structured checks with pass/fail status.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ArtifactRecord(BaseModel):
    """Record of a single artifact in the proof bundle."""

    artifact_name: str
    path: str
    artifact_type: Literal["json", "markdown", "text", "binary"] = "json"
    required: bool = True
    exists: bool = False
    sha256: str = ""
    schema_name: str = ""
    validated: bool = False
    error: str | None = None


class HarnessCheck(BaseModel):
    """A single harness validation check."""

    check_name: str
    passed: bool
    severity: Literal["blocking", "warning", "info"] = "blocking"
    message: str = ""
    details: dict = Field(default_factory=dict)


class RunManifest(BaseModel):
    """Manifest of all artifacts produced by a run."""

    run_id: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    topic: str = ""
    source_policy: str = "local_deterministic"
    retrieval_mode: str = "hybrid"
    generation_backend: str = "deterministic_local"
    verification_version: str = "v2"
    artifact_count: int = 0
    status: Literal["complete", "incomplete", "failed"] = "complete"
    artifacts: list[ArtifactRecord] = Field(default_factory=list)


class ProofBundleManifest(BaseModel):
    """Manifest of the entire proof bundle."""

    run_id: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    total_artifacts: int = 0
    required_artifacts: int = 0
    optional_artifacts: int = 0
    missing_required: list[str] = Field(default_factory=list)
    invalid_artifacts: list[str] = Field(default_factory=list)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)


class HarnessReport(BaseModel):
    """Complete harness validation report."""

    passed: bool = False
    checks: list[HarnessCheck] = Field(default_factory=list)
    blocking_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    artifact_count: int = 0
    run_id: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class ReleaseGateReport(BaseModel):
    """Release gate verification report."""

    status: Literal["PASS", "FAIL", "REVIEW"] = "FAIL"
    release_candidate: str = "local"
    docs_check: Literal["PASS", "FAIL"] = "FAIL"
    module_check: Literal["PASS", "FAIL"] = "FAIL"
    proof_bundle_check: Literal["PASS", "FAIL"] = "FAIL"
    harness_check: Literal["PASS", "FAIL"] = "FAIL"
    unsupported_high_risk_claims: int = 0
    citation_resolution_rate: float = 0.0
    blocking_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RunStatus(BaseModel):
    """Status of a production run."""

    run_id: str
    run_dir: str
    topic: str = ""
    harness_passed: bool = False
    proof_bundle_complete: bool = False
    release_gate_status: str = "FAIL"
    artifact_count: int = 0
    created_at: str = ""
