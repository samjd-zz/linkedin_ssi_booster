"""Article ranking service for curation candidates."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Callable

from services.selection_learning._constants import DEFAULT_RANK_ALPHA, FRESHNESS_HALF_LIFE_DAYS
from services.selection_learning._models import FeaturePrior
from services.selection_learning._priors import PriorService

logger = logging.getLogger(__name__)


class RankingService:
    """Rank articles using relevance, freshness, priors, and boosts."""

    def __init__(self, nlp_provider: Callable[[], Any]) -> None:
        self._nlp_provider = nlp_provider

    @staticmethod
    def _freshness_score(published_date_str: str, half_life_days: float) -> float:
        """Exponential freshness decay: 1.0 when new, 0.5 at half-life."""
        if not published_date_str:
            return 0.5

        for fmt in (
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                dt = datetime.strptime(published_date_str, fmt)
                break
            except ValueError:
                continue
        else:
            return 0.5

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        age_days = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400)
        return math.pow(0.5, age_days / half_life_days)

    @staticmethod
    def _relevance_score(article: dict[str, Any], keywords: list[str]) -> float:
        """Normalized keyword match count against title+summary (0.0-1.0)."""
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        matches = sum(1 for kw in keywords if kw.lower() in text)
        return min(matches / 10.0, 1.0)

    @staticmethod
    def _category_boost(article: dict[str, Any], ssi_component: str) -> float:
        """Return a small boost (1.0–1.15) when the article's Model2Vec category
        aligns with the requested SSI component.

        This rewards articles whose primary_category maps to the SSI component
        that is currently targeted, nudging them toward the top of the ranking
        without overriding relevance or freshness signals.
        """
        primary_ssi = article.get("primary_ssi_component", "")
        if not primary_ssi or not ssi_component:
            return 1.0
        if primary_ssi == ssi_component:
            return 1.15  # 15% boost for on-target category
        return 1.0

    def rank_articles(
        self,
        articles: list[dict[str, Any]],
        priors: dict[tuple[str, str], FeaturePrior],
        *,
        ssi_component: str = "",
        keywords: list[str] | None = None,
        alpha: float = DEFAULT_RANK_ALPHA,
        freshness_half_life_days: float = FRESHNESS_HALF_LIFE_DAYS,
        use_boost_factors: bool = True,
        extract_themes: bool = True,
    ) -> list[dict[str, Any]]:
        """Re-rank *articles* using relevance, freshness, prior, boosts, and category alignment."""
        kw_list = keywords or []

        if extract_themes:
            try:
                nlp = self._nlp_provider()
                for article in articles:
                    if "themes" not in article:
                        text = f"{article.get('title', '')} {article.get('summary', '')}"
                        article["themes"] = nlp.extract_themes(text[:1000])
            except Exception as exc:
                logger.debug("selection_learning: theme extraction failed (continuing): %s", exc)

        scored: list[tuple[float, dict[str, Any]]] = []
        for article in articles:
            source = article.get("source", "")
            themes = article.get("themes", [])

            rel = self._relevance_score(article, kw_list)
            fresh = self._freshness_score(article.get("published", ""), freshness_half_life_days)
            acc = PriorService.get_acceptance_rate(source, ssi_component, priors)
            base_score = (1.0 - alpha) * (0.5 * rel + 0.5 * fresh) + alpha * acc

            if use_boost_factors:
                boost = PriorService.get_boost_factor(source, ssi_component, themes, priors)
                # Apply category alignment boost from Model2Vec classification
                cat_boost = self._category_boost(article, ssi_component)
                final_score = base_score * boost * cat_boost
                logger.debug(
                    "selection_learning: ranked article '%s' - base=%.3f boost=%.2f cat_boost=%.2f final=%.3f",
                    article.get("title", "")[:50],
                    base_score,
                    boost,
                    cat_boost,
                    final_score,
                )
            else:
                final_score = base_score

            scored.append((final_score, article))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [article for _, article in scored]
