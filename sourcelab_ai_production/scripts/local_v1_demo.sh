#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

sourcelab init-local
sourcelab local-demo
sourcelab verify-release --strict
sourcelab release manifest
sourcelab export latest --format markdown

echo "Local v1 demo complete."
