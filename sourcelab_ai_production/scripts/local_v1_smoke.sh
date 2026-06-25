#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

sourcelab version
sourcelab doctor
sourcelab init-local
sourcelab source-pack validate pqc_v1
sourcelab evals run --pack pqc_v1
sourcelab local-demo
sourcelab verify-release --strict
sourcelab release manifest
sourcelab export latest --format markdown

echo "Local v1 smoke complete."
