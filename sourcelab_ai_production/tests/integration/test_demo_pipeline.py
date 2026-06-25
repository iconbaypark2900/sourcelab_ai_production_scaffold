from pathlib import Path

from sourcelab.core.pipeline import run_demo_pipeline, run_lesson_create


def test_demo_pipeline_creates_proof_bundle(tmp_path):
    # Copy demo sources into tmp project shape.
    source_dir = tmp_path / "data" / "demo_sources"
    source_dir.mkdir(parents=True)
    source_dir.joinpath("nist_pqc_notes.md").write_text(
        "Post-quantum migration begins with a cryptographic inventory. "
        "Avoid claiming current quantum computers break RSA-2048 today.",
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

    result = run_demo_pipeline("post quantum cryptography migration", tmp_path)
    assert result["harness_passed"] is True
    assert result["source_count"] == 3
    assert result["retrieved_count"] > 0
    run_dir = Path(result["run_dir"])
    assert (run_dir / "grounding_report.md").exists()
    assert (run_dir / "trace.json").exists()


def test_demo_pipeline_writes_generation_v2_artifacts(tmp_path):
    """Demo pipeline writes all Generation v2 artifacts."""
    source_dir = tmp_path / "data" / "demo_sources"
    source_dir.mkdir(parents=True)
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

    result = run_demo_pipeline("post quantum cryptography migration", tmp_path)
    run_dir = Path(result["run_dir"])

    # Check all required Generation v2 artifacts exist
    assert (run_dir / "generated_lesson_package.json").exists()
    assert (run_dir / "generated_lesson.md").exists()
    assert (run_dir / "rubric.json").exists()
    assert (run_dir / "answer_key.md").exists()
    assert (run_dir / "claim_map.json").exists()
    assert (run_dir / "grounding_report.md").exists()
    assert (run_dir / "harness_report.json").exists()
    assert (run_dir / "trace.json").exists()


def test_lesson_create_produces_valid_output(tmp_path):
    """sourcelab lesson create produces valid output."""
    source_dir = tmp_path / "data" / "demo_sources"
    source_dir.mkdir(parents=True)
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

    result = run_lesson_create(
        topic="post quantum cryptography migration",
        project_root=tmp_path,
        difficulty=3,
        task_format="architecture_review",
    )
    assert result["harness_passed"] is True
    assert result["source_count"] == 3
    assert result["retrieved_count"] > 0

    run_dir = Path(result["run_dir"])
    assert (run_dir / "generated_lesson_package.json").exists()
    assert (run_dir / "generated_lesson.md").exists()
    assert (run_dir / "rubric.json").exists()
    assert (run_dir / "answer_key.md").exists()
    assert (run_dir / "generation_trace.json").exists()
