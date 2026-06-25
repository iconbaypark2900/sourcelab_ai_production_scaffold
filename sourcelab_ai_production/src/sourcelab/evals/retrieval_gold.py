"""Retrieval golden eval for SourceLab AI.

Instruction:
- Evaluate retrieval quality against golden test cases.
- Uses source pack eval fixtures.
- Reports pass/fail for each case.
"""

from __future__ import annotations

import json
from pathlib import Path

from sourcelab.evals.schemas import GoldenEvalFailure, GoldenEvalReport
from sourcelab.sources.chunker import _strip_frontmatter
from sourcelab.sources.registry import SourceRegistry


def _term_search_text(
    project_root: Path,
    pack_name: str,
    results,
    hit_sources: set[str],
    top_k: int,
) -> str:
    """Build searchable text from previews and matched source bodies."""
    texts = [result.text_preview.lower() for result in results[:top_k]]

    if hit_sources:
        registry = SourceRegistry.for_pack(project_root, pack_name)
        for source in registry.sources:
            if source.source_id in hit_sources and source.path:
                source_path = Path(source.path)
                if not source_path.is_absolute():
                    source_path = project_root / source.path
                if source_path.exists():
                    body = _strip_frontmatter(source_path.read_text(encoding="utf-8", errors="ignore"))
                    texts.append(body.lower())

    return " ".join(texts)


def load_retrieval_gold_cases(project_root: Path, pack_name: str) -> list[dict]:
    """Load retrieval golden eval cases from source pack."""
    eval_path = project_root / "data" / "source_packs" / pack_name / "evals" / "retrieval_gold.json"
    if not eval_path.exists():
        return []

    try:
        data = json.loads(eval_path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("cases", [])
    except (json.JSONDecodeError, KeyError):
        return []


def run_retrieval_gold_eval(
    project_root: Path,
    pack_name: str,
    search_fn,
    top_k: int = 5,
) -> GoldenEvalReport:
    """Run retrieval golden eval against source pack.

    Args:
        project_root: Project root directory.
        pack_name: Source pack name.
        search_fn: Function that takes (query, top_k) and returns list of SearchResult.
        top_k: Number of results to retrieve per query.

    Returns:
        GoldenEvalReport with pass/fail status.
    """
    cases = load_retrieval_gold_cases(project_root, pack_name)
    total = len(cases)
    passed = 0
    failures = []
    diagnostics: list[dict] = []

    for idx, case in enumerate(cases):
        query = case.get("query", "")
        expected_sources = set(case.get("expected_source_ids", []))
        expected_terms = case.get("expected_terms", [])
        forbidden_sources = set(case.get("forbidden_source_ids", []))
        min_hit = case.get("min_hit_at_k", 1)
        description = case.get("description", f"Case {idx + 1}")

        if not query or not expected_sources:
            failures.append(GoldenEvalFailure(
                case_index=idx,
                case_description=description,
                expected=f"Valid query with expected sources",
                actual="Empty query or no expected sources",
                details="Invalid test case configuration",
            ))
            continue

        try:
            results = search_fn(query, top_k=top_k)
            result_source_ids = [r.source_id for r in results[:top_k]]
            diagnostics.append({
                "pack_name": pack_name,
                "case_index": idx,
                "candidate_source_ids": getattr(search_fn, "candidate_source_ids", []),
                "returned_source_ids": result_source_ids,
                "expected_source_ids": sorted(expected_sources),
            })

            if not results:
                failures.append(GoldenEvalFailure(
                    case_index=idx,
                    case_description=description,
                    expected=f"Results for query: {query}",
                    actual="No results returned",
                    details=f"Expected sources: {expected_sources}",
                ))
                continue

            # Check hit@k
            hit_sources = set(result_source_ids) & expected_sources

            if len(hit_sources) < min_hit:
                failures.append(GoldenEvalFailure(
                    case_index=idx,
                    case_description=description,
                    expected=f"At least {min_hit} hit(s) from {expected_sources}",
                    actual=f"Got {len(hit_sources)} hit(s): {hit_sources}",
                    details=f"Result sources: {result_source_ids}",
                ))
                continue

            # Check forbidden sources
            forbidden_hits = set(result_source_ids) & forbidden_sources
            if forbidden_hits:
                failures.append(GoldenEvalFailure(
                    case_index=idx,
                    case_description=description,
                    expected=f"No forbidden sources in results",
                    actual=f"Found forbidden sources: {forbidden_hits}",
                    details=f"Result sources: {result_source_ids}",
                ))
                continue

            # Check expected terms (optional)
            if expected_terms:
                result_texts = _term_search_text(
                    project_root,
                    pack_name,
                    results,
                    hit_sources,
                    top_k,
                )
                term_hits = sum(1 for term in expected_terms if term.lower() in result_texts)
                if term_hits == 0:
                    failures.append(GoldenEvalFailure(
                        case_index=idx,
                        case_description=description,
                        expected=f"At least one of terms: {expected_terms}",
                        actual="No expected terms found in results",
                        details=f"Result text preview: {result_texts[:200]}",
                    ))
                    continue

            passed += 1

        except Exception as e:
            failures.append(GoldenEvalFailure(
                case_index=idx,
                case_description=description,
                expected="Successful search",
                actual=f"Exception: {e}",
                details=str(e),
            ))

    pass_rate = passed / total if total > 0 else 0.0

    return GoldenEvalReport(
        eval_name="retrieval_gold",
        pack_name=pack_name,
        total_cases=total,
        passed_cases=passed,
        failed_cases=len(failures),
        pass_rate=pass_rate,
        failures=failures,
        diagnostics=diagnostics,
    )
