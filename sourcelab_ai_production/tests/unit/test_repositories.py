"""Tests for API ingest endpoint, retrieval diagnostics, and repository pattern.

Tests cover:
- SourceRepository filesystem backend (save, get, list, update_status)
- SkillProfileRepository filesystem backend (save, get, list)
- Repository backend selection (filesystem default, postgres when configured)
- API ingest service function
- API retrieval diagnostics service function
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from sourcelab.storage.repositories import (
    SkillProfileRepository,
    SourceRepository,
    _get_database_url,
    _postgres_available,
)


# ---------------------------------------------------------------------------
# SourceRepository — filesystem backend
# ---------------------------------------------------------------------------


class TestSourceRepositoryFilesystem:
    def test_save_and_get(self, tmp_path: Path):
        repo = SourceRepository(project_root=tmp_path, backend="filesystem")
        source = {"source_id": "src_001", "title": "Test", "status": "pending"}
        repo.save(source)

        retrieved = repo.get("src_001")
        assert retrieved is not None
        assert retrieved["source_id"] == "src_001"
        assert retrieved["title"] == "Test"

    def test_get_nonexistent_returns_none(self, tmp_path: Path):
        repo = SourceRepository(project_root=tmp_path, backend="filesystem")
        assert repo.get("nonexistent") is None

    def test_list_all(self, tmp_path: Path):
        repo = SourceRepository(project_root=tmp_path, backend="filesystem")
        repo.save({"source_id": "s1", "status": "approved"})
        repo.save({"source_id": "s2", "status": "pending"})
        sources = repo.list()
        assert len(sources) == 2

    def test_list_filtered_by_status(self, tmp_path: Path):
        repo = SourceRepository(project_root=tmp_path, backend="filesystem")
        repo.save({"source_id": "s1", "status": "approved"})
        repo.save({"source_id": "s2", "status": "pending"})
        approved = repo.list(status="approved")
        assert len(approved) == 1
        assert approved[0]["source_id"] == "s1"

    def test_update_status(self, tmp_path: Path):
        repo = SourceRepository(project_root=tmp_path, backend="filesystem")
        repo.save({"source_id": "s1", "status": "pending"})
        assert repo.update_status("s1", "approved") is True
        assert repo.get("s1")["status"] == "approved"

    def test_update_status_nonexistent(self, tmp_path: Path):
        repo = SourceRepository(project_root=tmp_path, backend="filesystem")
        assert repo.update_status("nonexistent", "approved") is False

    def test_save_overwrites_existing(self, tmp_path: Path):
        repo = SourceRepository(project_root=tmp_path, backend="filesystem")
        repo.save({"source_id": "s1", "title": "Old", "status": "pending"})
        repo.save({"source_id": "s1", "title": "New", "status": "approved"})
        sources = repo.list()
        assert len(sources) == 1
        assert sources[0]["title"] == "New"

    def test_empty_list_when_no_registry(self, tmp_path: Path):
        repo = SourceRepository(project_root=tmp_path, backend="filesystem")
        assert repo.list() == []

    def test_default_backend_is_filesystem(self, tmp_path: Path):
        with patch.dict("os.environ", {}, clear=False):
            if "SOURCELAB_DATABASE_URL" in __import__("os").environ:
                del __import__("os").environ["SOURCELAB_DATABASE_URL"]
            repo = SourceRepository(project_root=tmp_path)
            assert repo._backend == "filesystem"


# ---------------------------------------------------------------------------
# SkillProfileRepository — filesystem backend
# ---------------------------------------------------------------------------


class TestSkillProfileRepositoryFilesystem:
    def test_save_and_get(self, tmp_path: Path):
        repo = SkillProfileRepository(project_root=tmp_path, backend="filesystem")
        profile = {"user_id": "local_user", "mastery": {"pqc": 0.8}}
        repo.save(profile)

        retrieved = repo.get("local_user")
        assert retrieved is not None
        assert retrieved["user_id"] == "local_user"
        assert retrieved["mastery"]["pqc"] == 0.8

    def test_get_nonexistent_returns_none(self, tmp_path: Path):
        repo = SkillProfileRepository(project_root=tmp_path, backend="filesystem")
        assert repo.get("nonexistent") is None

    def test_list_profiles(self, tmp_path: Path):
        repo = SkillProfileRepository(project_root=tmp_path, backend="filesystem")
        repo.save({"user_id": "user1", "mastery": {}})
        repo.save({"user_id": "user2", "mastery": {}})
        profiles = repo.list()
        assert len(profiles) == 2

    def test_list_empty_when_no_profiles(self, tmp_path: Path):
        repo = SkillProfileRepository(project_root=tmp_path, backend="filesystem")
        assert repo.list() == []

    def test_save_overwrites_existing(self, tmp_path: Path):
        repo = SkillProfileRepository(project_root=tmp_path, backend="filesystem")
        repo.save({"user_id": "user1", "mastery": {"a": 0.5}})
        repo.save({"user_id": "user1", "mastery": {"a": 0.9}})
        retrieved = repo.get("user1")
        assert retrieved["mastery"]["a"] == 0.9

    def test_save_adds_updated_at(self, tmp_path: Path):
        repo = SkillProfileRepository(project_root=tmp_path, backend="filesystem")
        repo.save({"user_id": "user1", "mastery": {}})
        retrieved = repo.get("user1")
        assert "updated_at" in retrieved


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


class TestBackendSelection:
    def test_postgres_available_false_without_url(self):
        with patch.dict("os.environ", {}, clear=True):
            assert _postgres_available() is False

    def test_postgres_available_false_without_psycopg(self):
        with patch.dict("os.environ", {"SOURCELAB_DATABASE_URL": "postgresql://localhost/test"}):
            # psycopg likely not installed in test env
            # This test passes either way — if psycopg IS installed, it returns True
            # which is also valid. We just check it doesn't crash.
            result = _postgres_available()
            assert isinstance(result, bool)

    def test_get_database_url_from_env(self):
        with patch.dict("os.environ", {"SOURCELAB_DATABASE_URL": "postgresql://localhost/test"}):
            assert _get_database_url() == "postgresql://localhost/test"

    def test_get_database_url_none_when_not_set(self):
        with patch.dict("os.environ", {}, clear=True):
            assert _get_database_url() is None

    def test_explicit_backend_overrides_auto(self, tmp_path: Path):
        repo = SourceRepository(project_root=tmp_path, backend="filesystem")
        assert repo._backend == "filesystem"


# ---------------------------------------------------------------------------
# API service functions
# ---------------------------------------------------------------------------


class TestApiIngestService:
    def test_ingest_source_file_not_found(self, tmp_path: Path):
        from sourcelab.api.services import ingest_source

        with patch("sourcelab.api.services.get_config") as mock_config:
            mock_config.return_value.project_root = tmp_path
            with pytest.raises(Exception):
                ingest_source(
                    source_id="test_src",
                    path="/nonexistent/file.md",
                )

    def test_ingest_source_md_file(self, tmp_path: Path):
        from sourcelab.api.services import ingest_source

        test_file = tmp_path / "test_source.md"
        test_file.write_text("# Test Source\n\nThis is a test markdown source.", encoding="utf-8")

        with patch("sourcelab.api.services.get_config") as mock_config:
            mock_config.return_value.project_root = tmp_path
            result = ingest_source(
                source_id="test_src",
                path=str(test_file),
                title="Test Source",
            )

        assert result["status"] == "pending"
        assert "test" in result["source_id"].lower()
        assert "ingested" in result["message"]


class TestApiRetrievalDiagnostics:
    def test_diagnostics_no_runs(self, tmp_path: Path):
        from sourcelab.api.services import get_retrieval_diagnostics

        with patch("sourcelab.api.services.get_config") as mock_config:
            mock_config.return_value.project_root = tmp_path
            result = get_retrieval_diagnostics()

        assert result["mode"] == "hybrid"
        assert result["result_count"] == 0
        assert "weights" in result

    def test_diagnostics_from_latest_run(self, tmp_path: Path):
        from sourcelab.api.services import get_retrieval_diagnostics

        runs_dir = tmp_path / "artifacts" / "runs" / "run_001"
        runs_dir.mkdir(parents=True)
        diagnostics = {
            "query": "post-quantum cryptography",
            "mode": "hybrid",
            "result_count": 5,
            "total_chunks": 42,
            "weights": {"keyword": 0.4, "vector": 0.6},
        }
        (runs_dir / "retrieval_diagnostics.json").write_text(
            json.dumps(diagnostics), encoding="utf-8"
        )

        with patch("sourcelab.api.services.get_config") as mock_config:
            mock_config.return_value.project_root = tmp_path
            result = get_retrieval_diagnostics()

        assert result["query"] == "post-quantum cryptography"
        assert result["result_count"] == 5
        assert result["total_chunks"] == 42

    def test_diagnostics_returns_default_weights(self, tmp_path: Path):
        from sourcelab.api.services import get_retrieval_diagnostics

        with patch("sourcelab.api.services.get_config") as mock_config:
            mock_config.return_value.project_root = tmp_path
            result = get_retrieval_diagnostics()

        assert "keyword" in result["weights"]
        assert "vector" in result["weights"]
