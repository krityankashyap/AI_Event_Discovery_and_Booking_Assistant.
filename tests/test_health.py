from fastapi.testclient import TestClient

from backend.main import app


def test_health_ok():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "llm_provider" in body
