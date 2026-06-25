"""CLI smoke tests for batch commands."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sourcelab.cli", *args],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )


def test_batch_list_smoke():
    result = _run(["batch", "list"])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)


def test_batch_create_from_example():
    result = _run([
        "batch", "create",
        "--name", "CLI smoke batch",
        "--config", "examples/batch_pqc.json",
    ])
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["batch_id"]
    assert len(data["runs"]) >= 2

    show = _run(["batch", "show", data["batch_id"]])
    assert show.returncode == 0

    compare = _run(["batch", "compare", data["batch_id"]])
    assert compare.returncode == 0
    cmp_data = json.loads(compare.stdout)
    assert "recommendation" in cmp_data


def test_batch_answers_smoke():
    create = _run([
        "batch", "create",
        "--name", "CLI answers smoke",
        "--config", "examples/batch_pqc.json",
    ])
    assert create.returncode == 0, create.stderr
    batch_id = json.loads(create.stdout)["batch_id"]

    answers = _run(["batch", "answers", batch_id])
    assert answers.returncode == 0, answers.stderr
    assert "Run ID" in answers.stdout
