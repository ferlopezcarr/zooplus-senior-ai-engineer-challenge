from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import build_app


@pytest.fixture(autouse=True)
def _clear_llm_env(monkeypatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)


def test_root_endpoint_returns_service_status() -> None:
    client = TestClient(build_app())
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "zooplus-assistant-api",
    }


def test_health_endpoint_returns_healthy_status() -> None:
    client = TestClient(build_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_endpoint_stays_healthy_when_dataset_is_missing(
    tmp_path: Path, monkeypatch
) -> None:
    missing_dataset_path = tmp_path / "missing.json"
    monkeypatch.setenv("CATALOG_DATASET_PATH", str(missing_dataset_path))

    client = TestClient(build_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_endpoint_stays_healthy_when_dataset_json_is_invalid(
    tmp_path: Path, monkeypatch
) -> None:
    dataset_path = tmp_path / "invalid.json"
    dataset_path.write_text("{not-valid-json")
    monkeypatch.setenv("CATALOG_DATASET_PATH", str(dataset_path))

    client = TestClient(build_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_endpoint_stays_healthy_when_dataset_rows_are_malformed(
    tmp_path: Path, monkeypatch
) -> None:
    dataset_path = tmp_path / "invalid-rows.json"
    dataset_path.write_text(
        '[{"product_id":"broken-product","product_name":"Broken Food","site_id":1}]'
    )
    monkeypatch.setenv("CATALOG_DATASET_PATH", str(dataset_path))

    client = TestClient(build_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
