"""Streamlit dashboard for SourceLab AI.

Instruction:
- Install with `pip install -e ".[ui]"`.
- Run with `streamlit run src/sourcelab/ui/dashboard.py`.
- The dashboard reads existing artifacts; it does not rerun the pipeline.
- Missing artifacts show clear warnings, not crashes.
"""

from __future__ import annotations

import json
from pathlib import Path

from sourcelab.ui.release_dashboard import load_release_dashboard_summary
from sourcelab.ui.run_loader import (
    list_runs,
    load_json_artifact,
    load_markdown_artifact,
    load_artifact_inventory,
)


def _render_release_overview(st, summary: dict) -> None:
    """Landing section: release health and recommended next steps."""
    st.subheader("Release Overview")
    healthy = summary.get("release_healthy", False)
    st.metric("Release Healthy", "Yes" if healthy else "No")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Version", summary.get("version", "unknown"))
    col2.metric("Strict Release", summary.get("strict_release_status", "unknown"))
    col3.metric("Golden Evals", summary.get("golden_eval_status", "unknown"))
    bundle = summary.get("bundle_status", {})
    col4.metric("Release Bundle", bundle.get("status", "missing"))

    latest_run = summary.get("latest_run")
    if latest_run:
        st.write(
            f"**Latest run:** `{latest_run.get('run_id', 'unknown')}` — "
            f"{latest_run.get('topic') or '(no topic)'}"
        )
    else:
        st.info("No runs yet. Run `sourcelab local-demo` to generate proof artifacts.")

    export_path = summary.get("latest_export_path")
    if export_path:
        st.write(f"**Latest export:** `{export_path}`")
    else:
        st.info("No exported report yet. Run `sourcelab export latest --format markdown`.")

    golden = summary.get("golden_eval")
    if golden:
        st.write(
            f"**Golden eval ({golden.get('pack', 'unknown')}):** "
            f"{golden.get('total_passed', 0)}/{golden.get('total_cases', 0)} passed"
        )

    st.write("**Recommended next:**")
    for cmd in summary.get("recommended_next_commands", []):
        st.code(cmd, language="bash")


def main() -> None:
    try:
        import streamlit as st
    except ImportError as exc:
        raise SystemExit("Install UI extras: pip install -e '.[ui]'") from exc

    st.set_page_config(page_title="SourceLab AI", layout="wide")
    st.title("SourceLab AI")
    st.caption("Source-grounded adaptive technical lab generator — Local v1.0")

    project_root = Path.cwd()
    release_summary = load_release_dashboard_summary(project_root)
    _render_release_overview(st, release_summary)

    summaries = list_runs(project_root)
    if not summaries:
        st.warning("No runs found. Run `sourcelab demo` or `sourcelab local-demo` first.")
        _render_release_tab(st, project_root, release_summary, None, None)
        return

    run_ids = [s.run_id for s in summaries]
    selected_id = st.sidebar.selectbox("Select Run", run_ids, index=len(run_ids) - 1)
    selected_summary = next(s for s in summaries if s.run_id == selected_id)
    run_dir = Path(selected_summary.run_dir)

    tabs = st.tabs([
        "Overview",
        "Lesson",
        "Sources & Retrieval",
        "Sources",
        "Verification",
        "Harness & Proof",
        "Learning",
        "Artifacts",
        "Release",
    ])

    with tabs[0]:
        st.subheader(f"Run: {selected_summary.run_id}")
        st.write(f"**Topic:** {selected_summary.topic or '(not set)'}")

        col1, col2, col3, col4 = st.columns(4)
        harness_str = "PASS" if selected_summary.harness_passed is True else (
            "FAIL" if selected_summary.harness_passed is False else "UNKNOWN"
        )
        col1.metric("Harness Status", harness_str)
        col2.metric("Proof Bundle", selected_summary.proof_bundle_status or "unknown")
        if selected_summary.has_answer or selected_summary.answer_score is not None:
            col3.metric(
                "Answer Score",
                f"{selected_summary.answer_score:.2f}" if selected_summary.answer_score is not None else "N/A",
            )
        else:
            col3.metric("Answer Score", "N/A")
        col4.metric(
            "Citation Resolution",
            f"{selected_summary.citation_resolution_rate:.2f}"
            if selected_summary.citation_resolution_rate is not None
            else "N/A",
        )

        col5, col6 = st.columns(2)
        col5.metric("Unsupported High-Risk Claims", selected_summary.unsupported_high_risk_claims)
        col6.metric("Human Review Items", selected_summary.human_review_count)

        if selected_summary.has_answer or selected_summary.answer_score is not None:
            st.subheader("Learning Metrics")
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            metric_col1.metric(
                "Final Score",
                f"{selected_summary.answer_score:.2f}" if selected_summary.answer_score is not None else "N/A",
            )
            metric_col2.metric(
                "Rubric Alignment",
                f"{selected_summary.rubric_alignment_score:.2f}"
                if selected_summary.rubric_alignment_score is not None
                else "N/A",
            )
            metric_col3.metric(
                "Uncapped Score",
                f"{selected_summary.uncapped_score:.2f}"
                if selected_summary.uncapped_score is not None
                else "N/A",
            )
            detail_col1, detail_col2 = st.columns(2)
            detail_col1.metric(
                "Needs Review",
                "Yes" if selected_summary.needs_review else "No"
                if selected_summary.needs_review is not None
                else "N/A",
            )
            if selected_summary.cap_reason:
                detail_col2.write(f"**Cap Reason:** {selected_summary.cap_reason}")
            if selected_summary.human_review_reason:
                st.write(f"**Human Review Reason:** {selected_summary.human_review_reason}")
        else:
            st.info("No answer submitted for this run yet")

        if selected_summary.next_task_focus:
            st.write(f"**Next Task Focus:** {selected_summary.next_task_focus}")

    with tabs[1]:
        st.subheader("Generated Lesson")
        lesson_md = load_markdown_artifact(run_dir, "generated_lesson.md")
        if lesson_md:
            st.markdown(lesson_md)
        else:
            st.warning("No generated_lesson.md found.")

        st.subheader("Rubric")
        rubric_data = load_json_artifact(run_dir, "rubric.json")
        if rubric_data and isinstance(rubric_data, dict):
            criteria = rubric_data.get("criteria", [])
            if criteria:
                st.table([
                    {
                        "Criterion": c.get("name", ""),
                        "Weight": c.get("weight", 0),
                        "Description": c.get("description", ""),
                    }
                    for c in criteria
                ])
            else:
                st.info("No rubric criteria found.")
        else:
            st.warning("No rubric.json found.")

        st.subheader("Answer Key")
        answer_key_md = load_markdown_artifact(run_dir, "answer_key.md")
        if answer_key_md:
            st.markdown(answer_key_md)
        else:
            st.warning("No answer_key.md found.")

    with tabs[2]:
        st.subheader("Source Registry Snapshot")
        source_data = load_json_artifact(run_dir, "source_registry_snapshot.json")
        if source_data and isinstance(source_data, list):
            st.table([
                {
                    "Source ID": s.get("source_id", ""),
                    "Title": s.get("title", ""),
                    "Trust Tier": s.get("trust_tier", ""),
                }
                for s in source_data
            ])
        else:
            st.warning("No source_registry_snapshot.json found.")

        st.subheader("Retrieved Chunks")
        chunks_data = load_json_artifact(run_dir, "retrieved_chunks.json")
        if chunks_data and isinstance(chunks_data, list):
            st.table([
                {
                    "Chunk ID": c.get("chunk_id", ""),
                    "Source ID": c.get("source_id", ""),
                    "Score": f"{c.get('score', 0):.3f}",
                    "Preview": c.get("text_preview", "")[:80],
                }
                for c in chunks_data
            ])
        else:
            st.warning("No retrieved_chunks.json found.")

        st.subheader("Compression Report")
        compression = load_json_artifact(run_dir, "compression_report.json")
        if compression and isinstance(compression, dict):
            st.json(compression)
        else:
            st.warning("No compression_report.json found.")

    with tabs[3]:
        st.subheader("Source Pack (PQC v1)")
        pack_manifest = project_root / "data" / "source_packs" / "pqc_v1" / "manifest.json"
        if pack_manifest.exists():
            try:
                st.json(json.loads(pack_manifest.read_text(encoding="utf-8")))
            except Exception:
                st.warning("Could not read PQC pack manifest.")
        else:
            st.info("PQC source pack not installed. Run `sourcelab init-local`.")

        st.subheader("Source Quality Report")
        quality_report = load_json_artifact(run_dir, "source_quality_report.json")
        if quality_report and isinstance(quality_report, dict):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Sources", quality_report.get("total_sources", 0))
            col2.metric("Active Sources", quality_report.get("active_sources", 0))
            col3.metric("Pending Review", quality_report.get("pending_review_sources", 0))
            col4.metric("Stale Sources", quality_report.get("stale_sources", 0))
        else:
            st.info("No source_quality_report.json found.")

        st.subheader("Source Freshness Report")
        freshness_report = load_json_artifact(run_dir, "source_freshness_report.json")
        if freshness_report and isinstance(freshness_report, dict):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Fresh Sources", freshness_report.get("fresh_count", 0))
            col2.metric("Aging Sources", freshness_report.get("aging_count", 0))
            col3.metric("Stale Sources", freshness_report.get("stale_count", 0))
            col4.metric("Unknown", freshness_report.get("unknown_count", 0))
        else:
            st.info("No source_freshness_report.json found.")

    with tabs[4]:
        st.subheader("Grounding Report")
        grounding_md = load_markdown_artifact(run_dir, "grounding_report.md")
        if grounding_md:
            st.markdown(grounding_md)
        else:
            st.warning("No grounding_report.md found.")

        st.subheader("Claim Map")
        claim_map = load_json_artifact(run_dir, "claim_map.json")
        if claim_map and isinstance(claim_map, list):
            st.table([
                {
                    "Claim": c.get("claim", "")[:80],
                    "Support Status": c.get("support_status", ""),
                    "Source ID": c.get("source_id", ""),
                    "Severity": c.get("severity", ""),
                }
                for c in claim_map
            ])
        else:
            st.warning("No claim_map.json found.")

        st.subheader("Citation Resolution")
        citation = load_json_artifact(run_dir, "citation_resolution.json")
        if citation and isinstance(citation, dict):
            st.json(citation)
        else:
            st.warning("No citation_resolution.json found.")

        st.subheader("Human Review Queue")
        review_queue = load_json_artifact(run_dir, "human_review_queue.json")
        if review_queue and isinstance(review_queue, dict):
            items = review_queue.get("items", [])
            total = review_queue.get("total_items", len(items))
            st.write(f"**Total Items:** {total}")
            if items:
                st.table([
                    {
                        "Item ID": item.get("item_id", ""),
                        "Priority": item.get("priority", ""),
                        "Reason": item.get("reason", ""),
                        "Claim": item.get("claim_text", "")[:60],
                    }
                    for item in items
                ])
        else:
            st.warning("No human_review_queue.json found.")

    with tabs[5]:
        st.subheader("Harness Report")
        harness_data = load_json_artifact(run_dir, "harness_report.json")
        if harness_data and isinstance(harness_data, dict):
            col1, col2 = st.columns(2)
            col1.metric("Passed", "Yes" if harness_data.get("passed") else "No")
            col2.metric("Artifact Count", harness_data.get("artifact_count", "unknown"))
            blocking = harness_data.get("blocking_failures", [])
            if blocking:
                st.error("**Blocking Failures:**")
                for item in blocking:
                    st.write(f"- {item}")
        else:
            st.warning("No harness_report.json found.")

        st.subheader("Proof Summary")
        proof_summary = load_json_artifact(run_dir, "proof_summary.json")
        if proof_summary and isinstance(proof_summary, dict):
            st.json(proof_summary)
        else:
            st.warning("No proof_summary.json found.")

        st.subheader("Proof Bundle Manifest")
        bundle_manifest = load_json_artifact(run_dir, "proof_bundle_manifest.json")
        if bundle_manifest and isinstance(bundle_manifest, dict):
            st.json(bundle_manifest)
        else:
            st.warning("No proof_bundle_manifest.json found.")

    with tabs[6]:
        st.subheader("Learning Summary")
        if not selected_summary.has_answer and selected_summary.answer_score is None:
            st.info("No answer submitted for this run yet")
        else:
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            metric_col1.metric(
                "Final Score",
                f"{selected_summary.answer_score:.2f}" if selected_summary.answer_score is not None else "N/A",
            )
            metric_col2.metric(
                "Rubric Alignment",
                f"{selected_summary.rubric_alignment_score:.2f}"
                if selected_summary.rubric_alignment_score is not None
                else "N/A",
            )
            metric_col3.metric(
                "Uncapped Score",
                f"{selected_summary.uncapped_score:.2f}"
                if selected_summary.uncapped_score is not None
                else "N/A",
            )
            detail_col1, detail_col2, detail_col3 = st.columns(3)
            detail_col1.metric(
                "Needs Review",
                "Yes" if selected_summary.needs_review else "No"
                if selected_summary.needs_review is not None
                else "N/A",
            )
            if selected_summary.cap_reason:
                detail_col2.write(f"**Cap Reason:** {selected_summary.cap_reason}")
            if selected_summary.human_review_reason:
                detail_col3.write(f"**Human Review Reason:** {selected_summary.human_review_reason}")
            if selected_summary.source_grounding_score is not None:
                st.metric("Source Grounding Score", f"{selected_summary.source_grounding_score:.2f}")
            if selected_summary.concept_overlap_grounding_score is not None:
                st.metric(
                    "Concept Overlap Grounding Score",
                    f"{selected_summary.concept_overlap_grounding_score:.2f}",
                )

        learning_md = load_markdown_artifact(run_dir, "learning_report.md")
        if learning_md:
            st.markdown(learning_md)
        elif selected_summary.has_answer or selected_summary.answer_score is not None:
            st.info("No learning_report.md found.")

        answer_review = load_json_artifact(run_dir, "answer_review.json")
        if answer_review and isinstance(answer_review, dict):
            st.subheader("Answer Review")
            st.json(answer_review)

        mastery = load_json_artifact(run_dir, "mastery_update.json")
        if mastery and isinstance(mastery, dict):
            st.subheader("Mastery Update")
            st.json(mastery)

        next_task = load_json_artifact(run_dir, "next_task_decision.json")
        if next_task and isinstance(next_task, dict):
            st.subheader("Next Task Decision")
            st.json(next_task)

    with tabs[7]:
        st.subheader("Artifact Inventory")
        inventory = load_artifact_inventory(run_dir)
        if inventory:
            rows = [
                {
                    "Name": row.name,
                    "Type": row.artifact_type,
                    "Required": "Yes" if row.required else "No",
                    "Exists": "Yes" if row.exists else "No",
                    "Validated": "Yes" if row.validated else "No",
                    "Size": f"{row.size:,}" if row.size else "-",
                }
                for row in inventory
            ]
            st.table(rows)
            existing = sum(1 for r in inventory if r.exists)
            required_missing = sum(1 for r in inventory if r.required and not r.exists)
            st.write(f"**Existing:** {existing}/{len(inventory)} | **Missing Required:** {required_missing}")
        else:
            st.warning("No artifacts found.")

    with tabs[8]:
        _render_release_tab(st, project_root, release_summary, selected_summary, run_dir)


def _render_release_tab(st, project_root: Path, summary: dict, selected_summary, run_dir) -> None:
    """Release tab with manifest, evals, bundle, and export paths."""
    st.subheader("Release Status")

    manifest_data = summary.get("manifest")
    if manifest_data:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Strict Release", manifest_data.get("strict_release_status", "unknown"))
        col2.metric("Golden Evals", manifest_data.get("golden_eval_status", "unknown"))
        col3.metric("Doctor", manifest_data.get("doctor_status", "unknown"))
        col4.metric("Harness", manifest_data.get("harness_status", "unknown"))

        rate = manifest_data.get("golden_eval_pass_rate")
        if rate is not None:
            st.write(f"**Golden eval pass rate:** {rate:.1%}")
        st.write(f"**PQC pack installed:** {'Yes' if manifest_data.get('pqc_pack_installed') else 'No'}")
    else:
        st.info("No release manifest found. Run `sourcelab local-demo` to generate.")

    bundle = summary.get("bundle_status", {})
    st.subheader("Release Bundle")
    st.write(f"**Status:** {bundle.get('status', 'missing')}")
    if bundle.get("bundle_dir"):
        st.write(f"**Directory:** `{bundle['bundle_dir']}`")
    if bundle.get("bundle_zip"):
        st.write(f"**Zip:** `{bundle['bundle_zip']}`")

    report_path = project_root / "artifacts" / "release" / "local_v1_release_report.md"
    if report_path.exists():
        st.subheader("Release Report")
        try:
            st.markdown(report_path.read_text(encoding="utf-8"))
        except Exception as exc:
            st.warning(f"Could not read release report: {exc}")

    golden = summary.get("golden_eval")
    if golden:
        st.subheader("Golden Eval Summary")
        st.json(golden)

    if selected_summary and run_dir:
        st.subheader("Selected Run Proof / Harness")
        harness_data = load_json_artifact(run_dir, "harness_report.json")
        if harness_data:
            st.json(harness_data)
        proof_summary = load_json_artifact(run_dir, "proof_summary.json")
        if proof_summary:
            st.json(proof_summary)


if __name__ == "__main__":
    main()
