"""
RSS article fetching for the content curator.
Fetches and filters articles from configured RSS feeds.
"""

import feedparser
import logging
import re
import requests

try:
    import trafilatura as _trafilatura
    _TRAFILATURA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TRAFILATURA_AVAILABLE = False

from services.content_curator._config import CURATOR_MAX_PER_FEED, RSS_FEEDS, KEYWORDS

# Model2Vec classification is optional — imported lazily to avoid hard dependency
_classify_articles_fn = None


def _get_batch_classify():
    """Lazily import batch_classify_articles to avoid circular imports and hard deps."""
    global _classify_articles_fn
    if _classify_articles_fn is None:
        try:
            from services.model2vec_service import batch_classify_articles
            _classify_articles_fn = batch_classify_articles
        except Exception:
            _classify_articles_fn = None
    return _classify_articles_fn

logger = logging.getLogger(__name__)


def _looks_facty(text: str) -> bool:
    """Heuristic: does a short text look like it contains a concrete fact?"""
    # numeric signals (dates, metrics, versions)
    has_digit = any(c.isdigit() for c in text)
    # simple version-ish patterns
    has_version = bool(re.search(r"\b\d+\.\d+(\.\d+)?\b", text))
    # year-like patterns
    has_year = bool(re.search(r"\b20(2[0-9]|3[0-9])\b", text))
    # simple 'vX.Y' style
    has_v_prefix = bool(re.search(r"\bv\d+(\.\d+)*\b", text, flags=re.IGNORECASE))

    return has_digit or has_version or has_year or has_v_prefix

def fetch_article_text(url: str, max_chars: int = 3000, spacy_nlp=None) -> str:
    """Fetch a URL and return the article body as plain text.

    Uses trafilatura to extract the main article body (strips nav menus,
    sidebars, cookie banners, etc.) when available.  Falls back to naive
    tag-stripping if trafilatura is not installed or returns empty.

    When spacy_nlp is provided and the article is long enough, uses extractive
    summarization (5 sentences) to surface buried key content rather than
    front-truncating. Falls back to truncation if summarization returns empty.
    Used when RSS has no summary, or as a static fallback.
    """
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        html = resp.text

        # --- primary: trafilatura extracts clean article body ---
        text = ""
        if _TRAFILATURA_AVAILABLE:
            text = _trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                no_fallback=False,
            ) or ""
            if text:
                logger.debug("trafilatura extracted %d chars from %s", len(text), url)

        # --- fallback: naive HTML tag stripping ---
        if not text:
            html = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", " ", html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            logger.debug("trafilatura returned empty; using tag-strip fallback (%d chars) from %s", len(text), url)

        text_stripped = text.strip()
        if len(text_stripped) < 200:
            if _looks_facty(text_stripped):
                logger.debug(
                    "[fetch_article_text] Short but facty-looking article (%d chars), keeping: %s",
                    len(text_stripped),
                    url,
                )
            else:
                logger.info(
                    "[fetch_article_text] Skipping article (too short, %d chars, not facty): %s",
                    len(text_stripped),
                    url,
                )
                return ""

        # --- nav/blob detection on the *start* of the article only ---
        nav_sample = text_stripped[:800]  # only inspect the first ~800 chars
        letters = [c for c in nav_sample if c.isalpha()]
        is_nav_blob = False
        if letters:
            upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
            if upper_ratio > 0.90:
                is_nav_blob = True
                logger.debug(
                    "[fetch_article_text] High uppercase ratio in intro (%.2f%%) for %s",
                    upper_ratio * 100,
                    url,
                )

        # If it looks like nav, we *try* summarization first (if available) instead of dropping immediately.
        if is_nav_blob and spacy_nlp and len(text_stripped) > 500:
            try:
                summary = spacy_nlp.summarize_article(
                    article_text=text_stripped[:max_chars],
                    max_sentences=5,
                    focus_entities=True,
                )
                if summary and len(summary.strip()) >= 200:
                    logger.debug(
                        "spaCy summary rescued nav-heavy article (%d -> %d chars) for %s",
                        len(text_stripped),
                        len(summary),
                        url,
                    )
                    return summary
                else:
                    logger.info(
                        "[fetch_article_text] Skipping nav blob after summarization (len=%d): %s",
                        len(summary or ""),
                        url,
                    )
                    return ""
            except Exception as _exc:
                logger.debug("spaCy summarization failed on nav blob, skipping article: %s", _exc)
                return ""

        # If is_nav_blob but no spacy_nlp or too short, keep current behavior (skip)
        if is_nav_blob:
            logger.info(
                "[fetch_article_text] Skipping article (nav blob, %.2f%% uppercase in intro): %s",
                upper_ratio * 100,
                url,
            )
            return ""

        if spacy_nlp and len(text) > 500:
            try:
                summary = spacy_nlp.summarize_article(
                    article_text=text[:max_chars],
                    max_sentences=5,
                    focus_entities=True,
                )
                if summary:
                    logger.debug("spaCy summarized fallback fetch from %d to %d chars", len(text[:max_chars]), len(summary))
                    return summary
            except Exception as _exc:
                logger.debug("spaCy summarization failed in fetch_article_text, using truncation: %s", _exc)
        return text[:max_chars]
    except Exception as exc:
        logger.debug("Could not fetch article text from %s: %s", url, exc)
        return ""


def _attach_classifications(articles: list) -> None:
    """Batch-classify articles and attach category metadata in-place.

    Each article dict gains two optional keys:
      - ``primary_category``: str — top predicted category name (or "")
      - ``primary_ssi_component``: str — SSI component mapped from category (or "")

    Classification failures are silently swallowed so the pipeline continues.
    """
    if not articles:
        return
    fn = _get_batch_classify()
    if fn is None:
        return
    try:
        results = fn(articles, top_k=1)
        for article, result in zip(articles, results):
            article["primary_category"] = result.primary_category
            article["primary_ssi_component"] = result.primary_ssi_component
            if result.primary_category:
                logger.debug(
                    "  🏷️  [%s] → %s (%.3f)",
                    article.get("title", "")[:50],
                    result.primary_category,
                    result.top_confidence,
                )
    except Exception as exc:
        logger.debug("Model2Vec: batch classification failed (continuing): %s", exc)


def fetch_relevant_articles(
    max_per_feed: int = CURATOR_MAX_PER_FEED,
    spacy_nlp=None,
    classify: bool = False,
) -> list:
    """Fetch recent articles matching our keyword list.

    When *classify* is True (or CURATE_CLASSIFY env var is set), articles are
    batch-classified by Model2Vec and gain ``primary_category`` /
    ``primary_ssi_component`` metadata keys.
    """
    import os
    _classify = classify or os.getenv("CURATE_CLASSIFY", "false").lower() == "true"

    articles = []
    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:max_per_feed]:
                title   = str(entry.get("title") or "")
                summary = str(entry.get("summary") or "")
                link    = str(entry.get("link") or "")
                content = f"{title} {summary}".lower()

                if any(kw.lower() in content for kw in KEYWORDS):
                    if len(summary.strip()) < 100 and link:
                        logger.debug("RSS summary empty for '%s' — fetching URL", title[:50])
                        summary = fetch_article_text(link, spacy_nlp=spacy_nlp)
                    articles.append({
                        "source":    feed_info["name"],
                        "title":     title,
                        "summary":   summary,
                        "link":      link,
                        "published": entry.get("published", ""),
                        "primary_category": "",
                        "primary_ssi_component": "",
                    })
                    logger.info("  🧲 Matched: [%s] %s", feed_info["name"], title[:60])
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", feed_info["name"], exc)
    logger.info("🗞️  Found %d relevant articles across %d feeds", len(articles), len(RSS_FEEDS))

    if _classify and articles:
        logger.info("🏷️  Classifying %d articles via Model2Vec…", len(articles))
        _attach_classifications(articles)

    return articles
