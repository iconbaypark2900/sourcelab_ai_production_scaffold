"""Retrieval evaluation module.

Instruction:
- Evaluates retrieval quality using standard metrics.
- Uses a fixture file for test queries with expected results.
- Reports hit@k, source match rate, and average scores.
"""

from __future__ import annotations

import json
from pathlib import Path

from sourcelab.retrieval.schemas import RetrievalEvaluationReport


def load_eval_fixtures(project_root: Path | None = None) -> list[dict]:
    """Load evaluation fixtures from the test fixtures directory.

    Args:
        project_root: Root directory of the project. If None, uses current dir.

    Returns:
        List of evaluation queries with expected results.
    """
    if project_root is None:
        project_root = Path.cwd()

    fixture_path = project_root / "tests" / "fixtures" / "retrieval_eval.json"
    if not fixture_path.exists():
        return []

    try:
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        return data.get("queries", [])
    except (json.JSONDecodeError, KeyError):
        return []


def evaluate_retrieval(
    search_fn,
    queries: list[dict],
    top_k: int = 3,
    backend: str = "hash",
    store: str = "memory",
) -> RetrievalEvaluationReport:
    """Evaluate retrieval quality.

    Args:
        search_fn: Function that takes (query, top_k) and returns list of SearchResult.
        queries: List of query dicts with 'query' and 'expected_source_ids' keys.
        top_k: Number of results to retrieve per query.
        backend: Name of the embedding backend used.
        store: Name of the vector store used.

    Returns:
        Evaluation report with metrics.
    """
    hit_at_1_count = 0
    hit_at_3_count = 0
    source_match_count = 0
    total_score = 0.0
    failed_queries: list[str] = []
    valid_queries = 0

    for query_data in queries:
        query = query_data.get("query", "")
        expected_sources = set(query_data.get("expected_source_ids", []))

        if not query or not expected_sources:
            continue

        valid_queries += 1

        try:
            results = search_fn(query, top_k=top_k)

            if not results:
                failed_queries.append(query)
                continue

            # Check hit@1
            if results[0].source_id in expected_sources:
                hit_at_1_count += 1

            # Check hit@3
            top_3_sources = {r.source_id for r in results[:3]}
            if top_3_sources & expected_sources:
                hit_at_3_count += 1

            # Check source match rate
            matched_sources = {r.source_id for r in results} & expected_sources
            if matched_sources:
                source_match_count += 1

            # Accumulate scores
            for r in results:
                total_score += r.score

        except Exception:
            failed_queries.append(query)

    if valid_queries == 0:
        return RetrievalEvaluationReport(
            query_count=0,
            hit_at_1=0.0,
            hit_at_3=0.0,
            source_match_rate=0.0,
            average_final_score=0.0,
            failed_queries=[],
            backend=backend,
            store=store,
        )

    total_results = valid_queries * top_k

    return RetrievalEvaluationReport(
        query_count=valid_queries,
        hit_at_1=round(hit_at_1_count / valid_queries, 4),
        hit_at_3=round(hit_at_3_count / valid_queries, 4),
        source_match_rate=round(source_match_count / valid_queries, 4),
        average_final_score=round(total_score / max(total_results, 1), 4),
        failed_queries=failed_queries,
        backend=backend,
        store=store,
    )


def format_evaluation_report(report: RetrievalEvaluationReport) -> dict:
    """Format an evaluation report for display.

    Args:
        report: The evaluation report to format.

    Returns:
        Formatted dictionary for JSON output.
    """
    return {
        "query_count": report.query_count,
        "hit_at_1": f"{report.hit_at_1:.2%}",
        "hit_at_3": f"{report.hit_at_3:.2%}",
        "source_match_rate": f"{report.source_match_rate:.2%}",
        "average_final_score": round(report.average_final_score, 4),
        "failed_queries": report.failed_queries,
        "backend": report.backend,
        "store": report.store,
        "timestamp": report.timestamp.isoformat(),
    }
