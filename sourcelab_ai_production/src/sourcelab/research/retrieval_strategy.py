"""Library-aware retrieval strategy and execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from sourcelab.core.models import SearchResult, SourceChunk, SourceRecord
from sourcelab.library.io import load_model, utc_now
from sourcelab.library.normalize import load_source_cards
from sourcelab.library.paths import library_root
from sourcelab.library.schemas import SourceChunk as LibraryChunk
from sourcelab.research.planner import build_research_plan
from sourcelab.research.schemas import (
    EvidenceOrigin,
    LabeledRetrievalHit,
    ResearchPlan,
    RetrievalQuery,
    RetrievalStrategy,
)
from sourcelab.retrieval.compression import int8_dequantize, int8_quantize
from sourcelab.retrieval.embedding_backends import HashEmbeddingBackend
from sourcelab.retrieval.index import PocketIndex
from sourcelab.sources.chunker import simple_chunk_source
from sourcelab.sources.registry import SourceRegistry
from sourcelab.sources.trust import trust_weight


@dataclass(frozen=True)
class IndexedChunk:
    chunk: SourceChunk
    title: str
    origin: EvidenceOrigin
    library_card_id: str | None = None


def queries_from_plan(plan: ResearchPlan) -> list[RetrievalQuery]:
    """Derive retrieval queries from a research plan."""
    queries: list[RetrievalQuery] = []
    queries.append(
        RetrievalQuery(
            query_id=f"{plan.run_id}_topic",
            text=plan.topic,
            rationale="Primary topic query",
            priority="high",
        )
    )
    for sub in plan.subtopics:
        queries.append(
            RetrievalQuery(
                query_id=f"{plan.run_id}_{sub.subtopic_id}",
                text=f"{plan.topic} {sub.title}",
                rationale=sub.rationale,
                priority=sub.priority,
                subtopic_id=sub.subtopic_id,
            )
        )
    for idx, question in enumerate(plan.research_questions[:3]):
        queries.append(
            RetrievalQuery(
                query_id=f"{plan.run_id}_q{idx + 1}",
                text=question,
                rationale="Research question query",
                priority="medium",
            )
        )
    return queries


DOMAIN_RESEARCH_PACKS = frozenset(
    {
        "agentic_engineering_v1",
        "quantum_finance_v1",
        "biomedical_ai_v1",
        "trading_research_v1",
    }
)


def _library_enabled_for_pack(source_pack: str) -> bool:
    return source_pack in DOMAIN_RESEARCH_PACKS


def _load_library_silver_chunks(project_root: Path, plan: ResearchPlan) -> list[IndexedChunk]:
    if not _library_enabled_for_pack(plan.source_pack):
        return []
    chunks_dir = library_root(project_root) / "silver" / "chunks"
    if not chunks_dir.exists():
        return []
    indexed: list[IndexedChunk] = []
    cards = {card.source_id: card for card in load_source_cards(project_root)}
    target_domains = set(plan.target_domains)
    for path in sorted(chunks_dir.glob("*.json")):
        lib_chunk = load_model(path, LibraryChunk)
        card = cards.get(lib_chunk.source_id)
        if card is None:
            continue
        if target_domains and not (set(card.domain_tags) & target_domains):
            if "user_project_library" not in card.domain_tags:
                continue
        indexed.append(
            IndexedChunk(
                chunk=SourceChunk(
                    chunk_id=lib_chunk.chunk_id,
                    source_id=lib_chunk.source_id,
                    text=lib_chunk.text,
                    section_title=lib_chunk.section,
                    trust_tier=card.trust_tier if card else "C",
                    token_count=lib_chunk.token_estimate or len(lib_chunk.text.split()),
                ),
                title=card.title if card else lib_chunk.source_id,
                origin="library_silver",
                library_card_id=lib_chunk.source_id,
            )
        )
    return indexed


def _load_promoted_candidate_chunks(project_root: Path, source_pack: str) -> list[IndexedChunk]:
    candidates_dir = library_root(project_root) / "promotion" / "candidates" / source_pack
    if not candidates_dir.exists():
        return []
    indexed: list[IndexedChunk] = []
    for path in sorted(candidates_dir.glob("*.md")):
        source_id = f"promoted_{path.stem}"
        record = SourceRecord(
            source_id=source_id,
            title=path.stem.replace("_", " "),
            path=str(path),
            trust_tier="B",
            retrieved_at=utc_now(),
            hash_sha256="promoted",
            source_pack=source_pack,
        )
        for chunk in simple_chunk_source(record):
            indexed.append(
                IndexedChunk(
                    chunk=chunk,
                    title=record.title,
                    origin="promoted_candidate",
                    library_card_id=source_id,
                )
            )
    return indexed


def _load_source_pack_chunks(registry: SourceRegistry) -> list[IndexedChunk]:
    indexed: list[IndexedChunk] = []
    for source in registry.sources:
        for chunk in simple_chunk_source(source):
            indexed.append(
                IndexedChunk(
                    chunk=chunk,
                    title=source.title,
                    origin="source_pack",
                    library_card_id=None,
                )
            )
    return indexed


def _search_indexed_chunks(
    indexed: list[IndexedChunk],
    query: str,
    query_id: str,
    top_k: int,
    dim: int = 128,
) -> list[LabeledRetrievalHit]:
    if not indexed:
        return []
    backend = HashEmbeddingBackend()
    chunks = [item.chunk for item in indexed]
    texts = [chunk.text for chunk in chunks]
    fp32 = backend.embed_batch(texts, dim=dim)
    int8, scale = int8_quantize(fp32)
    matrix = int8_dequantize(int8, scale)
    query_vec = backend.embed(query, dim=dim)
    raw_scores = matrix @ query_vec

    ranked: list[tuple[int, float]] = []
    for idx, raw_score in enumerate(raw_scores):
        adjusted = float(raw_score) * trust_weight(chunks[idx].trust_tier)
        ranked.append((idx, adjusted))
    ranked.sort(key=lambda item: item[1], reverse=True)

    hits: list[LabeledRetrievalHit] = []
    for idx, score in ranked[:top_k]:
        item = indexed[idx]
        chunk = item.chunk
        hits.append(
            LabeledRetrievalHit(
                chunk_id=chunk.chunk_id,
                source_id=chunk.source_id,
                library_card_id=item.library_card_id,
                title=item.title,
                score=round(float(score), 4),
                trust_tier=chunk.trust_tier,
                text_preview=" ".join(chunk.text.split()[:50]),
                origin=item.origin,
                query_id=query_id,
            )
        )
    return hits


def build_retrieval_strategy(
    project_root: Path,
    run_id: str,
    topic: str,
    source_pack: str,
    plan: ResearchPlan | None = None,
    per_query_top_k: int = 2,
    final_top_k: int = 6,
) -> RetrievalStrategy:
    """Build and execute a library-aware retrieval strategy."""
    plan = plan or build_research_plan(run_id, topic, source_pack)
    queries = queries_from_plan(plan)

    registry = SourceRegistry.for_pack(project_root, source_pack)
    pack_chunks = _load_source_pack_chunks(registry)
    silver_chunks = _load_library_silver_chunks(project_root, plan)
    promoted_chunks = _load_promoted_candidate_chunks(project_root, source_pack) if _library_enabled_for_pack(source_pack) else []

    origins_enabled: list[EvidenceOrigin] = ["source_pack"]
    if silver_chunks:
        origins_enabled.append("library_silver")
    if promoted_chunks:
        origins_enabled.append("promoted_candidate")

    all_indexed = pack_chunks + silver_chunks + promoted_chunks
    hits_by_chunk: dict[str, LabeledRetrievalHit] = {}

    for query in queries:
        query_hits = _search_indexed_chunks(all_indexed, query.text, query.query_id, per_query_top_k)
        for hit in query_hits:
            existing = hits_by_chunk.get(hit.chunk_id)
            if existing is None or hit.score > existing.score:
                hits_by_chunk[hit.chunk_id] = hit

    ranked_hits = sorted(hits_by_chunk.values(), key=lambda hit: hit.score, reverse=True)
    pack_hits = [hit for hit in ranked_hits if hit.origin == "source_pack"]
    other_hits = [hit for hit in ranked_hits if hit.origin != "source_pack"]

    selected: list[LabeledRetrievalHit] = []
    if pack_hits:
        selected.extend(pack_hits[: max(final_top_k // 2, 2)])
    for hit in other_hits:
        if len(selected) >= final_top_k:
            break
        if hit.chunk_id not in {row.chunk_id for row in selected}:
            selected.append(hit)
    for hit in pack_hits:
        if len(selected) >= final_top_k:
            break
        if hit.chunk_id not in {row.chunk_id for row in selected}:
            selected.append(hit)
    selected = selected[:final_top_k]

    return RetrievalStrategy(
        run_id=run_id,
        topic=topic,
        source_pack=source_pack,
        generated_at=utc_now(),
        queries=queries,
        origins_enabled=origins_enabled,
        source_pack_source_count=len(registry.sources),
        library_silver_card_count=len(load_source_cards(project_root)),
        promoted_candidate_count=len(list((library_root(project_root) / "promotion" / "candidates" / source_pack).glob("*.md")))
        if (library_root(project_root) / "promotion" / "candidates" / source_pack).exists()
        else 0,
        hits=selected,
        selected_chunk_ids=[hit.chunk_id for hit in selected],
    )


def strategy_to_search_results(strategy: RetrievalStrategy) -> list[SearchResult]:
    """Convert labeled hits to standard SearchResult objects for the lesson pipeline."""
    return [
        SearchResult(
            chunk_id=hit.chunk_id,
            source_id=hit.source_id,
            title=hit.title,
            score=hit.score,
            trust_tier=hit.trust_tier,  # type: ignore[arg-type]
            text_preview=hit.text_preview,
        )
        for hit in strategy.hits
    ]


def fallback_pack_search(registry: SourceRegistry, topic: str, top_k: int = 4) -> list[SearchResult]:
    """Fallback to pack-only PocketIndex search when library layers are empty."""
    index = PocketIndex.from_registry(registry)
    return index.search(topic, top_k=top_k)
