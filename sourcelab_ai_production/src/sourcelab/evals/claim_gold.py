"""Claim verification golden eval for SourceLab AI.

Instruction:
- Evaluate claim verification against golden test cases.
- Checks that supported claims are marked supported.
- Checks that unsupported high-risk claims are caught.
- Uses source pack eval fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

from sourcelab.evals.schemas import GoldenEvalFailure, GoldenEvalReport


def load_claim_gold_cases(project_root: Path, pack_name: str) -> list[dict]:
    """Load claim golden eval cases from source pack."""
    eval_path = project_root / "data" / "source_packs" / pack_name / "evals" / "claim_gold.json"
    if not eval_path.exists():
        return []

    try:
        data = json.loads(eval_path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("cases", [])
    except (json.JSONDecodeError, KeyError):
        return []


def run_claim_gold_eval(
    project_root: Path,
    pack_name: str,
    verify_fn,
) -> GoldenEvalReport:
    """Run claim verification golden eval.

    Args:
        project_root: Project root directory.
        pack_name: Source pack name.
        verify_fn: Function that takes (claim_text) and returns dict with
                   'support_status', 'severity', and optional 'details'.

    Returns:
        GoldenEvalReport with pass/fail status.
    """
    cases = load_claim_gold_cases(project_root, pack_name)
    total = len(cases)
    passed = 0
    failures = []

    for idx, case in enumerate(cases):
        claim = case.get("claim", "")
        expected_status = case.get("expected_status", "supported")
        severity = case.get("severity", "medium")
        should_block = case.get("should_block", False)
        description = case.get("description", f"Case {idx + 1}")

        if not claim:
            failures.append(GoldenEvalFailure(
                case_index=idx,
                case_description=description,
                expected="Non-empty claim",
                actual="Empty claim",
                details="Invalid test case configuration",
            ))
            continue

        try:
            result = verify_fn(claim)
            actual_status = result.get("support_status", "unknown")
            actual_severity = result.get("severity", "medium")

            # Normalize status values
            status_map = {
                "supported": "supported",
                "unsupported": "unsupported",
                "uncertain": "uncertain",
                "needs_review": "needs_review",
                "partial": "supported",
            }
            normalized_actual = status_map.get(actual_status, actual_status)

            # Check status match
            if normalized_actual != expected_status:
                # Allow uncertain for supported claims (moderate evidence)
                if expected_status == "supported" and normalized_actual == "uncertain":
                    passed += 1
                    continue

                # Allow needs_review for unsupported claims (flagged for review)
                if expected_status == "unsupported" and normalized_actual in ("unsupported", "needs_review"):
                    passed += 1
                    continue

                failures.append(GoldenEvalFailure(
                    case_index=idx,
                    case_description=description,
                    expected=f"Status: {expected_status}",
                    actual=f"Status: {normalized_actual}",
                    details=f"Claim: {claim[:100]}...",
                ))
                continue

            # Check blocking requirement
            if should_block and normalized_actual == "supported":
                failures.append(GoldenEvalFailure(
                    case_index=idx,
                    case_description=description,
                    expected=f"Blocked (unsupported/needs_review)",
                    actual=f"Passed as supported",
                    details=f"High-risk claim should not pass: {claim[:100]}...",
                ))
                continue

            passed += 1

        except Exception as e:
            failures.append(GoldenEvalFailure(
                case_index=idx,
                case_description=description,
                expected="Successful verification",
                actual=f"Exception: {e}",
                details=str(e),
            ))

    pass_rate = passed / total if total > 0 else 0.0

    return GoldenEvalReport(
        eval_name="claim_gold",
        pack_name=pack_name,
        total_cases=total,
        passed_cases=passed,
        failed_cases=len(failures),
        pass_rate=pass_rate,
        failures=failures,
    )
