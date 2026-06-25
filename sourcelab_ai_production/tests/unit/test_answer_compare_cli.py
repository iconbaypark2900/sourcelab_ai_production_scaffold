"""CLI tests for batch/run answer comparison output formats."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from sourcelab.cli import cmd_batch_answers, cmd_runs_answers_compare


def _seed_batch(project_root: Path) -> tuple[str, Path]:
    runs_dir = project_root / "artifacts" / "runs"
    run_a = runs_dir / "run_a"
    run_b = runs_dir / "run_b"
    for run_dir in (run_a, run_b):
        run_dir.mkdir(parents=True)
        (run_dir / "run_manifest.json").write_text(
            json.dumps({"run_id": run_dir.name, "topic": "topic"}),
            encoding="utf-8",
        )

    batch_id = "batch_cli"
    batch_dir = project_root / "artifacts" / "batches" / batch_id
    batch_dir.mkdir(parents=True)
    (batch_dir / "batch_manifest.json").write_text(
        json.dumps(
            {
                "batch_id": batch_id,
                "batch_name": "cli",
                "run_ids": ["run_a", "run_b"],
                "runs": [],
                "failures": [],
            }
        ),
        encoding="utf-8",
    )
    return batch_id, run_a


def test_cmd_batch_answers_json_and_markdown(capsys, tmp_path: Path, monkeypatch):
    batch_id, _ = _seed_batch(tmp_path)
    monkeypatch.chdir(tmp_path)

    cmd_batch_answers(Namespace(batch_id=batch_id, json=True, markdown=False))
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["summary"]["total_runs"] == 2

    cmd_batch_answers(Namespace(batch_id=batch_id, json=False, markdown=True))
    md = capsys.readouterr().out
    assert "No learner answer attempts" in md


def test_cmd_runs_answers_compare_markdown(capsys, tmp_path: Path, monkeypatch):
    _seed_batch(tmp_path)
    monkeypatch.chdir(tmp_path)

    cmd_runs_answers_compare(
        Namespace(run_ids=["run_a", "run_b"], json=False, markdown=True),
    )
    md = capsys.readouterr().out
    assert "No learner answer attempts" in md
    assert "Answer recommendation" in md
