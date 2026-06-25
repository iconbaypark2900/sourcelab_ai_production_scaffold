"""Unit tests for Source Pack Smoke Matrix v1 and bootstrap legacy eval helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import bootstrap_sourcelab_source_packs as bootstrap  # noqa: E402
import smoke_source_packs as smoke  # noqa: E402


def _write_pack(
    root: Path,
    pack_name: str,
    *,
    example_lessons: list[str] | None = None,
    topics: list[str] | None = None,
    legacy_evals: list[str] | None = None,
    gold_evals: list[str] | None = None,
) -> None:
    pack_dir = root / "data" / "source_packs" / pack_name
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "sources").mkdir(exist_ok=True)
    (pack_dir / "evals").mkdir(exist_ok=True)
    (pack_dir / "README.md").write_text("# test\n", encoding="utf-8")

    payload = {
        "name": pack_name,
        "title": pack_name.replace("_", " "),
        "topics": topics or ["fallback topic"],
        "example_lessons": example_lessons or [],
    }
    (pack_dir / "pack.json").write_text(json.dumps(payload), encoding="utf-8")
    manifest = {
        "pack_name": pack_name,
        "version": "1.0.0",
        "title": payload["title"],
        "sources": [{"source_id": "s1", "filename": "s1.md"}],
        "evals": ["retrieval_gold.json"],
    }
    (pack_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    for filename in legacy_evals or []:
        (pack_dir / "evals" / filename).write_text("[]\n", encoding="utf-8")
    for filename in gold_evals or []:
        (pack_dir / "evals" / filename).write_text("[]\n", encoding="utf-8")


@pytest.fixture
def mini_root(tmp_path: Path) -> Path:
    (tmp_path / "data" / "source_packs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "sourcelab").mkdir(parents=True, exist_ok=True)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    return tmp_path


class TestSmokePackDiscovery:
    def test_discover_source_packs_skips_builtins_by_default(self, mini_root: Path):
        _write_pack(mini_root, "agentic_engineering_v1")
        _write_pack(mini_root, "pqc_v1")

        discovered = smoke.discover_source_packs(mini_root, skip_builtins=True)
        assert discovered == ["agentic_engineering_v1"]

    def test_discover_source_packs_includes_builtins_when_not_skipping(self, mini_root: Path):
        _write_pack(mini_root, "pqc_v1")

        discovered = smoke.discover_source_packs(mini_root, skip_builtins=False)
        assert "pqc_v1" in discovered


class TestSmokePackSelection:
    def test_resolve_core_selection(self, mini_root: Path):
        for name in bootstrap.GROUPS["core"]:
            _write_pack(mini_root, name)

        selected = smoke.resolve_pack_selection(mini_root, "core", skip_builtins=True)
        assert selected == bootstrap.GROUPS["core"]

    def test_resolve_comma_list(self, mini_root: Path):
        _write_pack(mini_root, "agentic_engineering_v1")
        _write_pack(mini_root, "local_ai_infra_v1")

        selected = smoke.resolve_pack_selection(
            mini_root,
            "agentic_engineering_v1,local_ai_infra_v1",
            skip_builtins=True,
        )
        assert selected == ["agentic_engineering_v1", "local_ai_infra_v1"]

    def test_unknown_pack_exits(self, mini_root: Path):
        with pytest.raises(SystemExit, match="Unknown or missing pack"):
            smoke.resolve_pack_selection(mini_root, "missing_pack_v1", skip_builtins=True)


class TestLessonTopicSelection:
    def test_prefers_pack_json_example_lessons(self, mini_root: Path):
        _write_pack(
            mini_root,
            "agentic_engineering_v1",
            example_lessons=["example lesson topic"],
            topics=["topic fallback"],
        )
        assert smoke.select_lesson_topic(mini_root, "agentic_engineering_v1") == "example lesson topic"

    def test_falls_back_to_first_topic(self, mini_root: Path):
        _write_pack(mini_root, "local_ai_infra_v1", topics=["first topic", "second topic"])
        assert smoke.select_lesson_topic(mini_root, "local_ai_infra_v1") == "first topic"


class TestSmokeReportRows:
    def test_report_row_fields(self, mini_root: Path):
        _write_pack(mini_root, "agentic_engineering_v1")

        def fake_runner(command: list[str], cwd: Path) -> tuple[int, str]:
            if command[:3] == ["sourcelab", "source-pack", "doctor"]:
                return 0, json.dumps(
                    {
                        "valid": True,
                        "source_count": 2,
                        "eval_count": 4,
                        "warnings": ["warn"],
                        "errors": [],
                    }
                )
            if command[:3] == ["sourcelab", "evals", "run"]:
                return 0, json.dumps({"summary": {"total_failed": 0}})
            return 0, "{}"

        row = smoke.smoke_pack_row(
            mini_root,
            "agentic_engineering_v1",
            difficulty=2,
            run_evals=True,
            run_lessons=False,
            dry_run=False,
            command_runner=fake_runner,
        )
        assert row.pack_name == "agentic_engineering_v1"
        assert row.doctor_valid is True
        assert row.source_count == 2
        assert row.eval_count == 4
        assert row.eval_status == "pass"
        assert row.lesson_status == "skipped"

    def test_render_matrix_markdown_includes_rows(self, mini_root: Path):
        report = {
            "generated_at": "2026-06-20T00:00:00+00:00",
            "project_root": str(mini_root),
            "selection": "core",
            "skip_builtins": True,
            "dry_run": False,
            "run_evals": True,
            "run_lessons": False,
            "difficulty": 2,
            "pack_count": 1,
            "passed_count": 1,
            "failed_count": 0,
            "packs": [
                {
                    "pack_name": "agentic_engineering_v1",
                    "doctor_valid": True,
                    "source_count": 2,
                    "eval_count": 4,
                    "eval_status": "pass",
                    "lesson_status": "skipped",
                    "run_id": "",
                    "proof_status": "skipped",
                    "harness_status": "skipped",
                    "errors": [],
                    "warnings": [],
                }
            ],
        }
        md = smoke.render_matrix_markdown(report)
        assert "agentic_engineering_v1" in md
        assert "Eval Status" in md


class TestSmokeFailedCommandHandling:
    def test_doctor_failure_records_errors(self, mini_root: Path):
        _write_pack(mini_root, "agentic_engineering_v1")

        def fake_runner(command: list[str], cwd: Path) -> tuple[int, str]:
            return 1, json.dumps({"valid": False, "errors": ["missing file"], "warnings": []})

        row = smoke.smoke_pack_row(
            mini_root,
            "agentic_engineering_v1",
            difficulty=2,
            run_evals=False,
            run_lessons=False,
            dry_run=False,
            command_runner=fake_runner,
        )
        assert row.doctor_valid is False
        assert "missing file" in row.errors

    def test_eval_failure_sets_status_fail(self, mini_root: Path):
        _write_pack(mini_root, "agentic_engineering_v1")

        def fake_runner(command: list[str], cwd: Path) -> tuple[int, str]:
            if command[:3] == ["sourcelab", "source-pack", "doctor"]:
                return 0, json.dumps({"valid": True, "source_count": 1, "eval_count": 4})
            return 0, json.dumps({"summary": {"total_failed": 2}})

        row = smoke.smoke_pack_row(
            mini_root,
            "agentic_engineering_v1",
            difficulty=2,
            run_evals=True,
            run_lessons=False,
            dry_run=False,
            command_runner=fake_runner,
        )
        assert row.eval_status == "fail"
        assert any("evals failed" in error for error in row.errors)


class TestSmokeStrictMode:
    def test_main_strict_stops_after_first_failure(self, mini_root: Path, monkeypatch: pytest.MonkeyPatch):
        _write_pack(mini_root, "agentic_engineering_v1")
        _write_pack(mini_root, "local_ai_infra_v1")

        calls: list[str] = []

        def fake_smoke_pack_row(root, pack_name, **kwargs):
            calls.append(pack_name)
            row = smoke.PackSmokeRow(pack_name=pack_name)
            if pack_name == "agentic_engineering_v1":
                row.errors.append("forced failure")
            return row

        monkeypatch.setattr(smoke, "find_project_root", lambda _cwd: mini_root)
        monkeypatch.setattr(smoke, "smoke_pack_row", fake_smoke_pack_row)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "smoke_source_packs.py",
                "--packs",
                "agentic_engineering_v1,local_ai_infra_v1",
                "--strict",
            ],
        )

        exit_code = smoke.main()
        assert exit_code == 1
        assert calls == ["agentic_engineering_v1"]


class TestLegacyEvalHelpers:
    def test_list_legacy_evals_groups_by_pack(self, mini_root: Path, capsys: pytest.CaptureFixture[str]):
        _write_pack(
            mini_root,
            "agentic_engineering_v1",
            legacy_evals=["retrieval_eval.json", "lesson_eval.json"],
        )
        _write_pack(mini_root, "pqc_v1", legacy_evals=["answer_eval.json"])

        bootstrap.list_legacy_eval_files(mini_root, include_builtins=False)
        output = capsys.readouterr().out
        assert "agentic_engineering_v1:" in output
        assert "retrieval_eval.json" in output
        assert "pqc_v1" not in output

    def test_delete_legacy_evals_skips_gold_files(self, mini_root: Path):
        _write_pack(
            mini_root,
            "agentic_engineering_v1",
            legacy_evals=["retrieval_eval.json", "answer_eval.json"],
            gold_evals=["retrieval_gold.json"],
        )

        results = bootstrap.delete_legacy_eval_files(mini_root, include_builtins=False, dry_run=False)
        assert any("deleted" in item and "retrieval_eval.json" in item for item in results)
        assert (mini_root / "data/source_packs/agentic_engineering_v1/evals/retrieval_gold.json").exists()
        assert not (
            mini_root / "data/source_packs/agentic_engineering_v1/evals/retrieval_eval.json"
        ).exists()

    def test_delete_legacy_evals_dry_run(self, mini_root: Path):
        _write_pack(mini_root, "local_ai_infra_v1", legacy_evals=["lesson_eval.json"])

        results = bootstrap.delete_legacy_eval_files(mini_root, include_builtins=False, dry_run=True)
        assert any("would_delete" in item for item in results)
        assert (
            mini_root / "data/source_packs/local_ai_infra_v1/evals/lesson_eval.json"
        ).exists()

    def test_discover_legacy_evals_include_builtins(self, mini_root: Path):
        _write_pack(mini_root, "pqc_v1", legacy_evals=["answer_eval.json"])

        grouped = bootstrap.discover_legacy_eval_files(mini_root, include_builtins=True)
        assert "pqc_v1" in grouped
        assert "answer_eval.json" in grouped["pqc_v1"]


class TestRepairManifests:
    def test_repair_manifests_does_not_overwrite_sources(self, mini_root: Path):
        pack_name = "agentic_engineering_v1"
        pack_dir = mini_root / "data" / "source_packs" / pack_name
        pack_dir.mkdir(parents=True, exist_ok=True)
        (pack_dir / "sources").mkdir(exist_ok=True)
        (pack_dir / "evals").mkdir(exist_ok=True)
        source_path = pack_dir / "sources" / "custom_source.md"
        custom_body = "# Custom strengthened source\n\nDGX Spark routing notes.\n"
        source_path.write_text(custom_body, encoding="utf-8")

        pack_payload = {
            "name": pack_name,
            "title": "Agentic Engineering",
            "topics": ["topic"],
            "example_lessons": ["lesson topic"],
        }
        (pack_dir / "pack.json").write_text(json.dumps(pack_payload), encoding="utf-8")
        (pack_dir / "manifest.json").write_text(json.dumps({"pack_name": pack_name}), encoding="utf-8")
        for gold_name in bootstrap.GOLD_EVAL_FILES:
            (pack_dir / "evals" / gold_name).write_text("[]\n", encoding="utf-8")

        bootstrap.repair_pack_manifests(mini_root, [pack_name], dry_run=False)
        assert source_path.read_text(encoding="utf-8") == custom_body


class TestCoreGoldEvalPresence:
    @pytest.mark.parametrize("pack_name", bootstrap.GROUPS["core"])
    def test_core_packs_have_gold_eval_files(self, mini_root: Path, pack_name: str):
        _write_pack(
            mini_root,
            pack_name,
            gold_evals=list(bootstrap.GOLD_EVAL_FILES),
        )
        evals_dir = mini_root / "data" / "source_packs" / pack_name / "evals"
        for gold_name in bootstrap.GOLD_EVAL_FILES:
            assert (evals_dir / gold_name).is_file()


class TestSafetyPackSeeds:
    def test_safety_group_contains_ml_safety_and_cloud_security(self):
        assert bootstrap.GROUPS["safety"] == ["ml_safety_v1", "cloud_security_v1"]

    def test_safety_packs_in_all_group(self):
        for name in bootstrap.GROUPS["safety"]:
            assert name in bootstrap.GROUPS["all"]

    @pytest.mark.parametrize("pack_name", bootstrap.GROUPS["safety"])
    def test_safety_pack_seed_has_required_fields(self, pack_name: str):
        pack = bootstrap.PACKS[pack_name]
        assert pack.name == pack_name
        assert pack.title
        assert pack.domain
        assert pack.description
        assert len(pack.topics) >= 3
        assert len(pack.example_lessons) >= 2
        assert len(pack.sources) == 2
        for source in pack.sources:
            assert source.source_id
            assert source.title
            assert source.summary
            assert len(source.key_claims) >= 2
            assert len(source.use_cases) >= 1

    @pytest.mark.parametrize("pack_name", bootstrap.GROUPS["safety"])
    def test_safety_pack_scaffolds_gold_evals(self, mini_root: Path, pack_name: str):
        pack = bootstrap.PACKS[pack_name]
        results = bootstrap.scaffold_pack(
            mini_root, pack, force=False, dry_run=False
        )
        evals_dir = mini_root / "data" / "source_packs" / pack_name / "evals"
        for gold_name in bootstrap.GOLD_EVAL_FILES:
            assert (evals_dir / gold_name).is_file()
        assert any("written" in r for r in results)

    @pytest.mark.parametrize("pack_name", bootstrap.GROUPS["safety"])
    def test_safety_pack_manifest_lists_all_gold_evals(self, mini_root: Path, pack_name: str):
        import json as _json

        pack = bootstrap.PACKS[pack_name]
        bootstrap.scaffold_pack(mini_root, pack, force=False, dry_run=False)
        manifest = _json.loads(
            (mini_root / "data" / "source_packs" / pack_name / "manifest.json").read_text()
        )
        assert manifest["pack_name"] == pack_name
        assert set(manifest["evals"]) == set(bootstrap.GOLD_EVAL_FILES)
        assert len(manifest["sources"]) == len(pack.sources)
