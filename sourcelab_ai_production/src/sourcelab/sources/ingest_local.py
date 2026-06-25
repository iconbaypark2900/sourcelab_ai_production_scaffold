"""Local source ingestion for SourceLab AI.

Instruction:
- Discover and ingest local markdown, text, and PDF files.
- PDF support requires pypdf: pip install -e ".[ingest]"
- Extracted text from PDFs is saved to data/approved_sources/extracted/.
- Compute hashes and register sources in the registry.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from sourcelab.core.models import SourceRecord
from sourcelab.sources.registry import SourceRegistry, normalize_source_id

SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf"}


def discover_local_files(folder: str | Path) -> list[Path]:
    """Return supported local files for ingestion."""
    folder = Path(folder)
    return sorted(
        [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
    )


def extract_pdf_text(pdf_path: Path) -> tuple[str, str | None]:
    """Extract text from a PDF file.

    Returns:
        Tuple of (extracted_text, error_message).
        If successful, error_message is None.
        If failed, extracted_text is empty and error_message explains the issue.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", "pypdf not installed. Install with: pip install -e '.[ingest]'"

    try:
        reader = PdfReader(str(pdf_path))
        text_parts = []
        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")
        extracted_text = "\n\n".join(text_parts)
        if not extracted_text.strip():
            return "", f"No text could be extracted from {pdf_path.name}"
        return extracted_text, None
    except Exception as e:
        return "", f"Error reading PDF {pdf_path.name}: {e}"


def save_extracted_text(
    text: str, source_id: str, project_root: Path
) -> Path:
    """Save extracted text to data/approved_sources/extracted/."""
    extracted_dir = project_root / "data" / "approved_sources" / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    extracted_path = extracted_dir / f"{source_id}.txt"
    extracted_path.write_text(text, encoding="utf-8")
    return extracted_path


def ingest_local_source(
    filepath: Path,
    trust_tier: str,
    publisher: str,
    source_type: str,
    registry: SourceRegistry,
    project_root: Path,
) -> SourceRecord | None:
    """Ingest a single local source file.

    Returns:
        SourceRecord if successful, None if skipped or error.
    """
    suffix = filepath.suffix.lower()

    if suffix == ".pdf":
        extracted_text, error = extract_pdf_text(filepath)
        if error:
            return None
        text = extracted_text
        source_id = normalize_source_id(filepath.stem)
        extracted_path = save_extracted_text(text, source_id, project_root)
        file_hash = SourceRegistry._hash_text(text)
        record = SourceRegistry._create_source_record(
            source_id=source_id,
            filepath=extracted_path,
            text=text,
            file_hash=file_hash,
            publisher=publisher,
            source_type=source_type,
            trust_tier=trust_tier,
        )
        record.path = str(extracted_path)
        record.url = str(filepath)
        return record
    else:
        text = filepath.read_text(encoding="utf-8")
        file_hash = SourceRegistry._hash_text(text)
        source_id = normalize_source_id(filepath.stem)
        return SourceRegistry._create_source_record(
            source_id=source_id,
            filepath=filepath,
            text=text,
            file_hash=file_hash,
            publisher=publisher,
            source_type=source_type,
            trust_tier=trust_tier,
        )
