"""Schema validators for harness artifacts.

Instruction:
- Validate JSON artifacts against their expected Pydantic schemas.
- Keep validators local and deterministic.
- Return structured validation results for the harness report.
"""

from __future__ import annotations

import json
from pathlib import Path

from sourcelab.harness.schemas import HarnessCheck


def _load_json(path: Path) -> tuple[dict | list | None, str | None]:
    """Load and parse a JSON file. Returns (data, error)."""
    try:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
        return data, None
    except FileNotFoundError:
        return None, f"File not found: {path}"
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}"


def validate_generated_lesson_package(path: Path) -> HarnessCheck:
    """Validate generated_lesson_package.json schema."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_generated_lesson_package",
            passed=False,
            message=error,
        )

    required_fields = ["topic"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return HarnessCheck(
            check_name="schema_generated_lesson_package",
            passed=False,
            message=f"Missing required fields: {missing}",
        )

    return HarnessCheck(
        check_name="schema_generated_lesson_package",
        passed=True,
        message="Valid GeneratedLessonPackage",
    )


def validate_rubric(path: Path) -> HarnessCheck:
    """Validate rubric.json schema."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_rubric",
            passed=False,
            message=error,
        )

    if "criteria" not in data:
        return HarnessCheck(
            check_name="schema_rubric",
            passed=False,
            message="Missing 'criteria' field",
        )

    criteria = data["criteria"]
    if not criteria:
        return HarnessCheck(
            check_name="schema_rubric",
            passed=False,
            message="Rubric has no criteria",
        )

    # Check weights sum to 1.0
    total_weight = sum(c.get("weight", 0) for c in criteria)
    if abs(total_weight - 1.0) > 0.01:
        return HarnessCheck(
            check_name="schema_rubric",
            passed=False,
            message=f"Rubric weights sum to {total_weight:.4f}, expected 1.0",
        )

    return HarnessCheck(
        check_name="schema_rubric",
        passed=True,
        message=f"Valid rubric with {len(criteria)} criteria",
    )


def validate_answer_key(path: Path) -> HarnessCheck:
    """Validate answer_key.json schema."""
    data, error = _load_json(path)
    if error:
        # Try the markdown version
        md_path = path.with_suffix(".md")
        if md_path.exists():
            content = md_path.read_text(encoding="utf-8")
            if "Source References" in content:
                return HarnessCheck(
                    check_name="schema_answer_key",
                    passed=True,
                    message="Valid answer key (markdown format with Source References)",
                )
        return HarnessCheck(
            check_name="schema_answer_key",
            passed=False,
            message=error,
        )

    # Check for source references
    source_references = data.get("source_references", [])
    if not source_references:
        return HarnessCheck(
            check_name="schema_answer_key",
            passed=False,
            message="Answer key has no source references",
        )

    # Check each reference has required fields
    for i, ref in enumerate(source_references):
        if not ref.get("source_id"):
            return HarnessCheck(
                check_name="schema_answer_key",
                passed=False,
                message=f"Source reference {i} missing source_id",
            )
        if not ref.get("chunk_id"):
            return HarnessCheck(
                check_name="schema_answer_key",
                passed=False,
                message=f"Source reference {i} missing chunk_id",
            )

    return HarnessCheck(
        check_name="schema_answer_key",
        passed=True,
        message=f"Valid answer key with {len(source_references)} source references",
    )


def validate_generation_trace(path: Path) -> HarnessCheck:
    """Validate generation_trace.json schema."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_generation_trace",
            passed=False,
            message=error,
        )

    # Check for source_ids and chunk_ids
    source_ids = data.get("source_ids", [])
    chunk_ids = data.get("chunk_ids", [])

    if not source_ids:
        return HarnessCheck(
            check_name="schema_generation_trace",
            passed=False,
            message="Generation trace missing source_ids",
        )

    if not chunk_ids:
        return HarnessCheck(
            check_name="schema_generation_trace",
            passed=False,
            message="Generation trace missing chunk_ids",
        )

    # Check for fail_closed_reason
    if data.get("fail_closed_reason"):
        return HarnessCheck(
            check_name="schema_generation_trace",
            passed=False,
            message=f"Generation failed closed: {data['fail_closed_reason']}",
        )

    return HarnessCheck(
        check_name="schema_generation_trace",
        passed=True,
        message=f"Valid generation trace with {len(source_ids)} sources",
    )


def validate_verification_report(path: Path) -> HarnessCheck:
    """Validate verification_report.json schema."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_verification_report",
            passed=False,
            message=error,
        )

    # Check summary exists
    summary = data.get("summary", {})
    if not summary:
        return HarnessCheck(
            check_name="schema_verification_report",
            passed=False,
            message="Verification report missing summary",
        )

    # Check release gate status
    release_status = summary.get("release_gate_status", "FAIL")
    if release_status == "FAIL":
        blocking_reasons = data.get("blocking_reasons", [])
        return HarnessCheck(
            check_name="schema_verification_report",
            passed=False,
            severity="warning",
            message=f"Verification gate: {', '.join(blocking_reasons)}",
        )

    return HarnessCheck(
        check_name="schema_verification_report",
        passed=True,
        message=f"Verification report status: {release_status}",
    )


def validate_citation_resolution(path: Path) -> HarnessCheck:
    """Validate citation_resolution.json schema."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_citation_resolution",
            passed=False,
            message=error,
        )

    resolution_rate = data.get("resolution_rate", 0)
    unsupported_high_risk = data.get("unsupported_high_risk", 0)

    if unsupported_high_risk > 0:
        return HarnessCheck(
            check_name="schema_citation_resolution",
            passed=False,
            message=f"{unsupported_high_risk} high-risk claims unsupported",
        )

    return HarnessCheck(
        check_name="schema_citation_resolution",
        passed=True,
        message=f"Citation resolution rate: {resolution_rate:.2%}",
    )


def validate_human_review_queue(path: Path) -> HarnessCheck:
    """Validate human_review_queue.json schema."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_human_review_queue",
            passed=False,
            message=error,
        )

    total_items = data.get("total_items", 0)
    high_priority = data.get("high_priority", 0)

    if high_priority > 0:
        return HarnessCheck(
            check_name="schema_human_review_queue",
            passed=False,
            severity="warning",
            message=f"{high_priority} high-priority items require human review",
        )

    return HarnessCheck(
        check_name="schema_human_review_queue",
        passed=True,
        message=f"Human review queue: {total_items} items",
    )


def validate_answer_submission(path: Path) -> HarnessCheck:
    """Validate answer_submission.json schema."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_answer_submission",
            passed=False,
            message=error,
        )

    required_fields = ["topic", "run_id", "answer_text"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return HarnessCheck(
            check_name="schema_answer_submission",
            passed=False,
            message=f"Missing required fields: {missing}",
        )

    answer_text = data.get("answer_text", "")
    if not answer_text or not answer_text.strip():
        return HarnessCheck(
            check_name="schema_answer_submission",
            passed=False,
            message="Answer text is empty",
        )

    return HarnessCheck(
        check_name="schema_answer_submission",
        passed=True,
        message=f"Valid answer submission for topic: {data['topic']}",
    )


def validate_answer_review(path: Path) -> HarnessCheck:
    """Validate answer_review.json schema (v2 with rubric-based scoring)."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_answer_review",
            passed=False,
            message=error,
        )

    # Check overall_score is present and in range
    overall_score = data.get("overall_score")
    if overall_score is None:
        return HarnessCheck(
            check_name="schema_answer_review",
            passed=False,
            message="Answer review missing overall_score",
        )

    if not (0.0 <= overall_score <= 1.0):
        return HarnessCheck(
            check_name="schema_answer_review",
            passed=False,
            message=f"overall_score {overall_score} out of range [0.0, 1.0]",
        )

    # Check criterion_scores is present and non-empty
    criterion_scores = data.get("criterion_scores", [])
    if not criterion_scores:
        return HarnessCheck(
            check_name="schema_answer_review",
            passed=False,
            message="Answer review missing criterion_scores",
        )

    # Check each criterion has required fields
    for i, cs in enumerate(criterion_scores):
        if "criterion_name" not in cs:
            return HarnessCheck(
                check_name="schema_answer_review",
                passed=False,
                message=f"Criterion score {i} missing 'criterion_name' field",
            )
        score = cs.get("score")
        if score is None or not (0.0 <= score <= 1.0):
            return HarnessCheck(
                check_name="schema_answer_review",
                passed=False,
                message=f"Criterion '{cs.get('criterion_name', i)}' score {score} out of range [0.0, 1.0]",
            )

    # Check strengths and weaknesses are lists
    strengths = data.get("strengths", [])
    weaknesses = data.get("weaknesses", [])
    if not isinstance(strengths, list):
        return HarnessCheck(
            check_name="schema_answer_review",
            passed=False,
            message="strengths must be a list",
        )
    if not isinstance(weaknesses, list):
        return HarnessCheck(
            check_name="schema_answer_review",
            passed=False,
            message="weaknesses must be a list",
        )

    rubric_alignment = data.get("rubric_alignment_score")
    uncapped_score = data.get("uncapped_score")
    if rubric_alignment is not None and uncapped_score is not None:
        if uncapped_score + 1e-6 < rubric_alignment:
            return HarnessCheck(
                check_name="schema_answer_review",
                passed=False,
                message=(
                    f"uncapped_score {uncapped_score} is below rubric_alignment_score {rubric_alignment}"
                ),
            )
        cap_reason = data.get("cap_reason", "")
        if overall_score + 1e-6 < uncapped_score and not cap_reason:
            return HarnessCheck(
                check_name="schema_answer_review",
                passed=False,
                message="overall_score is capped below uncapped_score but cap_reason is missing",
            )

    return HarnessCheck(
        check_name="schema_answer_review",
        passed=True,
        message=f"Answer review score: {overall_score:.2%} with {len(criterion_scores)} criteria",
    )


def validate_source_grounding_review(path: Path) -> HarnessCheck:
    """Validate source_grounding_review.json schema."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_source_grounding_review",
            passed=False,
            message=error,
        )

    # Check concept-overlap grounding score is present and in range
    grounding_score = data.get("source_grounding_score")
    if grounding_score is None:
        return HarnessCheck(
            check_name="schema_source_grounding_review",
            passed=False,
            message="Source grounding review missing source_grounding_score (concept overlap evidence score)",
        )

    if not (0.0 <= grounding_score <= 1.0):
        return HarnessCheck(
            check_name="schema_source_grounding_review",
            passed=False,
            message=f"source_grounding_score {grounding_score} out of range [0.0, 1.0]",
        )

    # Check matched_sources and unsupported_phrases are lists
    matched_sources = data.get("matched_sources", [])
    unsupported_phrases = data.get("unsupported_phrases", [])
    if not isinstance(matched_sources, list):
        return HarnessCheck(
            check_name="schema_source_grounding_review",
            passed=False,
            message="matched_sources must be a list",
        )
    if not isinstance(unsupported_phrases, list):
        return HarnessCheck(
            check_name="schema_source_grounding_review",
            passed=False,
            message="unsupported_phrases must be a list",
        )

    return HarnessCheck(
        check_name="schema_source_grounding_review",
        passed=True,
        message=f"Source grounding score: {grounding_score:.2%}, matched: {len(matched_sources)} sources",
    )


def validate_mastery_update(path: Path) -> HarnessCheck:
    """Validate mastery_update.json schema."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_mastery_update",
            passed=False,
            message=error,
        )

    required_fields = ["topic", "topic_mastery_before", "topic_mastery_after", "difficulty_multiplier"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return HarnessCheck(
            check_name="schema_mastery_update",
            passed=False,
            message=f"Missing required fields: {missing}",
        )

    mastery_before = data.get("topic_mastery_before", 0)
    mastery_after = data.get("topic_mastery_after", 0)
    multiplier = data.get("difficulty_multiplier", 0)

    # Validate ranges
    for name, val in [("mastery_before", mastery_before), ("mastery_after", mastery_after), ("multiplier", multiplier)]:
        if not (0.0 <= val <= 1.0):
            return HarnessCheck(
                check_name="schema_mastery_update",
                passed=False,
                message=f"{name} {val} out of range [0.0, 1.0]",
            )

    return HarnessCheck(
        check_name="schema_mastery_update",
        passed=True,
        message=f"Mastery update: {mastery_before:.2%} -> {mastery_after:.2%}",
    )


def validate_skill_profile_snapshot(path: Path) -> HarnessCheck:
    """Validate skill_profile_snapshot.json schema."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_skill_profile_snapshot",
            passed=False,
            message=error,
        )

    required_fields = ["user_id", "topic_mastery", "criterion_mastery", "attempts"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return HarnessCheck(
            check_name="schema_skill_profile_snapshot",
            passed=False,
            message=f"Missing required fields: {missing}",
        )

    topic_mastery = data.get("topic_mastery", {})
    attempts = data.get("attempts", [])
    criteria_mastery = data.get("criterion_mastery", {})

    if not isinstance(topic_mastery, dict):
        return HarnessCheck(
            check_name="schema_skill_profile_snapshot",
            passed=False,
            message="topic_mastery must be a dict",
        )

    if not isinstance(attempts, list):
        return HarnessCheck(
            check_name="schema_skill_profile_snapshot",
            passed=False,
            message=f"attempts must be a list, got {type(attempts).__name__}",
        )

    return HarnessCheck(
        check_name="schema_skill_profile_snapshot",
        passed=True,
        message=f"Skill profile: topics={len(topic_mastery)}, attempts={len(attempts)}, criteria_topics={len(criteria_mastery)}",
    )


def validate_learning_report(path: Path) -> HarnessCheck:
    """Validate learning_report.json schema."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_learning_report",
            passed=False,
            message=error,
        )

    required_fields = ["overall_score", "topic_mastery_before", "topic_mastery_after", "recommended_focus"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return HarnessCheck(
            check_name="schema_learning_report",
            passed=False,
            message=f"Missing required fields: {missing}",
        )

    overall_score = data.get("overall_score", 0)
    mastery_before = data.get("topic_mastery_before", 0)
    mastery_after = data.get("topic_mastery_after", 0)
    recommended_focus = data.get("recommended_focus", "")
    human_review_flag = data.get("human_review_flag", False)

    for name, val in [("overall_score", overall_score), ("mastery_before", mastery_before), ("mastery_after", mastery_after)]:
        if not (0.0 <= val <= 1.0):
            return HarnessCheck(
                check_name="schema_learning_report",
                passed=False,
                message=f"{name} {val} out of range [0.0, 1.0]",
            )

    if not isinstance(recommended_focus, str) or not recommended_focus:
        return HarnessCheck(
            check_name="schema_learning_report",
            passed=False,
            message="recommended_focus must be a non-empty string",
        )

    if not isinstance(human_review_flag, bool):
        return HarnessCheck(
            check_name="schema_learning_report",
            passed=False,
            message="human_review_flag must be a boolean",
        )

    return HarnessCheck(
        check_name="schema_learning_report",
        passed=True,
        message=f"Learning report: score={overall_score:.2%}, focus={recommended_focus}",
    )


def validate_next_task_decision(path: Path) -> HarnessCheck:
    """Validate next_task_decision.json schema."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_next_task_decision",
            passed=False,
            message=error,
        )

    reason = data.get("reason", "")
    difficulty = data.get("difficulty", 0)

    if not reason:
        return HarnessCheck(
            check_name="schema_next_task_decision",
            passed=False,
            message="Next task decision missing reason",
        )

    if difficulty < 1 or difficulty > 5:
        return HarnessCheck(
            check_name="schema_next_task_decision",
            passed=False,
            message=f"Invalid difficulty level: {difficulty}",
        )

    return HarnessCheck(
        check_name="schema_next_task_decision",
        passed=True,
        message=f"Next task: difficulty={difficulty}, reason provided",
    )


def validate_run_manifest(path: Path) -> HarnessCheck:
    """Validate run_manifest.json schema."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_run_manifest",
            passed=False,
            message=error,
        )

    run_id = data.get("run_id", "")
    artifact_count = data.get("artifact_count", 0)

    if not run_id:
        return HarnessCheck(
            check_name="schema_run_manifest",
            passed=False,
            message="Run manifest missing run_id",
        )

    if artifact_count == 0:
        return HarnessCheck(
            check_name="schema_run_manifest",
            passed=False,
            message="Run manifest has zero artifacts",
        )

    return HarnessCheck(
        check_name="schema_run_manifest",
        passed=True,
        message=f"Run manifest: {artifact_count} artifacts for run {run_id}",
    )


def validate_proof_bundle_manifest(path: Path) -> HarnessCheck:
    """Validate proof_bundle_manifest.json schema."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_proof_bundle_manifest",
            passed=False,
            message=error,
        )

    total = data.get("total_artifacts", 0)
    missing = data.get("missing_required", [])

    if missing:
        return HarnessCheck(
            check_name="schema_proof_bundle_manifest",
            passed=False,
            message=f"Proof bundle missing required artifacts: {missing}",
        )

    return HarnessCheck(
        check_name="schema_proof_bundle_manifest",
        passed=True,
        message=f"Proof bundle manifest: {total} artifacts",
    )


def validate_proof_summary(path: Path) -> HarnessCheck:
    """Validate proof_summary.json schema."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_proof_summary",
            passed=False,
            message=error,
        )

    run_id = data.get("run_id", "")
    if not run_id:
        return HarnessCheck(
            check_name="schema_proof_summary",
            passed=False,
            message="Proof summary missing run_id",
        )

    return HarnessCheck(
        check_name="schema_proof_summary",
        passed=True,
        message=f"Proof summary for run {run_id}",
    )


def validate_retrieval_diagnostics(path: Path) -> HarnessCheck:
    """Validate retrieval_diagnostics.json schema."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_retrieval_diagnostics",
            passed=False,
            message=error,
        )

    required_fields = ["query", "mode", "result_count", "total_chunks"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return HarnessCheck(
            check_name="schema_retrieval_diagnostics",
            passed=False,
            message=f"Missing required fields: {missing}",
        )

    result_count = data.get("result_count", 0)
    total_chunks = data.get("total_chunks", 0)
    backend = data.get("backend", "unknown")
    store = data.get("store", "unknown")

    return HarnessCheck(
        check_name="schema_retrieval_diagnostics",
        passed=True,
        message=f"Retrieval diagnostics: {result_count}/{total_chunks} chunks, backend={backend}, store={store}",
    )


def validate_retrieval_evaluation_report(path: Path) -> HarnessCheck:
    """Validate retrieval_evaluation_report.json schema."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_retrieval_evaluation_report",
            passed=False,
            message=error,
        )

    required_fields = ["query_count", "hit_at_1", "hit_at_3", "source_match_rate"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return HarnessCheck(
            check_name="schema_retrieval_evaluation_report",
            passed=False,
            message=f"Missing required fields: {missing}",
        )

    query_count = data.get("query_count", 0)
    hit_at_1 = data.get("hit_at_1", 0)
    hit_at_3 = data.get("hit_at_3", 0)

    return HarnessCheck(
        check_name="schema_retrieval_evaluation_report",
        passed=True,
        message=f"Retrieval evaluation: {query_count} queries, hit@1={hit_at_1:.2%}, hit@3={hit_at_3:.2%}",
    )


def validate_model_call_trace(path: Path) -> HarnessCheck:
    """Validate model_call_trace.json schema."""
    data, error = _load_json(path)
    if error:
        return HarnessCheck(
            check_name="schema_model_call_trace",
            passed=False,
            message=error,
        )

    required_fields = ["calls", "total_calls", "fallback_count", "mode", "backend"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return HarnessCheck(
            check_name="schema_model_call_trace",
            passed=False,
            message=f"Missing required fields: {missing}",
        )

    return HarnessCheck(
        check_name="schema_model_call_trace",
        passed=True,
        message=f"Valid ModelCallTraceLog: {data['total_calls']} calls, {data['fallback_count']} fallbacks, mode={data['mode']}",
    )


def validate_all_schemas(run_dir: Path) -> list[HarnessCheck]:
    """Run all schema validators on a run directory.
    
    Note: proof_bundle_manifest.json is NOT validated here because it is written
    AFTER the harness validation (it records the state of all other artifacts).
    """
    checks = []

    validators = [
        ("generated_lesson_package.json", validate_generated_lesson_package),
        ("rubric.json", validate_rubric),
        ("answer_key.json", validate_answer_key),
        ("generation_trace.json", validate_generation_trace),
        ("verification_report.json", validate_verification_report),
        ("citation_resolution.json", validate_citation_resolution),
        ("human_review_queue.json", validate_human_review_queue),
        ("answer_submission.json", validate_answer_submission),
        ("answer_review.json", validate_answer_review),
        ("source_grounding_review.json", validate_source_grounding_review),
        ("mastery_update.json", validate_mastery_update),
        ("skill_profile_snapshot.json", validate_skill_profile_snapshot),
        ("learning_report.json", validate_learning_report),
        ("next_task_decision.json", validate_next_task_decision),
        ("run_manifest.json", validate_run_manifest),
        ("proof_summary.json", validate_proof_summary),
        ("retrieval_diagnostics.json", validate_retrieval_diagnostics),
        ("retrieval_evaluation_report.json", validate_retrieval_evaluation_report),
        ("model_call_trace.json", validate_model_call_trace),
    ]

    for artifact_name, validator in validators:
        path = run_dir / artifact_name
        if path.exists():
            check = validator(path)
            checks.append(check)

    return checks
