"""SourceLab AI package.

This package is intentionally split into production-oriented modules:
sources, retrieval, generation, verification, harness, and learning.

Every module should remain independently testable.
"""

from sourcelab.version import RELEASE_LABEL, __version__

__all__ = ["__version__", "RELEASE_LABEL"]
