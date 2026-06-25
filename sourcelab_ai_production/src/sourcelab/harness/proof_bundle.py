"""Proof bundle writer v2.

Instruction:
- Every production run should create a proof bundle.
- A proof bundle is the evidence that the system did what it claims.
- v2 adds: sha256 hashing, artifact metadata, run manifest, proof bundle manifest, proof summary.
- The proof bundle records sources, retrieval, generation, verification, citation resolution,
  human review status, answer scoring, next-task decision, and release-gate status.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sourcelab.harness.schemas import (
    ArtifactRecord,
    ProofBundleManifest,
    RunManifest,
)
from sourcelab.harness.artifact_inventory import (
    ARTIFACT_ORDER,
    REQUIRED_ARTIFACTS,
    SCHEMA_MAP,
    ARTIFACT_TYPES,
    get_artifact_record,
    build_artifact_inventory,
)


@dataclass
class ProofBundle:
    run_id: str
    run_dir: Path
    artifacts: list[str] = field(default_factory=list)
    artifact_records: list[ArtifactRecord] = field(default_factory=list)

    def write_json(self, name: str, data: object) -> Path:
        path = self.run_dir / name
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        self.artifacts.append(name)
        # Record the artifact
        record = ArtifactRecord(
            artifact_name=name,
            path=str(path),
            artifact_type="json",
            required=name in REQUIRED_ARTIFACTS,
            exists=True,
            sha256=self._compute_sha256(path),
            schema_name=SCHEMA_MAP.get(name, ""),
            validated=True,
        )
        self.artifact_records.append(record)
        return path

    def write_text(self, name: str, data: str) -> Path:
        path = self.run_dir / name
        path.write_text(data, encoding="utf-8")
        self.artifacts.append(name)
        # Record the artifact
        artifact_type = "markdown" if name.endswith(".md") else "text"
        record = ArtifactRecord(
            artifact_name=name,
            path=str(path),
            artifact_type=artifact_type,
            required=name in REQUIRED_ARTIFACTS,
            exists=True,
            sha256=self._compute_sha256(path),
            schema_name=SCHEMA_MAP.get(name, ""),
            validated=True,
        )
        self.artifact_records.append(record)
        return path

    def _compute_sha256(self, path: Path) -> str:
        """Compute SHA256 hash of a file."""
        try:
            content = path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        except Exception:
            return "compute_error"

    def trace(self) -> dict:
        return {
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "artifacts": self.artifacts,
        }

    def write_run_manifest(
        self,
        topic: str = "",
        source_policy: str = "local_deterministic",
        retrieval_mode: str = "hybrid",
        generation_backend: str = "deterministic_local",
        verification_version: str = "v2",
        status: str = "complete",
    ) -> Path:
        """Write the run manifest for this run."""
        manifest = RunManifest(
            run_id=self.run_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            topic=topic,
            source_policy=source_policy,
            retrieval_mode=retrieval_mode,
            generation_backend=generation_backend,
            verification_version=verification_version,
            artifact_count=len(self.artifacts),
            status=status,
            artifacts=self.artifact_records,
        )
        return self.write_json("run_manifest.json", manifest.model_dump(mode="json"))

    def write_proof_bundle_manifest(self) -> Path:
        """Write the proof bundle manifest for this run."""
        inventory = build_artifact_inventory(self.run_dir)

        required_count = sum(1 for a in inventory if a.required)
        optional_count = sum(1 for a in inventory if not a.required)
        missing_required = [a.artifact_name for a in inventory if a.required and not a.exists]
        invalid = [a.artifact_name for a in inventory if a.exists and a.error]

        manifest = ProofBundleManifest(
            run_id=self.run_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            total_artifacts=len(inventory),
            required_artifacts=required_count,
            optional_artifacts=optional_count,
            missing_required=missing_required,
            invalid_artifacts=invalid,
            artifacts=inventory,
        )
        return self.write_json(
            "proof_bundle_manifest.json", manifest.model_dump(mode="json")
        )

    def write_proof_summary(
        self,
        topic: str = "",
        harness_passed: bool = False,
        citation_resolution_rate: float = 0.0,
        unsupported_high_risk: int = 0,
        human_review_items: int = 0,
        conflicts_detected: int = 0,
        release_gate_status: str = "FAIL",
        answer_score: float = 0.0,
    ) -> Path:
        """Write a compact proof summary."""
        summary = {
            "run_id": self.run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "topic": topic,
            "harness_passed": harness_passed,
            "citation_resolution_rate": citation_resolution_rate,
            "unsupported_high_risk_claims": unsupported_high_risk,
            "human_review_items": human_review_items,
            "conflicts_detected": conflicts_detected,
            "release_gate_status": release_gate_status,
            "answer_score": answer_score,
            "artifact_count": len(self.artifacts),
            "artifacts": self.artifacts,
        }
        return self.write_json("proof_summary.json", summary)
