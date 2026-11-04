"""Curator article helpers: published-title cache, text prefetch, and learning."""

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import requests

from services.content_curator._config import IDEAS_CACHE_PATH
from services.content_curator._curator_base import CuratorHost
from services.content_curator._ssi_picker import build_topic_signal

logger = logging.getLogger(__name__)


class CuratorArticleMixin(CuratorHost):
    """Article I/O and continual-learning helpers used by ContentCurator."""

    def _load_published_titles(self) -> set:
        if not IDEAS_CACHE_PATH.exists():
            return set()
        try:
            raw: list = json.loads(IDEAS_CACHE_PATH.read_text())
        except Exception:
            return set()
        # Support both old plain-list format and new [[title, ts], ...] format
        if raw and isinstance(raw[0], str):
            return set(raw)
        return {t for t, _ts in raw}

    def _save_published_title(self, title: str) -> None:
        """Save title to cache (with 30-day TTL rollover) and update in-memory set."""
        import time
        _TTL_DAYS = int(os.getenv("IDEAS_CACHE_TTL_DAYS", "30"))
        _cutoff = time.time() - _TTL_DAYS * 86400
        # Load as list-of-[title, timestamp]; fall back gracefully from old plain-list format
        raw: list = []
        if IDEAS_CACHE_PATH.exists():
            try:
                raw = json.loads(IDEAS_CACHE_PATH.read_text())
            except Exception:
                raw = []
        # Migrate old plain-list format → [[title, timestamp], ...]
        if raw and isinstance(raw[0], str):
            raw = [[t, 0] for t in raw]  # 0 → treated as epoch, immediately prunable next cycle
        # Prune expired entries
        raw = [[t, ts] for t, ts in raw if ts >= _cutoff]
        # Upsert this title
        raw = [[t, ts] for t, ts in raw if t != title]
        raw.append([title, time.time()])
        IDEAS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        IDEAS_CACHE_PATH.write_text(json.dumps(raw, indent=2))

    def _fetch_article_text_with_summary(self, url: str, max_chars: int = 3000) -> str:
        """Fetch and optionally spaCy-summarize article text."""
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            html = resp.text
            html = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", " ", html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            if self._spacy_nlp and len(text) > 500:
                try:
                    summary = self._spacy_nlp.summarize_article(
                        article_text=text[:max_chars],
                        max_sentences=5,
                        focus_entities=True,
                    )
                    if summary:
                        logger.debug("spaCy summarized article from %d to %d chars", len(text[:max_chars]), len(summary))
                        return summary
                except Exception as _sum_exc:
                    logger.debug("spaCy summarization failed, using truncated text: %s", _sum_exc)
            return text[:max_chars]
        except Exception as exc:
            logger.debug("Could not fetch article text from %s: %s", url, exc)
            return ""

    def _prefetch_article_texts(self, articles: list[dict[str, Any]]) -> dict[str, str]:
        """Fetch full text for short-summary articles in parallel, keyed by link."""
        fetch_targets = [
            article for article in articles
            if len(article["summary"].strip()) < 800 and article["link"]
        ]
        try:
            fetch_workers = max(1, min(len(fetch_targets), int(os.getenv("CURATOR_LEARN_FETCH_WORKERS", "4"))))
        except ValueError:
            fetch_workers = min(len(fetch_targets), 4) or 1

        with ThreadPoolExecutor(max_workers=fetch_workers, thread_name_prefix="learn-fetch") as executor:
            fetched_texts = executor.map(
                lambda article: (article["link"], self._fetch_article_text_with_summary(article["link"])),
                fetch_targets,
            )
            return {link: text for link, text in fetched_texts if text}

    def _learn_from_article(
        self,
        article: dict[str, Any],
        prefetched_article_text: dict[str, str],
        *,
        learn_only: bool,
    ) -> None:
        """Persist new knowledge from *article* and refresh the topic signal."""
        try:
            from services.avatar_intelligence import extract_and_append_knowledge
            _learn_text = article["summary"]
            if len(_learn_text.strip()) < 800 and article["link"]:
                _fetched = prefetched_article_text.get(article["link"], "")
                if _fetched:
                    logger.debug("🧠 fetched full text for '%s' (%d chars)", article["title"][:60], len(_fetched))
                    _learn_text = _fetched
            _new_facts = extract_and_append_knowledge(
                article_text=_learn_text,
                source_url=article["link"],
                source_title=article["title"],
                spacy_nlp=self._spacy_nlp,
            )
            if _new_facts:
                from services.avatar_intelligence import load_avatar_state, normalize_extracted_facts
                _latest_state = load_avatar_state()
                self._extracted_facts = normalize_extracted_facts(_latest_state)
                _topic_window = int(os.getenv("TOPIC_SIGNAL_WINDOW", "50"))
                self._topic_signal = build_topic_signal(self._extracted_facts, window=_topic_window)
                logger.info(
                    "🧠 ✨ +%d fact(s) from '%s' (🗂️ pool=%d)" if learn_only
                    else "🧠 Knowledge extraction: ✨ +%d fact(s) from '%s' (🗂️ pool=%d)",
                    len(_new_facts), article["title"][:60], len(self._extracted_facts),
                )
            else:
                logger.info(
                    "🧠 0 new facts from '%s' (🗂️ pool=%d)" if learn_only
                    else "🧠 Knowledge extraction: ➕ 0 new facts from '%s' (🗂️ pool=%d)",
                    article["title"][:60], len(self._extracted_facts),
                )
        except Exception as _exc:
            logger.debug("Knowledge extraction skipped (continuing): %s", _exc)
