"""Library expansion plan derived from source_expansion_suggestions.json."""

from __future__ import annotations

from pathlib import Path

from sourcelab.harness.proof_bundle import ProofBundle
from sourcelab.library.io import load_model, utc_now
from sourcelab.library.schemas import SourceExpansionSuggestions
from sourcelab.research.schemas import CollectorQueryPlan, LibraryExpansionPlan, ResearchPlan


COLLECTOR_COMMANDS: dict[str, str] = {
    "local_docs": 'sourcelab library collect-local --path . --domain user_project_library',
    "arxiv": 'sourcelab library collect-arxiv --query "{query}" --domain research --max-results 5',
    "pubmed": 'sourcelab library collect-pubmed --query "{query}" --domain research --max-results 5',
    "nvd": 'sourcelab library collect-nvd --keyword "{query}" --domain security --max-results 5',
}


def _example_command(collector: str, query: str) -> str:
    template = COLLECTOR_COMMANDS.get(collector, f"sourcelab library collect-{collector}")
    if "{query}" in template:
        safe_query = query.replace('"', "'")
        return template.format(query=safe_query)
    return template


def build_library_expansion_plan(
    run_id: str,
    topic: str,
    source_pack: str,
    suggestions: SourceExpansionSuggestions | None,
) -> LibraryExpansionPlan:
    """Build a deterministic library expansion plan from expansion suggestions."""
    if suggestions is None or not suggestions.suggestions:
        return LibraryExpansionPlan(
            run_id=run_id,
            topic=topic,
            source_pack=source_pack,
            generated_at=utc_now(),
            manual_source_requests=[
                "No thin-evidence triggers — library expansion not required for this run.",
            ],
        )

    query_hint = topic.strip() or "source expansion"
    recommended: list[str] = []
    collector_queries: list[CollectorQueryPlan] = []
    promotion_targets: list[str] = []
    manual_requests: list[str] = []

    for suggestion in suggestions.suggestions:
        if suggestion.collector not in recommended:
            recommended.append(suggestion.collector)
        hint = suggestion.query_hint.strip() or query_hint
        collector_queries.append(
            CollectorQueryPlan(
                collector=suggestion.collector,
                query=hint,
                example_command=_example_command(suggestion.collector, hint),
                priority=suggestion.priority,
            )
        )
        if suggestion.collector == "local_docs":
            promotion_targets.append(
                f"sourcelab library promote --domain user_project_library --target-pack {source_pack} --dry-run"
            )
        elif suggestion.domain_tags:
            domain = suggestion.domain_tags[0]
            promotion_targets.append(
                f"sourcelab library promote --domain {domain} --target-pack {source_pack} --dry-run"
            )

    manual_requests.append(
        "Review collector output under data/library/bronze/ before promotion."
    )
    if suggestions.triggers:
        manual_requests.append(f"Thin-evidence triggers: {', '.join(suggestions.triggers)}")

    return LibraryExpansionPlan(
        run_id=run_id,
        topic=topic,
        source_pack=source_pack,
        generated_at=utc_now(),
        recommended_collectors=recommended,
        collector_queries=collector_queries,
        promotion_targets=sorted(set(promotion_targets)),
        manual_source_requests=manual_requests,
    )


def render_expansion_plan_markdown(plan: LibraryExpansionPlan) -> str:
    """Render a human-readable library expansion plan."""
    lines = [
        f"# Library Expansion Plan — {plan.topic}",
        "",
        f"- **Run:** `{plan.run_id}`",
        f"- **Source pack:** `{plan.source_pack}`",
        f"- **Generated:** {plan.generated_at.isoformat()}",
        "",
        "## Recommended collectors",
        "",
    ]
    if plan.recommended_collectors:
        for collector in plan.recommended_collectors:
            lines.append(f"- `{collector}`")
    else:
        lines.append("- _(none)_")

    lines.extend(["", "## Collector queries", ""])
    for entry in plan.collector_queries:
        lines.append(f"### {entry.collector} ({entry.priority})")
        lines.append(f"- Query: {entry.query}")
        lines.append(f"- Command: `{entry.example_command}`")
        lines.append("")

    lines.extend(["## Promotion targets", ""])
    for target in plan.promotion_targets:
        lines.append(f"- `{target}`")

    lines.extend(["", "## Manual source requests", ""])
    for request in plan.manual_source_requests:
        lines.append(f"- {request}")
    lines.append("")
    return "\n".join(lines)


def maybe_write_library_expansion_plan(
    run_dir: Path,
    plan: ResearchPlan,
    proof: ProofBundle | None = None,
) -> LibraryExpansionPlan | None:
    """Write library_expansion_plan.json when expansion suggestions exist."""
    expansion_path = run_dir / "source_expansion_suggestions.json"
    suggestions: SourceExpansionSuggestions | None = None
    if expansion_path.exists():
        suggestions = load_model(expansion_path, SourceExpansionSuggestions)

    if suggestions is None and not plan.profile_source_expansion_suggestions:
        return None

    payload = build_library_expansion_plan(
        run_dir.name,
        plan.topic,
        plan.source_pack,
        suggestions,
    )
    markdown = render_expansion_plan_markdown(payload)
    if proof is not None:
        proof.write_json("library_expansion_plan.json", payload.model_dump(mode="json"))
        proof.write_text("library_expansion_plan.md", markdown)
    else:
        (run_dir / "library_expansion_plan.json").write_text(
            payload.model_dump_json(indent=2),
            encoding="utf-8",
        )
        (run_dir / "library_expansion_plan.md").write_text(markdown, encoding="utf-8")
    return payload
