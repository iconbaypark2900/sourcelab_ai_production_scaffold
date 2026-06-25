"""Lesson generation golden eval for SourceLab AI.

Instruction:
- Evaluate lesson generation against golden test cases.
- Checks that lesson packages validate.
- Checks that generated lessons include source IDs.
- Checks that no unsupported high-risk claims pass.
- Uses source pack eval fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

from sourcelab.evals.schemas import GoldenEvalFailure, GoldenEvalReport


def load_lesson_gold_cases(project_root: Path, pack_name: str) -> list[dict]:
    """Load lesson golden eval cases from source pack."""
    eval_path = project_root / "data" / "source_packs" / pack_name / "evals" / "lesson_gold.json"
    if not eval_path.exists():
        return []

    try:
        data = json.loads(eval_path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("cases", [])
    except (json.JSONDecodeError, KeyError):
        return []


def run_lesson_gold_eval(
    project_root: Path,
    pack_name: str,
    generate_fn,
) -> GoldenEvalReport:
    """Run lesson generation golden eval.

    Args:
        project_root: Project root directory.
        pack_name: Source pack name.
        generate_fn: Function that takes (topic, difficulty, task_format) and returns dict with
                     'package', 'harness_passed', 'verification', and optional 'error'.

    Returns:
        GoldenEvalReport with pass/fail status.
    """
    cases = load_lesson_gold_cases(project_root, pack_name)
    total = len(cases)
    passed = 0
    failures = []

    for idx, case in enumerate(cases):
        topic = case.get("topic", "")
        difficulty = case.get("difficulty", 3)
        task_format = case.get("task_format", "architecture_review")
        required_sources = case.get("required_source_ids", [])
        forbidden_claims = case.get("forbidden_claims", [])
        description = case.get("description", f"Case {idx + 1}")

        if not topic:
            failures.append(GoldenEvalFailure(
                case_index=idx,
                case_description=description,
                expected="Non-empty topic",
                actual="Empty topic",
                details="Invalid test case configuration",
            ))
            continue

        try:
            result = generate_fn(topic, difficulty, task_format)

            if "error" in result and result["error"]:
                failures.append(GoldenEvalFailure(
                    case_index=idx,
                    case_description=description,
                    expected="Successful generation",
                    actual=f"Error: {result['error']}",
                    details=f"Topic: {topic}",
                ))
                continue

            package = result.get("package", {})
            harness_passed = result.get("harness_passed", False)
            verification = result.get("verification", {})

            # Check package exists and has required fields
            if not package:
                failures.append(GoldenEvalFailure(
                    case_index=idx,
                    case_description=description,
                    expected="Valid lesson package",
                    actual="Empty package",
                    details=f"Topic: {topic}",
                ))
                continue

            # Check source IDs are present
            source_ids = package.get("source_ids", [])
            if required_sources and not any(s in source_ids for s in required_sources):
                failures.append(GoldenEvalFailure(
                    case_index=idx,
                    case_description=description,
                    expected=f"Source IDs including: {required_sources}",
                    actual=f"Source IDs: {source_ids}",
                    details=f"Topic: {topic}",
                ))
                continue

            # Check harness passed
            if not harness_passed:
                failures.append(GoldenEvalFailure(
                    case_index=idx,
                    case_description=description,
                    expected="Harness validation passed",
                    actual="Harness validation failed",
                    details=f"Topic: {topic}",
                ))
                continue

            # Check verification - no unsupported high-risk claims
            high_risk = verification.get("unsupported_high_risk", 0)
            if high_risk > 0:
                failures.append(GoldenEvalFailure(
                    case_index=idx,
                    case_description=description,
                    expected="No unsupported high-risk claims",
                    actual=f"{high_risk} unsupported high-risk claims",
                    details=f"Topic: {topic}",
                ))
                continue

            # Check forbidden claims don't appear in supported claims
            if forbidden_claims:
                claim_map = verification.get("claim_map", [])
                for claim_record in claim_map:
                    claim_text = claim_record.get("claim", "").lower()
                    for forbidden in forbidden_claims:
                        if forbidden.lower() in claim_text:
                            if claim_record.get("support_status") == "supported":
                                failures.append(GoldenEvalFailure(
                                    case_index=idx,
                                    case_description=description,
                                    expected=f"Forbidden claim not supported: {forbidden}",
                                    actual=f"Forbidden claim marked as supported",
                                    details=f"Claim: {claim_text[:100]}",
                                ))
                                continue

            passed += 1

        except Exception as e:
            failures.append(GoldenEvalFailure(
                case_index=idx,
                case_description=description,
                expected="Successful generation",
                actual=f"Exception: {e}",
                details=str(e),
            ))

    pass_rate = passed / total if total > 0 else 0.0

    return GoldenEvalReport(
        eval_name="lesson_gold",
        pack_name=pack_name,
        total_cases=total,
        passed_cases=passed,
        failed_cases=len(failures),
        pass_rate=pass_rate,
        failures=failures,
    )
