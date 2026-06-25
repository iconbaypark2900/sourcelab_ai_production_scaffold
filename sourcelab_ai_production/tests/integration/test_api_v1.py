"""Integration tests for API v1.

These tests validate the REST API endpoints using FastAPI's TestClient.
Run with: pytest tests/integration/test_api_v1.py -v
"""

from __future__ import annotations

import pytest

try:
    from fastapi.testclient import TestClient
    from sourcelab.api.main import app
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


pytestmark = pytest.mark.skipif(
    not HAS_FASTAPI,
    reason="FastAPI not installed. Install with: pip install -e '.[api]'"
)


@pytest.fixture
def client():
    """Create a TestClient for the FastAPI app."""
    return TestClient(app)


def test_health_endpoint(client):
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_readiness_endpoint(client):
    """Test readiness endpoint."""
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "components" in data


def test_version_endpoint(client):
    """Test version endpoint."""
    from sourcelab.version import RELEASE_LABEL, __version__

    response = client.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == __version__
    assert data["release_label"] == RELEASE_LABEL
    assert data["api_version"] == "v1"
    assert "python_version" in data
    assert "project_root" in data
    assert "artifacts_directory" in data


def test_list_sources(client):
    """Test list sources endpoint."""
    response = client.get("/sources/")
    assert response.status_code == 200
    data = response.json()
    assert "sources" in data
    assert "total" in data


def test_validate_sources(client):
    """Test validate sources endpoint."""
    response = client.get("/sources/validate")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ["PASS", "FAIL"]


def test_search_sources(client):
    """Test search sources endpoint."""
    response = client.post(
        "/retrieval/search",
        json={"query": "test query", "top_k": 5, "mode": "hybrid"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "query" in data
    assert "results" in data
    assert "total" in data


def test_build_index(client):
    """Test build index endpoint."""
    response = client.post("/retrieval/index")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"


def test_list_runs(client):
    """Test list runs endpoint."""
    response = client.get("/runs/")
    assert response.status_code == 200
    data = response.json()
    assert "runs" in data
    assert "total" in data


def test_get_latest_run(client):
    """Test get latest run endpoint."""
    response = client.get("/runs/latest")
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data


def test_create_lesson(client):
    """Test create lesson endpoint."""
    response = client.post(
        "/lessons/",
        json={
            "topic": "test topic",
            "source_pack": "pqc_v1",
            "level": "intermediate",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "lesson_id" in data
    assert "run_id" in data
    assert data["run_id"] == data["lesson_id"]
    assert data["status"] == "created"
    assert data["source_pack"] == "pqc_v1"
    assert "harness_status" in data
    assert "proof_status" in data
    assert data["artifact_count"] > 0
    assert data["run_url"] == f"/runs/{data['run_id']}"


def test_create_lesson_requires_topic(client):
    """Empty topic returns structured validation error."""
    response = client.post(
        "/lessons/",
        json={"topic": "   ", "source_pack": "pqc_v1"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body.get("code") == "VALIDATION_ERROR" or "detail" in body


def test_create_lesson_requires_source_pack(client):
    """Missing source pack returns structured validation error."""
    response = client.post(
        "/lessons/",
        json={"topic": "post-quantum migration planning"},
    )
    assert response.status_code == 422


def test_create_lesson_invalid_source_pack(client):
    """Invalid source pack returns structured validation error."""
    response = client.post(
        "/lessons/",
        json={
            "topic": "post-quantum migration planning",
            "source_pack": "nonexistent_pack_xyz",
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body.get("code") == "VALIDATION_ERROR"
    assert "Invalid source pack" in body.get("error", "")


def test_create_lesson_respects_source_pack(client):
    """Created run is fetchable and includes generated lesson artifact."""
    topic = "api integration source pack scoped lesson"
    response = client.post(
        "/lessons/",
        json={
            "topic": topic,
            "source_pack": "pqc_v1",
            "lesson_format": "architecture_review",
            "difficulty": 2,
        },
    )
    assert response.status_code == 200
    data = response.json()
    run_id = data["run_id"]

    runs = client.get("/runs/").json()
    run_ids = [run["run_id"] for run in runs["runs"]]
    assert run_id in run_ids

    run = client.get(f"/runs/{run_id}").json()
    assert run["run_id"] == run_id
    assert topic in run["topic"]

    artifacts = client.get(f"/runs/{run_id}/artifacts").json()
    artifact_names = {row["name"] for row in artifacts["artifacts"]}
    assert "generated_lesson.md" in artifact_names

    lesson = client.get(f"/lessons/{run_id}").json()
    assert lesson["run_id"] == run_id
    assert lesson["lesson_markdown"]


def test_submit_answer(client):
    """Test submit answer endpoint (legacy shape: topic + answer_text)."""
    response = client.post(
        "/learning/answers",
        json={"topic": "test topic", "answer_text": "Test answer"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert "score" in data
    assert "feedback" in data


def test_submit_answer_resolves_latest_and_exposes_metrics(client):
    """`latest` resolves to a concrete run id and the response carries the
    transparent v1.0.2 learning metrics the UI renders."""
    latest = client.get("/runs/latest").json()
    run_id = latest.get("run_id")
    if not run_id:
        pytest.skip("No runs available to exercise answer submission")

    response = client.post(
        "/learning/answers",
        json={
            "run_id": "latest",
            "answer_text": (
                "A safe post-quantum migration starts with a cryptographic "
                "inventory, separates harvest-now-decrypt-later risk from "
                "operational risk, and avoids claiming RSA-2048 is broken today."
            ),
        },
    )
    assert response.status_code == 200
    data = response.json()
    # "latest" was resolved to a concrete run id (not echoed back verbatim).
    assert data["run_id"] == run_id
    assert data["run_id"] not in ("", "latest")
    # Transparent metrics are present (keys exist even when a value is null).
    for key in (
        "overall_score",
        "rubric_alignment_score",
        "uncapped_score",
        "needs_review",
        "cap_reason",
        "human_review_reason",
        "next_task_decision",
    ):
        assert key in data
    assert isinstance(data["next_task_decision"], dict)


def test_submit_answer_missing_run_returns_structured_error(client):
    """An unknown run id returns a structured 404 rather than crashing."""
    response = client.post(
        "/learning/answers",
        json={"run_id": "does-not-exist-run", "answer_text": "anything"},
    )
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["code"] == "NOT_FOUND"


def test_submit_answer_empty_answer_is_validation_error(client):
    """A blank answer is rejected cleanly (no crash, no degenerate artifact).

    Validation happens before run resolution, so this holds with or without
    any runs present.
    """
    response = client.post(
        "/learning/answers",
        json={"run_id": "latest", "answer_text": "   "},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["code"] == "VALIDATION_ERROR"


def test_submit_answer_returns_attempt_id(client):
    """POST /learning/answers returns attempt_id after scoring."""
    latest = client.get("/runs/latest").json()
    run_id = latest.get("run_id")
    if not run_id:
        pytest.skip("No runs available")

    response = client.post(
        "/learning/answers",
        json={
            "run_id": "latest",
            "answer_text": "Begin with a cryptographic inventory according to NIST guidance.",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("attempt_id")
    assert data.get("attempt_manifest_path")


def test_get_answer_history_empty_list(client):
    """History endpoint returns empty list when no attempts exist."""
    latest = client.get("/runs/latest").json()
    run_id = latest.get("run_id")
    if not run_id:
        pytest.skip("No runs available")

    response = client.get(f"/learning/answers/{run_id}")
    assert response.status_code == 200
    data = response.json()
    assert "attempts" in data
    assert isinstance(data["attempts"], list)


def test_get_answer_history_latest_resolves(client):
    """run_id=latest resolves for answer history."""
    response = client.get("/learning/answers/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] not in ("", "latest")


def test_answer_history_detail_and_diff(client):
    """History, detail, and diff endpoints work after two submissions."""
    latest = client.get("/runs/latest").json()
    run_id = latest.get("run_id")
    if not run_id:
        pytest.skip("No runs available")

    for text in (
        "Weak answer without inventory.",
        "Strong answer with cryptographic inventory and NIST guidance.",
    ):
        resp = client.post(
            "/learning/answers",
            json={"run_id": run_id, "answer_text": text},
        )
        assert resp.status_code == 200

    history = client.get(f"/learning/answers/{run_id}").json()
    assert history["total"] >= 2
    first = history["attempts"][0]["attempt_id"]
    second = history["attempts"][-1]["attempt_id"]

    detail = client.get(f"/learning/answers/{run_id}/{second}")
    assert detail.status_code == 200
    detail_json = detail.json()
    assert detail_json["attempt_id"] == second
    assert detail_json.get("manifest")
    assert detail_json.get("answer_review")
    assert detail_json.get("learning_report")
    assert "artifact_names" in detail_json
    assert "attempt_manifest.json" in detail_json["artifact_names"]

    diff = client.get(
        f"/learning/answers/{run_id}/diff",
        params={"from_attempt": first, "to_attempt": second},
    )
    assert diff.status_code == 200
    assert "score_delta" in diff.json()


def test_answer_history_missing_run_404(client):
    """Unknown run returns 404."""
    response = client.get("/learning/answers/does-not-exist-run")
    assert response.status_code == 404


def test_answer_attempt_missing_404(client):
    """Unknown attempt returns 404."""
    latest = client.get("/runs/latest").json()
    run_id = latest.get("run_id")
    if not run_id:
        pytest.skip("No runs available")

    response = client.get(f"/learning/answers/{run_id}/attempt_missing")
    assert response.status_code == 404


def test_get_skill_profile(client):
    """Test get skill profile endpoint."""
    response = client.get("/learning/profile")
    assert response.status_code == 200
    data = response.json()
    assert "profile_id" in data


def test_get_learning_report(client):
    """Test get learning report endpoint."""
    response = client.get("/learning/reports/latest")
    # When no runs exist, this returns 404
    assert response.status_code in [200, 404]


def test_get_next_task(client):
    """Test get next task endpoint."""
    response = client.get("/learning/next-task/latest")
    # When no runs exist, this returns 404
    assert response.status_code in [200, 404]


def test_get_proof_bundle(client):
    """Test get proof bundle endpoint."""
    response = client.get("/runs/latest/proof")
    # When no runs exist, this returns 404
    assert response.status_code in [200, 404]


def test_get_harness_report(client):
    """Test get harness report endpoint."""
    response = client.get("/runs/latest/harness")
    # When no runs exist, this returns 404
    assert response.status_code in [200, 404]


def test_get_run_artifact_content(client):
    """Test fetching a single run artifact's parsed content."""
    latest = client.get("/runs/latest").json()
    run_id = latest.get("run_id")
    if not run_id:
        pytest.skip("No runs available to exercise artifact content endpoint")

    response = client.get(f"/runs/{run_id}/artifacts/claim_map.json")
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == run_id
    assert data["artifact_name"] == "claim_map.json"
    assert data["exists"] is True
    assert data["artifact_type"] == "json"
    assert isinstance(data["content_json"], list)


def test_get_run_artifact_content_missing_artifact(client):
    """Missing artifacts report exists=False rather than 404."""
    latest = client.get("/runs/latest").json()
    run_id = latest.get("run_id")
    if not run_id:
        pytest.skip("No runs available to exercise artifact content endpoint")

    response = client.get(f"/runs/{run_id}/artifacts/does_not_exist.json")
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is False
    assert data["content_json"] is None


def test_get_run_artifact_content_unknown_run(client):
    """Unknown run id returns a structured 404."""
    response = client.get("/runs/does-not-exist/artifacts/claim_map.json")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["code"] == "NOT_FOUND"


def test_error_handling_not_found(client):
    """Test error handling for not found resources."""
    response = client.get("/sources/nonexistent_source")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "code" in data


def test_error_handling_invalid_request(client):
    """Test error handling for invalid requests."""
    response = client.post(
        "/retrieval/search",
        json={"query": "test", "top_k": 0},  # Invalid top_k
    )
    assert response.status_code == 422


def test_cors_headers(client):
    """Test CORS headers are present."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    # CORS headers should be present
    assert "access-control-allow-origin" in response.headers
