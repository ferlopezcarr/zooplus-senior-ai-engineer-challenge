from __future__ import annotations

import json
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.application.response_context import ResponseContext


DEFAULT_LLM_TIMEOUT_SECONDS = 2.0


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

    def from_catalog(self, site_id: int, context: ResponseContext) -> str:
        payload = {
            "model": self._model,
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
                    "content": self._build_prompt(site_id, context),
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

        with urlopen(request, timeout=self._timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))

        return str(body["choices"][0]["message"]["content"])

    def _build_prompt(self, site_id: int, context: ResponseContext) -> str:
        products = "\n".join(
            f"- {product.title} | category: {product.category} | summary: {product.summary}"
            for product in context.products
        )
        return (
            f"Site ID: {site_id}\n"
            "Use only these retrieved products as evidence:\n"
            f"{products}\n"
            "Answer the user with a concise grounded summary of the matches."
        )
