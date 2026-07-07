"""Buffer publish reconciliation service."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from services.selection_learning._constants import (
    ACCEPTANCE_WINDOW_DAYS,
    CANDIDATES_LOG_PATH,
    PUBLISHED_CACHE_PATH,
)
from services.selection_learning._published import upsert_published_record
from services.selection_learning._storage import JsonlStore
from services.selection_learning._text import TextMatcher

logger = logging.getLogger(__name__)


class ReconcileService:
    """Reconcile generated candidates with published Buffer posts."""

    @staticmethod
    def reconcile_published(
        buffer_service: Any,
        channel_ids: dict[str, str],
        *,
        candidates_path: Path | None = None,
        published_path: Path | None = None,
        acceptance_window_days: int = ACCEPTANCE_WINDOW_DAYS,
        limit_per_channel: int = 50,
    ) -> dict[str, int]:
        """Fetch SENT posts, upsert cache records, and label candidates."""
        c_path = candidates_path or CANDIDATES_LOG_PATH
        p_path = published_path or PUBLISHED_CACHE_PATH

        stats: dict[str, int] = {
            "fetched": 0,
            "matched": 0,
            "labelled_selected": 0,
            "labelled_rejected": 0,
        }

        candidates = JsonlStore.read(c_path)
        pending = [c for c in candidates if c.get("selected") is None]

        for channel_name, channel_id in channel_ids.items():
            try:
                posts = buffer_service.get_published_posts(channel_id, limit=limit_per_channel)
            except Exception as exc:
                logger.warning(
                    "selection_learning: failed to fetch published posts for %s: %s",
                    channel_name,
                    exc,
                )
                continue

            for post in posts:
                buffer_id = post.get("id", "")
                text = post.get("text", "")
                published_at = post.get("dueAt", datetime.now(timezone.utc).isoformat())
                stats["fetched"] += 1

                candidate_id = TextMatcher.match_candidate(
                    {"buffer_id": buffer_id, "text_snippet": text[:200]},
                    pending,
                )
                upsert_published_record(
                    buffer_id=buffer_id,
                    channel=channel_name,
                    text_snippet=text,
                    published_at=published_at,
                    candidate_id=candidate_id,
                    path=p_path,
                )
                if candidate_id:
                    stats["matched"] += 1

        published_records = JsonlStore.read(p_path)
        matched_candidate_ids: set[str] = {
            r["candidate_id"]
            for r in published_records
            if r.get("candidate_id")
        }

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=acceptance_window_days)
        changed = False

        for rec in candidates:
            cid = rec.get("candidate_id")
            if rec.get("selected") is not None:
                continue

            if cid in matched_candidate_ids:
                rec["selected"] = True
                rec["selected_at"] = now.isoformat()
                stats["labelled_selected"] += 1
                changed = True
            else:
                try:
                    ts = datetime.fromisoformat(rec.get("timestamp", ""))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                except ValueError:
                    ts = now
                if ts < cutoff:
                    rec["selected"] = False
                    rec["selected_at"] = now.isoformat()
                    stats["labelled_rejected"] += 1
                    changed = True

        if changed:
            JsonlStore.rewrite(c_path, candidates)

        # Sync IDEAS_CACHE_PATH with actual Buffer published posts
        try:
            from services.content_curator._config import IDEAS_CACHE_PATH
            
            # Extract article titles from published_records that have a candidate match
            published_titles: set[str] = set()
            for rec in published_records:
                cid = rec.get("candidate_id")
                if cid:
                    # Find matching candidate to get article title
                    for cand in candidates:
                        if cand.get("candidate_id") == cid:
                            article_title = cand.get("article_title", "")
                            if article_title:
                                published_titles.add(article_title)
                            break
            
            # Update IDEAS_CACHE_PATH with only articles that are actually published.
            # Supports both legacy string-list format and new [[title, timestamp], ...] format.
            import time as _time
            raw_cache: list = []
            if IDEAS_CACHE_PATH.exists():
                try:
                    raw_cache = json.loads(IDEAS_CACHE_PATH.read_text())
                except Exception:
                    raw_cache = []
            # Normalise to [[title, timestamp], ...]
            if raw_cache and isinstance(raw_cache[0], str):
                raw_cache = [[t, 0] for t in raw_cache]
            existing_titles = {t for t, _ts in raw_cache}

            # Merge — add any newly published titles not already in the cache
            _now = _time.time()
            merged = {t: ts for t, ts in raw_cache}
            for title in published_titles - existing_titles:
                merged[title] = _now
            raw_cache = sorted(merged.items())  # deterministic order
            IDEAS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            IDEAS_CACHE_PATH.write_text(json.dumps([[t, ts] for t, ts in raw_cache], indent=2))

            stats["ideas_cache_synced"] = len(raw_cache)
            logger.info(
                "selection_learning reconcile: synced IDEAS_CACHE_PATH with %d article titles",
                len(raw_cache),
            )
        except Exception as exc:
            logger.warning("Failed to sync IDEAS_CACHE_PATH (continuing): %s", exc)

        logger.info(
            "selection_learning reconcile: fetched=%d matched=%d selected=%d rejected=%d",
            stats["fetched"],
            stats["matched"],
            stats["labelled_selected"],
            stats["labelled_rejected"],
        )
        return stats
