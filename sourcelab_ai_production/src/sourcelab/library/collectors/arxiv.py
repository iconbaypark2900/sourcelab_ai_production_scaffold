"""arXiv metadata collector (metadata-only, no PDF download)."""

from __future__ import annotations

from collections.abc import Callable
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from sourcelab.library.io import save_json, sha256_text, utc_now
from sourcelab.library.paths import ensure_library_layout, library_root
from sourcelab.library.schemas import LibraryBuildReport, RawSourceRecord
from sourcelab.sources.registry import normalize_source_id

ARXIV_API = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
DEFAULT_DELAY_SECONDS = 3.0


def _parse_arxiv_feed(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    entries = []
    for entry in root.findall("atom:entry", ATOM_NS):
        entry_id = entry.findtext("atom:id", default="", namespaces=ATOM_NS)
        arxiv_id = entry_id.rsplit("/", maxsplit=1)[-1] if entry_id else ""
        title = (entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").strip()
        summary = (entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or "").strip()
        published = entry.findtext("atom:published", default="", namespaces=ATOM_NS)
        authors = [
            author.findtext("atom:name", default="", namespaces=ATOM_NS)
            for author in entry.findall("atom:author", ATOM_NS)
        ]
        authors = [name for name in authors if name]
        links = entry.findall("atom:link", ATOM_NS)
        abs_url = next((link.get("href") for link in links if link.get("rel") == "alternate"), entry_id)
        entries.append(
            {
                "arxiv_id": arxiv_id,
                "title": title.replace("\n", " "),
                "summary": summary.replace("\n", " "),
                "published": published,
                "authors": authors,
                "url": abs_url,
            }
        )
    return entries


def _http_get(url: str, fetcher: Callable[[str], str] | None = None) -> str:
    if fetcher is not None:
        return fetcher(url)
    request = urllib.request.Request(url, headers={"User-Agent": "SourceLab-Library/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def fetch_arxiv_metadata(
    query: str,
    max_results: int = 5,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    fetcher: Callable[[str], str] | None = None,
) -> list[dict]:
    """Fetch arXiv metadata for a search query."""
    params = f"search_query=all:{quote(query)}&start=0&max_results={max_results}"
    url = f"{ARXIV_API}?{params}"
    time.sleep(delay_seconds)
    return _parse_arxiv_feed(_http_get(url, fetcher=fetcher))


def collect_arxiv(
    project_root: Path,
    query: str,
    domain: str,
    max_results: int = 5,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    fetcher: Callable[[str], str] | None = None,
) -> LibraryBuildReport:
    """Collect arXiv metadata into bronze raw records."""
    ensure_library_layout(project_root)
    raw_dir = library_root(project_root) / "raw" / "arxiv"
    raw_dir.mkdir(parents=True, exist_ok=True)

    entries = fetch_arxiv_metadata(
        query, max_results=max_results, delay_seconds=delay_seconds, fetcher=fetcher
    )
    retrieved_at = utc_now()
    count = 0

    for entry in entries:
        arxiv_id = entry["arxiv_id"]
        if not arxiv_id:
            continue
        record_id = normalize_source_id(f"arxiv_{arxiv_id.replace('.', '_')}")
        abstract_path = raw_dir / f"{record_id}.txt"
        abstract_text = entry["summary"]
        abstract_path.write_text(abstract_text, encoding="utf-8")
        published_at = None
        if entry.get("published"):
            published_at = datetime.fromisoformat(entry["published"].replace("Z", "+00:00"))

        record = RawSourceRecord(
            record_id=record_id,
            origin="arxiv",
            external_id=arxiv_id,
            title=entry["title"],
            url=entry.get("url"),
            publisher="arxiv",
            authors=entry.get("authors", []),
            published_at=published_at,
            retrieved_at=retrieved_at,
            license="arxiv",
            source_type="preprint_metadata",
            domain_tags=[domain],
            topic_tags=[],
            summary=abstract_text[:500],
            key_terms=[],
            raw_path=str(abstract_path.relative_to(project_root)),
            checksum=sha256_text(abstract_text),
            metadata={"query": query},
        )
        save_json(raw_dir / f"{record_id}.json", record.model_dump(mode="json"))
        count += 1

    return LibraryBuildReport(
        generated_at=retrieved_at,
        stage="collect-arxiv",
        status="ok",
        message=f"Collected {count} arXiv metadata records for query={query!r}",
        counts={"raw_records": count},
    )
