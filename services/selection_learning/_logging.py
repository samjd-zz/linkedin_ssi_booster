"""Candidate logging/update services."""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from services.database.repositories import CandidateRecordRepository
from services.selection_learning._constants import CANDIDATES_LOG_PATH
from services.selection_learning._models import CandidateRecord
from services.selection_learning._storage import JsonlStore
from services.selection_learning._text import TextMatcher
from services.shared import DATABASE_ENABLED

logger = logging.getLogger(__name__)


def make_candidate_id() -> str:
    """Return a new UUID4 string."""
    return str(uuid.uuid4())


class CandidateService:
    """Manage candidate record lifecycle (create/update)."""

    def __init__(self, nlp_provider: Callable[[], Any]) -> None:
        self._nlp_provider = nlp_provider

    def log_candidate(
        self,
        *,
        candidate_id: str,
        article_url: str,
        article_title: str,
        article_source: str,
        ssi_component: str,
        channel: str,
        post_text: str,
        buffer_id: str | None,
        route: str,
        run_id: str,
        path: Path | None = None,
        enable_nlp: bool = True,
    ) -> CandidateRecord:
        """Append one CandidateRecord to the candidates log and optionally to the database."""
        themes: list[str] = []
        sentiment: dict[str, Any] = {}

        if enable_nlp:
            try:
                nlp = self._nlp_provider()
                themes = nlp.extract_themes(post_text)
                sentiment = nlp.analyze_sentiment(post_text)
                logger.debug(
                    "selection_learning: extracted %d themes, sentiment=%s",
                    len(themes),
                    sentiment.get("polarity", "unknown"),
                )
            except Exception as exc:
                logger.warning("selection_learning: NLP analysis failed (continuing): %s", exc)

        timestamp = datetime.now(timezone.utc)
        text_hash = TextMatcher.text_hash(post_text)

        record = CandidateRecord(
            candidate_id=candidate_id,
            timestamp=timestamp.isoformat(),
            article_url=article_url,
            article_title=article_title,
            article_source=article_source,
            ssi_component=ssi_component,
            channel=channel,
            text_hash=text_hash,
            text_snippet=post_text[:200],
            buffer_id=buffer_id,
            route=route,
            selected=None,
            selected_at=None,
            run_id=run_id,
            themes=themes,
            sentiment=sentiment,
        )

        # Write to JSONL
        target = path or CANDIDATES_LOG_PATH
        try:
            JsonlStore.append(target, asdict(record))
        except OSError as exc:
            logger.warning("selection_learning: candidate log write failed (continuing): %s", exc)

        # Write to database if enabled
        if DATABASE_ENABLED:
            self._write_candidate_to_db(
                candidate_id=candidate_id,
                timestamp=timestamp,
                article_url=article_url,
                article_title=article_title,
                article_source=article_source,
                ssi_component=ssi_component,
                channel=channel,
                text_hash=text_hash,
                text_snippet=post_text[:200],
                buffer_id=buffer_id,
                route=route,
                run_id=run_id,
                themes=themes,
                sentiment=sentiment,
            )

        return record

    @staticmethod
    def _write_candidate_to_db(
        candidate_id: str,
        timestamp: datetime,
        article_url: str,
        article_title: str,
        article_source: str,
        ssi_component: str,
        channel: str,
        text_hash: str,
        text_snippet: str,
        buffer_id: Optional[str],
        route: str,
        run_id: str,
        themes: list[str],
        sentiment: dict[str, Any],
    ) -> None:
        """Write candidate record to PostgreSQL database."""
        try:
            from services.database.session import get_session_factory

            SessionLocal = get_session_factory()
            with SessionLocal() as session:
                CandidateRecordRepository.create(
                    session=session,
                    candidate_id=candidate_id,
                    timestamp=timestamp,
                    article_url=article_url,
                    article_title=article_title,
                    article_source=article_source,
                    ssi_component=ssi_component,
                    channel=channel,
                    text_hash=text_hash,
                    text_snippet=text_snippet,
                    buffer_id=buffer_id,
                    route=route,
                    run_id=run_id,
                    themes=themes,
                    sentiment=sentiment,
                )
                session.commit()
        except Exception as exc:
            logger.warning("selection_learning: failed to write candidate to database (continuing): %s", exc)

    @staticmethod
    def update_candidate_buffer_id(
        candidate_id: str,
        buffer_id: str,
        path: Path | None = None,
    ) -> bool:
        """Set buffer_id on an existing candidate record in the log and database."""
        # Update JSONL
        target = path or CANDIDATES_LOG_PATH
        records = JsonlStore.read(target)
        found = False
        for rec in records:
            if rec.get("candidate_id") == candidate_id:
                rec["buffer_id"] = buffer_id
                found = True
                break
        if found:
            JsonlStore.rewrite(target, records)
        else:
            logger.warning(
                "selection_learning: candidate_id %s not found in JSONL — buffer_id not updated",
                candidate_id,
            )

        # Update database if enabled
        if DATABASE_ENABLED:
            try:
                from services.database.session import get_session_factory

                SessionLocal = get_session_factory()
                with SessionLocal() as session:
                    from sqlalchemy import update
                    from services.database.models import CandidateRecord as CandidateRecordModel

                    stmt = (
                        update(CandidateRecordModel)
                        .where(CandidateRecordModel.candidate_id == candidate_id)
                        .values(buffer_id=buffer_id)
                    )
                    session.execute(stmt)
                    session.commit()
            except Exception as exc:
                logger.warning(
                    "selection_learning: failed to update candidate buffer_id in database (continuing): %s",
                    exc,
                )

        return found

    def find_similar_candidates(
        self,
        post_text: str,
        candidates: list[dict[str, Any]] | None = None,
        similarity_threshold: float = 0.75,
        path: Path | None = None,
    ) -> list[dict[str, Any]]:
        """Find candidates similar to *post_text* using spaCy semantic similarity."""
        if candidates is None:
            target = path or CANDIDATES_LOG_PATH
            candidates = JsonlStore.read(target)

        nlp = self._nlp_provider()
        similar: list[tuple[float, dict[str, Any]]] = []

        for candidate in candidates:
            candidate_text = candidate.get("text_snippet", "")
            if not candidate_text:
                continue

            try:
                similarity = nlp.compute_similarity(post_text, candidate_text)
                if similarity >= similarity_threshold:
                    enriched = candidate.copy()
                    enriched["similarity_score"] = similarity
                    similar.append((similarity, enriched))
            except Exception as exc:
                logger.debug(
                    "selection_learning: similarity computation failed for candidate %s: %s",
                    candidate.get("candidate_id", "unknown"),
                    exc,
                )

        similar.sort(key=lambda x: x[0], reverse=True)
        return [candidate for _, candidate in similar]
