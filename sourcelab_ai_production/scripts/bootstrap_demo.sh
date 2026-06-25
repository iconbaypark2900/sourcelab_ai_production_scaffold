#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
sourcelab demo --topic "post-quantum cryptography migration"
sourcelab verify-release
pytest -q
