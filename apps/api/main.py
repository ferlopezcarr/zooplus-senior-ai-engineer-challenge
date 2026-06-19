"""FastAPI bootstrap for the assistant API foundation."""

from collections.abc import Mapping

from fastapi import FastAPI


def build_app() -> FastAPI:
    """Build the FastAPI app for the current repository runtime."""

    app = FastAPI(
        title="Zooplus Assistant API",
        version="0.1.0",
        description="FastAPI bootstrap exposing the current repository HTTP surface.",
    )

    @app.get("/")
    async def root() -> Mapping[str, str]:
        """Liveness ping for the API shell."""

        return {"status": "ok", "service": "zooplus-assistant-api"}

    @app.get("/health")
    async def health() -> Mapping[str, str]:
        """Health probe used by local and CI checks."""

        return {"status": "healthy"}

    return app


app = build_app()
