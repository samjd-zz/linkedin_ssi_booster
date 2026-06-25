"""Published-cache write helpers."""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from services.database.repositories import PublishedRecordRepository
from services.selection_learning._constants import PUBLISHED_CACHE_PATH
from services.selection_learning._models import PublishedRecord
from services.selection_learning._storage import JsonlStore
from services.shared import DATABASE_ENABLED

logger = logging.getLogger(__name__)


def _coerce_published_at(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    normalized_value = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized_value)


def upsert_published_record(
    *,
    buffer_id: str,
    channel: str,
    text_snippet: str,
    published_at: str,
    candidate_id: Optional[str] = None,
    path: Path | None = None,
) -> None:
    """Write a PublishedRecord to the published cache and optionally to the database."""
    target = path or PUBLISHED_CACHE_PATH
    existing_ids = JsonlStore.load_published_ids(target)
    if buffer_id in existing_ids:
        return

    record = PublishedRecord(
        buffer_id=buffer_id,
        channel=channel,
        text_snippet=text_snippet[:200],
        published_at=published_at,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        candidate_id=candidate_id,
    )

    # Write to JSONL
    try:
        JsonlStore.append(target, asdict(record))
    except OSError as exc:
        logger.warning("selection_learning: published cache write failed (continuing): %s", exc)

    # Write to database if enabled
    if DATABASE_ENABLED:
        _write_published_to_db(
            buffer_id=buffer_id,
            channel=channel,
            text_snippet=text_snippet[:200],
            published_at=published_at,
            fetched_at=datetime.now(timezone.utc),
            candidate_id=candidate_id,
        )


def _write_published_to_db(
    buffer_id: str,
    channel: str,
    text_snippet: str,
    published_at: str,
    fetched_at: datetime,
    candidate_id: Optional[str] = None,
) -> None:
    """Write published record to PostgreSQL database."""
    try:
        from services.database.session import get_session_factory

        published_at_dt = _coerce_published_at(published_at)

        SessionLocal = get_session_factory()
        with SessionLocal() as session:

            PublishedRecordRepository.create(
                session=session,
                buffer_id=buffer_id,
                channel=channel,
                text_snippet=text_snippet,
                published_at=published_at_dt,
                fetched_at=fetched_at,
                candidate_id=candidate_id,
            )
            session.commit()
    except Exception as exc:
        logger.warning(
            "selection_learning: failed to write published record to database (continuing): %s",
            exc,
        )
