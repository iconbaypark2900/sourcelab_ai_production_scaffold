"""NVD CVE metadata collector."""

from __future__ import annotations

import json
import time
import urllib.request
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from sourcelab.library.io import save_json, sha256_text, utc_now
from sourcelab.library.paths import ensure_library_layout, library_root
from sourcelab.library.schemas import LibraryBuildReport, RawSourceRecord
from sourcelab.sources.registry import normalize_source_id

NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
DEFAULT_DELAY_SECONDS = 6.0


def _parse_nvd_response(payload: dict) -> list[dict]:
    vulnerabilities = payload.get("vulnerabilities", [])
    records = []
    for item in vulnerabilities:
        cve = item.get("cve", {})
        cve_id = cve.get("id", "")
        descriptions = cve.get("descriptions", [])
        summary = next((d.get("value", "") for d in descriptions if d.get("lang") == "en"), "")
        if not summary and descriptions:
            summary = descriptions[0].get("value", "")
        published = cve.get("published")
        records.append({"cve_id": cve_id, "summary": summary, "published": published, "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}"})
    return records


def _http_get(url: str, fetcher: Callable[[str], str] | None = None) -> str:
    if fetcher is not None:
        return fetcher(url)
    request = urllib.request.Request(url, headers={"User-Agent": "SourceLab-Library/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def fetch_nvd_metadata(
    keyword: str | None = None,
    modified_since: str | None = None,
    max_results: int = 5,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    fetcher: Callable[[str], str] | None = None,
) -> list[dict]:
    """Fetch CVE metadata from the NVD API."""
    params: dict[str, str | int] = {"resultsPerPage": max_results}
    if keyword:
        params["keywordSearch"] = keyword
    if modified_since:
        params["lastModStartDate"] = modified_since

    time.sleep(delay_seconds)
    url = f"{NVD_API}?{urlencode(params)}"
    return _parse_nvd_response(json.loads(_http_get(url, fetcher=fetcher)))


def collect_nvd(
    project_root: Path,
    domain: str,
    keyword: str | None = None,
    modified_since: str | None = None,
    max_results: int = 5,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    fetcher: Callable[[str], str] | None = None,
) -> LibraryBuildReport:
    """Collect NVD CVE metadata into bronze raw records."""
    ensure_library_layout(project_root)
    raw_dir = library_root(project_root) / "raw" / "nvd"
    raw_dir.mkdir(parents=True, exist_ok=True)

    if not keyword and not modified_since:
        keyword = "library"

    entries = fetch_nvd_metadata(
        keyword=keyword,
        modified_since=modified_since,
        max_results=max_results,
        delay_seconds=delay_seconds,
        fetcher=fetcher,
    )
    retrieved_at = utc_now()
    count = 0

    for entry in entries:
        cve_id = entry.get("cve_id", "")
        if not cve_id:
            continue
        record_id = normalize_source_id(cve_id.lower().replace("-", "_"))
        summary_path = raw_dir / f"{record_id}.txt"
        summary_text = entry.get("summary", "")
        summary_path.write_text(summary_text, encoding="utf-8")
        published_at = None
        if entry.get("published"):
            published_at = datetime.fromisoformat(entry["published"].replace("Z", "+00:00"))

        record = RawSourceRecord(
            record_id=record_id,
            origin="nvd",
            external_id=cve_id,
            title=cve_id,
            url=entry.get("url"),
            publisher="nvd",
            authors=[],
            published_at=published_at,
            retrieved_at=retrieved_at,
            license="public_domain",
            source_type="cve_metadata",
            domain_tags=[domain],
            topic_tags=["security", "cve"],
            summary=summary_text[:500],
            key_terms=["cve", "vulnerability"],
            raw_path=str(summary_path.relative_to(project_root)),
            checksum=sha256_text(summary_text),
            metadata={"keyword": keyword or "", "modified_since": modified_since or ""},
        )
        save_json(raw_dir / f"{record_id}.json", record.model_dump(mode="json"))
        count += 1

    return LibraryBuildReport(
        generated_at=retrieved_at,
        stage="collect-nvd",
        status="ok",
        message=f"Collected {count} NVD CVE metadata records",
        counts={"raw_records": count},
    )
