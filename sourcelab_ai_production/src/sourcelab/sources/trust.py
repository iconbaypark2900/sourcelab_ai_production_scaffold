"""Source trust policy.

Instruction:
- Production systems should gate lesson generation by trust policy.
- High-risk verticals should prefer trust tier A/B sources.
"""

from __future__ import annotations

from sourcelab.core.models import SourceRecord


TRUST_WEIGHTS = {"A": 1.00, "B": 0.85, "C": 0.65, "D": 0.45, "E": 0.25}


def trust_weight(source: SourceRecord | str) -> float:
    tier = source.trust_tier if isinstance(source, SourceRecord) else source
    return TRUST_WEIGHTS.get(tier, 0.0)


def is_allowed_for_lesson(source: SourceRecord, min_tier: str = "C") -> bool:
    order = ["A", "B", "C", "D", "E"]
    return order.index(source.trust_tier) <= order.index(min_tier)
