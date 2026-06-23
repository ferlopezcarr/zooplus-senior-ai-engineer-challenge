import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main


TEST_DATABASE_URL = (
    "postgresql+psycopg://test_user:test_password@example.test:5432/catalog"
)


@pytest.fixture(autouse=True)
def _clear_llm_env(monkeypatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("EMBEDDING_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("PRODUCT_CATALOG_DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setattr(main, "DOTENV_PATH", Path(".missing-test.env"))
    monkeypatch.setattr(main, "_missing_llm_config_warnings_emitted", set())
    monkeypatch.setattr(main, "_embedding_retrieval_warnings_emitted", set())

    class StubDatabaseProductRetriever:
        def __init__(
            self,
            database_url: str,
            embedding_client_factory=None,
        ) -> None:
            self.database_url = database_url
            self.embedding_client_factory = embedding_client_factory

        def readiness_error(self) -> str | None:
            return None

        def retrieve(self, chat, limit: int = 3):
            return []

    monkeypatch.setattr(main, "DatabaseProductRetriever", StubDatabaseProductRetriever)


def test_root_endpoint_returns_service_status() -> None:
    client = TestClient(main.build_app())
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "zooplus-assistant-api",
    }


def test_health_endpoint_returns_healthy_status() -> None:
    client = TestClient(main.build_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_public_health_endpoint_is_not_registered() -> None:
    client = TestClient(main.build_app())

    assert client.get("/public/health").status_code == 404


@pytest.mark.parametrize("database_url", [None, "", "   "])
def test_build_app_fails_fast_when_database_url_is_missing_or_blank(
    database_url: str | None, monkeypatch
) -> None:
    if database_url is None:
        monkeypatch.delenv("PRODUCT_CATALOG_DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("PRODUCT_CATALOG_DATABASE_URL", database_url)

    with pytest.raises(ValueError, match="PRODUCT_CATALOG_DATABASE_URL"):
        main.build_app()


def test_build_app_fails_fast_for_invalid_llm_base_url_without_api_key(
    monkeypatch,
) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://unsafe.test/v1")

    with pytest.raises(ValueError, match="LLM_BASE_URL"):
        main.build_app()


@pytest.mark.parametrize("api_key", [None, "", "   "])
def test_build_app_uses_deterministic_when_llm_key_is_missing_or_blank(
    api_key: str | None, monkeypatch, caplog
) -> None:
    if api_key is None:
        monkeypatch.delenv("LLM_API_KEY", raising=False)
    else:
        monkeypatch.setenv("LLM_API_KEY", api_key)
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    caplog.set_level(logging.WARNING)

    client = TestClient(main.build_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    assert [record.getMessage() for record in caplog.records] == [
        f"LLM_API_KEY is not set after loading {main.DOTENV_PATH}; using deterministic answer generation."
    ]


def test_build_app_uses_deterministic_when_llm_base_url_is_missing(
    monkeypatch, caplog
) -> None:
    monkeypatch.setenv("LLM_API_KEY", "replace-me")
    caplog.set_level(logging.WARNING)

    client = TestClient(main.build_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    assert [record.getMessage() for record in caplog.records] == [
        f"LLM_BASE_URL is not set after loading {main.DOTENV_PATH}; using deterministic answer generation."
    ]


def test_build_app_fails_fast_for_invalid_llm_base_url_with_api_key(
    monkeypatch,
) -> None:
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_BASE_URL", "http://unsafe.test/v1")

    with pytest.raises(ValueError, match="LLM_BASE_URL"):
        main.build_app()


def test_build_app_loads_llm_config_from_dotenv(tmp_path: Path, monkeypatch) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        f"PRODUCT_CATALOG_DATABASE_URL={TEST_DATABASE_URL}\n"
        "LLM_API_KEY=secret\n"
        "LLM_MODEL=test-model\n"
        "LLM_BASE_URL=https://example.test/v1\n"
        "LLM_TIMEOUT_SECONDS=2\n"
    )

    class StubAnswerClient:
        def __init__(
            self,
            api_key: str,
            model: str,
            base_url: str,
            timeout_seconds: float,
        ) -> None:
            assert api_key == "secret"
            assert model == "test-model"
            assert base_url == "https://example.test/v1"
            assert timeout_seconds == 2.0

        def from_catalog(self, site_id: int, context) -> str:
            return "Grounded answer from LLM"

    monkeypatch.setattr(main, "DOTENV_PATH", dotenv_path)
    monkeypatch.setattr(main, "OpenAICompatibleAnswerClient", StubAnswerClient)

    client = TestClient(main.build_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_build_app_logs_when_llm_generator_is_enabled(monkeypatch, caplog) -> None:
    class StubAnswerClient:
        def __init__(
            self,
            api_key: str,
            model: str,
            base_url: str,
            timeout_seconds: float,
        ) -> None:
            assert api_key == "secret"
            assert model == "test-model"
            assert base_url == "https://example.test/v1"
            assert timeout_seconds == 2.0

        def from_catalog(self, site_id: int, context) -> str:
            return "Grounded answer from LLM"

    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "2")
    monkeypatch.setattr(main, "OpenAICompatibleAnswerClient", StubAnswerClient)
    caplog.set_level(logging.INFO)

    client = TestClient(main.build_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    assert [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.INFO and record.name == main.__name__
    ] == [
        "Catalog retrieval enabled from PostgreSQL database_url=postgresql+psycopg://example.test:5432/catalog.",
        "LLM answer generation enabled with model=test-model base_url=https://example.test/v1.",
    ]


def test_build_app_treats_replace_me_key_as_configured_value(
    monkeypatch,
) -> None:
    class StubAnswerClient:
        def __init__(
            self,
            api_key: str,
            model: str,
            base_url: str,
            timeout_seconds: float,
        ) -> None:
            assert api_key == "replace-me"
            assert model == "gpt-4o-mini"
            assert base_url == "https://example.test/v1"
            assert timeout_seconds == 2.0

        def from_catalog(self, site_id: int, context) -> str:
            return "Grounded answer from LLM"

    monkeypatch.setenv("LLM_API_KEY", "replace-me")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "2")
    monkeypatch.setattr(main, "OpenAICompatibleAnswerClient", StubAnswerClient)

    client = TestClient(main.build_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_build_app_logs_llm_base_url_without_userinfo(monkeypatch, caplog) -> None:
    class StubAnswerClient:
        def __init__(
            self,
            api_key: str,
            model: str,
            base_url: str,
            timeout_seconds: float,
        ) -> None:
            assert api_key == "secret"
            assert model == "test-model"
            assert base_url == "https://user:pass@example.test/v1"
            assert timeout_seconds == 2.0

        def from_catalog(self, site_id: int, context) -> str:
            return "Grounded answer from LLM"

    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_BASE_URL", "https://user:pass@example.test/v1")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "2")
    monkeypatch.setattr(main, "OpenAICompatibleAnswerClient", StubAnswerClient)
    caplog.set_level(logging.INFO)

    client = TestClient(main.build_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    assert [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.INFO and record.name == main.__name__
    ] == [
        "Catalog retrieval enabled from PostgreSQL database_url=postgresql+psycopg://example.test:5432/catalog.",
        "LLM answer generation enabled with model=test-model base_url=https://example.test/v1.",
    ]


def test_build_app_prefers_os_env_over_dotenv_values(
    tmp_path: Path, monkeypatch
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "LLM_API_KEY=dotenv-secret\n"
        "LLM_MODEL=dotenv-model\n"
        "LLM_BASE_URL=https://dotenv.example/v1\n"
        "LLM_TIMEOUT_SECONDS=2\n"
    )

    class StubAnswerClient:
        def __init__(
            self,
            api_key: str,
            model: str,
            base_url: str,
            timeout_seconds: float,
        ) -> None:
            assert api_key == "env-secret"
            assert model == "env-model"
            assert base_url == "https://env.example/v1"
            assert timeout_seconds == 2.0

        def from_catalog(self, site_id: int, context) -> str:
            return "Grounded answer from LLM"

    monkeypatch.setenv("LLM_API_KEY", "env-secret")
    monkeypatch.setenv("LLM_MODEL", "env-model")
    monkeypatch.setenv("LLM_BASE_URL", "https://env.example/v1")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "2")
    monkeypatch.setattr(main, "DOTENV_PATH", dotenv_path)
    monkeypatch.setattr(main, "OpenAICompatibleAnswerClient", StubAnswerClient)

    client = TestClient(main.build_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_build_app_logs_missing_llm_base_url_warning_once_when_no_llm_config(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(f"PRODUCT_CATALOG_DATABASE_URL={TEST_DATABASE_URL}\n")
    monkeypatch.setattr(main, "DOTENV_PATH", dotenv_path)
    caplog.set_level(logging.WARNING)

    main.build_app()
    main.build_app()

    assert [record.getMessage() for record in caplog.records] == [
        f"LLM_BASE_URL is not set after loading {dotenv_path}; using deterministic answer generation."
    ]


def test_build_app_logs_missing_llm_key_warning_once_when_base_url_exists(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        f"PRODUCT_CATALOG_DATABASE_URL={TEST_DATABASE_URL}\n"
        "LLM_BASE_URL=https://example.test/v1\n"
    )
    monkeypatch.setattr(main, "DOTENV_PATH", dotenv_path)
    caplog.set_level(logging.WARNING)

    main.build_app()
    main.build_app()

    assert [record.getMessage() for record in caplog.records] == [
        f"LLM_API_KEY is not set after loading {dotenv_path}; using deterministic answer generation."
    ]


def test_build_app_fails_fast_for_invalid_llm_base_url_from_dotenv(
    tmp_path: Path, monkeypatch
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        f"PRODUCT_CATALOG_DATABASE_URL={TEST_DATABASE_URL}\n"
        "LLM_API_KEY=secret\n"
        "LLM_BASE_URL=http://unsafe.test/v1\n"
    )
    monkeypatch.setattr(main, "DOTENV_PATH", dotenv_path)

    with pytest.raises(ValueError, match="LLM_BASE_URL"):
        main.build_app()


def test_build_app_uses_database_retriever_when_database_url_is_configured(
    monkeypatch, caplog
) -> None:
    captured: dict[str, str] = {}

    class StubDatabaseProductRetriever:
        def __init__(
            self,
            database_url: str,
            embedding_client_factory=None,
        ) -> None:
            captured["database_url"] = database_url
            captured["embedding_client_factory"] = embedding_client_factory

        def readiness_error(self) -> str | None:
            return None

        def retrieve(self, chat, limit: int = 3):
            return []

    monkeypatch.setenv(
        "PRODUCT_CATALOG_DATABASE_URL",
        TEST_DATABASE_URL,
    )
    monkeypatch.setattr(main, "DatabaseProductRetriever", StubDatabaseProductRetriever)
    caplog.set_level(logging.INFO)

    client = TestClient(main.build_app())

    assert client.get("/health").status_code == 200
    assert captured["database_url"] == TEST_DATABASE_URL
    assert [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.INFO and record.name == main.__name__
    ] == [
        "Catalog retrieval enabled from PostgreSQL database_url=postgresql+psycopg://example.test:5432/catalog."
    ]


def test_build_app_fails_fast_when_database_retriever_is_not_ready(monkeypatch) -> None:
    class StubDatabaseProductRetriever:
        def __init__(self, database_url: str, embedding_client_factory=None) -> None:
            self.database_url = database_url

        def readiness_error(self) -> str | None:
            return "missing product_catalog_entries table"

    monkeypatch.setenv(
        "PRODUCT_CATALOG_DATABASE_URL",
        TEST_DATABASE_URL,
    )
    monkeypatch.setattr(main, "DatabaseProductRetriever", StubDatabaseProductRetriever)

    with pytest.raises(ValueError, match="PRODUCT_CATALOG_DATABASE_URL"):
        main.build_app()


def test_build_app_retrieval_startup_error_stays_concise(monkeypatch) -> None:
    class StubDatabaseProductRetriever:
        def __init__(self, database_url: str, embedding_client_factory=None) -> None:
            self.database_url = database_url

        def readiness_error(self) -> str | None:
            return "password authentication failed for user 'postgres'"

    monkeypatch.setenv(
        "PRODUCT_CATALOG_DATABASE_URL",
        TEST_DATABASE_URL,
    )
    monkeypatch.setattr(main, "DatabaseProductRetriever", StubDatabaseProductRetriever)

    with pytest.raises(ValueError) as exc_info:
        main.build_app()

    assert str(exc_info.value) == (
        "PRODUCT_CATALOG_DATABASE_URL must point to a ready PostgreSQL catalog database."
    )


def test_build_app_does_not_log_raw_retrieval_startup_error(
    monkeypatch, caplog
) -> None:
    class StubDatabaseProductRetriever:
        def __init__(self, database_url: str, embedding_client_factory=None) -> None:
            self.database_url = database_url

        def readiness_error(self) -> str | None:
            return "password authentication failed for user 'postgres'"

    monkeypatch.setenv(
        "PRODUCT_CATALOG_DATABASE_URL",
        TEST_DATABASE_URL,
    )
    monkeypatch.setattr(main, "DatabaseProductRetriever", StubDatabaseProductRetriever)
    caplog.set_level(logging.WARNING)

    with pytest.raises(ValueError):
        main.build_app()

    assert [record.getMessage() for record in caplog.records] == [
        (
            "Catalog retrieval startup check failed for "
            "database_url=postgresql+psycopg://example.test:5432/catalog."
        )
    ]


def test_build_app_uses_default_llm_timeout_when_env_is_missing(monkeypatch) -> None:
    class StubAnswerClient:
        def __init__(self, **kwargs) -> None:
            assert kwargs["timeout_seconds"] == 10.0

        def from_catalog(self, site_id: int, context) -> str:
            return "Grounded answer from LLM"

    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setattr(main, "OpenAICompatibleAnswerClient", StubAnswerClient)

    client = TestClient(main.build_app())

    assert client.get("/health").status_code == 200


def test_build_app_uses_overridden_llm_timeout(monkeypatch) -> None:
    class StubAnswerClient:
        def __init__(self, **kwargs) -> None:
            assert kwargs["timeout_seconds"] == 12.5

        def from_catalog(self, site_id: int, context) -> str:
            return "Grounded answer from LLM"

    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setattr(main, "OpenAICompatibleAnswerClient", StubAnswerClient)

    client = TestClient(main.build_app())

    assert client.get("/health").status_code == 200


@pytest.mark.parametrize(
    "timeout_value", ["0", "-1", "nope", "   0.0   ", "nan", "inf", "1e309"]
)
def test_build_app_fails_fast_for_invalid_llm_timeout_when_llm_is_enabled(
    timeout_value: str, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", timeout_value)

    with pytest.raises(ValueError, match="LLM_TIMEOUT_SECONDS"):
        main.build_app()


@pytest.mark.parametrize(
    "timeout_value", ["0", "-1", "nope", "   0.0   ", "nan", "inf", "1e309"]
)
def test_build_app_ignores_invalid_llm_timeout_when_llm_is_disabled(
    timeout_value: str, monkeypatch, caplog
) -> None:
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", timeout_value)
    caplog.set_level(logging.WARNING)

    client = TestClient(main.build_app())

    assert client.get("/health").status_code == 200
    assert [record.getMessage() for record in caplog.records] == [
        f"LLM_BASE_URL is not set after loading {main.DOTENV_PATH}; using deterministic answer generation."
    ]
