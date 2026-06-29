"""Release versioning strategy for SourceLab AI.

Instruction:
- Semantic versioning (MAJOR.MINOR.PATCH).
- Determine bump type from change descriptions.
- Calculate next version string.
- Keep version bumping manual (not automatic from commit messages).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

BumpType = Literal["major", "minor", "patch"]


VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True)
class Change:
    """A single change for version bump determination."""

    description: str
    breaking: bool = False
    feature: bool = False
    fix: bool = False


class VersionPolicy:
    """Semantic versioning policy for SourceLab releases."""

    def parse(self, version: str) -> tuple[int, int, int]:
        """Parse a semantic version string into (major, minor, patch)."""
        match = VERSION_RE.match(version)
        if not match:
            raise ValueError(f"Invalid version format: {version} (expected MAJOR.MINOR.PATCH)")
        return int(match.group(1)), int(match.group(2)), int(match.group(3))

    def determine_bump(self, changes: list[Change]) -> BumpType:
        """Determine version bump type from a list of changes."""
        if any(c.breaking for c in changes):
            return "major"
        if any(c.feature for c in changes):
            return "minor"
        return "patch"

    def bump_version(self, current: str, bump_type: BumpType) -> str:
        """Calculate the next version string."""
        major, minor, patch = self.parse(current)
        if bump_type == "major":
            return f"{major + 1}.0.0"
        if bump_type == "minor":
            return f"{major}.{minor + 1}.0"
        return f"{major}.{minor}.{patch + 1}"

    def compare(self, version_a: str, version_b: str) -> int:
        """Compare two versions. Returns -1, 0, or 1."""
        a = self.parse(version_a)
        b = self.parse(version_b)
        if a < b:
            return -1
        if a > b:
            return 1
        return 0

    def validate(self, version: str) -> bool:
        """Check if a version string is valid."""
        return VERSION_RE.match(version) is not None
