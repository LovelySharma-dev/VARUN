from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_inference_generates_tiles():
    response = client.post(
        "/v1/inference",
        json={
            "image_width": 2048,
            "image_height": 2048,
            "tile_size": 1024,
            "overlap": 128,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "SUCCESS"
    assert data["tile_count"] > 1
    assert data["tiles"][0]["x"] == 0
    assert data["tiles"][0]["y"] == 0
