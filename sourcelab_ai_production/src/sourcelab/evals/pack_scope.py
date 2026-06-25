"""Helpers for pack-scoped golden eval execution."""

from __future__ import annotations

from pathlib import Path

from sourcelab.core.models import SearchResult
from sourcelab.retrieval.index import PocketIndex
from sourcelab.sources.registry import SourceRegistry
from sourcelab.sources.source_pack import load_source_pack_manifest


def get_pack_source_ids(project_root: Path, pack_name: str) -> set[str]:
    """Return source IDs declared in a source pack manifest."""
    manifest = load_source_pack_manifest(project_root, pack_name)
    if manifest is None:
        return set()
    return {
        source_info.get("source_id", "")
        for source_info in manifest.get("sources", [])
        if source_info.get("source_id")
    }


def get_pack_scoped_registry(project_root: Path, pack_name: str) -> SourceRegistry:
    """Load active/approved sources for a source pack."""
    return SourceRegistry.for_pack(project_root, pack_name)


def build_pack_search(project_root: Path, pack_name: str):
    """Build a search function scoped to one source pack."""
    registry = get_pack_scoped_registry(project_root, pack_name)
    candidate_source_ids = [source.source_id for source in registry.sources]
    index = PocketIndex.from_registry(registry)

    def search_fn(query: str, top_k: int = 5) -> list[SearchResult]:
        return index.search(query, top_k=top_k)

    return search_fn, candidate_source_ids
