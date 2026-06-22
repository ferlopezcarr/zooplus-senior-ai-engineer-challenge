from __future__ import annotations

import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from src.application.response_context import ResponseContext
from src.domain import Product
from src.infrastructure.output.llm_answer_client import (
    HTTP_ERROR_BODY_LIMIT,
    LlmProviderHttpError,
    OpenAICompatibleAnswerClient,
    build_llm_chat_completions_url,
)


class _StubHTTPResponse:
    def __init__(self, body: dict[str, object]) -> None:
        self._payload = json.dumps(body).encode("utf-8")

    def __enter__(self) -> _StubHTTPResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


def test_openai_compatible_answer_client_posts_grounded_prompt(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def stub_urlopen(request, timeout: float):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _StubHTTPResponse(
            {"choices": [{"message": {"content": "Grounded answer from LLM"}}]}
        )

    monkeypatch.setattr(
        "src.infrastructure.output.llm_answer_client.urlopen", stub_urlopen
    )

    client = OpenAICompatibleAnswerClient(
        api_key="secret",
        model="test-model",
        base_url="https://example.test/v1/",
        timeout_seconds=1.5,
    )
    context = ResponseContext(
        products=[
            Product(
                article_id=5511354,
                product_id="dog-ball",
                variant_id="759837.1",
                title="Env Only Ball - Dog Toy",
                summary="ball for dog fetch",
                site_id=77,
                category="dog",
                score=2.0,
            )
        ]
    )

    answer = client.from_catalog(site_id=77, context=context)

    assert answer == "Grounded answer from LLM"
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["timeout"] == 1.5
    assert captured["authorization"] == "Bearer secret"
    assert captured["body"] == {
        "model": "test-model",
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Answer only from the provided catalog context. "
                    "Do not mention products that are not in the context. "
                    "If the context is insufficient, say that you only know the provided catalog matches."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Site ID: 77\n"
                    "Use only these retrieved products as evidence:\n"
                    "- Env Only Ball - Dog Toy | category: dog | summary: ball for dog fetch\n"
                    "Answer the user with a concise grounded summary of the matches."
                ),
            },
        ],
    }


def test_build_llm_chat_completions_url_accepts_https_base_url() -> None:
    assert (
        build_llm_chat_completions_url("https://example.test/v1/")
        == "https://example.test/v1/chat/completions"
    )


@pytest.mark.parametrize(
    ("base_url", "message"),
    [
        (
            "",
            "LLM_BASE_URL must be a non-empty HTTPS base URL without params, query, or fragment",
        ),
        (
            "   ",
            "LLM_BASE_URL must be a non-empty HTTPS base URL without params, query, or fragment",
        ),
        ("example.test/v1", "LLM_BASE_URL must use HTTPS and include a host"),
        ("http://example.test/v1", "LLM_BASE_URL must use HTTPS and include a host"),
        (
            "https://example.test/v1;params",
            "LLM_BASE_URL must be an HTTPS base URL without params, query, or fragment",
        ),
        (
            "https://example.test/v1?debug=true",
            "LLM_BASE_URL must be an HTTPS base URL without params, query, or fragment",
        ),
        (
            "https://example.test/v1#fragment",
            "LLM_BASE_URL must be an HTTPS base URL without params, query, or fragment",
        ),
    ],
)
def test_build_llm_chat_completions_url_rejects_urls_outside_our_env_contract(
    base_url: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        build_llm_chat_completions_url(base_url)


def test_build_llm_chat_completions_url_preserves_intentionally_narrow_env_contract() -> (
    None
):
    assert (
        build_llm_chat_completions_url("https://user@example.test/v1")
        == "https://user@example.test/v1/chat/completions"
    )


def test_openai_compatible_answer_client_summarizes_http_errors(monkeypatch) -> None:
    response_body = (
        '{"error":{"message":"bad request",'
        '"authorization":"Bearer provider-secret-token",'
        '"api_key":"provider-api-key",'
        '"access_token":"access-secret-token",'
        '"token":"token-secret",'
        '"details":"Authorization: Bearer header-secret provider echoed client-secret-key"}}'
    ).encode("utf-8")

    def stub_urlopen(request, timeout: float):
        raise HTTPError(
            url=request.full_url,
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=BytesIO(response_body),
        )

    monkeypatch.setattr(
        "src.infrastructure.output.llm_answer_client.urlopen", stub_urlopen
    )

    client = OpenAICompatibleAnswerClient(
        api_key="client-secret-key",
        model="test-model",
        base_url="https://example.test/v1/",
    )

    with pytest.raises(LlmProviderHttpError) as excinfo:
        client.from_catalog(site_id=77, context=ResponseContext(products=[]))

    message = str(excinfo.value)
    assert message.startswith("LLM provider request failed with HTTP 400: ")
    assert "provider-secret-token" not in message
    assert "provider-api-key" not in message
    assert "access-secret-token" not in message
    assert "token-secret" not in message
    assert "header-secret" not in message
    assert "client-secret-key" not in message
    assert '"authorization":"[REDACTED]"' in message
    assert '"api_key":"[REDACTED]"' in message
    assert '"access_token":"[REDACTED]"' in message
    assert '"token":"[REDACTED]"' in message
    assert "Authorization: Bearer [REDACTED]" in message


def test_openai_compatible_answer_client_truncates_sanitized_http_error_body(
    monkeypatch,
) -> None:
    response_body = (
        '{"error":{"message":"bad request",'
        '"details":"Authorization: Bearer header-secret '
        + ("x" * (HTTP_ERROR_BODY_LIMIT + 50))
        + '"}}'
    ).encode("utf-8")

    def stub_urlopen(request, timeout: float):
        raise HTTPError(
            url=request.full_url,
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=BytesIO(response_body),
        )

    monkeypatch.setattr(
        "src.infrastructure.output.llm_answer_client.urlopen", stub_urlopen
    )

    client = OpenAICompatibleAnswerClient(
        api_key="client-secret-key",
        model="test-model",
        base_url="https://example.test/v1/",
    )

    with pytest.raises(LlmProviderHttpError) as excinfo:
        client.from_catalog(site_id=77, context=ResponseContext(products=[]))

    message = str(excinfo.value)
    assert "header-secret" not in message
    assert "Authorization: Bearer [REDACTED]" in message
    assert len(message) < 500
    assert message.endswith("...")
