"""URL source ingestion for SourceLab AI.

Instruction:
- Fetch and parse web content from URLs.
- Requires requests and beautifulsoup4: pip install -e ".[ingest]"
- Save extracted text to data/approved_sources/web/.
- Compute hashes and register sources in the registry.
- Enforce max content size and timeout limits.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from sourcelab.core.models import SourceRecord
from sourcelab.sources.registry import SourceRegistry, normalize_source_id

MAX_CONTENT_SIZE = 5 * 1024 * 1024  # 5MB
REQUEST_TIMEOUT = 30  # seconds
ALLOWED_CONTENT_TYPES = {"text/html", "text/plain", "text/markdown", "application/xhtml+xml"}


def fetch_url_content(url: str) -> tuple[str, str, str | None]:
    """Fetch content from a URL.

    Returns:
        Tuple of (text_content, content_type, error_message).
        If successful, error_message is None.
    """
    try:
        import requests
    except ImportError:
        return "", "", "requests not installed. Install with: pip install -e '.[ingest]'"

    try:
        headers = {
            "User-Agent": "SourceLab-AI/1.0 (source-grounded-lesson-generator)"
        }
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "text/html").split(";")[0].strip()

        if content_type not in ALLOWED_CONTENT_TYPES:
            return "", content_type, f"Unsupported content type: {content_type}"

        if len(response.content) > MAX_CONTENT_SIZE:
            return "", content_type, f"Content too large: {len(response.content)} bytes (max: {MAX_CONTENT_SIZE})"

        return response.text, content_type, None

    except requests.exceptions.Timeout:
        return "", "", f"Request timed out after {REQUEST_TIMEOUT} seconds"
    except requests.exceptions.RequestException as e:
        return "", "", f"Request failed: {e}"


def parse_html_to_text(html_content: str) -> tuple[str, str | None]:
    """Parse HTML content to readable text.

    Returns:
        Tuple of (extracted_text, error_message).
        If successful, error_message is None.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return "", "beautifulsoup4 not installed. Install with: pip install -e '.[ingest]'"

    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        # Get text with reasonable formatting
        text = soup.get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        text = re.sub(r"\n\s*\n\s*\n", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)

        return text.strip(), None
    except Exception as e:
        return "", f"Error parsing HTML: {e}"


def save_url_content(text: str, source_id: str, project_root: Path) -> Path:
    """Save URL content to data/approved_sources/web/."""
    web_dir = project_root / "data" / "approved_sources" / "web"
    web_dir.mkdir(parents=True, exist_ok=True)
    web_path = web_dir / f"{source_id}.txt"
    web_path.write_text(text, encoding="utf-8")
    return web_path


def ingest_url_source(
    url: str,
    trust_tier: str,
    publisher: str,
    source_type: str,
    project_root: Path,
) -> SourceRecord | None:
    """Ingest a source from a URL.

    Returns:
        SourceRecord if successful, None if error.
    """
    # Fetch content
    html_content, content_type, error = fetch_url_content(url)
    if error:
        return None

    # Parse HTML to text
    text, parse_error = parse_html_to_text(html_content)
    if parse_error:
        return None

    if not text.strip():
        return None

    # Generate source ID from URL
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    source_id = normalize_source_id(f"url_{url_hash}")

    # Save content
    web_path = save_url_content(text, source_id, project_root)

    # Compute hash
    file_hash = SourceRegistry._hash_text(text)

    # Create record
    record = SourceRecord(
        source_id=source_id,
        title=f"Web Source: {url[:50]}",
        path=str(web_path),
        url=url,
        publisher=publisher,
        source_type=source_type,
        trust_tier=trust_tier,
        retrieved_at=datetime.now(timezone.utc),
        last_checked_at=datetime.now(timezone.utc),
        hash_sha256=file_hash,
        status="active",
        approval_status="approved",
    )

    return record
