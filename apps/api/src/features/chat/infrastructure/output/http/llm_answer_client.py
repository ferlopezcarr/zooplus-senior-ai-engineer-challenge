from __future__ import annotations

import json
import re
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.features.chat.application.answer_context import ResponseContext
from src.features.chat.infrastructure.output.http.errors import LlmProviderHttpError


DEFAULT_LLM_TIMEOUT_SECONDS = 10.0
HTTP_ERROR_BODY_LIMIT = 400

_REDACTED = "[REDACTED]"
_BEARER_TOKEN_PATTERN = re.compile(r'(?i)\bbearer\s+([^\s,;"\']+)')


def build_llm_chat_completions_url(base_url: str) -> str:
    normalized_base_url = base_url.strip()
    if not normalized_base_url:
        raise ValueError(
            "LLM_BASE_URL must be a non-empty HTTPS base URL without params, query, or fragment"
        )

    parsed = urlparse(normalized_base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("LLM_BASE_URL must use HTTPS and include a host")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError(
            "LLM_BASE_URL must be an HTTPS base URL without params, query, or fragment"
        )

    base_path = parsed.path.rstrip("/")
    path = f"{base_path}/chat/completions" if base_path else "/chat/completions"
    return parsed._replace(path=path).geturl()


class OpenAICompatibleAnswerClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = DEFAULT_LLM_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._url = build_llm_chat_completions_url(base_url)
        self._timeout_seconds = timeout_seconds

    def from_catalog(self, site_id: int, query: str, context: ResponseContext) -> str:
        payload = {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Answer in the same language as the user query. "
                        "Answer only from the provided retrieved products context. "
                        "Do not mention or invent products that are not in the context. "
                        "If the context is insufficient, say that you only know the provided catalog matches."
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_prompt(site_id, query, context),
                },
            ],
        }
        request = Request(
            self._url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            message = f"LLM provider request failed with HTTP {exc.code}"
            body_snippet = _read_http_error_body_snippet(exc, self._api_key)
            if body_snippet:
                message = f"{message}: {body_snippet}"
            raise LlmProviderHttpError(message) from exc

        return str(body["choices"][0]["message"]["content"])

    def _build_prompt(self, site_id: int, query: str, context: ResponseContext) -> str:
        products = "\n".join(
            f"- {product.title} | category: {product.category} | summary: {product.summary}"
            for product in context.products
        )
        return (
            f"Site ID: {site_id}\n"
            f"User query: {query}\n"
            "Use only these retrieved products as evidence:\n"
            f"{products}\n"
            "Answer the user with a concise grounded summary of the matches."
        )


def _read_http_error_body_snippet(error: HTTPError, api_key: str) -> str:
    if error.fp is None:
        return ""

    try:
        body = error.read()
    except Exception:
        return ""

    if not body:
        return ""

    snippet = _sanitize_http_error_body(
        " ".join(body.decode("utf-8", errors="replace").split()),
        api_key,
    )
    if len(snippet) <= HTTP_ERROR_BODY_LIMIT:
        return snippet
    return f"{snippet[:HTTP_ERROR_BODY_LIMIT].rstrip()}..."


def _sanitize_http_error_body(body: str, api_key: str) -> str:
    sanitized = body

    if api_key:
        sanitized = sanitized.replace(api_key, _REDACTED)

    sanitized = _BEARER_TOKEN_PATTERN.sub(f"Bearer {_REDACTED}", sanitized)

    return sanitized
