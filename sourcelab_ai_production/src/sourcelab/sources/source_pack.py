"""Source pack loader for SourceLab AI.

Instruction:
- Load and install curated source packs from data/source_packs/.
- Preserve metadata from pack manifest.
- Deduplicate by hash/source_id.
- Return install summary.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from sourcelab.core.models import SourceRecord
from sourcelab.sources.registry import SourceRegistry, normalize_source_id

SUPPORTED_EVAL_FILES = frozenset({
    "retrieval_gold.json",
    "claim_gold.json",
    "answer_gold.json",
    "lesson_gold.json",
})
REQUIRED_MANIFEST_FIELDS = ("pack_name", "version", "title", "sources")
REQUIRED_SOURCE_FIELDS = ("source_id", "filename", "trust_tier", "publisher", "source_type")


def _apply_pack_metadata(
    record: SourceRecord,
    pack_name: str,
    source_info: dict,
) -> SourceRecord:
    """Merge pack metadata onto a source record."""
    record.source_pack = pack_name
    record.pack_name = pack_name
    record.title = source_info.get("title", record.title)
    record.publisher = source_info.get("publisher", record.publisher)
    record.source_type = source_info.get("source_type", record.source_type)
    record.trust_tier = source_info.get("trust_tier", record.trust_tier)
    record.status = "active"
    record.approval_status = "approved"
    return record


def list_source_packs(project_root: Path) -> list[dict]:
    """List available source packs in data/source_packs/."""
    packs_dir = project_root / "data" / "source_packs"
    if not packs_dir.exists():
        return []

    packs = []
    for pack_dir in sorted(packs_dir.iterdir()):
        if pack_dir.is_dir():
            manifest_path = pack_dir / "manifest.json"
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    packs.append({
                        "pack_name": manifest.get("pack_name", pack_dir.name),
                        "version": manifest.get("version", "unknown"),
                        "title": manifest.get("title", pack_dir.name),
                        "description": manifest.get("description", ""),
                        "source_count": len(manifest.get("sources", [])),
                        "eval_count": len(manifest.get("evals", [])),
                    })
                except (json.JSONDecodeError, KeyError):
                    packs.append({
                        "pack_name": pack_dir.name,
                        "version": "invalid",
                        "title": pack_dir.name,
                        "description": "Invalid manifest",
                        "source_count": 0,
                        "eval_count": 0,
                    })
    return packs


def load_source_pack_manifest(project_root: Path, pack_name: str) -> dict | None:
    """Load a source pack manifest. Returns None if not found."""
    manifest_path = project_root / "data" / "source_packs" / pack_name / "manifest.json"
    if not manifest_path.exists():
        return None

    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError):
        return None


def validate_source_pack(project_root: Path, pack_name: str) -> dict:
    """Validate a source pack's structure and content."""
    return _validate_source_pack_internal(project_root, pack_name, strict=False)


def doctor_source_pack(project_root: Path, pack_name: str) -> dict:
    """Run strengthened source pack validation checks."""
    return _validate_source_pack_internal(project_root, pack_name, strict=True)


def _validate_source_pack_internal(project_root: Path, pack_name: str, strict: bool) -> dict:
    """Shared validation logic for validate and doctor commands."""
    errors = []
    warnings = []

    pack_dir = project_root / "data" / "source_packs" / pack_name
    if not pack_dir.exists():
        return {"valid": False, "errors": [f"Pack directory not found: {pack_name}"], "warnings": []}

    readme_path = pack_dir / "README.md"
    if not readme_path.is_file():
        msg = "Missing README.md"
        if strict:
            errors.append(msg)
        else:
            warnings.append(msg)
    elif strict and not readme_path.read_text(encoding="utf-8").strip():
        errors.append("README.md is empty")

    manifest = load_source_pack_manifest(project_root, pack_name)
    if manifest is None:
        return {"valid": False, "errors": ["Invalid or missing manifest.json"], "warnings": []}

    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            errors.append(f"Missing required field in manifest: {field}")

    if manifest.get("pack_name") and manifest.get("pack_name") != pack_name:
        errors.append(
            f"Manifest pack_name '{manifest.get('pack_name')}' does not match directory '{pack_name}'"
        )

    sources_dir = pack_dir / "sources"
    evals_dir = pack_dir / "evals"
    if strict:
        if not sources_dir.is_dir():
            errors.append("Missing sources/ directory")
        if not evals_dir.is_dir():
            errors.append("Missing evals/ directory")

    source_ids: list[str] = []
    known_source_ids: set[str] = set()
    for source in manifest.get("sources", []):
        source_id = source.get("source_id", "")
        if source_id:
            if source_id in known_source_ids:
                errors.append(f"Duplicate source_id in manifest: {source_id}")
            known_source_ids.add(source_id)
            source_ids.append(source_id)

        if strict:
            for field in REQUIRED_SOURCE_FIELDS:
                if field not in source:
                    errors.append(f"Source '{source_id or 'unknown'}' missing metadata field: {field}")

        filename = source.get("filename", "")
        source_path = sources_dir / filename
        if not source_path.exists():
            errors.append(f"Source file not found: {filename}")
        else:
            try:
                content = source_path.read_text(encoding="utf-8")
                if strict and not content.strip():
                    errors.append(f"Source file has empty body: {filename}")
                elif not content.startswith("---"):
                    warnings.append(f"Source file missing frontmatter: {filename}")
                if strict:
                    body = _strip_frontmatter(content)
                    if not body.strip():
                        errors.append(f"Source file body is empty after frontmatter: {filename}")
            except Exception as e:
                errors.append(f"Error reading source file {filename}: {e}")

    for eval_name in manifest.get("evals", []):
        if strict and eval_name not in SUPPORTED_EVAL_FILES:
            errors.append(f"Unsupported eval type: {eval_name}")
        eval_path = evals_dir / eval_name
        if not eval_path.exists():
            errors.append(f"Eval file not found: {eval_name}")
        else:
            try:
                eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
                if strict:
                    _validate_eval_references(eval_name, eval_data, known_source_ids, errors)
            except json.JSONDecodeError as e:
                errors.append(f"Invalid JSON in eval file {eval_name}: {e}")

    # Surface per-pack eval threshold compliance
    threshold_compliance: dict | None = None
    try:
        from sourcelab.evals.thresholds import (
            evaluate_against_thresholds,
            load_pack_thresholds,
        )

        pack_thresholds = load_pack_thresholds(project_root, pack_name)
        summary_path = (
            project_root / "artifacts" / "evals" / pack_name / "golden_eval_summary.json"
        )
        summary: dict | None = None
        if summary_path.is_file():
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                summary = None
        evaluation = evaluate_against_thresholds(pack_name, summary, pack_thresholds)
        threshold_compliance = evaluation.to_dict()
        if strict and not evaluation.meets_thresholds:
            errors.append(
                f"Pack does not meet eval thresholds: "
                f"{evaluation.overall_pass_rate or 0:.1%} < {pack_thresholds.min_pass_rate:.1%}"
            )
    except Exception:  # pragma: no cover - defensive
        threshold_compliance = None

    result = {
        "valid": len(errors) == 0,
        "pack_name": pack_name,
        "strict": strict,
        "source_count": len(source_ids),
        "eval_count": len(manifest.get("evals", [])),
        "errors": errors,
        "warnings": warnings,
    }
    if threshold_compliance is not None:
        result["threshold_compliance"] = threshold_compliance
    return result


def _strip_frontmatter(content: str) -> str:
    if not content.startswith("---"):
        return content
    match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
    if match:
        return content[match.end():]
    return content


def _validate_eval_references(
    eval_name: str,
    eval_data: object,
    known_source_ids: set[str],
    errors: list[str],
) -> None:
    cases = eval_data if isinstance(eval_data, list) else []
    if not isinstance(eval_data, list):
        errors.append(f"Eval file {eval_name} must contain a JSON array")
        return

    source_id_fields = ("expected_source_ids", "required_source_ids")
    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"Eval case {idx + 1} in {eval_name} is not an object")
            continue
        for field in source_id_fields:
            for source_id in case.get(field, []):
                if source_id not in known_source_ids:
                    errors.append(
                        f"Eval {eval_name} case {idx + 1} references unknown source_id: {source_id}"
                    )


def install_source_pack(project_root: Path, pack_name: str) -> dict:
    """Install a source pack into the source registry.

    Copies source files and registers them in the registry.
    Deduplicates by hash/source_id.
    Returns install summary.
    """
    manifest = load_source_pack_manifest(project_root, pack_name)
    if manifest is None:
        return {
            "success": False,
            "error": f"Pack not found: {pack_name}",
            "installed": 0,
            "skipped": 0,
            "errors": [],
        }

    # Load existing registry
    registry_path = project_root / "data" / "source_registry.json"
    if registry_path.exists():
        registry = SourceRegistry.load_from_json(registry_path)
    else:
        registry = SourceRegistry(sources=[])

    pack_dir = project_root / "data" / "source_packs" / pack_name
    sources_dir = pack_dir / "sources"

    installed = 0
    skipped = 0
    updated = 0
    errors = []
    installed_sources = []

    for source_info in manifest.get("sources", []):
        filename = source_info.get("filename", "")
        source_id = source_info.get("source_id", normalize_source_id(filename))
        trust_tier = source_info.get("trust_tier", "C")
        publisher = source_info.get("publisher", "source_pack")
        source_type = source_info.get("source_type", "source_pack")

        source_path = sources_dir / filename
        if not source_path.exists():
            errors.append(f"Source file not found: {filename}")
            continue

        try:
            text = source_path.read_text(encoding="utf-8")
            file_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

            # Check for duplicates by hash
            existing_by_hash = next(
                (s for s in registry.sources if s.hash_sha256 == file_hash), None
            )
            if existing_by_hash:
                _apply_pack_metadata(existing_by_hash, pack_name, source_info)
                skipped += 1
                updated += 1
                continue

            # Check for duplicates by source_id
            existing_by_id = registry.get(source_id)
            if existing_by_id:
                _apply_pack_metadata(existing_by_id, pack_name, source_info)
                if existing_by_id.hash_sha256 != file_hash:
                    existing_by_id.hash_sha256 = file_hash
                    existing_by_id.retrieved_at = datetime.now(timezone.utc)
                    installed += 1
                    installed_sources.append(source_id)
                else:
                    skipped += 1
                updated += 1
                continue

            # Create new source record
            record = SourceRecord(
                source_id=source_id,
                title=source_info.get("title", source_id.replace("_", " ").title()),
                path=str(source_path),
                publisher=publisher,
                source_type=source_type,
                trust_tier=trust_tier,
                retrieved_at=datetime.now(timezone.utc),
                hash_sha256=file_hash,
                status="active",
                approval_status="approved",
                source_pack=pack_name,
                pack_name=pack_name,
            )
            registry.add_source(record)
            installed += 1
            updated += 1
            installed_sources.append(source_id)

        except Exception as e:
            errors.append(f"Error installing {filename}: {e}")

    # Save updated registry when sources were installed or metadata merged
    if updated > 0:
        registry.save_to_json(registry_path)

    return {
        "success": len(errors) == 0,
        "pack_name": pack_name,
        "installed": installed,
        "skipped": skipped,
        "updated": updated,
        "total_sources": len(manifest.get("sources", [])),
        "installed_sources": installed_sources,
        "errors": errors,
        "registry_path": str(registry_path),
    }


def source_pack_status(project_root: Path, pack_name: str) -> dict:
    """Get installation status of a source pack."""
    manifest = load_source_pack_manifest(project_root, pack_name)
    if manifest is None:
        return {"installed": False, "error": f"Pack not found: {pack_name}"}

    registry_path = project_root / "data" / "source_registry.json"
    if not registry_path.exists():
        return {
            "installed": False,
            "pack_name": pack_name,
            "total_sources": len(manifest.get("sources", [])),
            "installed_count": 0,
            "installed_sources": [],
        }

    registry = SourceRegistry.load_from_json(registry_path)

    installed_sources = []
    for source_info in manifest.get("sources", []):
        source_id = source_info.get("source_id", "")
        if registry.get(source_id):
            installed_sources.append(source_id)

    return {
        "installed": len(installed_sources) > 0,
        "pack_name": pack_name,
        "version": manifest.get("version", "unknown"),
        "total_sources": len(manifest.get("sources", [])),
        "installed_count": len(installed_sources),
        "installed_sources": installed_sources,
        "registry_path": str(registry_path),
    }
