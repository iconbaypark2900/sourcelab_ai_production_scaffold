"""PubMed metadata collector (PMID metadata and abstract only)."""

from __future__ import annotations

import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from sourcelab.library.io import save_json, sha256_text, utc_now
from sourcelab.library.paths import ensure_library_layout, library_root
from sourcelab.library.schemas import LibraryBuildReport, RawSourceRecord
from sourcelab.sources.registry import normalize_source_id

ESEARCH_URL = "https://eutils.ncbi.n.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
DEFAULT_DELAY_SECONDS = 0.5


def _parse_pubmed_xml(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    articles = []
    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        pmid = pmid_el.text if pmid_el is not None else ""
        title_el = article.find(".//ArticleTitle")
        title = title_el.text if title_el is not None else ""
        abstract_parts = []
        for abstract_text in article.findall(".//AbstractText"):
            label = abstract_text.get("Label", "")
            text = abstract_text.text or ""
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
        abstract = " ".join(abstract_parts).strip()
        authors = []
        for author in article.findall(".//Author"):
            last = author.findtext("LastName", default="")
            fore = author.findtext("ForeName", default="")
            if last:
                authors.append(f"{fore} {last}".strip())
        pub_date = article.find(".//PubDate/Year")
        published = pub_date.text if pub_date is not None else None
        articles.append(
            {
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "published": published,
            }
        )
    return articles


def _http_get(url: str, fetcher: Callable[[str], str] | None = None) -> str:
    if fetcher is not None:
        return fetcher(url)
    request = urllib.request.Request(url, headers={"User-Agent": "SourceLab-Library/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def fetch_pubmed_metadata(
    query: str,
    max_results: int = 5,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    fetcher: Callable[[str], str] | None = None,
) -> list[dict]:
    """Search PubMed and fetch PMID metadata/abstracts."""
    time.sleep(delay_seconds)
    search_url = f"{ESEARCH_URL}?{urlencode({'db': 'pubmed', 'term': query, 'retmax': max_results, 'retmode': 'json'})}"
    search_payload = json.loads(_http_get(search_url, fetcher=fetcher))
    id_list = search_payload.get("esearchresult", {}).get("idlist", [])
    if not id_list:
        return []

    time.sleep(delay_seconds)
    fetch_url = f"{EFETCH_URL}?{urlencode({'db': 'pubmed', 'id': ','.join(id_list), 'retmode': 'xml'})}"
    return _parse_pubmed_xml(_http_get(fetch_url, fetcher=fetcher))


def collect_pubmed(
    project_root: Path,
    query: str,
    domain: str,
    max_results: int = 5,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    fetcher: Callable[[str], str] | None = None,
) -> LibraryBuildReport:
    """Collect PubMed metadata into bronze raw records."""
    ensure_library_layout(project_root)
    raw_dir = library_root(project_root) / "raw" / "pubmed"
    raw_dir.mkdir(parents=True, exist_ok=True)

    articles = fetch_pubmed_metadata(
        query, max_results=max_results, delay_seconds=delay_seconds, fetcher=fetcher
    )
    retrieved_at = utc_now()
    count = 0

    for article in articles:
        pmid = article.get("pmid", "")
        if not pmid:
            continue
        record_id = normalize_source_id(f"pubmed_{pmid}")
        abstract_path = raw_dir / f"{record_id}.txt"
        abstract_text = article.get("abstract") or article.get("title", "")
        abstract_path.write_text(abstract_text, encoding="utf-8")
        published_at = None
        if article.get("published"):
            try:
                published_at = datetime(int(article["published"]), 1, 1, tzinfo=timezone.utc)
            except ValueError:
                published_at = None

        record = RawSourceRecord(
            record_id=record_id,
            origin="pubmed",
            external_id=pmid,
            title=article.get("title", f"PubMed {pmid}"),
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            publisher="pubmed",
            authors=article.get("authors", []),
            published_at=published_at,
            retrieved_at=retrieved_at,
            license="pubmed",
            source_type="journal_metadata",
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
        stage="collect-pubmed",
        status="ok",
        message=f"Collected {count} PubMed metadata records for query={query!r}",
        counts={"raw_records": count},
    )
