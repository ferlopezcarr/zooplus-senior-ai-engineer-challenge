from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.infrastructure.output.model.error import EmbeddingProviderHttpError


DEFAULT_EMBEDDING_TIMEOUT_SECONDS = 10.0


def build_embeddings_url(base_url: str) -> str:
    normalized_base_url = base_url.strip()
    if not normalized_base_url:
        raise ValueError(
            "EMBEDDING_BASE_URL must be a non-empty HTTPS base URL without params, query, or fragment"
        )

    parsed = urlparse(normalized_base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("EMBEDDING_BASE_URL must use HTTPS and include a host")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError(
            "EMBEDDING_BASE_URL must be an HTTPS base URL without params, query, or fragment"
        )

    base_path = parsed.path.rstrip("/")
    path = f"{base_path}/embeddings" if base_path else "/embeddings"
    return parsed._replace(path=path).geturl()


class OpenAICompatibleEmbeddingClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = DEFAULT_EMBEDDING_TIMEOUT_SECONDS,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._url = build_embeddings_url(base_url)
        self._timeout_seconds = timeout_seconds

    def embed(self, text: str) -> list[float]:
        request = Request(
            self._url,
            data=json.dumps({"model": self.model, "input": text}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
            return [float(value) for value in body["data"][0]["embedding"]]
        except HTTPError as exc:
            raise EmbeddingProviderHttpError(
                "Embedding provider request failed."
            ) from exc
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise EmbeddingProviderHttpError(
                "Embedding provider request failed."
            ) from exc
