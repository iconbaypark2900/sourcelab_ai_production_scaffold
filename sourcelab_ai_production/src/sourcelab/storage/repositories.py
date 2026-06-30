"""Repository abstractions for source and skill profile persistence.

Instruction:
- Keep database-specific code behind repository interfaces.
- Filesystem backend is the default (local-first, no external deps).
- Postgres backend activates when SOURCELAB_DATABASE_URL is set.
- psycopg is an optional dependency: pip install -e ".[postgres]"
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _get_database_url() -> str | None:
    """Return the Postgres connection URL if configured."""
    return os.environ.get("SOURCELAB_DATABASE_URL")


def _postgres_available() -> bool:
    """Check if Postgres is both configured and the driver is installed."""
    if not _get_database_url():
        return False
    try:
        import psycopg  # noqa: F401
        return True
    except ImportError:
        return False


class SourceRepository:
    """Source persistence with filesystem and Postgres backends."""

    def __init__(
        self,
        project_root: Path | None = None,
        backend: str | None = None,
    ) -> None:
        self._root = project_root or Path.cwd()
        self._backend = backend or ("postgres" if _postgres_available() else "filesystem")
        self._registry_path = self._root / "data" / "source_registry.json"

    def save(self, source: dict[str, Any]) -> None:
        """Save or update a source record."""
        if self._backend == "postgres":
            self._save_postgres(source)
        else:
            self._save_filesystem(source)

    def get(self, source_id: str) -> dict[str, Any] | None:
        """Get a source by ID."""
        if self._backend == "postgres":
            return self._get_postgres(source_id)
        return self._get_filesystem(source_id)

    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        """List all sources, optionally filtered by status."""
        if self._backend == "postgres":
            return self._list_postgres(status)
        return self._list_filesystem(status)

    def update_status(self, source_id: str, status: str) -> bool:
        """Update a source's status. Returns True if found and updated."""
        if self._backend == "postgres":
            return self._update_status_postgres(source_id, status)
        return self._update_status_filesystem(source_id, status)

    # -- Filesystem backend --

    def _load_registry(self) -> list[dict[str, Any]]:
        if not self._registry_path.exists():
            return []
        try:
            data = json.loads(self._registry_path.read_text(encoding="utf-8"))
            return data.get("sources", [])
        except (json.JSONDecodeError, KeyError):
            return []

    def _save_registry(self, sources: list[dict[str, Any]]) -> None:
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._registry_path.write_text(
            json.dumps({"sources": sources}, indent=2, default=str),
            encoding="utf-8",
        )

    def _save_filesystem(self, source: dict[str, Any]) -> None:
        sources = self._load_registry()
        sid = source.get("source_id", "")
        sources = [s for s in sources if s.get("source_id") != sid]
        sources.append(source)
        self._save_registry(sources)

    def _get_filesystem(self, source_id: str) -> dict[str, Any] | None:
        for s in self._load_registry():
            if s.get("source_id") == source_id:
                return s
        return None

    def _list_filesystem(self, status: str | None = None) -> list[dict[str, Any]]:
        sources = self._load_registry()
        if status:
            return [s for s in sources if s.get("status") == status]
        return sources

    def _update_status_filesystem(self, source_id: str, status: str) -> bool:
        sources = self._load_registry()
        found = False
        for s in sources:
            if s.get("source_id") == source_id:
                s["status"] = status
                s["updated_at"] = datetime.now(timezone.utc).isoformat()
                found = True
                break
        if found:
            self._save_registry(sources)
        return found

    # -- Postgres backend --

    def _get_conn(self):
        import psycopg
        return psycopg.connect(_get_database_url())

    def _save_postgres(self, source: dict[str, Any]) -> None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sources (source_id, title, publisher, source_type,
                        trust_tier, url, local_path, hash_sha256, status, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        status = EXCLUDED.status,
                        updated_at = now()
                    """,
                    (
                        source.get("source_id", ""),
                        source.get("title", ""),
                        source.get("publisher", ""),
                        source.get("source_type", ""),
                        source.get("trust_tier", "C"),
                        source.get("url"),
                        source.get("path"),
                        source.get("hash_sha256"),
                        source.get("status", "pending"),
                        json.dumps(source.get("metadata", {})),
                    ),
                )

    def _get_postgres(self, source_id: str) -> dict[str, Any] | None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sources WHERE source_id = %s", (source_id,))
                row = cur.fetchone()
                if not row:
                    return None
                cols = [desc[0] for desc in cur.description]
                return dict(zip(cols, row))

    def _list_postgres(self, status: str | None = None) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                if status:
                    cur.execute("SELECT * FROM sources WHERE status = %s", (status,))
                else:
                    cur.execute("SELECT * FROM sources")
                rows = cur.fetchall()
                cols = [desc[0] for desc in cur.description]
                return [dict(zip(cols, row)) for row in rows]

    def _update_status_postgres(self, source_id: str, status: str) -> bool:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE sources SET status = %s, updated_at = now() WHERE source_id = %s",
                    (status, source_id),
                )
                return cur.rowcount > 0


class SkillProfileRepository:
    """Skill profile persistence with filesystem and Postgres backends."""

    def __init__(
        self,
        project_root: Path | None = None,
        backend: str | None = None,
    ) -> None:
        self._root = project_root or Path.cwd()
        self._backend = backend or ("postgres" if _postgres_available() else "filesystem")
        self._profiles_dir = self._root / "artifacts" / "profiles"

    def save(self, profile: dict[str, Any]) -> None:
        """Save or update a skill profile."""
        if self._backend == "postgres":
            self._save_postgres(profile)
        else:
            self._save_filesystem(profile)

    def get(self, profile_id: str) -> dict[str, Any] | None:
        """Get a skill profile by ID."""
        if self._backend == "postgres":
            return self._get_postgres(profile_id)
        return self._get_filesystem(profile_id)

    def list(self) -> list[dict[str, Any]]:
        """List all skill profiles."""
        if self._backend == "postgres":
            return self._list_postgres()
        return self._list_filesystem()

    # -- Filesystem backend --

    def _profile_path(self, profile_id: str) -> Path:
        return self._profiles_dir / f"{profile_id}_skill_profile.json"

    def _save_filesystem(self, profile: dict[str, Any]) -> None:
        self._profiles_dir.mkdir(parents=True, exist_ok=True)
        pid = profile.get("user_id", "local_user")
        profile["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._profile_path(pid).write_text(
            json.dumps(profile, indent=2, default=str),
            encoding="utf-8",
        )

    def _get_filesystem(self, profile_id: str) -> dict[str, Any] | None:
        path = self._profile_path(profile_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def _list_filesystem(self) -> list[dict[str, Any]]:
        if not self._profiles_dir.exists():
            return []
        profiles: list[dict[str, Any]] = []
        for p in self._profiles_dir.glob("*_skill_profile.json"):
            try:
                profiles.append(json.loads(p.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return profiles

    # -- Postgres backend --

    def _get_conn(self):
        import psycopg
        return psycopg.connect(_get_database_url())

    def _save_postgres(self, profile: dict[str, Any]) -> None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO skill_profiles (profile_id, topic, mastery,
                        criterion_mastery, strengths, weaknesses,
                        source_grounding_history, preferred_next_difficulty,
                        preferred_guidance_level, last_practiced)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (profile_id) DO UPDATE SET
                        mastery = EXCLUDED.mastery,
                        criterion_mastery = EXCLUDED.criterion_mastery,
                        strengths = EXCLUDED.strengths,
                        weaknesses = EXCLUDED.weaknesses,
                        source_grounding_history = EXCLUDED.source_grounding_history,
                        updated_at = now()
                    """,
                    (
                        profile.get("user_id", "local_user"),
                        profile.get("topic"),
                        json.dumps(profile.get("mastery", {})),
                        json.dumps(profile.get("criterion_mastery", {})),
                        json.dumps(profile.get("strengths", [])),
                        json.dumps(profile.get("weaknesses", [])),
                        json.dumps(profile.get("source_grounding_history", [])),
                        profile.get("preferred_next_difficulty", 3),
                        profile.get("preferred_guidance_level", 2),
                        profile.get("last_practiced"),
                    ),
                )

    def _get_postgres(self, profile_id: str) -> dict[str, Any] | None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM skill_profiles WHERE profile_id = %s", (profile_id,))
                row = cur.fetchone()
                if not row:
                    return None
                cols = [desc[0] for desc in cur.description]
                return dict(zip(cols, row))

    def _list_postgres(self) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM skill_profiles")
                rows = cur.fetchall()
                cols = [desc[0] for desc in cur.description]
                return [dict(zip(cols, row)) for row in rows]
