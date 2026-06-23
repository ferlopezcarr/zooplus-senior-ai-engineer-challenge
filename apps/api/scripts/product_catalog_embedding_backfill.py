# ruff: noqa: E402

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from dataclasses import dataclass
from os import getenv
from pathlib import Path
from time import perf_counter

from sqlalchemy import create_engine, func, select, update

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from scripts.product_catalog_feed import (
    get_product_catalog_database_url,
    load_product_catalog_env,
    product_catalog_entries,
)
from src.infrastructure.output.embedding_client import (
    DEFAULT_EMBEDDING_TIMEOUT_SECONDS,
    OpenAICompatibleEmbeddingClient,
    build_embeddings_url,
)
from src.infrastructure.output.model.error import ProductEmbeddingEntryNotFoundError


@dataclass(frozen=True)
class EmbeddingBackfillTarget:
    article_id: int
    embedding_document: str
    missing_embedding: bool


@dataclass(frozen=True)
class EmbeddingBackfillResult:
    selected: int
    selected_missing: int
    updated: int
    updated_missing: int
    skipped: int
    failed: int


class RunTraceWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle = path.open("a", encoding="utf-8")

    def write(self, event: str, **payload: object) -> None:
        line = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "event": event,
            **payload,
        }
        self._handle.write(json.dumps(line, sort_keys=True) + "\n")
        self._handle.flush()

    def close(self) -> None:
        self._handle.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill product catalog embeddings in PostgreSQL."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of catalog rows to process.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-embed selected rows even when an embedding already exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show how many rows would be processed without calling the provider.",
    )
    return parser.parse_args()


def build_target_select_statement(*, limit: int | None, force: bool):
    statement = select(
        product_catalog_entries.c.article_id,
        product_catalog_entries.c.embedding_document,
        product_catalog_entries.c.embedding.is_(None).label("missing_embedding"),
    ).order_by(product_catalog_entries.c.article_id)

    if not force:
        statement = statement.where(product_catalog_entries.c.embedding.is_(None))

    if limit is not None:
        statement = statement.limit(limit)

    return statement


def load_backfill_targets(
    database_url: str, *, limit: int | None, force: bool
) -> list[EmbeddingBackfillTarget]:
    engine = create_engine(database_url)
    statement = build_target_select_statement(limit=limit, force=force)

    try:
        with engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
    finally:
        engine.dispose()

    return [
        EmbeddingBackfillTarget(
            article_id=int(row["article_id"]),
            embedding_document=str(row["embedding_document"]),
            missing_embedding=bool(row["missing_embedding"]),
        )
        for row in rows
    ]


def count_missing_embeddings(database_url: str) -> int:
    engine = create_engine(database_url)
    statement = (
        select(func.count())
        .select_from(product_catalog_entries)
        .where(product_catalog_entries.c.embedding.is_(None))
    )

    try:
        with engine.connect() as connection:
            count = connection.execute(statement).scalar_one()
    finally:
        engine.dispose()

    return int(count)


def save_embedding(database_url: str, article_id: int, embedding: list[float]) -> None:
    engine = create_engine(database_url)
    statement = (
        update(product_catalog_entries)
        .where(product_catalog_entries.c.article_id == article_id)
        .values(embedding=embedding)
    )

    try:
        with engine.begin() as connection:
            result = connection.execute(statement)
    finally:
        engine.dispose()

    if result.rowcount != 1:
        raise ProductEmbeddingEntryNotFoundError("Product not found.")


def build_embedding_client_from_env() -> OpenAICompatibleEmbeddingClient:
    base_url = _get_required_env("EMBEDDING_BASE_URL")
    api_key = _get_required_env("EMBEDDING_API_KEY")
    model = _get_required_env("EMBEDDING_MODEL")
    timeout_seconds = _get_timeout_seconds(
        "EMBEDDING_TIMEOUT_SECONDS", DEFAULT_EMBEDDING_TIMEOUT_SECONDS
    )

    build_embeddings_url(base_url)
    return OpenAICompatibleEmbeddingClient(
        api_key=api_key,
        model=model,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )


def build_run_trace_writer() -> RunTraceWriter:
    filename = datetime.now().strftime("product_catalog_embedding_%Y%m%d-%H%M%S.log")
    return RunTraceWriter(Path(__file__).with_name(filename))


def _short_text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _short_embedding_hash(embedding: list[float]) -> str:
    payload = json.dumps(embedding, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def backfill_embeddings(
    targets: list[EmbeddingBackfillTarget],
    *,
    client: object,
    save_embedding,
    dry_run: bool,
    trace_writer: RunTraceWriter,
    model: str | None,
) -> EmbeddingBackfillResult:
    selected_missing = sum(1 for target in targets if target.missing_embedding)

    if dry_run:
        for target in targets:
            trace_writer.write(
                "product_trace",
                article_id=target.article_id,
                status="skipped",
                model=model,
                source_text_hash=_short_text_hash(target.embedding_document),
                embedding_hash=None,
                embedding_dimensions=None,
                duration_ms=0,
                error=None,
            )
        return EmbeddingBackfillResult(
            selected=len(targets),
            selected_missing=selected_missing,
            updated=0,
            updated_missing=0,
            skipped=len(targets),
            failed=0,
        )

    updated = 0
    updated_missing = 0
    failed = 0
    for target in targets:
        started_at = perf_counter()
        source_text_hash = _short_text_hash(target.embedding_document)
        embedding_hash = None
        embedding_dimensions = None

        try:
            embedding = client.embed(target.embedding_document)
            embedding_hash = _short_embedding_hash(embedding)
            embedding_dimensions = len(embedding)
            save_embedding(target.article_id, embedding)
            updated += 1
            if target.missing_embedding:
                updated_missing += 1
            trace_writer.write(
                "product_trace",
                article_id=target.article_id,
                status="updated",
                model=model,
                source_text_hash=source_text_hash,
                embedding_hash=embedding_hash,
                embedding_dimensions=embedding_dimensions,
                duration_ms=int((perf_counter() - started_at) * 1000),
                error=None,
            )
        except Exception as exc:
            failed += 1
            trace_writer.write(
                "product_trace",
                article_id=target.article_id,
                status="failed",
                model=model,
                source_text_hash=source_text_hash,
                embedding_hash=embedding_hash,
                embedding_dimensions=embedding_dimensions,
                duration_ms=int((perf_counter() - started_at) * 1000),
                error=str(exc),
            )

    return EmbeddingBackfillResult(
        selected=len(targets),
        selected_missing=selected_missing,
        updated=updated,
        updated_missing=updated_missing,
        skipped=0,
        failed=failed,
    )


def main() -> None:
    load_product_catalog_env()
    args = parse_args()
    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit must be a positive integer")

    trace_writer = build_run_trace_writer()

    try:
        database_url = get_product_catalog_database_url()
        missing_before = count_missing_embeddings(database_url)
        targets = load_backfill_targets(
            database_url, limit=args.limit, force=args.force
        )
        client = None if args.dry_run else build_embedding_client_from_env()
        model = (
            getattr(client, "model", None)
            if client is not None
            else _get_optional_env("EMBEDDING_MODEL")
        )
        trace_writer.write(
            "run_started",
            dry_run=args.dry_run,
            force=args.force,
            limit=args.limit,
            selected=len(targets),
            selected_missing=sum(1 for target in targets if target.missing_embedding),
            model=model,
        )
        result = backfill_embeddings(
            targets,
            client=client,
            save_embedding=lambda article_id, embedding: save_embedding(
                database_url, article_id, embedding
            ),
            dry_run=args.dry_run,
            trace_writer=trace_writer,
            model=model,
        )
        remaining_without_embeddings = max(missing_before - result.updated_missing, 0)

        mode = "force" if args.force else "missing-only"
        trace_writer.write(
            "run_summary",
            dry_run=args.dry_run,
            mode=mode,
            missing_before=missing_before,
            selected=result.selected,
            selected_missing=result.selected_missing,
            updated=result.updated,
            skipped=result.skipped,
            failed=result.failed,
            remaining_without_embeddings=remaining_without_embeddings,
        )
        if args.dry_run:
            remaining_after_successful_run = max(
                missing_before - result.selected_missing, 0
            )
            print(
                "Dry run ok: "
                f"missing before={missing_before}, "
                f"selected for this run={result.selected}, "
                f"would generate/update={result.selected}, "
                f"missing now={missing_before}, "
                f"would remain after a fully successful run={remaining_after_successful_run} "
                f"({mode} mode), log={trace_writer.path.name}."
            )
            return

        status = "Backfill completed with failures" if result.failed else "Backfill ok"
        print(
            f"{status}: "
            f"missing before={missing_before}, "
            f"selected for this run={result.selected}, "
            f"generated/updated={result.updated}, "
            f"failed={result.failed}, "
            f"remaining without embeddings={remaining_without_embeddings} "
            f"({mode} mode), log={trace_writer.path.name}."
        )
        if result.failed:
            raise SystemExit(1)
    except Exception as exc:
        trace_writer.write("run_failed", error=str(exc))
        raise
    finally:
        trace_writer.close()


def _get_required_env(name: str) -> str:
    value = getenv(name)
    if value is None or not value.strip():
        raise ValueError(f"{name} must be set for embedding backfill commands.")

    return value.strip()


def _get_optional_env(name: str) -> str | None:
    value = getenv(name)
    if value is None or not value.strip():
        return None

    return value.strip()


def _get_timeout_seconds(name: str, default: float) -> float:
    value = getenv(name)
    if value is None or not value.strip():
        return default

    timeout_seconds = float(value)
    if timeout_seconds <= 0:
        raise ValueError(f"{name} must be a positive number")

    return timeout_seconds


if __name__ == "__main__":
    main()
