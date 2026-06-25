#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

exec sourcelab api --serve --host "${SOURCELAB_API_HOST:-0.0.0.0}" --port "${SOURCELAB_API_PORT:-8000}"
