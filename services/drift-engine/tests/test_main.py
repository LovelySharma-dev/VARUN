from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_version():
    response = client.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "phase2-drift"
    assert data["contractVersion"] == "phase2-to-phase3-v1"


def test_drift_run():
    response = client.post(
        "/internal/v1/drift-runs",
        json={
            "case_id": "CASE_TEST_001",
            "phase2_run_id": "DRIFT_RUN_TEST",
            "phase1_handoff_ref": "P1_RUN_001",
            "mode": "HINDCAST_AND_FORECAST",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("COMPLETED", "COMPLETED_WITH_WARNINGS")
    assert data["contract_version"] == "phase2-to-phase3-v1"
    assert len(data["trajectories"]) > 0
