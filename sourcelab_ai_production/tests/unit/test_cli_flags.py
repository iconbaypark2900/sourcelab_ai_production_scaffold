"""Regression tests for recently wired CLI flags."""

from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from sourcelab.cli import (
    build_parser,
    cmd_answer_diff,
    cmd_answer_history,
    cmd_answer_show,
    cmd_answer_submit,
    cmd_learning_report,
    cmd_lesson_create,
)
from sourcelab.core.pipeline import run_lesson_create
from sourcelab.sources.source_pack import install_source_pack


@pytest.fixture
def project_root():
    return Path.cwd()


def _run_cmd(func, args) -> dict:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        func(args)
    output = buffer.getvalue().strip()
    assert output, "Expected JSON output from CLI command"
    return json.loads(output)


def _seed_demo_sources(root: Path) -> None:
    source_dir = root / "data" / "demo_sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_dir.joinpath("nist_pqc_notes.md").write_text(
        "Post-quantum migration begins with a cryptographic inventory.",
        encoding="utf-8",
    )
    source_dir.joinpath("rag_grounding_notes.md").write_text(
        "Generated claims should map to source chunks.",
        encoding="utf-8",
    )
    source_dir.joinpath("developer_tools_notes.md").write_text(
        "Harnesses record artifacts, validations, and reports.",
        encoding="utf-8",
    )


class TestLessonCreateSourcePackFlag:
    def test_lesson_create_source_pack_pqc_v1(self, project_root):
        install_source_pack(project_root, "pqc_v1")
        args = build_parser().parse_args(
            [
                "lesson",
                "create",
                "--topic",
                "post-quantum cryptography migration",
                "--source-pack",
                "pqc_v1",
            ]
        )
        result = _run_cmd(cmd_lesson_create, args)
        assert result["harness_passed"] is True
        assert result["topic"] == "post-quantum cryptography migration"
        snapshot = json.loads(
            (Path(result["run_dir"]) / "source_registry_snapshot.json").read_text(encoding="utf-8")
        )
        source_ids = {source["source_id"] for source in snapshot}
        assert "nist_pqc_overview" in source_ids
        assert "crypto_inventory_migration" in source_ids


class TestAnswerSubmitRunFlags:
    @pytest.fixture
    def run_with_package(self, tmp_path):
        _seed_demo_sources(tmp_path)
        return run_lesson_create(
            topic="post-quantum cryptography migration",
            project_root=tmp_path,
            difficulty=3,
            task_format="architecture_review",
        )

    def test_answer_submit_run_latest(self, tmp_path, run_with_package):
        answer_path = Path.cwd() / "examples" / "strong_answer.md"
        args = build_parser().parse_args(
            [
                "answer",
                "submit",
                "--run",
                "latest",
                "--file",
                str(answer_path),
            ]
        )
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = _run_cmd(cmd_answer_submit, args)
        finally:
            os.chdir(original_cwd)

        assert result["run_id"] == run_with_package["run_id"]
        assert result["topic"] == "post-quantum cryptography migration"
        assert "overall_score" in result

    def test_answer_submit_run_id_latest(self, tmp_path, run_with_package):
        answer_path = Path.cwd() / "examples" / "strong_answer.md"
        args = build_parser().parse_args(
            [
                "answer",
                "submit",
                "--run-id",
                "latest",
                "--file",
                str(answer_path),
            ]
        )
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = _run_cmd(cmd_answer_submit, args)
        finally:
            os.chdir(original_cwd)

        assert result["run_id"] == run_with_package["run_id"]
        assert result["topic"] == "post-quantum cryptography migration"

    def test_answer_submit_without_topic_uses_run_package(self, tmp_path, run_with_package):
        args = build_parser().parse_args(
            [
                "answer",
                "submit",
                "--run",
                "latest",
                "--text",
                "Begin with a cryptographic inventory according to NIST guidance.",
            ]
        )
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = _run_cmd(cmd_answer_submit, args)
        finally:
            os.chdir(original_cwd)

        assert result["topic"] == "post-quantum cryptography migration"


class TestAnswerHistoryCommands:
    @pytest.fixture
    def run_with_answers(self, tmp_path):
        _seed_demo_sources(tmp_path)
        run = run_lesson_create(
            topic="post-quantum cryptography migration",
            project_root=tmp_path,
            difficulty=3,
            task_format="architecture_review",
        )
        answer_path = Path.cwd() / "examples" / "strong_answer.md"
        from sourcelab.core.pipeline import run_answer_submit

        run_answer_submit(
            topic=run["topic"],
            answer_text=answer_path.read_text(encoding="utf-8"),
            project_root=tmp_path,
            run_id=run["run_id"],
        )
        run_answer_submit(
            topic=run["topic"],
            answer_text="Weak answer without inventory.",
            project_root=tmp_path,
            run_id=run["run_id"],
        )
        return run

    def test_answer_history_latest(self, tmp_path, run_with_answers):
        args = build_parser().parse_args(["answer", "history", "--run", "latest"])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = _run_cmd(cmd_answer_history, args)
        finally:
            os.chdir(original_cwd)

        assert result["run_id"] == run_with_answers["run_id"]
        assert result["total"] >= 2

    def test_answer_show_and_diff(self, tmp_path, run_with_answers):
        history_args = build_parser().parse_args(["answer", "history", "--run", "latest"])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            history = _run_cmd(cmd_answer_history, history_args)
            first = history["attempts"][0]["attempt_id"]
            second = history["attempts"][-1]["attempt_id"]

            show_args = build_parser().parse_args(
                ["answer", "show", "--run", "latest", "--attempt", second]
            )
            detail = _run_cmd(cmd_answer_show, show_args)
            assert detail["attempt_id"] == second

            diff_args = build_parser().parse_args(
                ["answer", "diff", "--run", "latest", "--from", first, "--to", second]
            )
            diff = _run_cmd(cmd_answer_diff, diff_args)
            assert diff["from_attempt_id"] == first
            assert diff["to_attempt_id"] == second
            assert "score_delta" in diff
        finally:
            os.chdir(original_cwd)


class TestLearningReportLatestFlag:
    def test_learning_report_latest(self, tmp_path):
        _seed_demo_sources(tmp_path)
        run = run_lesson_create(
            topic="post-quantum cryptography migration",
            project_root=tmp_path,
        )
        run_dir = Path(run["run_dir"])
        run_dir.joinpath("learning_report.json").write_text(
            json.dumps(
                {
                    "report_id": "report_test",
                    "topic": run["topic"],
                    "run_id": run["run_id"],
                    "overall_score": 0.5,
                }
            ),
            encoding="utf-8",
        )

        args = build_parser().parse_args(["learning", "report", "--latest"])
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = _run_cmd(cmd_learning_report, args)
        finally:
            os.chdir(original_cwd)

        assert result["run_id"] == run["run_id"]
        assert result["topic"] == "post-quantum cryptography migration"
