"""Source expansion suggestions when runs have thin evidence."""

from __future__ import annotations

import json
from pathlib import Path

from sourcelab.library.io import save_model, utc_now
from sourcelab.library.schemas import SourceExpansionSuggestion, SourceExpansionSuggestions


THIN_RETRIEVAL_THRESHOLD = 2
THIN_GROUNDING_THRESHOLD = 0.35


def _load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def detect_thin_evidence(run_dir: Path) -> tuple[bool, list[str]]:
    """Return whether a run has thin evidence and the trigger reasons."""
    triggers: list[str] = []

    retrieved = _load_json(run_dir / "retrieved_chunks.json")
    if isinstance(retrieved, list) and len(retrieved) < THIN_RETRIEVAL_THRESHOLD:
        triggers.append(f"low_retrieval_count:{len(retrieved)}")

    grounding = _load_json(run_dir / "source_grounding_review.json")
    if isinstance(grounding, dict):
        score = grounding.get("source_grounding_score")
        if score is not None and float(score) < THIN_GROUNDING_THRESHOLD:
            triggers.append(f"low_source_grounding:{score}")

    registry = _load_json(run_dir / "source_registry_snapshot.json")
    if isinstance(registry, list) and len(registry) < THIN_RETRIEVAL_THRESHOLD:
        triggers.append(f"low_source_count:{len(registry)}")

    verification = _load_json(run_dir / "verification_report.json")
    if isinstance(verification, dict):
        summary = verification.get("summary", {})
        unsupported = summary.get("unsupported_high_risk", 0)
        if isinstance(unsupported, int) and unsupported > 0:
            triggers.append(f"unsupported_high_risk:{unsupported}")

    return bool(triggers), triggers


def build_expansion_suggestions(run_id: str, topic: str, triggers: list[str]) -> SourceExpansionSuggestions:
    """Build deterministic expansion suggestions from thin-evidence triggers."""
    suggestions: list[SourceExpansionSuggestion] = []
    topic_hint = topic.strip() or "source expansion"

    suggestions.append(
        SourceExpansionSuggestion(
            suggestion_id=f"{run_id}_local_docs",
            reason="Collect project-local markdown into the library bronze layer",
            collector="local_docs",
            query_hint=str(Path.cwd()),
            domain_tags=["user_project_library"],
            priority="high",
        )
    )
    suggestions.append(
        SourceExpansionSuggestion(
            suggestion_id=f"{run_id}_arxiv",
            reason="Add arXiv metadata for the run topic",
            collector="arxiv",
            query_hint=topic_hint,
            domain_tags=["research"],
            priority="medium",
        )
    )
    suggestions.append(
        SourceExpansionSuggestion(
            suggestion_id=f"{run_id}_pubmed",
            reason="Add PubMed abstracts for biomedical or safety topics",
            collector="pubmed",
            query_hint=topic_hint,
            domain_tags=["research"],
            priority="medium" if "bio" in topic_hint.lower() else "low",
        )
    )
    suggestions.append(
        SourceExpansionSuggestion(
            suggestion_id=f"{run_id}_nvd",
            reason="Add CVE metadata when security evidence is thin",
            collector="nvd",
            query_hint=topic_hint,
            domain_tags=["security"],
            priority="high" if any("security" in trigger or "risk" in trigger for trigger in triggers) else "low",
        )
    )

    return SourceExpansionSuggestions(
        run_id=run_id,
        generated_at=utc_now(),
        thin_evidence=True,
        triggers=triggers,
        suggestions=suggestions,
    )


def maybe_write_source_expansion_suggestions(
    project_root: Path,
    run_dir: Path,
    topic: str,
) -> SourceExpansionSuggestions | None:
    """Write source_expansion_suggestions.json when a run has thin evidence."""
    thin, triggers = detect_thin_evidence(run_dir)
    if not thin:
        return None

    payload = build_expansion_suggestions(run_dir.name, topic, triggers)
    save_model(run_dir / "source_expansion_suggestions.json", payload)
    return payload
