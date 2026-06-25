"""Safety and unsupported-claim checks.

Instruction:
- High-risk unsupported claims should block final output.
"""

from __future__ import annotations

from sourcelab.core.models import ClaimRecord


def has_blocking_claims(claims: list[ClaimRecord]) -> bool:
    return any(c.support_status == "unsupported" and c.severity == "high" for c in claims)
