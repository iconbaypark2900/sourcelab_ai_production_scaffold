"""Source registry.

Instruction:
- Production must treat this module as the source of truth for approved sources.
- Never generate lessons from unregistered sources.
- Every source must have trust tier, retrieved date, and hash.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from sourcelab.core.models import SourceRecord

VALID_TRUST_TIERS = {"A", "B", "C", "D", "E"}
SUPPORTED_EXTENSIONS = {".md", ".txt"}
REGISTRY_FILENAME = "source_registry.json"


def normalize_source_id(name: str) -> str:
    """Normalize a filename or string into a safe source_id.

    - Lowercase
    - Replace spaces with underscores
    - Remove anything that is not alphanumeric or underscore/hyphen
    - Collapse multiple underscores
    - Strip leading/trailing underscores
    """
    normalized = name.lower()
    normalized = normalized.replace(" ", "_")
    normalized = re.sub(r"[^a-z0-9_-]", "", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    normalized = normalized.strip("_")
    if not normalized:
        normalized = "source"
    return normalized


def make_unique_source_id(base_id: str, existing_ids: set[str]) -> str:
    """Append numeric suffix if the source_id already exists."""
    if base_id not in existing_ids:
        return base_id
    counter = 2
    while f"{base_id}_{counter}" in existing_ids:
        counter += 1
    return f"{base_id}_{counter}"


class SourceRegistry:
    """In-memory registry for the scaffold; replace with Postgres in production."""

    def __init__(self, sources: list[SourceRecord]):
        self.sources = sources

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @classmethod
    def load_from_json(cls, registry_path: Path) -> "SourceRegistry":
        """Load registry from a JSON file. Raises FileNotFoundError if missing."""
        if not registry_path.exists():
            raise FileNotFoundError(f"Registry file not found: {registry_path}")
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        sources = [SourceRecord(**entry) for entry in data.get("sources", [])]
        return cls(sources=sources)

    def save_to_json(self, registry_path: Path) -> None:
        """Save the registry to a JSON file."""
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"sources": [s.model_dump(mode="json") for s in self.sources]}
        registry_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def validate(self) -> list[str]:
        """Validate all sources in the registry. Returns list of error strings."""
        errors: list[str] = []
        ids_seen: set[str] = set()

        for idx, source in enumerate(self.sources):
            prefix = f"source[{idx}]"

            # Required fields
            if not source.source_id:
                errors.append(f"{prefix}: missing source_id")
            if not source.title:
                errors.append(f"{prefix}: missing title")
            if not source.hash_sha256:
                errors.append(f"{prefix}: missing hash_sha256")

            # Trust tier validation
            if source.trust_tier not in VALID_TRUST_TIERS:
                errors.append(
                    f"{prefix}: invalid trust_tier '{source.trust_tier}' "
                    f"(must be one of {sorted(VALID_TRUST_TIERS)})"
                )

            # File existence check (only if path is set)
            if source.path:
                source_path = Path(source.path)
                if not source_path.is_absolute():
                    # Try relative to current working directory
                    source_path = Path.cwd() / source.path
                if not source_path.exists():
                    errors.append(f"{prefix}: file not found: {source.path}")

            # Duplicate check
            if source.source_id in ids_seen:
                errors.append(f"{prefix}: duplicate source_id '{source.source_id}'")
            ids_seen.add(source.source_id)

        return errors

    def export_snapshot(self) -> list[dict]:
        """Export a normalized snapshot of all sources."""
        return [s.model_dump(mode="json") for s in self.sources]

    def add_source(self, source: SourceRecord) -> None:
        """Add a source to the registry, avoiding duplicate IDs."""
        existing_ids = {s.source_id for s in self.sources}
        source.source_id = make_unique_source_id(source.source_id, existing_ids)
        self.sources.append(source)

    def upsert_by_path(self, source: SourceRecord) -> bool:
        """Insert or update a source based on its path. Returns True if updated."""
        for i, existing in enumerate(self.sources):
            if existing.path == source.path:
                # Update hash and retrieved_at, keep existing metadata
                self.sources[i] = SourceRecord(
                    source_id=existing.source_id,
                    title=existing.title,
                    path=existing.path,
                    url=existing.url,
                    publisher=existing.publisher,
                    source_type=existing.source_type,
                    trust_tier=existing.trust_tier,
                    retrieved_at=source.retrieved_at,
                    hash_sha256=source.hash_sha256,
                    status="active",
                )
                return True
        self.add_source(source)
        return False

    @classmethod
    def bootstrap_demo(cls, project_root: Path) -> "SourceRegistry":
        """Create a registry from local demo sources."""
        source_dir = project_root / "data" / "demo_sources"
        sources: list[SourceRecord] = []

        for path in sorted(source_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            trust_tier = "A" if "nist" in path.name.lower() else "C"
            publisher = "NIST/local demo" if trust_tier == "A" else "local demo"

            sources.append(
                SourceRecord(
                    source_id=path.stem,
                    title=path.stem.replace("_", " ").title(),
                    path=str(path),
                    publisher=publisher,
                    source_type="local_demo_source",
                    trust_tier=trust_tier,
                    retrieved_at=datetime.now(timezone.utc),
                    hash_sha256=cls._hash_text(text),
                    status="active",
                )
            )
        return cls(sources=sources)

    @staticmethod
    def _create_source_record(
        source_id: str,
        filepath: Path,
        text: str,
        file_hash: str,
        publisher: str,
        source_type: str,
        trust_tier: str,
    ) -> SourceRecord:
        """Create a SourceRecord from an ingested file."""
        # Derive title from the stem: replace underscores/hyphens with spaces, title-case
        title = filepath.stem.replace("_", " ").replace("-", " ").title()
        return SourceRecord(
            source_id=source_id,
            title=title,
            path=str(filepath),
            publisher=publisher,
            source_type=source_type,
            trust_tier=trust_tier,
            retrieved_at=datetime.now(timezone.utc),
            hash_sha256=file_hash,
            status="active",
        )

    def get(self, source_id: str) -> SourceRecord | None:
        return next((s for s in self.sources if s.source_id == source_id), None)

    def approve_source(self, source_id: str) -> bool:
        """Approve a source. Returns True if found and approved."""
        source = self.get(source_id)
        if source is None:
            return False
        source.status = "active"
        source.approval_status = "approved"
        return True

    def reject_source(self, source_id: str, reason: str = "") -> bool:
        """Reject a source. Returns True if found and rejected."""
        source = self.get(source_id)
        if source is None:
            return False
        source.status = "rejected"
        source.approval_status = "rejected"
        return True

    def archive_source(self, source_id: str) -> bool:
        """Archive a source. Returns True if found and archived."""
        source = self.get(source_id)
        if source is None:
            return False
        source.status = "archived"
        return True

    def get_pending_sources(self) -> list[SourceRecord]:
        """Get all sources with pending_review status."""
        return [s for s in self.sources if s.status == "pending_review"]

    def get_active_approved_sources(self) -> list[SourceRecord]:
        """Get all active and approved sources for retrieval."""
        return [
            s for s in self.sources
            if s.status == "active" and s.approval_status == "approved"
        ]

    def filter_by_pack(self, pack_name: str) -> list[SourceRecord]:
        """Return active/approved sources belonging to a source pack."""
        return [
            source
            for source in self.filter_for_retrieval()
            if source.source_pack == pack_name
            or source.pack_name == pack_name
        ]

    @classmethod
    def load_default(cls, project_root: Path) -> "SourceRegistry":
        """Load the persisted registry or fall back to demo bootstrap."""
        registry_path = project_root / "data" / REGISTRY_FILENAME
        if registry_path.exists():
            return cls.load_from_json(registry_path)
        return cls.bootstrap_demo(project_root)

    @classmethod
    def for_pack(cls, project_root: Path, pack_name: str, source_ids: set[str] | None = None) -> "SourceRegistry":
        """Build a retrieval registry scoped to one source pack."""
        registry = cls.load_default(project_root)
        if source_ids is None:
            from sourcelab.sources.source_pack import load_source_pack_manifest

            manifest = load_source_pack_manifest(project_root, pack_name)
            if manifest is None:
                return cls(sources=[])
            source_ids = {
                source_info.get("source_id", "")
                for source_info in manifest.get("sources", [])
                if source_info.get("source_id")
            }

        scoped_sources = [
            source
            for source in registry.filter_for_retrieval()
            if source.source_id in source_ids
        ]
        return cls(sources=scoped_sources)

    def filter_for_retrieval(
        self,
        include_pending: bool = False,
        include_archived: bool = False,
    ) -> list[SourceRecord]:
        """Filter sources for retrieval based on status.

        Args:
            include_pending: If True, include pending_review sources.
            include_archived: If True, include archived sources.

        Returns:
            List of sources safe for retrieval.
        """
        filtered = []
        for source in self.sources:
            # Never include rejected sources
            if source.status == "rejected" or source.approval_status == "rejected":
                continue
            # Include active approved sources
            if source.status == "active" and source.approval_status == "approved":
                filtered.append(source)
                continue
            # Optionally include pending sources
            if include_pending and source.status == "pending_review":
                filtered.append(source)
                continue
            # Optionally include archived sources
            if include_archived and source.status == "archived":
                filtered.append(source)
                continue
        return filtered
