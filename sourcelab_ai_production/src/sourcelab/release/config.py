"""Local v1 readiness thresholds.

Instruction:
- Default thresholds for local v1 release verification.
- Used by strict release gate and release checklist.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReleaseThresholds:
    """Thresholds for local v1 release verification."""

    retrieval_min_pass_rate: float = 0.8
    golden_eval_min_pass_rate: float = 0.8
    citation_resolution_required: float = 1.0
    unsupported_high_risk_allowed: int = 0
    harness_must_pass: bool = True
    strict_release_must_pass: bool = True

    def to_dict(self) -> dict:
        return {
            "retrieval_min_pass_rate": self.retrieval_min_pass_rate,
            "golden_eval_min_pass_rate": self.golden_eval_min_pass_rate,
            "citation_resolution_required": self.citation_resolution_required,
            "unsupported_high_risk_allowed": self.unsupported_high_risk_allowed,
            "harness_must_pass": self.harness_must_pass,
            "strict_release_must_pass": self.strict_release_must_pass,
        }


def get_default_thresholds() -> ReleaseThresholds:
    """Return default release thresholds for local v1."""
    return ReleaseThresholds()
