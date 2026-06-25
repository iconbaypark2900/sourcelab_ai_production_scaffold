"""API configuration.

Instruction:
- Configure API settings from environment variables.
- Provide sensible defaults for local development.
- No external services required.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class APIConfig:
    """API configuration with sensible defaults."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True
    workers: int = 1

    # CORS settings (local development only)
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:3000", "http://localhost:8080"])
    cors_methods: list[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    cors_headers: list[str] = field(default_factory=lambda: ["*"])

    # Project root
    project_root: Path = field(default_factory=Path.cwd)

    # API metadata
    title: str = "SourceLab AI"
    description: str = "REST API for SourceLab AI production scaffold"
    version: str = "1.0.0"
    api_version: str = "v1"

    @classmethod
    def from_env(cls) -> "APIConfig":
        """Load configuration from environment variables."""
        return cls(
            host=os.getenv("SOURCELAB_API_HOST", "0.0.0.0"),
            port=int(os.getenv("SOURCELAB_API_PORT", "8000")),
            reload=os.getenv("SOURCELAB_API_RELOAD", "true").lower() == "true",
            workers=int(os.getenv("SOURCELAB_API_WORKERS", "1")),
            cors_origins=os.getenv("SOURCELAB_CORS_ORIGINS", "http://localhost:3000,http://localhost:8080").split(","),
            project_root=Path(os.getenv("SOURCELAB_PROJECT_ROOT", str(Path.cwd()))),
        )


def get_config() -> APIConfig:
    """Get API configuration from environment."""
    return APIConfig.from_env()
