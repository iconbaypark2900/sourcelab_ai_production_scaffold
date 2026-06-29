"""Tests for release versioning and changelog generation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from sourcelab.release.changelog import ChangelogGenerator
from sourcelab.release.versioning import Change, VersionPolicy


class TestVersionPolicy:
    def test_parse_valid_version(self):
        policy = VersionPolicy()
        assert policy.parse("1.0.2") == (1, 0, 2)
        assert policy.parse("2.3.14") == (2, 3, 14)

    def test_parse_invalid_version_raises(self):
        policy = VersionPolicy()
        with pytest.raises(ValueError, match="Invalid version format"):
            policy.parse("1.0")
        with pytest.raises(ValueError, match="Invalid version format"):
            policy.parse("v1.0.2")
        with pytest.raises(ValueError, match="Invalid version format"):
            policy.parse("")

    def test_determine_bump_major(self):
        policy = VersionPolicy()
        changes = [Change("break API", breaking=True), Change("fix bug")]
        assert policy.determine_bump(changes) == "major"

    def test_determine_bump_minor(self):
        policy = VersionPolicy()
        changes = [Change("new feature", feature=True), Change("fix bug")]
        assert policy.determine_bump(changes) == "minor"

    def test_determine_bump_patch(self):
        policy = VersionPolicy()
        changes = [Change("fix bug", fix=True)]
        assert policy.determine_bump(changes) == "patch"

    def test_determine_bump_empty_defaults_to_patch(self):
        policy = VersionPolicy()
        assert policy.determine_bump([]) == "patch"

    def test_bump_version_major(self):
        policy = VersionPolicy()
        assert policy.bump_version("1.0.2", "major") == "2.0.0"

    def test_bump_version_minor(self):
        policy = VersionPolicy()
        assert policy.bump_version("1.0.2", "minor") == "1.1.0"

    def test_bump_version_patch(self):
        policy = VersionPolicy()
        assert policy.bump_version("1.0.2", "patch") == "1.0.3"

    def test_bump_version_from_zero(self):
        policy = VersionPolicy()
        assert policy.bump_version("0.0.0", "patch") == "0.0.1"
        assert policy.bump_version("0.0.0", "minor") == "0.1.0"
        assert policy.bump_version("0.0.0", "major") == "1.0.0"

    def test_compare_versions(self):
        policy = VersionPolicy()
        assert policy.compare("1.0.0", "1.0.1") == -1
        assert policy.compare("1.0.1", "1.0.0") == 1
        assert policy.compare("1.0.0", "1.0.0") == 0

    def test_validate_valid(self):
        policy = VersionPolicy()
        assert policy.validate("1.0.0") is True
        assert policy.validate("10.20.30") is True

    def test_validate_invalid(self):
        policy = VersionPolicy()
        assert policy.validate("1.0") is False
        assert policy.validate("v1.0.0") is False
        assert policy.validate("") is False

    def test_breaking_takes_priority_over_feature(self):
        policy = VersionPolicy()
        changes = [Change("new feature", feature=True), Change("break API", breaking=True)]
        assert policy.determine_bump(changes) == "major"

    def test_feature_takes_priority_over_fix(self):
        policy = VersionPolicy()
        changes = [Change("fix bug", fix=True), Change("new feature", feature=True)]
        assert policy.determine_bump(changes) == "minor"


class TestChangelogGenerator:
    def test_generate_dry_run(self, tmp_path: Path):
        gen = ChangelogGenerator(tmp_path)
        changelog = gen.generate("v1.0.0", "v1.0.1", dry_run=True)
        assert "v1.0.1" in changelog
        assert "Verification" in changelog

    def test_generate_writes_file(self, tmp_path: Path):
        gen = ChangelogGenerator(tmp_path)
        gen.generate("v1.0.0", "v1.0.1", dry_run=False)
        output = tmp_path / "artifacts" / "release" / "changelog_v1.0.1.md"
        assert output.exists()

    def test_generate_no_commits(self, tmp_path: Path):
        gen = ChangelogGenerator(tmp_path)
        changelog = gen.generate("v1.0.0", "v1.0.1", dry_run=True)
        assert "No changes recorded" in changelog

    def test_normalize_ref_with_v_prefix(self, tmp_path: Path):
        gen = ChangelogGenerator(tmp_path)
        assert gen._normalize_ref("1.0.0") == "v1.0.0"
        assert gen._normalize_ref("v1.0.0") == "v1.0.0"

    def test_generate_includes_date(self, tmp_path: Path):
        gen = ChangelogGenerator(tmp_path)
        changelog = gen.generate("v1.0.0", "v1.0.1", dry_run=True)
        assert "—" in changelog  # date separator

    def test_generate_includes_verification_section(self, tmp_path: Path):
        gen = ChangelogGenerator(tmp_path)
        changelog = gen.generate("v1.0.0", "v1.0.1", dry_run=True)
        assert "local-demo" in changelog
        assert "verify-release" in changelog

    def test_classify_commits_feat(self, tmp_path: Path):
        gen = ChangelogGenerator(tmp_path)
        entries = [{"hash": "abc1234", "subject": "feat: add new feature", "author": "test", "date": "2026-01-01"}]
        classified = gen._classify_commits(entries)
        assert len(classified["added"]) == 1
        assert len(classified["fixed"]) == 0

    def test_classify_commits_fix(self, tmp_path: Path):
        gen = ChangelogGenerator(tmp_path)
        entries = [{"hash": "abc1234", "subject": "fix: resolve bug", "author": "test", "date": "2026-01-01"}]
        classified = gen._classify_commits(entries)
        assert len(classified["fixed"]) == 1
        assert len(classified["added"]) == 0

    def test_classify_commits_refactor_goes_to_changed(self, tmp_path: Path):
        gen = ChangelogGenerator(tmp_path)
        entries = [{"hash": "abc1234", "subject": "refactor: clean up code", "author": "test", "date": "2026-01-01"}]
        classified = gen._classify_commits(entries)
        assert len(classified["changed"]) == 1

    def test_classify_commits_unknown_goes_to_changed(self, tmp_path: Path):
        gen = ChangelogGenerator(tmp_path)
        entries = [{"hash": "abc1234", "subject": "random commit message", "author": "test", "date": "2026-01-01"}]
        classified = gen._classify_commits(entries)
        assert len(classified["changed"]) == 1
