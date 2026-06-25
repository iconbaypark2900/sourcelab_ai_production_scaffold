"""Per-pack golden eval thresholds.

Instruction:
- Each source pack's manifest.json may declare ``eval_thresholds``:
  ``{"min_pass_rate": 0.8, "min_cases": 1, "required_evals": ["retrieval_gold"]}``
- All fields are optional; missing fields fall back to defaults.
- Packs without an explicit ``eval_thresholds`` block use DEFAULT_THRESHOLDS.
- Thresholds are consumed by verify-release --strict, source-pack doctor,
  and the Evals dashboard tab.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_MIN_PASS_RATE: float = 0.8
DEFAULT_MIN_CASES: int = 1


@dataclass
class PackEvalThresholds:
    """Per-pack golden eval thresholds."""

    min_pass_rate: float = DEFAULT_MIN_PASS_RATE
    min_cases: int = DEFAULT_MIN_CASES
    required_evals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_default(self) -> bool:
        return (
            self.min_pass_rate == DEFAULT_MIN_PASS_RATE
            and self.min_cases == DEFAULT_MIN_CASES
            and not self.required_evals
        )


DEFAULT_THRESHOLDS = PackEvalThresholds()


# Built-in threshold presets applied when a pack has no explicit
# eval_thresholds block but is recognized as a strict-release pack.
BUILTIN_THRESHOLDS: dict[str, PackEvalThresholds] = {
    "pqc_v1": PackEvalThresholds(min_pass_rate=1.0),
    "ai_safety_v1": PackEvalThresholds(min_pass_rate=1.0),
}


def _coerce_thresholds(payload: Any) -> PackEvalThresholds:
    """Coerce a manifest ``eval_thresholds`` payload into a typed object."""
    if not isinstance(payload, dict):
        return PackEvalThresholds()

    min_pass_rate_raw = payload.get("min_pass_rate", DEFAULT_MIN_PASS_RATE)
    try:
        min_pass_rate = float(min_pass_rate_raw)
    except (TypeError, ValueError):
        min_pass_rate = DEFAULT_MIN_PASS_RATE
    if min_pass_rate < 0 or min_pass_rate > 1:
        min_pass_rate = DEFAULT_MIN_PASS_RATE

    min_cases_raw = payload.get("min_cases", DEFAULT_MIN_CASES)
    try:
        min_cases = int(min_cases_raw)
    except (TypeError, ValueError):
        min_cases = DEFAULT_MIN_CASES
    if min_cases < 0:
        min_cases = DEFAULT_MIN_CASES

    required_raw = payload.get("required_evals", [])
    if isinstance(required_raw, list):
        required_evals = [str(item) for item in required_raw if item]
    else:
        required_evals = []

    return PackEvalThresholds(
        min_pass_rate=min_pass_rate,
        min_cases=min_cases,
        required_evals=required_evals,
    )


def load_pack_thresholds(
    project_root: Path,
    pack_name: str,
) -> PackEvalThresholds:
    """Load eval thresholds for a pack, with sensible fallbacks.

    Resolution order:
    1. ``<project>/data/source_packs/<pack>/manifest.json`` -> ``eval_thresholds``
    2. ``BUILTIN_THRESHOLDS[pack]`` (e.g. ``pqc_v1`` defaults to 100%)
    3. ``DEFAULT_THRESHOLDS`` (80% pass rate, 1 case minimum)
    """
    manifest_path = project_root / "data" / "source_packs" / pack_name / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            manifest = None
        if manifest:
            payload = manifest.get("eval_thresholds")
            thresholds = _coerce_thresholds(payload)
            # If manifest didn't declare eval_thresholds at all, fall back
            # to builtin or default for this pack name.
            if payload is None and pack_name in BUILTIN_THRESHOLDS:
                return BUILTIN_THRESHOLDS[pack_name]
            if payload is None:
                return DEFAULT_THRESHOLDS
            return thresholds

    return BUILTIN_THRESHOLDS.get(pack_name, DEFAULT_THRESHOLDS)


def write_pack_thresholds(
    project_root: Path,
    pack_name: str,
    thresholds: PackEvalThresholds,
) -> Path:
    """Persist ``eval_thresholds`` to a pack's ``manifest.json``.

    Preserves all other manifest fields. Raises ``FileNotFoundError`` if
    the manifest does not exist; raises ``ValueError`` if the manifest
    is unparseable.
    """
    manifest_path = project_root / "data" / "source_packs" / pack_name / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid manifest JSON for {pack_name}: {exc}") from exc

    if not isinstance(manifest, dict):
        raise ValueError(f"Manifest for {pack_name} is not a JSON object")

    manifest["eval_thresholds"] = thresholds.to_dict()
    manifest_path.write_text(
        json.dumps(manifest, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return manifest_path


@dataclass
class ThresholdCheck:
    """A single threshold check result."""

    name: str
    passed: bool
    actual: float | int | None
    required: float | int | None
    message: str


@dataclass
class ThresholdEvaluation:
    """Result of evaluating a summary against per-pack thresholds."""

    pack_name: str
    thresholds: PackEvalThresholds
    overall_pass_rate: float | None
    total_cases: int
    total_failed: int
    eval_names: list[str]
    checks: list[ThresholdCheck]
    meets_thresholds: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack_name": self.pack_name,
            "thresholds": self.thresholds.to_dict(),
            "overall_pass_rate": self.overall_pass_rate,
            "total_cases": self.total_cases,
            "total_failed": self.total_failed,
            "eval_names": self.eval_names,
            "checks": [asdict(c) for c in self.checks],
            "meets_thresholds": self.meets_thresholds,
        }


def evaluate_against_thresholds(
    pack_name: str,
    summary: dict | None,
    thresholds: PackEvalThresholds,
) -> ThresholdEvaluation:
    """Evaluate a golden eval summary against per-pack thresholds.

    Returns a ``ThresholdEvaluation`` describing each individual check
    and an overall ``meets_thresholds`` flag.
    """
    if summary is None:
        return ThresholdEvaluation(
            pack_name=pack_name,
            thresholds=thresholds,
            overall_pass_rate=None,
            total_cases=0,
            total_failed=0,
            eval_names=[],
            checks=[
                ThresholdCheck(
                    name="summary_present",
                    passed=False,
                    actual=None,
                    required=None,
                    message="No eval summary found for this pack",
                )
            ],
            meets_thresholds=False,
        )

    overall_pass_rate = summary.get("overall_pass_rate")
    total_cases = int(summary.get("total_cases", 0) or 0)
    total_failed = int(summary.get("total_failed", 0) or 0)
    eval_names: list[str] = []
    for report in summary.get("eval_reports", []) or []:
        name = report.get("eval_name")
        if name:
            eval_names.append(name)

    checks: list[ThresholdCheck] = []

    pass_rate_check = ThresholdCheck(
        name="min_pass_rate",
        passed=(
            overall_pass_rate is not None
            and overall_pass_rate >= thresholds.min_pass_rate
        ),
        actual=overall_pass_rate,
        required=thresholds.min_pass_rate,
        message=(
            f"Pass rate {overall_pass_rate:.1%} below threshold {thresholds.min_pass_rate:.1%}"
            if overall_pass_rate is not None
            and overall_pass_rate < thresholds.min_pass_rate
            else f"Pass rate {overall_pass_rate:.1%} meets threshold {thresholds.min_pass_rate:.1%}"
        ),
    )
    checks.append(pass_rate_check)

    cases_check = ThresholdCheck(
        name="min_cases",
        passed=total_cases >= thresholds.min_cases,
        actual=total_cases,
        required=thresholds.min_cases,
        message=(
            f"Total cases {total_cases} below minimum {thresholds.min_cases}"
            if total_cases < thresholds.min_cases
            else f"Total cases {total_cases} meets minimum {thresholds.min_cases}"
        ),
    )
    checks.append(cases_check)

    for required_eval in thresholds.required_evals:
        present = required_eval in eval_names
        checks.append(
            ThresholdCheck(
                name=f"required_eval:{required_eval}",
                passed=present,
                actual=required_eval if present else None,
                required=required_eval,
                message=(
                    f"Required eval {required_eval} present"
                    if present
                    else f"Required eval {required_eval} missing from summary"
                ),
            )
        )

    meets = all(check.passed for check in checks)
    return ThresholdEvaluation(
        pack_name=pack_name,
        thresholds=thresholds,
        overall_pass_rate=overall_pass_rate,
        total_cases=total_cases,
        total_failed=total_failed,
        eval_names=eval_names,
        checks=checks,
        meets_thresholds=meets,
    )
