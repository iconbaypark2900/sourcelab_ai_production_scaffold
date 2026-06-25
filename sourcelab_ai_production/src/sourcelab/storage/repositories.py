"""Repository abstractions.

Instruction:
- Keep database-specific code behind repository interfaces.
- This scaffold uses files/in-memory objects; production should use Postgres and object storage.
"""

from __future__ import annotations


class SourceRepository:
    """Placeholder for source persistence."""

    def save(self, source: object) -> None:
        raise NotImplementedError
