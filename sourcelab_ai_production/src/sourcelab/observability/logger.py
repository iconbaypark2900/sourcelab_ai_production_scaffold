"""Structured logging helpers.

Instruction:
- Production should send these logs to OpenTelemetry/Sentry/Grafana.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone


def log_event(event: str, **fields: object) -> str:
    payload = {"event": event, "timestamp": datetime.now(timezone.utc).isoformat(), **fields}
    line = json.dumps(payload, default=str)
    print(line)
    return line
