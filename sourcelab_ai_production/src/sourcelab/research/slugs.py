"""Shared slug helpers for research modules."""

from __future__ import annotations

import re


def topic_slug(topic: str) -> str:
    """Filesystem-safe slug for topic profile paths."""
    slug = re.sub(r"[^a-z0-9]+", "_", topic.lower().strip())
    slug = slug.strip("_")
    return slug[:80] if slug else "topic"
