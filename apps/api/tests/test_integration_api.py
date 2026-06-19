from __future__ import annotations

from fastapi.testclient import TestClient

from main import app


def test_root_endpoint_returns_service_status() -> None:
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "zooplus-assistant-api",
    }


def test_health_endpoint_returns_healthy_status() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_chat_endpoint_is_not_exposed_in_bootstrap_runtime() -> None:
    client = TestClient(app)

    response = client.post("/chat", json={"site_id": 1, "query": "food"})

    assert response.status_code == 404
