from pathlib import Path

from sourcelab.sources.registry import (
    SourceRegistry,
    normalize_source_id,
    make_unique_source_id,
    SUPPORTED_EXTENSIONS,
)
from sourcelab.sources.chunker import simple_chunk_source


def test_demo_registry_has_sources():
    registry = SourceRegistry.bootstrap_demo(Path.cwd())
    assert len(registry.sources) >= 3
    assert all(s.source_id for s in registry.sources)
    assert all(s.hash_sha256 for s in registry.sources)


def test_chunker_preserves_source_id():
    registry = SourceRegistry.bootstrap_demo(Path.cwd())
    chunks = simple_chunk_source(registry.sources[0])
    assert chunks
    assert all(c.source_id == registry.sources[0].source_id for c in chunks)


# --- Source ID normalization tests ---


def test_normalize_source_id_basic():
    assert normalize_source_id("hello world") == "hello_world"


def test_normalize_source_id_special_chars():
    assert normalize_source_id("My File (v2).md") == "my_file_v2md"


def test_normalize_source_id_collapses_underscores():
    assert normalize_source_id("a___b") == "a_b"


def test_normalize_source_id_empty():
    assert normalize_source_id("") == "source"


def test_make_unique_source_id_no_collision():
    assert make_unique_source_id("foo", set()) == "foo"


def test_make_unique_source_id_with_collision():
    assert make_unique_source_id("foo", {"foo"}) == "foo_2"


def test_make_unique_source_id_multiple_collisions():
    assert make_unique_source_id("foo", {"foo", "foo_2"}) == "foo_3"


# --- Ingest tests ---


def test_ingest_folder_with_markdown_files(tmp_path):
    """Ingest a folder with markdown files."""
    # Set up project structure
    project = tmp_path / "project"
    project.mkdir()
    data_dir = project / "data"
    data_dir.mkdir()

    # Create source folder
    source_dir = project / "my_sources"
    source_dir.mkdir()
    (source_dir / "alpha notes.md").write_text("Content of alpha notes", encoding="utf-8")
    (source_dir / "beta-notes.md").write_text("Content of beta notes", encoding="utf-8")

    # Create registry
    registry_path = data_dir / "source_registry.json"
    registry = SourceRegistry(sources=[])
    registry.save_to_json(registry_path)

    # Ingest
    from datetime import datetime, timezone
    import hashlib

    files = sorted(source_dir.glob("*.md"))
    assert len(files) == 2

    for filepath in files:
        text = filepath.read_text(encoding="utf-8")
        file_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        normalized_id = normalize_source_id(filepath.stem)
        record = SourceRegistry._create_source_record(
            source_id=normalized_id,
            filepath=filepath,
            text=text,
            file_hash=file_hash,
            publisher="test_pub",
            source_type="test_type",
            trust_tier="C",
        )
        registry.add_source(record)

    registry.save_to_json(registry_path)

    # Verify
    loaded = SourceRegistry.load_from_json(registry_path)
    assert len(loaded.sources) == 2
    source_ids = {s.source_id for s in loaded.sources}
    assert "alpha_notes" in source_ids
    assert "beta-notes" in source_ids
    assert loaded.validate() == []


def test_duplicate_ingest_does_not_duplicate(tmp_path):
    """Ingesting the same folder twice should not create duplicates."""
    project = tmp_path / "project"
    project.mkdir()
    data_dir = project / "data"
    data_dir.mkdir()

    source_dir = project / "sources"
    source_dir.mkdir()
    (source_dir / "doc1.md").write_text("Some content", encoding="utf-8")

    registry_path = data_dir / "source_registry.json"
    registry = SourceRegistry(sources=[])
    registry.save_to_json(registry_path)

    # First ingest
    import hashlib
    from datetime import datetime, timezone

    for filepath in source_dir.glob("*.md"):
        text = filepath.read_text(encoding="utf-8")
        file_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        record = SourceRegistry._create_source_record(
            source_id=normalize_source_id(filepath.stem),
            filepath=filepath,
            text=text,
            file_hash=file_hash,
            publisher="pub",
            source_type="type",
            trust_tier="C",
        )
        registry.upsert_by_path(record)

    registry.save_to_json(registry_path)

    # Second ingest with same content
    for filepath in source_dir.glob("*.md"):
        text = filepath.read_text(encoding="utf-8")
        file_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        record = SourceRegistry._create_source_record(
            source_id=normalize_source_id(filepath.stem),
            filepath=filepath,
            text=text,
            file_hash=file_hash,
            publisher="pub",
            source_type="type",
            trust_tier="C",
        )
        registry.upsert_by_path(record)

    registry.save_to_json(registry_path)

    loaded = SourceRegistry.load_from_json(registry_path)
    assert len(loaded.sources) == 1


def test_changed_file_updates_hash(tmp_path):
    """When a file changes, its hash should be updated."""
    project = tmp_path / "project"
    project.mkdir()
    data_dir = project / "data"
    data_dir.mkdir()

    source_dir = project / "sources"
    source_dir.mkdir()
    filepath = source_dir / "doc1.md"
    filepath.write_text("Original content", encoding="utf-8")

    registry_path = data_dir / "source_registry.json"
    registry = SourceRegistry(sources=[])

    import hashlib
    from datetime import datetime, timezone

    # First ingest
    text = filepath.read_text(encoding="utf-8")
    file_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    record = SourceRegistry._create_source_record(
        source_id="doc1",
        filepath=filepath,
        text=text,
        file_hash=file_hash,
        publisher="pub",
        source_type="type",
        trust_tier="C",
    )
    registry.add_source(record)
    original_hash = registry.sources[0].hash_sha256

    # Change the file
    filepath.write_text("Updated content", encoding="utf-8")

    # Upsert should detect change
    text = filepath.read_text(encoding="utf-8")
    new_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    new_record = SourceRegistry._create_source_record(
        source_id="doc1",
        filepath=filepath,
        text=text,
        file_hash=new_hash,
        publisher="pub",
        source_type="type",
        trust_tier="C",
    )
    updated = registry.upsert_by_path(new_record)

    assert updated is True
    assert registry.sources[0].hash_sha256 == new_hash
    assert registry.sources[0].hash_sha256 != original_hash


def test_unsupported_file_types_are_ignored(tmp_path):
    """Only .md and .txt files should be processed."""
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    (source_dir / "readme.md").write_text("Markdown content", encoding="utf-8")
    (source_dir / "notes.txt").write_text("Text content", encoding="utf-8")
    (source_dir / "image.png").write_bytes(b"\x89PNG")
    (source_dir / "data.json").write_text('{"key": "value"}', encoding="utf-8")

    files = [
        f for f in source_dir.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    names = [f.name for f in files]
    assert "readme.md" in names
    assert "notes.txt" in names
    assert "image.png" not in names
    assert "data.json" not in names


def test_invalid_trust_tier_fails(tmp_path):
    """Invalid trust tier should be rejected by validation."""
    from sourcelab.core.models import SourceRecord
    from datetime import datetime, timezone

    record = SourceRecord(
        source_id="test",
        title="Test",
        trust_tier="A",  # Valid for model
        retrieved_at=datetime.now(timezone.utc),
        hash_sha256="abc123",
    )
    registry = SourceRegistry(sources=[record])

    # Manually set invalid tier for validation test
    # (bypass model validation by using model_construct)
    bad_record = SourceRecord.model_construct(
        source_id="bad",
        title="Bad",
        trust_tier="Z",  # Invalid tier
        retrieved_at=datetime.now(timezone.utc),
        hash_sha256="abc123",
    )
    registry.sources.append(bad_record)

    errors = registry.validate()
    assert any("invalid trust_tier" in e for e in errors)


def test_registry_validation_passes_after_ingestion(tmp_path):
    """Registry should validate cleanly after ingesting sources."""
    project = tmp_path / "project"
    project.mkdir()
    data_dir = project / "data"
    data_dir.mkdir()

    source_dir = project / "sources"
    source_dir.mkdir()
    (source_dir / "test_source.md").write_text("Test content", encoding="utf-8")

    registry_path = data_dir / "source_registry.json"
    registry = SourceRegistry(sources=[])

    import hashlib
    from datetime import datetime, timezone

    filepath = source_dir / "test_source.md"
    text = filepath.read_text(encoding="utf-8")
    file_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    record = SourceRegistry._create_source_record(
        source_id="test_source",
        filepath=filepath,
        text=text,
        file_hash=file_hash,
        publisher="pub",
        source_type="type",
        trust_tier="C",
    )
    registry.add_source(record)
    registry.save_to_json(registry_path)

    # Reload and validate
    loaded = SourceRegistry.load_from_json(registry_path)
    errors = loaded.validate()
    assert errors == []
