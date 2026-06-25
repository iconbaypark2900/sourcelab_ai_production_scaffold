"""Release checklist for SourceLab AI.

Instruction:
- Checks that all local v1 release requirements are met.
- Used by `sourcelab release check` and `sourcelab local-demo`.
- Returns structured checklist results.
"""

from __future__ import annotations

import json
from pathlib import Path

from sourcelab.release.config import ReleaseThresholds, get_default_thresholds


def run_release_checklist(
    project_root: Path,
    thresholds: ReleaseThresholds | None = None,
) -> dict:
    """Run the local v1 release checklist.

    Returns a dict with:
        - status: PASS or FAIL
        - checks: list of individual check results
        - blocking: list of blocking issues
        - warnings: list of warnings
    """
    if thresholds is None:
        thresholds = get_default_thresholds()

    checks = []

    # 1. Tests exist
    checks.append(_check_tests_exist(project_root))

    # 2. PQC source pack installed
    checks.append(_check_source_pack(project_root))

    # 3. Source validation passes
    checks.append(_check_source_validation(project_root))

    # 4. Retrieval eval exists and passes
    checks.append(_check_retrieval_eval(project_root, thresholds))

    # 5. Golden eval summary exists and passes
    checks.append(_check_golden_evals(project_root, thresholds))

    # 6. Latest run has proof bundle
    checks.append(_check_latest_run_proof_bundle(project_root))

    # 7. Latest harness passed
    checks.append(_check_harness_passed(project_root))

    # 8. Citation resolution rate
    checks.append(_check_citation_resolution(project_root, thresholds))

    # 9. Unsupported high-risk claims
    checks.append(_check_high_risk_claims(project_root, thresholds))

    # 10. Model call trace exists
    checks.append(_check_model_call_trace(project_root))

    # 11. Dashboard/export commands available
    checks.append(_check_ui_commands(project_root))

    # 12. API routes available
    checks.append(_check_api_routes(project_root))

    # Determine overall status
    blocking = [c["message"] for c in checks if not c["passed"] and c.get("severity") == "blocking"]
    warnings = [c["message"] for c in checks if not c["passed"] and c.get("severity") == "warning"]

    status = "PASS" if not blocking else "FAIL"

    return {
        "status": status,
        "checks": checks,
        "blocking": blocking,
        "warnings": warnings,
    }


def _check_tests_exist(project_root: Path) -> dict:
    """Check that test files exist."""
    tests_dir = project_root / "tests"
    if not tests_dir.exists():
        return {
            "name": "tests_exist",
            "passed": False,
            "severity": "blocking",
            "message": "No tests directory found",
        }

    test_files = list(tests_dir.glob("**/test_*.py"))
    if not test_files:
        return {
            "name": "tests_exist",
            "passed": False,
            "severity": "blocking",
            "message": "No test files found",
        }

    return {
        "name": "tests_exist",
        "passed": True,
        "message": f"Found {len(test_files)} test files",
    }


def _check_source_pack(project_root: Path) -> dict:
    """Check that PQC source pack is installed."""
    from sourcelab.sources.source_pack import source_pack_status

    status = source_pack_status(project_root, "pqc_v1")
    if status.get("error"):
        return {
            "name": "pqc_pack_installed",
            "passed": False,
            "severity": "blocking",
            "message": f"PQC source pack not found: {status['error']}",
        }

    if not status.get("installed"):
        return {
            "name": "pqc_pack_installed",
            "passed": False,
            "severity": "blocking",
            "message": "PQC source pack not installed",
        }

    return {
        "name": "pqc_pack_installed",
        "passed": True,
        "message": f"PQC pack installed with {status.get('installed_count', 0)} sources",
    }


def _check_source_validation(project_root: Path) -> dict:
    """Check that source validation passes."""
    from sourcelab.sources.registry import SourceRegistry

    registry_path = project_root / "data" / "source_registry.json"
    if not registry_path.exists():
        return {
            "name": "source_validation",
            "passed": False,
            "severity": "warning",
            "message": "No source registry found",
        }

    try:
        registry = SourceRegistry.load_from_json(registry_path)
        errors = registry.validate()
        if errors:
            return {
                "name": "source_validation",
                "passed": False,
                "severity": "blocking",
                "message": f"Source validation failed: {errors}",
            }
        return {
            "name": "source_validation",
            "passed": True,
            "message": f"Source validation passed ({len(registry.sources)} sources)",
        }
    except Exception as e:
        return {
            "name": "source_validation",
            "passed": False,
            "severity": "blocking",
            "message": f"Source validation error: {e}",
        }


def _check_retrieval_eval(project_root: Path, thresholds: ReleaseThresholds) -> dict:
    """Check retrieval eval exists and passes threshold."""
    evals_dir = project_root / "artifacts" / "evals"
    if not evals_dir.exists():
        return {
            "name": "retrieval_eval",
            "passed": False,
            "severity": "warning",
            "message": "No eval results found (retrieval eval check skipped)",
        }

    # Check for retrieval eval in any pack
    for pack_dir in evals_dir.iterdir():
        if not pack_dir.is_dir():
            continue
        summary_path = pack_dir / "golden_eval_summary.json"
        if not summary_path.exists():
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            # Check if retrieval eval data exists in the pack
            reports_dir = pack_dir
            retrieval_report = reports_dir / "retrieval_gold_report.json"
            if retrieval_report.exists():
                report_data = json.loads(retrieval_report.read_text(encoding="utf-8"))
                pass_rate = report_data.get("pass_rate", 0)
                if pass_rate < thresholds.retrieval_min_pass_rate:
                    return {
                        "name": "retrieval_eval",
                        "passed": False,
                        "severity": "blocking",
                        "message": f"Retrieval eval pass rate {pass_rate:.1%} below threshold {thresholds.retrieval_min_pass_rate:.1%}",
                    }
                return {
                    "name": "retrieval_eval",
                    "passed": True,
                    "message": f"Retrieval eval pass rate: {pass_rate:.1%}",
                }
        except (json.JSONDecodeError, KeyError):
            continue

    return {
        "name": "retrieval_eval",
        "passed": False,
        "severity": "warning",
        "message": "No retrieval eval results found",
    }


def _check_golden_evals(project_root: Path, thresholds: ReleaseThresholds) -> dict:
    """Check golden eval summary exists and passes per-pack thresholds.

    Iterates over all packs in ``artifacts/evals/`` and evaluates each
    against its per-pack thresholds loaded from
    ``data/source_packs/<pack>/manifest.json``. The global
    ``golden_eval_min_pass_rate`` is used as a floor when a pack has no
    explicit per-pack threshold.
    """
    from sourcelab.evals.thresholds import (
        DEFAULT_THRESHOLDS,
        evaluate_against_thresholds,
        load_pack_thresholds,
    )

    evals_dir = project_root / "artifacts" / "evals"
    if not evals_dir.exists():
        return {
            "name": "golden_evals",
            "passed": False,
            "severity": "warning",
            "message": "No eval results found",
        }

    pack_results: list[dict] = []
    for pack_dir in sorted(evals_dir.iterdir()):
        if not pack_dir.is_dir():
            continue
        summary_path = pack_dir / "golden_eval_summary.json"
        if not summary_path.exists():
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, KeyError):
            continue

        pack_name = pack_dir.name
        pack_thresholds = load_pack_thresholds(project_root, pack_name)
        # If the pack has no explicit eval_thresholds in its manifest and
        # no builtin preset, raise the floor to the global release threshold
        # so the global default still applies.
        if pack_thresholds.is_default():
            from sourcelab.evals.thresholds import PackEvalThresholds

            pack_thresholds = PackEvalThresholds(
                min_pass_rate=thresholds.golden_eval_min_pass_rate,
                min_cases=pack_thresholds.min_cases,
                required_evals=pack_thresholds.required_evals,
            )

        evaluation = evaluate_against_thresholds(pack_name, summary, pack_thresholds)
        pack_results.append(evaluation.to_dict())

    if not pack_results:
        return {
            "name": "golden_evals",
            "passed": False,
            "severity": "warning",
            "message": "No golden eval summary found",
        }

    failing = [r for r in pack_results if not r["meets_thresholds"]]
    if failing:
        failing_names = ", ".join(r["pack_name"] for r in failing)
        return {
            "name": "golden_evals",
            "passed": False,
            "severity": "blocking",
            "message": (
                f"{len(failing)} pack(s) below per-pack eval thresholds: {failing_names}"
            ),
            "pack_results": pack_results,
        }

    # All packs meet their thresholds
    first = pack_results[0]
    pass_rate = first.get("overall_pass_rate") or 0
    return {
        "name": "golden_evals",
        "passed": True,
        "message": (
            f"All {len(pack_results)} pack(s) meet their per-pack eval thresholds "
            f"(latest pass rate: {pass_rate:.1%})"
        ),
        "pack_results": pack_results,
    }


def _check_latest_run_proof_bundle(project_root: Path) -> dict:
    """Check that latest run has a proof bundle."""
    from sourcelab.harness.release_gate import _find_latest_run

    latest_run = _find_latest_run(project_root)
    if latest_run is None:
        return {
            "name": "latest_proof_bundle",
            "passed": False,
            "severity": "warning",
            "message": "No runs found",
        }

    manifest_path = latest_run / "proof_bundle_manifest.json"
    if not manifest_path.exists():
        return {
            "name": "latest_proof_bundle",
            "passed": False,
            "severity": "blocking",
            "message": f"Proof bundle manifest missing in run {latest_run.name}",
        }

    return {
        "name": "latest_proof_bundle",
        "passed": True,
        "message": f"Proof bundle exists in run {latest_run.name}",
    }


def _check_harness_passed(project_root: Path) -> dict:
    """Check that latest harness passed."""
    from sourcelab.harness.release_gate import _find_latest_run

    latest_run = _find_latest_run(project_root)
    if latest_run is None:
        return {
            "name": "harness_passed",
            "passed": False,
            "severity": "warning",
            "message": "No runs found",
        }

    harness_path = latest_run / "harness_report.json"
    if not harness_path.exists():
        return {
            "name": "harness_passed",
            "passed": False,
            "severity": "blocking",
            "message": "Harness report missing",
        }

    try:
        report = json.loads(harness_path.read_text(encoding="utf-8"))
        if not report.get("passed", False):
            return {
                "name": "harness_passed",
                "passed": False,
                "severity": "blocking",
                "message": f"Harness validation failed in run {latest_run.name}",
            }
        return {
            "name": "harness_passed",
            "passed": True,
            "message": f"Harness passed in run {latest_run.name}",
        }
    except (json.JSONDecodeError, KeyError):
        return {
            "name": "harness_passed",
            "passed": False,
            "severity": "blocking",
            "message": "Invalid harness report",
        }


def _check_citation_resolution(project_root: Path, thresholds: ReleaseThresholds) -> dict:
    """Check citation resolution rate."""
    from sourcelab.harness.release_gate import _find_latest_run

    latest_run = _find_latest_run(project_root)
    if latest_run is None:
        return {
            "name": "citation_resolution",
            "passed": False,
            "severity": "warning",
            "message": "No runs found",
        }

    citation_path = latest_run / "citation_resolution.json"
    if not citation_path.exists():
        return {
            "name": "citation_resolution",
            "passed": False,
            "severity": "warning",
            "message": "Citation resolution file missing",
        }

    try:
        data = json.loads(citation_path.read_text(encoding="utf-8"))
        rate = data.get("resolution_rate", 0)
        if rate < thresholds.citation_resolution_required:
            return {
                "name": "citation_resolution",
                "passed": False,
                "severity": "blocking",
                "message": f"Citation resolution rate {rate:.2%} below required {thresholds.citation_resolution_required:.2%}",
            }
        return {
            "name": "citation_resolution",
            "passed": True,
            "message": f"Citation resolution rate: {rate:.2%}",
        }
    except (json.JSONDecodeError, KeyError):
        return {
            "name": "citation_resolution",
            "passed": False,
            "severity": "warning",
            "message": "Invalid citation resolution data",
        }


def _check_high_risk_claims(project_root: Path, thresholds: ReleaseThresholds) -> dict:
    """Check unsupported high-risk claims."""
    from sourcelab.harness.release_gate import _find_latest_run

    latest_run = _find_latest_run(project_root)
    if latest_run is None:
        return {
            "name": "high_risk_claims",
            "passed": False,
            "severity": "warning",
            "message": "No runs found",
        }

    citation_path = latest_run / "citation_resolution.json"
    if not citation_path.exists():
        return {
            "name": "high_risk_claims",
            "passed": False,
            "severity": "warning",
            "message": "Citation resolution file missing",
        }

    try:
        data = json.loads(citation_path.read_text(encoding="utf-8"))
        unsupported = data.get("unsupported_high_risk", 0)
        if unsupported > thresholds.unsupported_high_risk_allowed:
            return {
                "name": "high_risk_claims",
                "passed": False,
                "severity": "blocking",
                "message": f"{unsupported} unsupported high-risk claims (allowed: {thresholds.unsupported_high_risk_allowed})",
            }
        return {
            "name": "high_risk_claims",
            "passed": True,
            "message": f"No unsupported high-risk claims ({unsupported} found)",
        }
    except (json.JSONDecodeError, KeyError):
        return {
            "name": "high_risk_claims",
            "passed": False,
            "severity": "warning",
            "message": "Invalid citation resolution data",
        }


def _check_model_call_trace(project_root: Path) -> dict:
    """Check that model call trace exists."""
    from sourcelab.harness.release_gate import _find_latest_run

    latest_run = _find_latest_run(project_root)
    if latest_run is None:
        return {
            "name": "model_call_trace",
            "passed": False,
            "severity": "info",
            "message": "No runs found",
        }

    trace_path = latest_run / "model_call_trace.json"
    if not trace_path.exists():
        return {
            "name": "model_call_trace",
            "passed": True,
            "severity": "info",
            "message": "Model call trace not present (deterministic mode)",
        }

    return {
        "name": "model_call_trace",
        "passed": True,
        "message": "Model call trace exists",
    }


def _check_ui_commands(project_root: Path) -> dict:
    """Check that dashboard/export commands are available."""
    dashboard_py = project_root / "src" / "sourcelab" / "ui" / "dashboard.py"
    export_py = project_root / "src" / "sourcelab" / "ui" / "export.py"

    missing = []
    if not dashboard_py.exists():
        missing.append("dashboard.py")
    if not export_py.exists():
        missing.append("export.py")

    if missing:
        return {
            "name": "ui_commands",
            "passed": False,
            "severity": "blocking",
            "message": f"Missing UI modules: {missing}",
        }

    return {
        "name": "ui_commands",
        "passed": True,
        "message": "Dashboard and export modules available",
    }


def _check_api_routes(project_root: Path) -> dict:
    """Check that API routes are available."""
    try:
        from sourcelab.api.main import app
        if app is None:
            return {
                "name": "api_routes",
                "passed": False,
                "severity": "warning",
                "message": "FastAPI not installed",
            }

        route_count = len([r for r in app.routes if hasattr(r, "path")])
        return {
            "name": "api_routes",
            "passed": True,
            "message": f"API available with {route_count} routes",
        }
    except Exception as e:
        return {
            "name": "api_routes",
            "passed": False,
            "severity": "warning",
            "message": f"API check failed: {e}",
        }
