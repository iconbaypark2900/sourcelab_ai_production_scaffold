"""Integration tests for batch runs and comparison API."""

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
    reason="FastAPI not installed. Install with: pip install -e '.[api]'",
)


@pytest.fixture
def client():
    return TestClient(app)


BATCH_PAYLOAD = {
    "batch_name": "API test batch",
    "items": [
        {
            "topic": "batch api test topic alpha",
            "source_pack": "pqc_v1",
            "difficulty": 2,
            "lesson_format": "architecture_review",
            "retrieval_mode": "hybrid",
            "model_mode": "deterministic",
        },
        {
            "topic": "batch api test topic beta",
            "source_pack": "pqc_v1",
            "difficulty": 2,
            "lesson_format": "concept_lesson",
            "retrieval_mode": "hybrid",
            "model_mode": "deterministic",
        },
    ],
}


def test_create_batch(client):
    response = client.post("/lessons/batch", json=BATCH_PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert data["batch_id"]
    assert data["batch_name"] == BATCH_PAYLOAD["batch_name"]
    assert len(data["runs"]) == 2
    assert data["status"] in {"complete", "partial"}


def test_create_batch_validation_empty_items(client):
    response = client.post(
        "/lessons/batch",
        json={"batch_name": "empty", "items": []},
    )
    assert response.status_code == 422


def test_list_batches(client):
    response = client.get("/batches/")
    assert response.status_code == 200
    data = response.json()
    assert "batches" in data
    assert "total" in data


def test_batch_detail_and_compare(client):
    create = client.post("/lessons/batch", json=BATCH_PAYLOAD).json()
    batch_id = create["batch_id"]

    detail = client.get(f"/batches/{batch_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["batch_id"] == batch_id
    assert len(body["run_ids"]) >= 2

    compare = client.get(f"/batches/{batch_id}/compare")
    assert compare.status_code == 200
    cmp_body = compare.json()
    assert len(cmp_body["run_ids"]) >= 2
    assert "recommendation" in cmp_body

    report = client.get(f"/batches/{batch_id}/report")
    assert report.status_code == 200
    assert report.json()["comparison_report_md"]


def test_batch_not_found(client):
    response = client.get("/batches/does-not-exist-batch")
    assert response.status_code == 404


def test_runs_compare(client):
    latest = client.get("/runs/latest").json()
    runs = client.get("/runs/").json()["runs"]
    if len(runs) < 2:
        pytest.skip("Need at least two runs")
    ids = [runs[-2]["run_id"], runs[-1]["run_id"]]
    response = client.get(f"/runs/compare?run_ids={','.join(ids)}")
    assert response.status_code == 200
    assert response.json()["run_ids"] == ids


def test_runs_compare_requires_two(client):
    latest = client.get("/runs/latest").json()
    run_id = latest.get("run_id")
    if not run_id:
        pytest.skip("No runs")
    response = client.get(f"/runs/compare?run_ids={run_id}")
    assert response.status_code == 422


def test_runs_compare_missing_run(client):
    response = client.get("/runs/compare?run_ids=missing_a,missing_b")
    assert response.status_code == 404


def test_batch_answers_compare(client):
    create = client.post("/lessons/batch", json=BATCH_PAYLOAD).json()
    batch_id = create["batch_id"]

    response = client.get(f"/batches/{batch_id}/answers/compare")
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["total_runs"] >= 2
    assert "per_run" in body
    assert "recommendation" in body


def test_batch_answers_compare_not_found(client):
    response = client.get("/batches/does-not-exist-batch/answers/compare")
    assert response.status_code == 404


def test_runs_answers_compare(client):
    runs = client.get("/runs/").json()["runs"]
    if len(runs) < 2:
        pytest.skip("Need at least two runs")
    ids = [runs[-2]["run_id"], runs[-1]["run_id"]]
    response = client.get(f"/runs/answers/compare?run_ids={','.join(ids)}")
    assert response.status_code == 200
    assert len(response.json()["per_run"]) == 2


def test_runs_answers_compare_requires_two(client):
    latest = client.get("/runs/latest").json()
    run_id = latest.get("run_id")
    if not run_id:
        pytest.skip("No runs")
    response = client.get(f"/runs/answers/compare?run_ids={run_id}")
    assert response.status_code == 422
