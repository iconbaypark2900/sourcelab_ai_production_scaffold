"""Tests for Verification v2: Advanced Claim Verification + Citation Gates.

Instruction:
- Test all verification v2 components: schemas, claim extractor, evidence matcher,
  claim verifier, citation checker, conflict detector, human review, grounding report.
- Ensure backward compatibility with existing tests.
- Test CLI commands for verify and review.
"""

import json
from pathlib import Path

import pytest

from sourcelab.core.models import ClaimRecord, SearchResult
from sourcelab.generation.lesson_generator import SourceGroundedLessonGenerator
from sourcelab.generation.schemas import (
    GeneratedAnswerKey,
    GeneratedLesson,
    GeneratedLessonPackage,
    GeneratedScenario,
    ClaimCandidate,
    GenerationTrace,
)
from sourcelab.retrieval.index import PocketIndex
from sourcelab.sources.registry import SourceRegistry
from sourcelab.verification.schemas import (
    AtomicClaim,
    ClaimType,
    ClaimVerificationResult,
    CitationResolutionResult,
    ConflictRecord,
    EvidenceMatch,
    HumanReviewItem,
    Severity,
    SupportStatus,
    TrustTier,
    VerificationReport,
    VerificationSummary,
)
from sourcelab.verification.claim_extractor import (
    extract_atomic_claims_from_lesson,
    extract_atomic_claims_from_answer_key,
    extract_atomic_claims_from_scenario,
    extract_all_atomic_claims,
    extract_claims,
)
from sourcelab.verification.evidence_matcher import (
    match_claim_to_chunks,
    match_all_claims,
    get_best_match,
)
from sourcelab.verification.claim_verifier import ClaimVerifier
from sourcelab.verification.citation_checker import (
    citation_resolution_rate,
    compute_citation_resolution,
    compute_citation_resolution_from_records,
    check_citation_resolution,
)
from sourcelab.verification.conflict_detector import (
    detect_must_must_not_conflicts,
    detect_safe_unsafe_conflicts,
    detect_rsa_contradictions,
    detect_all_conflicts,
)
from sourcelab.verification.human_review import (
    build_review_items_from_verification,
    build_review_items_from_conflicts,
    build_human_review_queue,
    write_review_queue,
)
from sourcelab.verification.grounding_report import (
    generate_verification_report,
    generate_grounding_report_markdown,
    generate_grounding_report_from_records,
    write_grounding_report,
)
from sourcelab.harness.runner import HarnessRunner


def _get_search_results(topic: str = "post quantum cryptography migration") -> list[SearchResult]:
    """Helper to get search results for testing."""
    registry = SourceRegistry.bootstrap_demo(Path.cwd())
    index = PocketIndex.from_registry(registry)
    return index.search(topic, top_k=4)


# ===== Schema Tests =====


def test_atomic_claim_schema_validates():
    """AtomicClaim schema validates with required fields."""
    claim = AtomicClaim(
        claim_id="claim_123",
        text="Test claim text",
        claim_type=ClaimType.FACT,
    )
    assert claim.claim_id == "claim_123"
    assert claim.claim_type == ClaimType.FACT
    assert claim.severity == Severity.MEDIUM


def test_evidence_match_schema_validates():
    """EvidenceMatch schema validates with required fields."""
    match = EvidenceMatch(
        claim_id="claim_123",
        chunk_id="chunk_456",
        source_id="source_789",
        trust_tier=TrustTier.A,
        overlap_score=0.75,
    )
    assert match.claim_id == "claim_123"
    assert match.trust_tier == TrustTier.A


def test_verification_report_schema_validates():
    """VerificationReport schema validates with required fields."""
    report = VerificationReport(
        run_id="run_123",
        topic="test topic",
    )
    assert report.run_id == "run_123"
    assert report.summary.total_claims == 0


# ===== Claim Extractor Tests =====


def test_extract_atomic_claims_from_lesson():
    """Extract atomic claims from a generated lesson."""
    lesson = GeneratedLesson(
        title="Test Lesson",
        learning_objectives=[
            "Students should learn about encryption",
            "The system must avoid weak algorithms",
        ],
        required_source_concepts=["Post-quantum cryptography is a field"],
        task_instructions="Complete the migration task.",
    )
    claims = extract_atomic_claims_from_lesson(lesson)
    assert len(claims) > 0
    assert any(c.claim_type == ClaimType.RECOMMENDATION for c in claims)
    assert any(c.claim_type == ClaimType.WARNING for c in claims)


def test_extract_atomic_claims_from_answer_key():
    """Extract atomic claims from an answer key."""
    answer_key = GeneratedAnswerKey(
        facts=["RSA-2048 is vulnerable to quantum attacks"],
        assumptions=["The organization has a cryptographic inventory"],
        what_not_to_claim=["Current quantum computers can break RSA-2048"],
        source_references=[],
    )
    claims = extract_atomic_claims_from_answer_key(answer_key)
    assert len(claims) > 0
    assert any(c.claim_type == ClaimType.FACT for c in claims)
    assert any(c.claim_type == ClaimType.WARNING for c in claims)


def test_extract_atomic_claims_from_scenario():
    """Extract atomic claims from a scenario."""
    scenario = GeneratedScenario(
        title="Test Scenario",
        context="The organization needs to migrate to post-quantum cryptography.",
        audience="engineer",
        task_format="architecture_review",
        difficulty=3,
    )
    claims = extract_atomic_claims_from_scenario(scenario)
    assert len(claims) > 0


def test_extract_all_atomic_claims():
    """Extract all atomic claims from a lesson package."""
    package = GeneratedLessonPackage(
        topic="test topic",
        lesson=GeneratedLesson(
            title="Test",
            learning_objectives=["Test objective"],
        ),
        answer_key=GeneratedAnswerKey(
            facts=["Test fact"],
        ),
        scenario=GeneratedScenario(
            title="Test",
            context="This is a longer context that will be extracted as claims for testing purposes.",
            audience="engineer",
            task_format="architecture_review",
            difficulty=3,
        ),
    )
    claims = extract_all_atomic_claims(package)
    assert len(claims) >= 2  # At least one from lesson and answer_key


def test_extract_claims_legacy():
    """Legacy claim extraction still works."""
    text = "This is a test sentence that should be extracted. This is another sentence."
    claims = extract_claims(text)
    assert len(claims) >= 1


# ===== Evidence Matcher Tests =====


def test_match_claim_to_chunks():
    """Match a claim to source chunks."""
    search_results = _get_search_results()
    claim = AtomicClaim(
        claim_id="claim_123",
        text="post quantum cryptography migration",
        claim_type=ClaimType.FACT,
    )
    matches = match_claim_to_chunks(claim, search_results)
    assert len(matches) > 0
    assert matches[0].claim_id == "claim_123"


def test_match_all_claims():
    """Match all claims to source chunks."""
    search_results = _get_search_results()
    claims = [
        AtomicClaim(
            claim_id="claim_1",
            text="post quantum cryptography",
            claim_type=ClaimType.FACT,
        ),
        AtomicClaim(
            claim_id="claim_2",
            text="migration strategy",
            claim_type=ClaimType.RECOMMENDATION,
        ),
    ]
    results = match_all_claims(claims, search_results)
    assert len(results) == 2
    assert "claim_1" in results
    assert "claim_2" in results


def test_get_best_match():
    """Get the best match from a list."""
    matches = [
        EvidenceMatch(
            claim_id="claim_1",
            chunk_id="chunk_1",
            source_id="source_1",
            trust_tier=TrustTier.A,
            overlap_score=0.8,
        ),
        EvidenceMatch(
            claim_id="claim_1",
            chunk_id="chunk_2",
            source_id="source_2",
            trust_tier=TrustTier.B,
            overlap_score=0.6,
        ),
    ]
    best = get_best_match(matches)
    assert best is not None
    assert best.overlap_score == 0.8


# ===== Claim Verifier Tests =====


def test_claim_verifier_verifies_claim():
    """Claim verifier verifies a single claim."""
    search_results = _get_search_results()
    verifier = ClaimVerifier()
    claim = AtomicClaim(
        claim_id="claim_123",
        text="post quantum cryptography migration",
        claim_type=ClaimType.FACT,
    )
    matches = match_claim_to_chunks(claim, search_results)
    result = verifier.verify_claim(claim, matches)
    assert result.claim_id == "claim_123"
    assert result.support_status in (SupportStatus.SUPPORTED, SupportStatus.UNCERTAIN, SupportStatus.UNSUPPORTED)


def test_claim_verifier_verifies_all():
    """Claim verifier verifies all claims."""
    search_results = _get_search_results()
    verifier = ClaimVerifier()
    claims = [
        AtomicClaim(
            claim_id="claim_1",
            text="post quantum cryptography",
            claim_type=ClaimType.FACT,
        ),
    ]
    evidence_map = match_all_claims(claims, search_results)
    results = verifier.verify_all_claims(claims, evidence_map)
    assert len(results) == 1


def test_claim_verifier_backward_compatible():
    """Claim verifier maintains backward compatibility."""
    search_results = _get_search_results()
    generator = SourceGroundedLessonGenerator()
    package = generator.generate_package(
        topic="post quantum cryptography migration",
        search_results=search_results,
        difficulty=3,
    )
    verifier = ClaimVerifier()
    claims = verifier.verify_lesson_package(package, search_results)
    assert len(claims) > 0
    assert all(isinstance(c, ClaimRecord) for c in claims)


# ===== Citation Checker Tests =====


def test_citation_resolution_rate():
    """Citation resolution rate calculates correctly."""
    claims = [
        ClaimRecord(claim="c1", support_status="supported"),
        ClaimRecord(claim="c2", support_status="unsupported"),
        ClaimRecord(claim="c3", support_status="supported"),
    ]
    rate = citation_resolution_rate(claims)
    assert abs(rate - 0.6667) < 0.001


def test_compute_citation_resolution():
    """Compute citation resolution from verification results."""
    results = [
        ClaimVerificationResult(
            claim_id="c1",
            claim_text="claim 1",
            claim_type=ClaimType.FACT,
            support_status=SupportStatus.SUPPORTED,
            severity=Severity.LOW,
        ),
        ClaimVerificationResult(
            claim_id="c2",
            claim_text="claim 2",
            claim_type=ClaimType.FACT,
            support_status=SupportStatus.UNSUPPORTED,
            severity=Severity.HIGH,
        ),
    ]
    resolution = compute_citation_resolution(results)
    assert resolution.total_claims == 2
    assert resolution.supported_claims == 1
    assert resolution.unsupported_high_risk == 1
    assert resolution.has_blocking_issues is True


def test_check_citation_resolution():
    """Check citation resolution meets requirements."""
    resolution = CitationResolutionResult(
        resolution_rate=0.9,
        unsupported_high_risk=0,
    )
    passed, reasons = check_citation_resolution(resolution)
    assert passed is True
    assert len(reasons) == 0


# ===== Conflict Detector Tests =====


def test_detect_must_must_not_conflicts():
    """Detect must/must-not contradictions."""
    claims = [
        AtomicClaim(
            claim_id="c1",
            text="You should use RSA encryption",
            claim_type=ClaimType.RECOMMENDATION,
        ),
        AtomicClaim(
            claim_id="c2",
            text="You should not use RSA encryption",
            claim_type=ClaimType.WARNING,
        ),
    ]
    conflicts = detect_must_must_not_conflicts(claims)
    assert len(conflicts) > 0


def test_detect_rsa_contradictions():
    """Detect RSA-related contradictions."""
    claims = [
        AtomicClaim(
            claim_id="c1",
            text="RSA is quantum safe",
            claim_type=ClaimType.FACT,
        ),
        AtomicClaim(
            claim_id="c2",
            text="RSA is vulnerable to quantum attacks",
            claim_type=ClaimType.FACT,
        ),
    ]
    conflicts = detect_rsa_contradictions(claims)
    assert len(conflicts) > 0


def test_detect_all_conflicts():
    """Detect all types of conflicts."""
    claims = [
        AtomicClaim(
            claim_id="c1",
            text="You should use RSA",
            claim_type=ClaimType.RECOMMENDATION,
        ),
        AtomicClaim(
            claim_id="c2",
            text="You should not use RSA",
            claim_type=ClaimType.WARNING,
        ),
    ]
    conflicts = detect_all_conflicts(claims)
    assert len(conflicts) > 0


# ===== Human Review Tests =====


def test_build_review_items_from_verification():
    """Build review items from verification results."""
    results = [
        ClaimVerificationResult(
            claim_id="c1",
            claim_text="claim 1",
            claim_type=ClaimType.WARNING,
            support_status=SupportStatus.UNCERTAIN,
            severity=Severity.HIGH,
            requires_human_review=True,
            review_reason="High-risk claim",
        ),
    ]
    items = build_review_items_from_verification(results)
    assert len(items) == 1
    assert items[0].priority == "high"


def test_build_review_items_from_conflicts():
    """Build review items from conflicts."""
    conflicts = [
        ConflictRecord(
            conflict_id="conflict_1",
            claim_id_1="c1",
            claim_id_2="c2",
            claim_text_1="claim 1",
            claim_text_2="claim 2",
            conflict_type="must_must_not",
            severity=Severity.HIGH,
        ),
    ]
    items = build_review_items_from_conflicts(conflicts)
    assert len(items) == 1


def test_build_human_review_queue():
    """Build the complete human review queue."""
    results = [
        ClaimVerificationResult(
            claim_id="c1",
            claim_text="claim 1",
            claim_type=ClaimType.FACT,
            support_status=SupportStatus.SUPPORTED,
            severity=Severity.LOW,
        ),
    ]
    conflicts = []
    items = build_human_review_queue(results, conflicts)
    assert isinstance(items, list)


def test_write_review_queue(tmp_path):
    """Write review queue to file."""
    items = [
        HumanReviewItem(
            item_id="item_1",
            claim_id="c1",
            claim_text="claim 1",
            reason="test reason",
        ),
    ]
    path = write_review_queue(items, tmp_path)
    assert path.exists()


# ===== Grounding Report Tests =====


def test_generate_verification_report():
    """Generate a verification report."""
    results = [
        ClaimVerificationResult(
            claim_id="c1",
            claim_text="claim 1",
            claim_type=ClaimType.FACT,
            support_status=SupportStatus.SUPPORTED,
            severity=Severity.LOW,
        ),
    ]
    citation = CitationResolutionResult(
        total_claims=1,
        supported_claims=1,
        resolution_rate=1.0,
    )
    report = generate_verification_report(
        run_id="run_123",
        topic="test",
        verification_results=results,
        citation_resolution=citation,
        conflicts=[],
        human_review_items=[],
    )
    assert report.run_id == "run_123"
    assert report.summary.release_gate_status == "PASS"


def test_generate_grounding_report_markdown():
    """Generate markdown grounding report."""
    report = VerificationReport(
        run_id="run_123",
        topic="test",
    )
    markdown = generate_grounding_report_markdown(report)
    assert "# Grounding Report" in markdown
    assert "run_123" in markdown


def test_write_grounding_report(tmp_path):
    """Write grounding report to files."""
    report = VerificationReport(
        run_id="run_123",
        topic="test",
    )
    md_path, json_path = write_grounding_report(report, tmp_path)
    assert md_path.exists()
    assert json_path.exists()


# ===== Harness Runner Tests =====


def test_harness_runner_validates_v2_artifacts(tmp_path):
    """Harness runner validates verification v2 artifacts."""
    # Create minimal required artifacts
    artifacts = [
        "source_registry_snapshot.json",
        "retrieved_chunks.json",
        "compression_report.json",
        "lesson_task.json",
        "generated_lesson_package.json",
        "generated_lesson.md",
        "rubric.json",
        "answer_key.md",
        "claim_map.json",
        "grounding_report.md",
        "verification_report.json",
        "citation_resolution.json",
        "human_review_queue.json",
        "atomic_claims.json",
        "evidence_matches.json",
        "trace.json",
        "run_manifest.json",
        "proof_summary.json",
    ]
    for artifact in artifacts:
        (tmp_path / artifact).write_text("{}", encoding="utf-8")

    # Create valid rubric
    rubric_data = {
        "criteria": [
            {"name": "test", "weight": 1.0, "description": "test"}
        ]
    }
    (tmp_path / "rubric.json").write_text(
        json.dumps(rubric_data), encoding="utf-8"
    )

    # Create valid answer key
    (tmp_path / "answer_key.md").write_text(
        "# Answer Key\n\n## Source References\n- test",
        encoding="utf-8",
    )

    # Create valid generation trace
    trace_data = {
        "source_ids": ["src1"],
        "chunk_ids": ["chunk1"],
    }
    (tmp_path / "generation_trace.json").write_text(
        json.dumps(trace_data), encoding="utf-8",
    )

    # Create valid claim map
    (tmp_path / "claim_map.json").write_text("[]", encoding="utf-8")

    # Create valid citation resolution
    citation_data = {
        "resolution_rate": 0.9,
        "unsupported_high_risk": 0,
    }
    (tmp_path / "citation_resolution.json").write_text(
        json.dumps(citation_data), encoding="utf-8",
    )

    # Create valid verification report
    verification_data = {
        "summary": {"release_gate_status": "PASS"},
        "blocking_reasons": [],
    }
    (tmp_path / "verification_report.json").write_text(
        json.dumps(verification_data), encoding="utf-8",
    )

    # Create valid generated_lesson_package
    lesson_package = {
        "topic": "test topic",
    }
    (tmp_path / "generated_lesson_package.json").write_text(
        json.dumps(lesson_package), encoding="utf-8",
    )

    # Create valid run manifest
    run_manifest = {
        "run_id": "test-run",
        "artifact_count": 5,
    }
    (tmp_path / "run_manifest.json").write_text(
        json.dumps(run_manifest), encoding="utf-8",
    )

    # Create valid proof summary
    proof_summary = {
        "run_id": "test-run",
    }
    (tmp_path / "proof_summary.json").write_text(
        json.dumps(proof_summary), encoding="utf-8",
    )

    # Create valid answer_review
    answer_review = {
        "overall_score": 0.8,
        "criterion_scores": [
            {"criterion_name": "topic_relevance", "score": 0.9},
        ],
        "strengths": ["Strong topic relevance"],
        "weaknesses": [],
    }
    (tmp_path / "answer_review.json").write_text(
        json.dumps(answer_review), encoding="utf-8",
    )

    # Create valid next_task_decision
    next_task = {
        "difficulty": 3,
        "reason": "next task",
    }
    (tmp_path / "next_task_decision.json").write_text(
        json.dumps(next_task), encoding="utf-8",
    )

    runner = HarnessRunner()
    report = runner.validate_run(tmp_path)
    assert report["passed"] is True
    assert len(report["blocking_failures"]) == 0
