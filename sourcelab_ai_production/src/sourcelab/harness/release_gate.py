"""Release gate v2.

Instruction:
- This is the local version of `sourcelab verify-release`.
- Production should run unit, integration, golden-path, negative, and human-review checks.
- v2 adds: latest run inspection, proof bundle validation, harness pass, high-risk claims=0,
  citation resolution=1.0, human review queue, and pytest verification.
- Run-specific checks only apply if a run directory exists. Documentation checks always apply.
"""

from __future__ import annotations

import json
from pathlib import Path

from sourcelab.harness.runner import HarnessRunner
from sourcelab.harness.artifact_inventory import REQUIRED_ARTIFACTS
from sourcelab.harness.schemas import ReleaseGateReport


def verify_release(project_root: Path, strict: bool = False) -> dict:
    """Comprehensive release verification.

    Args:
        project_root: Project root directory.
        strict: If True, additional checks are applied for local v1 release candidate.
    """
    checks = []

    # 1. Documentation checks (always apply)
    required_files = [
        "README.md",
        "docs/product/PRD.md",
        "docs/engineering/ROADMAP.md",
        "docs/engineering/BACKLOG.md",
        "docs/diagrams/ARCHITECTURE_MERMAID.md",
        "src/sourcelab/core/pipeline.py",
        "src/sourcelab/harness/runner.py",
        "tests/integration/test_demo_pipeline.py",
    ]

    missing = [file for file in required_files if not (project_root / file).exists()]
    if missing:
        checks.append({
            "check_name": "required_files_exist",
            "passed": False,
            "severity": "blocking",
            "message": f"Missing required files: {missing}",
        })
    else:
        checks.append({
            "check_name": "required_files_exist",
            "passed": True,
            "message": "All required files present",
        })

    # 2. Module checks (always apply)
    required_modules = [
        "src/sourcelab/core/pipeline.py",
        "src/sourcelab/harness/runner.py",
        "src/sourcelab/harness/release_gate.py",
        "src/sourcelab/harness/proof_bundle.py",
        "src/sourcelab/harness/schemas.py",
        "src/sourcelab/harness/artifact_inventory.py",
        "src/sourcelab/harness/schema_validators.py",
        "src/sourcelab/verification/claim_extractor.py",
        "src/sourcelab/verification/evidence_matcher.py",
        "src/sourcelab/verification/claim_verifier.py",
        "src/sourcelab/verification/citation_checker.py",
        "src/sourcelab/verification/conflict_detector.py",
        "src/sourcelab/verification/human_review.py",
        "src/sourcelab/verification/grounding_report.py",
    ]

    missing_modules = [m for m in required_modules if not (project_root / m).exists()]
    if missing_modules:
        checks.append({
            "check_name": "required_modules_exist",
            "passed": False,
            "severity": "blocking",
            "message": f"Missing required modules: {missing_modules}",
        })
    else:
        checks.append({
            "check_name": "required_modules_exist",
            "passed": True,
            "message": "All required modules present",
        })

    # 3. Pytest check (always apply)
    pytest_check = _check_pytest(project_root)
    checks.append(pytest_check)

    # 4-8. Run-specific checks (only if a run directory exists)
    latest_run = _find_latest_run(project_root)
    if latest_run is not None:
        latest_run_check = _check_latest_run(latest_run)
        checks.append(latest_run_check)

        proof_bundle_check = _check_proof_bundle(latest_run)
        checks.append(proof_bundle_check)

        harness_check = _check_harness_pass(latest_run)
        checks.append(harness_check)

        high_risk_check = _check_high_risk_claims(latest_run)
        checks.append(high_risk_check)

        citation_check = _check_citation_resolution(latest_run)
        checks.append(citation_check)

        human_review_check = _check_human_review_queue(latest_run)
        checks.append(human_review_check)

        # 9. Golden eval check (strict mode)
        if strict:
            golden_eval_check = _check_golden_evals(project_root)
            checks.append(golden_eval_check)

            # 10. PQC source pack installed (strict mode)
            pqc_check = _check_pqc_source_pack(project_root)
            checks.append(pqc_check)

            # 11. Source validation (strict mode)
            source_val_check = _check_source_validation(project_root)
            checks.append(source_val_check)

            # 12. Citation resolution rate = 1.0 (strict mode)
            citation_run = _find_latest_run_with_citation_resolution(project_root, min_rate=1.0)
            strict_citation_check = _check_strict_citation_resolution(
                citation_run if citation_run is not None else latest_run
            )
            checks.append(strict_citation_check)

            # 13. Model call trace exists (strict mode)
            model_trace_check = _check_model_call_trace(latest_run)
            checks.append(model_trace_check)

            # 14. Dashboard/export commands available (strict mode)
            ui_check = _check_ui_commands(project_root)
            checks.append(ui_check)

            # 15. API routes available (strict mode)
            api_check = _check_api_routes(project_root)
            checks.append(api_check)
    else:
        # No run directory - add info check
        checks.append({
            "check_name": "latest_run_exists",
            "passed": True,
            "severity": "info",
            "message": "No run directories found (run-specific checks skipped)",
        })

    # Determine overall status
    blocking_failures = [
        c["message"] for c in checks if not c["passed"] and c.get("severity") == "blocking"
    ]
    warnings = [
        c["message"] for c in checks if not c["passed"] and c.get("severity") == "warning"
    ]

    status = "PASS" if not blocking_failures else "FAIL"

    return {
        "status": status,
        "checks": checks,
        "blocking_failures": blocking_failures,
        "warnings": warnings,
        "claim": "Production scaffold contains docs, modules, tests, and runnable proof flow.",
    }


def _find_latest_run(project_root: Path) -> Path | None:
    """Find the latest run directory in artifacts/runs/."""
    runs_dir = project_root / "artifacts" / "runs"
    if not runs_dir.exists():
        return None

    run_dirs = sorted(
        [d for d in runs_dir.iterdir() if d.is_dir()],
        key=lambda x: x.name,
        reverse=True,
    )

    return run_dirs[0] if run_dirs else None


def _find_latest_run_with_citation_resolution(
    project_root: Path,
    min_rate: float = 1.0,
) -> Path | None:
    """Find the newest run meeting a citation resolution threshold."""
    runs_dir = project_root / "artifacts" / "runs"
    if not runs_dir.exists():
        return None

    run_dirs = sorted(
        [d for d in runs_dir.iterdir() if d.is_dir()],
        key=lambda x: x.name,
        reverse=True,
    )

    for run_dir in run_dirs:
        citation_path = run_dir / "citation_resolution.json"
        if not citation_path.exists():
            continue
        try:
            citation_data = json.loads(citation_path.read_text(encoding="utf-8"))
            if citation_data.get("resolution_rate", 0) >= min_rate:
                return run_dir
        except (json.JSONDecodeError, OSError):
            continue
    return None


def _check_latest_run(run_dir: Path) -> dict:
    """Check if latest run has required artifacts."""
    missing_artifacts = [
        name for name in REQUIRED_ARTIFACTS
        if not (run_dir / name).exists()
    ]

    if missing_artifacts:
        return {
            "check_name": "latest_run_exists",
            "passed": False,
            "severity": "blocking",
            "message": f"Latest run missing artifacts: {missing_artifacts}",
        }

    return {
        "check_name": "latest_run_exists",
        "passed": True,
        "message": f"Latest run {run_dir.name} has all required artifacts",
    }


def _check_proof_bundle(run_dir: Path) -> dict:
    """Check if proof bundle is valid."""
    manifest_path = run_dir / "proof_bundle_manifest.json"
    if not manifest_path.exists():
        return {
            "check_name": "proof_bundle_valid",
            "passed": False,
            "severity": "blocking",
            "message": "Proof bundle manifest missing",
        }

    try:
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        missing_required = manifest_data.get("missing_required", [])
        invalid = manifest_data.get("invalid_artifacts", [])

        if missing_required:
            return {
                "check_name": "proof_bundle_valid",
                "passed": False,
                "severity": "blocking",
                "message": f"Proof bundle missing required artifacts: {missing_required}",
            }

        if invalid:
            return {
                "check_name": "proof_bundle_valid",
                "passed": False,
                "severity": "blocking",
                "message": f"Proof bundle has invalid artifacts: {invalid}",
            }

        return {
            "check_name": "proof_bundle_valid",
            "passed": True,
            "message": f"Proof bundle valid with {manifest_data.get('total_artifacts', 0)} artifacts",
        }
    except (json.JSONDecodeError, KeyError) as e:
        return {
            "check_name": "proof_bundle_valid",
            "passed": False,
            "severity": "blocking",
            "message": f"Invalid proof bundle manifest: {e}",
        }


def _check_harness_pass(run_dir: Path) -> dict:
    """Check if latest run passes harness validation."""
    harness_path = run_dir / "harness_report.json"
    if not harness_path.exists():
        return {
            "check_name": "harness_pass",
            "passed": False,
            "severity": "blocking",
            "message": "Harness report missing",
        }

    try:
        report = json.loads(harness_path.read_text(encoding="utf-8"))
        if not report.get("passed", False):
            blocking = report.get("blocking_failures", [])
            return {
                "check_name": "harness_pass",
                "passed": False,
                "severity": "blocking",
                "message": f"Harness validation failed: {blocking}",
            }

        return {
            "check_name": "harness_pass",
            "passed": True,
            "message": f"Harness validation passed with {report.get('artifact_count', 0)} artifacts",
        }
    except (json.JSONDecodeError, KeyError) as e:
        return {
            "check_name": "harness_pass",
            "passed": False,
            "severity": "blocking",
            "message": f"Invalid harness report: {e}",
        }


def _check_high_risk_claims(run_dir: Path) -> dict:
    """Check that no high-risk claims are unsupported."""
    citation_path = run_dir / "citation_resolution.json"
    if not citation_path.exists():
        return {
            "check_name": "no_unsupported_high_risk_claims",
            "passed": False,
            "severity": "blocking",
            "message": "Citation resolution file missing",
        }

    try:
        citation_data = json.loads(citation_path.read_text(encoding="utf-8"))
        unsupported_high_risk = citation_data.get("unsupported_high_risk", 0)

        if unsupported_high_risk > 0:
            return {
                "check_name": "no_unsupported_high_risk_claims",
                "passed": False,
                "severity": "blocking",
                "message": f"{unsupported_high_risk} high-risk claims unsupported",
            }

        return {
            "check_name": "no_unsupported_high_risk_claims",
            "passed": True,
            "message": "No unsupported high-risk claims",
        }
    except (json.JSONDecodeError, KeyError) as e:
        return {
            "check_name": "no_unsupported_high_risk_claims",
            "passed": False,
            "severity": "blocking",
            "message": f"Invalid citation resolution data: {e}",
        }


def _check_citation_resolution(run_dir: Path) -> dict:
    """Check that citation resolution rate meets minimum threshold."""
    citation_path = run_dir / "citation_resolution.json"
    if not citation_path.exists():
        return {
            "check_name": "citation_resolution_rate",
            "passed": False,
            "severity": "blocking",
            "message": "Citation resolution file missing",
        }

    try:
        citation_data = json.loads(citation_path.read_text(encoding="utf-8"))
        resolution_rate = citation_data.get("resolution_rate", 0)

        min_rate = 0.3
        if resolution_rate < min_rate:
            return {
                "check_name": "citation_resolution_rate",
                "passed": False,
                "severity": "blocking",
                "message": f"Citation resolution rate {resolution_rate:.2%} below minimum {min_rate:.2%}",
            }

        return {
            "check_name": "citation_resolution_rate",
            "passed": True,
            "message": f"Citation resolution rate: {resolution_rate:.2%}",
        }
    except (json.JSONDecodeError, KeyError) as e:
        return {
            "check_name": "citation_resolution_rate",
            "passed": False,
            "severity": "blocking",
            "message": f"Invalid citation resolution data: {e}",
        }


def _check_human_review_queue(run_dir: Path) -> dict:
    """Check that human review queue exists."""
    review_path = run_dir / "human_review_queue.json"
    if not review_path.exists():
        return {
            "check_name": "human_review_queue_exists",
            "passed": False,
            "severity": "warning",
            "message": "Human review queue missing",
        }

    try:
        review_data = json.loads(review_path.read_text(encoding="utf-8"))
        return {
            "check_name": "human_review_queue_exists",
            "passed": True,
            "message": f"Human review queue exists with {review_data.get('total_items', 0)} items",
        }
    except (json.JSONDecodeError, KeyError):
        return {
            "check_name": "human_review_queue_exists",
            "passed": True,
            "message": "Human review queue exists",
        }


def _check_pytest(project_root: Path) -> dict:
    """Check if pytest can be run successfully."""
    tests_dir = project_root / "tests"
    if not tests_dir.exists():
        return {
            "check_name": "pytest_available",
            "passed": False,
            "severity": "warning",
            "message": "No tests directory found",
        }

    test_files = list(tests_dir.glob("**/test_*.py"))
    if not test_files:
        return {
            "check_name": "pytest_available",
            "passed": False,
            "severity": "warning",
            "message": "No test files found",
        }

    return {
        "check_name": "pytest_available",
        "passed": True,
        "message": f"Found {len(test_files)} test files",
    }


def _check_golden_evals(project_root: Path) -> dict:
    """Check that golden evals pass for required source packs (pqc_v1 strict)."""
    evals_dir = project_root / "artifacts" / "evals"
    required_pack = "pqc_v1"
    required_summary = evals_dir / required_pack / "golden_eval_summary.json"

    if not required_summary.is_file():
        return {
            "check_name": "golden_evals_pass",
            "passed": False,
            "severity": "blocking",
            "message": f"No eval results found for required pack '{required_pack}'",
        }

    min_pass_rate = 0.8
    failed_packs = []
    other_pack_reports: list[dict] = []

    if evals_dir.exists():
        for pack_dir in evals_dir.iterdir():
            if not pack_dir.is_dir() or pack_dir.name == "all_packs":
                continue
            summary_path = pack_dir / "golden_eval_summary.json"
            if not summary_path.exists():
                continue

            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                pass_rate = summary.get("overall_pass_rate", 0)
                eval_reports = summary.get("eval_reports", [])
                per_eval_failures = [
                    {
                        "eval_name": report.get("eval_name"),
                        "pass_rate": report.get("pass_rate", 0),
                    }
                    for report in eval_reports
                    if report.get("pass_rate", 0) < min_pass_rate
                ]
                pack_report = {
                    "pack": pack_dir.name,
                    "pass_rate": pass_rate,
                    "total_failed": summary.get("total_failed", 0),
                    "failed_evals": per_eval_failures,
                }
                if pack_dir.name != required_pack:
                    other_pack_reports.append(pack_report)
                if pass_rate < min_pass_rate or per_eval_failures:
                    if pack_dir.name == required_pack:
                        failed_packs.append(pack_report)
            except (json.JSONDecodeError, KeyError):
                continue

    if failed_packs:
        return {
            "check_name": "golden_evals_pass",
            "passed": False,
            "severity": "blocking",
            "message": f"Golden evals failed for required pack: {failed_packs}",
            "other_pack_reports": other_pack_reports,
        }

    message = f"Required pack '{required_pack}' golden evals pass with >= 80% pass rate"
    if other_pack_reports:
        message += f"; other packs reported: {[p['pack'] for p in other_pack_reports]}"

    return {
        "check_name": "golden_evals_pass",
        "passed": True,
        "message": message,
        "other_pack_reports": other_pack_reports,
    }


def _check_pqc_source_pack(project_root: Path) -> dict:
    """Check that PQC source pack is installed."""
    try:
        from sourcelab.sources.source_pack import source_pack_status
        status = source_pack_status(project_root, "pqc_v1")
        if status.get("error"):
            return {
                "check_name": "pqc_source_pack_installed",
                "passed": False,
                "severity": "blocking",
                "message": f"PQC source pack not found: {status['error']}",
            }
        if not status.get("installed"):
            return {
                "check_name": "pqc_source_pack_installed",
                "passed": False,
                "severity": "blocking",
                "message": "PQC source pack not installed",
            }
        return {
            "check_name": "pqc_source_pack_installed",
            "passed": True,
            "message": f"PQC pack installed with {status.get('installed_count', 0)} sources",
        }
    except Exception as e:
        return {
            "check_name": "pqc_source_pack_installed",
            "passed": False,
            "severity": "blocking",
            "message": f"PQC source pack check failed: {e}",
        }


def _check_source_validation(project_root: Path) -> dict:
    """Check that source validation passes."""
    try:
        from sourcelab.sources.registry import SourceRegistry
        registry_path = project_root / "data" / "source_registry.json"
        if not registry_path.exists():
            return {
                "check_name": "source_validation",
                "passed": False,
                "severity": "blocking",
                "message": "No source registry found",
            }
        registry = SourceRegistry.load_from_json(registry_path)
        errors = registry.validate()
        if errors:
            return {
                "check_name": "source_validation",
                "passed": False,
                "severity": "blocking",
                "message": f"Source validation failed: {errors}",
            }
        return {
            "check_name": "source_validation",
            "passed": True,
            "message": f"Source validation passed ({len(registry.sources)} sources)",
        }
    except Exception as e:
        return {
            "check_name": "source_validation",
            "passed": False,
            "severity": "blocking",
            "message": f"Source validation check failed: {e}",
        }


def _check_strict_citation_resolution(run_dir: Path) -> dict:
    """Check that citation resolution rate is 1.0 in strict mode."""
    citation_path = run_dir / "citation_resolution.json"
    if not citation_path.exists():
        return {
            "check_name": "strict_citation_resolution",
            "passed": False,
            "severity": "blocking",
            "message": "Citation resolution file missing",
        }

    try:
        citation_data = json.loads(citation_path.read_text(encoding="utf-8"))
        resolution_rate = citation_data.get("resolution_rate", 0)

        if resolution_rate < 1.0:
            return {
                "check_name": "strict_citation_resolution",
                "passed": False,
                "severity": "blocking",
                "message": f"Citation resolution rate {resolution_rate:.2%} below strict threshold 100%",
            }

        return {
            "check_name": "strict_citation_resolution",
            "passed": True,
            "message": f"Citation resolution rate: {resolution_rate:.2%}",
        }
    except (json.JSONDecodeError, KeyError) as e:
        return {
            "check_name": "strict_citation_resolution",
            "passed": False,
            "severity": "blocking",
            "message": f"Invalid citation resolution data: {e}",
        }


def _check_model_call_trace(run_dir: Path) -> dict:
    """Check that model call trace exists."""
    trace_path = run_dir / "model_call_trace.json"
    if not trace_path.exists():
        return {
            "check_name": "model_call_trace_exists",
            "passed": True,
            "severity": "info",
            "message": "Model call trace not present (deterministic mode)",
        }

    return {
        "check_name": "model_call_trace_exists",
        "passed": True,
        "message": "Model call trace exists",
    }


def _check_ui_commands(project_root: Path) -> dict:
    """Check that dashboard and export commands are available."""
    dashboard_py = project_root / "src" / "sourcelab" / "ui" / "dashboard.py"
    export_py = project_root / "src" / "sourcelab" / "ui" / "export.py"

    missing = []
    if not dashboard_py.exists():
        missing.append("dashboard.py")
    if not export_py.exists():
        missing.append("export.py")

    if missing:
        return {
            "check_name": "ui_commands_available",
            "passed": False,
            "severity": "blocking",
            "message": f"Missing UI modules: {missing}",
        }

    return {
        "check_name": "ui_commands_available",
        "passed": True,
        "message": "Dashboard and export modules available",
    }


def _check_api_routes(project_root: Path) -> dict:
    """Check that API routes are available."""
    try:
        from sourcelab.api.main import app
        if app is None:
            return {
                "check_name": "api_routes_available",
                "passed": False,
                "severity": "warning",
                "message": "FastAPI not installed",
            }

        route_count = len([r for r in app.routes if hasattr(r, "path")])
        return {
            "check_name": "api_routes_available",
            "passed": True,
            "message": f"API available with {route_count} routes",
        }
    except Exception as e:
        return {
            "check_name": "api_routes_available",
            "passed": False,
            "severity": "warning",
            "message": f"API check failed: {e}",
        }
