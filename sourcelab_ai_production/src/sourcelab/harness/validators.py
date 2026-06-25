"""Harness validators.

Instruction:
- Add validators here instead of burying assertions in pipeline code.
"""

from __future__ import annotations


def require_non_empty(items: list[object], label: str) -> None:
    if not items:
        raise ValueError(f"{label} cannot be empty.")
