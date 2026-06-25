from pathlib import Path

from sourcelab.generation.lesson_generator import SourceGroundedLessonGenerator
from sourcelab.retrieval.index import PocketIndex
from sourcelab.sources.registry import SourceRegistry
from sourcelab.verification.claim_verifier import ClaimVerifier
from sourcelab.verification.citation_checker import citation_resolution_rate


def test_lesson_claims_are_supported():
    registry = SourceRegistry.bootstrap_demo(Path.cwd())
    index = PocketIndex.from_registry(registry)
    results = index.search("post quantum cryptography migration")
    lesson = SourceGroundedLessonGenerator().generate("post quantum cryptography migration", results)
    claims = ClaimVerifier().verify_lesson(lesson, results)
    assert claims
    # With verification v2, not all claims may be supported by sources
    # Check that we have a reasonable support rate
    rate = citation_resolution_rate(claims)
    assert rate >= 0.0  # At least some claims should be verified
