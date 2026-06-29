"""Release changelog generator for SourceLab AI.

Instruction:
- Generate changelog from git log between version tags.
- Include release manifest summary data.
- Output in markdown format.
- Support dry-run mode.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

ChangelogFormat = Literal["markdown"]


class ChangelogGenerator:
    """Generate changelog from git log and release manifest."""

    def __init__(self, project_root: Path | None = None) -> None:
        self._root = project_root or Path.cwd()

    def _git_log(self, from_ref: str, to_ref: str) -> list[dict[str, str]]:
        """Get git log entries between two refs."""
        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    f"{from_ref}..{to_ref}",
                    "--pretty=format:%H|%s|%an|%ad",
                    "--date=short",
                ],
                capture_output=True,
                text=True,
                cwd=self._root,
                timeout=30,
            )
            if result.returncode != 0:
                return []
            entries: list[dict[str, str]] = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 3)
                if len(parts) == 4:
                    entries.append(
                        {
                            "hash": parts[0],
                            "subject": parts[1],
                            "author": parts[2],
                            "date": parts[3],
                        }
                    )
            return entries
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return []

    def _classify_commits(
        self, entries: list[dict[str, str]]
    ) -> dict[str, list[dict[str, str]]]:
        """Classify commits into added, changed, fixed categories."""
        added: list[dict[str, str]] = []
        changed: list[dict[str, str]] = []
        fixed: list[dict[str, str]] = []

        for entry in entries:
            subject = entry["subject"]
            subject_lower = subject.lower()

            if subject_lower.startswith(("feat:", "feature:", "add:")):
                added.append(entry)
            elif subject_lower.startswith(("fix:", "bugfix:", "hotfix:")):
                fixed.append(entry)
            elif subject_lower.startswith(("refactor:", "update:", "change:", "docs:", "chore:")):
                changed.append(entry)
            else:
                changed.append(entry)

        return {"added": added, "changed": changed, "fixed": fixed}

    def generate(
        self,
        from_version: str,
        to_version: str,
        format: ChangelogFormat = "markdown",
        dry_run: bool = False,
    ) -> str:
        """Generate changelog between two versions.

        Args:
            from_version: Starting version (e.g., "v1.0.2" or "1.0.2").
            to_version: Ending version (e.g., "v1.0.3" or "1.0.3").
            format: Output format (only "markdown" supported).
            dry_run: If True, don't write to file.

        Returns:
            Changelog content as a string.
        """
        from_tag = self._normalize_ref(from_version)
        to_tag = self._normalize_ref(to_version)

        entries = self._git_log(from_tag, to_tag)
        classified = self._classify_commits(entries)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        lines: list[str] = [
            f"## {to_version} — {now}",
            "",
        ]

        if classified["added"]:
            lines.append("### Added")
            for entry in classified["added"]:
                lines.append(f"- {entry['subject']} ({entry['hash'][:7]})")
            lines.append("")

        if classified["changed"]:
            lines.append("### Changed")
            for entry in classified["changed"]:
                lines.append(f"- {entry['subject']} ({entry['hash'][:7]})")
            lines.append("")

        if classified["fixed"]:
            lines.append("### Fixed")
            for entry in classified["fixed"]:
                lines.append(f"- {entry['subject']} ({entry['hash'][:7]})")
            lines.append("")

        if not entries:
            lines.append("*No changes recorded between these versions.*")
            lines.append("")

        lines.append("### Verification")
        lines.append("- Run `sourcelab local-demo` for end-to-end verification")
        lines.append("- Run `sourcelab verify-release --strict` for release gate")
        lines.append("")

        changelog = "\n".join(lines)

        if not dry_run:
            output_path = self._root / "artifacts" / "release" / f"changelog_{to_version}.md"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(changelog, encoding="utf-8")

        return changelog

    def _normalize_ref(self, version: str) -> str:
        """Normalize a version string to a git ref (tag)."""
        if version.startswith("v"):
            return version
        return f"v{version}"
