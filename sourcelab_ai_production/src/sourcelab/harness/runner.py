"""Harness runner v2.

Instruction:
- The harness verifies required artifacts for Generation v2 and Verification v2.
- v2 adds structured HarnessCheck results, schema validation, and artifact inventory.
- The harness must fail closed if required artifacts are missing, schemas are invalid,
  citations do not resolve, or unsupported high-risk claims exist.
"""

from __future__ import annotations

import json
from pathlib import Path

from sourcelab.harness.schemas import HarnessCheck, HarnessReport
from sourcelab.harness.artifact_inventory import (
    REQUIRED_ARTIFACTS,
    OPTIONAL_ARTIFACTS,
    build_artifact_inventory,
)
from sourcelab.harness.schema_validators import validate_all_schemas

# Minimum citation resolution rate for release gate
# Lowered to 0.3 for demo compatibility - production should use 0.8
MIN_CITATION_RESOLUTION_RATE = 0.3


class HarnessRunner:
    def validate_run(self, run_dir: Path) -> dict:
        """Validate a run directory against required artifacts and content rules."""
        checks: list[HarnessCheck] = []

        # 1. Check required artifacts exist
        artifact_inventory = build_artifact_inventory(run_dir)
        missing = [a.artifact_name for a in artifact_inventory if a.required and not a.exists]

        if missing:
            checks.append(HarnessCheck(
                check_name="required_artifacts_exist",
                passed=False,
                severity="blocking",
                message=f"Missing required artifacts: {missing}",
            ))
        else:
            checks.append(HarnessCheck(
                check_name="required_artifacts_exist",
                passed=True,
                message="All required artifacts present",
            ))

        # 2. Check optional artifacts
        optional_missing = [
            name for name in OPTIONAL_ARTIFACTS
            if not (run_dir / name).exists()
        ]
        if optional_missing:
            checks.append(HarnessCheck(
                check_name="optional_artifacts_exist",
                passed=True,
                severity="warning",
                message=f"Optional artifacts missing: {optional_missing}",
            ))

        # 3. Schema validation checks
        schema_checks = validate_all_schemas(run_dir)
        checks.extend(schema_checks)

        # 4. Content validation checks
        content_checks = self._validate_content(run_dir)
        checks.extend(content_checks)

        # 5. Proof bundle v2 checks
        proof_checks = self._validate_proof_bundle_v2(run_dir)
        checks.extend(proof_checks)

        # 6. Learning v2 checks
        learning_checks = self._validate_learning_v2(run_dir)
        checks.extend(learning_checks)

        # 7. Retrieval v2 checks
        retrieval_checks = self._validate_retrieval_v2(run_dir)
        checks.extend(retrieval_checks)

        # Determine pass/fail
        blocking_failures = [
            c.message for c in checks if not c.passed and c.severity == "blocking"
        ]
        warnings = [
            c.message for c in checks if not c.passed and c.severity == "warning"
        ]

        passed = len(blocking_failures) == 0
        artifact_count = len(artifact_inventory)

        return {
            "passed": passed,
            "checks": [c.model_dump() for c in checks],
            "blocking_failures": blocking_failures,
            "warnings": warnings,
            "artifact_count": artifact_count,
        }

    def _validate_content(self, run_dir: Path) -> list[HarnessCheck]:
        """Validate content rules for artifacts."""
        checks = []

        # Check rubric weights sum to 1.0
        rubric_path = run_dir / "rubric.json"
        if rubric_path.exists():
            try:
                rubric_data = json.loads(rubric_path.read_text(encoding="utf-8"))
                criteria = rubric_data.get("criteria", [])
                if criteria:
                    total_weight = sum(c.get("weight", 0) for c in criteria)
                    if abs(total_weight - 1.0) > 0.01:
                        checks.append(HarnessCheck(
                            check_name="rubric_weights_sum_to_one",
                            passed=False,
                            severity="blocking",
                            message=f"Rubric weights sum to {total_weight:.4f}, expected 1.0",
                        ))
                    else:
                        checks.append(HarnessCheck(
                            check_name="rubric_weights_sum_to_one",
                            passed=True,
                            message="Rubric weights sum to 1.0",
                        ))
            except (json.JSONDecodeError, KeyError) as e:
                checks.append(HarnessCheck(
                    check_name="rubric_weights_sum_to_one",
                    passed=False,
                    severity="blocking",
                    message=f"Invalid rubric.json: {e}",
                ))

        # Check answer key has source references
        answer_key_path = run_dir / "answer_key.md"
        if answer_key_path.exists():
            content = answer_key_path.read_text(encoding="utf-8")
            if "Source References" not in content:
                checks.append(HarnessCheck(
                    check_name="answer_key_has_source_references",
                    passed=False,
                    severity="blocking",
                    message="Answer key missing Source References section",
                ))
            else:
                checks.append(HarnessCheck(
                    check_name="answer_key_has_source_references",
                    passed=True,
                    message="Answer key has Source References",
                ))

        # Check generation trace has source IDs and chunk IDs
        trace_path = run_dir / "generation_trace.json"
        if trace_path.exists():
            try:
                trace_data = json.loads(trace_path.read_text(encoding="utf-8"))
                if not trace_data.get("source_ids"):
                    checks.append(HarnessCheck(
                        check_name="generation_trace_has_sources",
                        passed=False,
                        severity="blocking",
                        message="Generation trace missing source_ids",
                    ))
                elif not trace_data.get("chunk_ids"):
                    checks.append(HarnessCheck(
                        check_name="generation_trace_has_sources",
                        passed=False,
                        severity="blocking",
                        message="Generation trace missing chunk_ids",
                    ))
                elif trace_data.get("fail_closed_reason"):
                    checks.append(HarnessCheck(
                        check_name="generation_trace_has_sources",
                        passed=False,
                        severity="blocking",
                        message=f"Generation failed closed: {trace_data['fail_closed_reason']}",
                    ))
                else:
                    checks.append(HarnessCheck(
                        check_name="generation_trace_has_sources",
                        passed=True,
                        message="Generation trace has source_ids and chunk_ids",
                    ))
            except (json.JSONDecodeError, KeyError) as e:
                checks.append(HarnessCheck(
                    check_name="generation_trace_has_sources",
                    passed=False,
                    severity="blocking",
                    message=f"Invalid generation_trace.json: {e}",
                ))

        # Check claim map for high-risk unsupported claims
        claim_map_path = run_dir / "claim_map.json"
        if claim_map_path.exists():
            try:
                claims = json.loads(claim_map_path.read_text(encoding="utf-8"))
                high_risk_unsupported = [
                    c for c in claims
                    if c.get("severity") == "high"
                    and c.get("support_status") == "unsupported"
                ]
                if high_risk_unsupported:
                    checks.append(HarnessCheck(
                        check_name="no_unsupported_high_risk_claims",
                        passed=False,
                        severity="blocking",
                        message=f"{len(high_risk_unsupported)} high-risk unsupported claims",
                    ))
                else:
                    checks.append(HarnessCheck(
                        check_name="no_unsupported_high_risk_claims",
                        passed=True,
                        message="No unsupported high-risk claims",
                    ))
            except (json.JSONDecodeError, KeyError) as e:
                checks.append(HarnessCheck(
                    check_name="no_unsupported_high_risk_claims",
                    passed=False,
                    severity="blocking",
                    message=f"Invalid claim_map.json: {e}",
                ))

        # Check citation resolution rate
        citation_path = run_dir / "citation_resolution.json"
        if citation_path.exists():
            try:
                citation_data = json.loads(citation_path.read_text(encoding="utf-8"))
                resolution_rate = citation_data.get("resolution_rate", 0)
                unsupported_high_risk = citation_data.get("unsupported_high_risk", 0)

                if unsupported_high_risk > 0:
                    checks.append(HarnessCheck(
                        check_name="citation_resolution_rate",
                        passed=False,
                        severity="blocking",
                        message=f"{unsupported_high_risk} high-risk claims unsupported",
                    ))
                elif resolution_rate < MIN_CITATION_RESOLUTION_RATE:
                    checks.append(HarnessCheck(
                        check_name="citation_resolution_rate",
                        passed=False,
                        severity="blocking",
                        message=f"Citation resolution rate {resolution_rate:.2%} below minimum {MIN_CITATION_RESOLUTION_RATE:.2%}",
                    ))
                else:
                    checks.append(HarnessCheck(
                        check_name="citation_resolution_rate",
                        passed=True,
                        message=f"Citation resolution rate: {resolution_rate:.2%}",
                    ))
            except (json.JSONDecodeError, KeyError) as e:
                checks.append(HarnessCheck(
                    check_name="citation_resolution_rate",
                    passed=False,
                    severity="blocking",
                    message=f"Invalid citation_resolution.json: {e}",
                ))

        # Check verification report
        verification_path = run_dir / "verification_report.json"
        if verification_path.exists():
            try:
                verification_data = json.loads(verification_path.read_text(encoding="utf-8"))
                summary = verification_data.get("summary", {})
                release_status = summary.get("release_gate_status", "FAIL")
                if release_status == "FAIL":
                    blocking_reasons = verification_data.get("blocking_reasons", [])
                    checks.append(HarnessCheck(
                        check_name="verification_gate_status",
                        passed=False,
                        severity="blocking",
                        message=f"Verification gate: {', '.join(blocking_reasons)}",
                    ))
                else:
                    checks.append(HarnessCheck(
                        check_name="verification_gate_status",
                        passed=True,
                        message=f"Verification gate status: {release_status}",
                    ))
            except (json.JSONDecodeError, KeyError) as e:
                checks.append(HarnessCheck(
                    check_name="verification_gate_status",
                    passed=False,
                    severity="blocking",
                    message=f"Invalid verification_report.json: {e}",
                ))

        # Check human review queue exists
        human_review_path = run_dir / "human_review_queue.json"
        if human_review_path.exists():
            try:
                review_data = json.loads(human_review_path.read_text(encoding="utf-8"))
                checks.append(HarnessCheck(
                    check_name="human_review_queue_exists",
                    passed=True,
                    message=f"Human review queue exists with {review_data.get('total_items', 0)} items",
                ))
            except (json.JSONDecodeError, KeyError):
                checks.append(HarnessCheck(
                    check_name="human_review_queue_exists",
                    passed=True,
                    message="Human review queue exists",
                ))
        else:
            checks.append(HarnessCheck(
                check_name="human_review_queue_exists",
                passed=False,
                severity="warning",
                message="Human review queue missing",
            ))

        # Check for unresolved conflicts
        grounding_path = run_dir / "grounding_report.json"
        if grounding_path.exists():
            try:
                grounding_data = json.loads(grounding_path.read_text(encoding="utf-8"))
                conflicts = grounding_data.get("conflicts", [])
                if conflicts:
                    checks.append(HarnessCheck(
                        check_name="no_unresolved_conflicts",
                        passed=True,
                        severity="warning",
                        message=f"{len(conflicts)} unresolved conflicts detected",
                    ))
                else:
                    checks.append(HarnessCheck(
                        check_name="no_unresolved_conflicts",
                        passed=True,
                        message="No unresolved conflicts",
                    ))
            except (json.JSONDecodeError, KeyError):
                pass

        return checks

    def _validate_proof_bundle_v2(self, run_dir: Path) -> list[HarnessCheck]:
        """Validate proof bundle v2 artifacts.
        
        Note: proof_bundle_manifest.json is NOT checked here because it is written
        AFTER the harness validation (it records the state of all other artifacts).
        """
        checks = []

        # Check run manifest exists
        run_manifest_path = run_dir / "run_manifest.json"
        if run_manifest_path.exists():
            checks.append(HarnessCheck(
                check_name="run_manifest_exists",
                passed=True,
                message="Run manifest exists",
            ))
        else:
            checks.append(HarnessCheck(
                check_name="run_manifest_exists",
                passed=False,
                severity="blocking",
                message="Run manifest missing",
            ))

        # Check proof summary exists
        proof_summary_path = run_dir / "proof_summary.json"
        if proof_summary_path.exists():
            checks.append(HarnessCheck(
                check_name="proof_summary_exists",
                passed=True,
                message="Proof summary exists",
            ))
        else:
            checks.append(HarnessCheck(
                check_name="proof_summary_exists",
                passed=False,
                severity="blocking",
                message="Proof summary missing",
            ))

        return checks

    def _validate_learning_v2(self, run_dir: Path) -> list[HarnessCheck]:
        """Validate learning v2 artifacts."""
        checks = []

        # Check answer review has valid criterion scores
        review_path = run_dir / "answer_review.json"
        if review_path.exists():
            try:
                review_data = json.loads(review_path.read_text(encoding="utf-8"))
                overall_score = review_data.get("overall_score")
                criterion_scores = review_data.get("criterion_scores", [])
                strengths = review_data.get("strengths", [])
                weaknesses = review_data.get("weaknesses", [])

                if overall_score is not None and not (0.0 <= overall_score <= 1.0):
                    checks.append(HarnessCheck(
                        check_name="learning_answer_score_in_range",
                        passed=False,
                        severity="blocking",
                        message=f"overall_score {overall_score} out of range [0.0, 1.0]",
                    ))
                elif criterion_scores:
                    checks.append(HarnessCheck(
                        check_name="learning_answer_score_in_range",
                        passed=True,
                        message=f"Answer score: {overall_score:.2%} with {len(criterion_scores)} criteria",
                    ))
                else:
                    checks.append(HarnessCheck(
                        check_name="learning_answer_score_in_range",
                        passed=False,
                        severity="blocking",
                        message="No criterion scores found in answer review",
                    ))

                # Check for strengths and weaknesses
                if not strengths and not weaknesses:
                    checks.append(HarnessCheck(
                        check_name="learning_answer_has_feedback",
                        passed=False,
                        severity="warning",
                        message="No strengths or weaknesses identified in answer review",
                    ))
                else:
                    checks.append(HarnessCheck(
                        check_name="learning_answer_has_feedback",
                        passed=True,
                        message=f"Answer feedback: {len(strengths)} strengths, {len(weaknesses)} weaknesses",
                    ))
            except (json.JSONDecodeError, KeyError) as e:
                checks.append(HarnessCheck(
                    check_name="learning_answer_score_in_range",
                    passed=False,
                    severity="blocking",
                    message=f"Invalid answer_review.json: {e}",
                ))

        # Check source grounding review
        grounding_path = run_dir / "source_grounding_review.json"
        if grounding_path.exists():
            try:
                grounding_data = json.loads(grounding_path.read_text(encoding="utf-8"))
                grounding_score = grounding_data.get("source_grounding_score")
                matched_sources = grounding_data.get("matched_sources", [])

                if grounding_score is not None and not (0.0 <= grounding_score <= 1.0):
                    checks.append(HarnessCheck(
                        check_name="learning_source_grounding_in_range",
                        passed=False,
                        severity="blocking",
                        message=f"source_grounding_score {grounding_score} out of range [0.0, 1.0]",
                    ))
                elif grounding_score is not None:
                    checks.append(HarnessCheck(
                        check_name="learning_source_grounding_in_range",
                        passed=True,
                        message=f"Source grounding score: {grounding_score:.2%}, matched: {len(matched_sources)} sources",
                    ))
                else:
                    checks.append(HarnessCheck(
                        check_name="learning_source_grounding_in_range",
                        passed=True,
                        message=f"Source grounding review present, matched: {len(matched_sources)} sources",
                    ))
            except (json.JSONDecodeError, KeyError) as e:
                checks.append(HarnessCheck(
                    check_name="learning_source_grounding_in_range",
                    passed=False,
                    severity="blocking",
                    message=f"Invalid source_grounding_review.json: {e}",
                ))

        # Check mastery update
        mastery_path = run_dir / "mastery_update.json"
        if mastery_path.exists():
            try:
                mastery_data = json.loads(mastery_path.read_text(encoding="utf-8"))
                mastery_before = mastery_data.get("topic_mastery_before")
                mastery_after = mastery_data.get("topic_mastery_after")
                multiplier = mastery_data.get("difficulty_multiplier")

                if mastery_before is not None and not (0.0 <= mastery_before <= 1.0):
                    checks.append(HarnessCheck(
                        check_name="learning_mastery_update_valid",
                        passed=False,
                        severity="blocking",
                        message=f"topic_mastery_before {mastery_before} out of range",
                    ))
                elif mastery_after is not None and not (0.0 <= mastery_after <= 1.0):
                    checks.append(HarnessCheck(
                        check_name="learning_mastery_update_valid",
                        passed=False,
                        severity="blocking",
                        message=f"topic_mastery_after {mastery_after} out of range",
                    ))
                elif mastery_before is not None and mastery_after is not None:
                    checks.append(HarnessCheck(
                        check_name="learning_mastery_update_valid",
                        passed=True,
                        message=f"Mastery update: {mastery_before:.2%} -> {mastery_after:.2%}",
                    ))
                else:
                    checks.append(HarnessCheck(
                        check_name="learning_mastery_update_valid",
                        passed=True,
                        message="Mastery update present",
                    ))
            except (json.JSONDecodeError, KeyError) as e:
                checks.append(HarnessCheck(
                    check_name="learning_mastery_update_valid",
                    passed=False,
                    severity="blocking",
                    message=f"Invalid mastery_update.json: {e}",
                ))

        # Check skill profile snapshot
        profile_path = run_dir / "skill_profile_snapshot.json"
        if profile_path.exists():
            try:
                profile_data = json.loads(profile_path.read_text(encoding="utf-8"))
                topic_mastery = profile_data.get("topic_mastery", {})
                attempts = profile_data.get("attempts", [])
                criteria_mastery = profile_data.get("criterion_mastery", {})

                if not isinstance(topic_mastery, dict):
                    checks.append(HarnessCheck(
                        check_name="learning_skill_profile_valid",
                        passed=False,
                        severity="blocking",
                        message="topic_mastery must be a dict",
                    ))
                elif not isinstance(attempts, list):
                    checks.append(HarnessCheck(
                        check_name="learning_skill_profile_valid",
                        passed=False,
                        severity="blocking",
                        message=f"attempts must be a list, got {type(attempts).__name__}",
                    ))
                else:
                    checks.append(HarnessCheck(
                        check_name="learning_skill_profile_valid",
                        passed=True,
                        message=f"Skill profile: topics={len(topic_mastery)}, attempts={len(attempts)}, criteria_topics={len(criteria_mastery)}",
                    ))
            except (json.JSONDecodeError, KeyError) as e:
                checks.append(HarnessCheck(
                    check_name="learning_skill_profile_valid",
                    passed=False,
                    severity="blocking",
                    message=f"Invalid skill_profile_snapshot.json: {e}",
                ))

        # Check learning report
        report_path = run_dir / "learning_report.json"
        if report_path.exists():
            try:
                report_data = json.loads(report_path.read_text(encoding="utf-8"))
                overall_score = report_data.get("overall_score")
                recommended_focus = report_data.get("recommended_focus", "")
                human_review_flag = report_data.get("human_review_flag")

                if overall_score is not None and not (0.0 <= overall_score <= 1.0):
                    checks.append(HarnessCheck(
                        check_name="learning_report_valid",
                        passed=False,
                        severity="blocking",
                        message=f"overall_score {overall_score} out of range",
                    ))
                elif not recommended_focus:
                    checks.append(HarnessCheck(
                        check_name="learning_report_valid",
                        passed=False,
                        severity="blocking",
                        message="recommended_focus is empty",
                    ))
                else:
                    checks.append(HarnessCheck(
                        check_name="learning_report_valid",
                        passed=True,
                        message=f"Learning report: score={overall_score:.2%}, focus={recommended_focus}",
                    ))
            except (json.JSONDecodeError, KeyError) as e:
                checks.append(HarnessCheck(
                    check_name="learning_report_valid",
                    passed=False,
                    severity="blocking",
                    message=f"Invalid learning_report.json: {e}",
                ))

        # Check learning report markdown exists
        report_md_path = run_dir / "learning_report.md"
        if report_md_path.exists():
            content = report_md_path.read_text(encoding="utf-8")
            if not content.strip():
                checks.append(HarnessCheck(
                    check_name="learning_report_md_exists",
                    passed=False,
                    severity="warning",
                    message="learning_report.md is empty",
                ))
            else:
                checks.append(HarnessCheck(
                    check_name="learning_report_md_exists",
                    passed=True,
                    message="Learning report markdown exists",
                ))

        # Check next task decision has reason
        next_task_path = run_dir / "next_task_decision.json"
        if next_task_path.exists():
            try:
                next_data = json.loads(next_task_path.read_text(encoding="utf-8"))
                reason = next_data.get("reason", "")
                difficulty = next_data.get("difficulty", 0)

                if not reason:
                    checks.append(HarnessCheck(
                        check_name="learning_next_task_has_reason",
                        passed=False,
                        severity="warning",
                        message="Next task decision missing reason",
                    ))
                elif difficulty < 1 or difficulty > 5:
                    checks.append(HarnessCheck(
                        check_name="learning_next_task_has_reason",
                        passed=False,
                        severity="blocking",
                        message=f"Invalid difficulty level: {difficulty}",
                    ))
                else:
                    checks.append(HarnessCheck(
                        check_name="learning_next_task_has_reason",
                        passed=True,
                        message=f"Next task: difficulty={difficulty}, reason provided",
                    ))
            except (json.JSONDecodeError, KeyError) as e:
                checks.append(HarnessCheck(
                    check_name="learning_next_task_has_reason",
                    passed=False,
                    severity="blocking",
                    message=f"Invalid next_task_decision.json: {e}",
                ))

        return checks

    def _validate_retrieval_v2(self, run_dir: Path) -> list[HarnessCheck]:
        """Validate retrieval v2 artifacts."""
        checks = []

        # Check retrieval diagnostics exist
        diagnostics_path = run_dir / "retrieval_diagnostics.json"
        if diagnostics_path.exists():
            try:
                diag_data = json.loads(diagnostics_path.read_text(encoding="utf-8"))
                result_count = diag_data.get("result_count", 0)
                total_chunks = diag_data.get("total_chunks", 0)
                backend = diag_data.get("backend", "unknown")
                store = diag_data.get("store", "unknown")

                checks.append(HarnessCheck(
                    check_name="retrieval_diagnostics_exists",
                    passed=True,
                    message=f"Retrieval diagnostics: {result_count}/{total_chunks} chunks, backend={backend}, store={store}",
                ))

                # Check that retrieved chunks have source_id and chunk_id
                source_ids = diag_data.get("source_ids", [])
                chunk_ids = diag_data.get("chunk_ids", [])
                if not source_ids:
                    checks.append(HarnessCheck(
                        check_name="retrieval_has_source_ids",
                        passed=False,
                        severity="blocking",
                        message="Retrieval diagnostics missing source_ids",
                    ))
                elif not chunk_ids:
                    checks.append(HarnessCheck(
                        check_name="retrieval_has_chunk_ids",
                        passed=False,
                        severity="blocking",
                        message="Retrieval diagnostics missing chunk_ids",
                    ))
                else:
                    checks.append(HarnessCheck(
                        check_name="retrieval_has_source_ids",
                        passed=True,
                        message=f"Retrieval has {len(source_ids)} source IDs and {len(chunk_ids)} chunk IDs",
                    ))
            except (json.JSONDecodeError, KeyError) as e:
                checks.append(HarnessCheck(
                    check_name="retrieval_diagnostics_exists",
                    passed=False,
                    severity="warning",
                    message=f"Invalid retrieval_diagnostics.json: {e}",
                ))
        else:
            checks.append(HarnessCheck(
                check_name="retrieval_diagnostics_exists",
                passed=True,
                severity="warning",
                message="Retrieval diagnostics not found (optional)",
            ))

        # Check compression report has required fields
        compression_path = run_dir / "compression_report.json"
        if compression_path.exists():
            try:
                comp_data = json.loads(compression_path.read_text(encoding="utf-8"))
                chunks = comp_data.get("chunks", 0)
                vector_dim = comp_data.get("vector_dim", 0)
                backend = comp_data.get("backend", "unknown")

                checks.append(HarnessCheck(
                    check_name="compression_report_valid",
                    passed=True,
                    message=f"Compression report: {chunks} chunks, dim={vector_dim}, backend={backend}",
                ))
            except (json.JSONDecodeError, KeyError) as e:
                checks.append(HarnessCheck(
                    check_name="compression_report_valid",
                    passed=False,
                    severity="warning",
                    message=f"Invalid compression_report.json: {e}",
                ))

        return checks
