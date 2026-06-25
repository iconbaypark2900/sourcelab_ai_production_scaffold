"""Regression tests for the `sourcelab api routes` command."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import pytest

try:
    import fastapi  # noqa: F401
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from sourcelab.cli import build_parser, cmd_api_routes


pytestmark = pytest.mark.skipif(
    not HAS_FASTAPI,
    reason="FastAPI not installed. Install with: pip install -e '.[api]'",
)


def _run_routes_json() -> dict:
    args = build_parser().parse_args(["api", "routes", "--json"])
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        args.func(args)
    return json.loads(buffer.getvalue().strip())


def test_api_routes_subcommand_is_wired():
    args = build_parser().parse_args(["api", "routes"])
    assert args.func is cmd_api_routes


def test_api_routes_lists_known_endpoints():
    payload = _run_routes_json()
    paths = {route["path"] for route in payload["routes"]}

    assert payload["total"] == len(payload["routes"])
    # A representative sample of real, verified endpoints.
    assert "/health" in paths
    assert "/version" in paths
    assert "/runs/" in paths
    assert "/runs/{run_id}/artifacts" in paths
    assert "/runs/{run_id}/proof" in paths
    assert "/learning/reports/{run_id}" in paths
    assert "/source-packs/" in paths
    assert "/evals/latest/{pack_name}" in paths


def test_api_routes_includes_new_artifact_content_endpoint():
    payload = _run_routes_json()
    artifact_route = next(
        (r for r in payload["routes"] if r["path"] == "/runs/{run_id}/artifacts/{artifact_name}"),
        None,
    )
    assert artifact_route is not None
    assert "GET" in artifact_route["methods"]
