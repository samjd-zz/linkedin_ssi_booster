"""Select Rei song themes, unique titles, and lyric language."""

import json
import logging
import random
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.avatar_intelligence._models import ExtractedEvidenceFact

from services.content_curator._text_utils import looks_like_nav_chrome
from services.rei_toei._models import Theme
from services.rei_toei._theme_quality import (
    display_theme_name,
    has_named_evidence,
    normalize_theme_candidate,
)

logger = logging.getLogger(__name__)


def _normalize_title(value: str) -> str:
    """Normalize a title string for uniqueness comparisons."""
    return re.sub(r"\W+", " ", value.lower()).strip()


REI_TITLE_HISTORY_FILE = "title_history.jsonl"
REI_TITLE_HISTORY_MAX = 200


def record_rei_title(output_dir: Path, title: str, theme: str = "", preview: bool = False) -> None:
    """Append a generated concept title so preview and console runs also count as recent."""
    cleaned = " ".join(title.split()).strip()
    if not cleaned:
        return
    history_path = output_dir / REI_TITLE_HISTORY_FILE
    entry = {
        "title": cleaned,
        "theme": theme,
        "preview": preview,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        lines = history_path.read_text(encoding="utf-8").splitlines() if history_path.exists() else []
        lines.append(json.dumps(entry, ensure_ascii=False))
        history_path.write_text("\n".join(lines[-REI_TITLE_HISTORY_MAX:]) + "\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not record Rei title history at %s: %s", history_path, exc)


def _load_title_history(output_dir: Path) -> List[str]:
    """Return history titles newest first."""
    history_path = output_dir / REI_TITLE_HISTORY_FILE
    try:
        lines = history_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    titles: List[str] = []
    for line in reversed(lines):
        try:
            title = str(json.loads(line).get("title", "")).strip()
        except (json.JSONDecodeError, AttributeError):
            continue
        if title:
            titles.append(title)
    return titles


def load_recent_rei_titles(output_dir: Path, limit: int = 20) -> List[str]:
    """Load recent titles from the title history log and saved Suno artifacts."""
    if not output_dir.exists():
        return []

    titles: List[str] = []
    seen: set[str] = set()

    def _add(title: str) -> None:
        key = _normalize_title(title)
        if key and key not in seen:
            seen.add(key)
            titles.append(title)

    for title in _load_title_history(output_dir):
        if len(titles) >= limit:
            return titles
        _add(title)

    for path in sorted(output_dir.glob("*_suno.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        if len(titles) >= limit:
            break
        try:
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            title = str(payload.get("title", "")).strip()
            if title:
                _add(title)
        except (OSError, json.JSONDecodeError, TypeError, AttributeError):
            continue
    return titles


def load_recent_rei_themes(output_dir: Path, limit: int = 20) -> List[str]:
    """Load recently used theme names from history and saved Suno artifacts."""
    if limit <= 0 or not output_dir.exists():
        return []

    themes: List[str] = []
    seen: set[str] = set()

    def _add(theme: str) -> None:
        cleaned = " ".join(theme.split()).strip()
        key = _normalize_title(cleaned)
        if cleaned and key and key not in seen:
            seen.add(key)
            themes.append(cleaned)

    history_path = output_dir / REI_TITLE_HISTORY_FILE
    try:
        lines = history_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for line in reversed(lines):
        try:
            theme = str(json.loads(line).get("theme", "")).strip()
        except (json.JSONDecodeError, AttributeError):
            continue
        if theme:
            _add(theme)
            if len(themes) >= limit:
                return themes

    for path in sorted(output_dir.glob("*_suno.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        if len(themes) >= limit:
            break
        try:
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            theme = str(payload.get("theme", "")).strip()
            if theme:
                _add(theme)
        except (OSError, json.JSONDecodeError, TypeError, AttributeError):
            continue
    return themes


def ensure_unique_rei_title(title: str, recent_titles: Optional[List[str]] = None) -> str:
    """Ensure generated title is unique versus recent Rei titles."""
    cleaned_title = " ".join(title.split()).strip() or "Untitled Protocol"
    if not recent_titles:
        return cleaned_title

    normalized_recent = {_normalize_title(t) for t in recent_titles if t}
    if _normalize_title(cleaned_title) not in normalized_recent:
        return cleaned_title

    suffix_options = ["Signal", "Vector", "Pulse", "Drift", "Phase", "Delta", "Echo"]
    for suffix in suffix_options:
        candidate = f"{cleaned_title} {suffix}"
        if _normalize_title(candidate) not in normalized_recent:
            return candidate

    stamp = datetime.now().strftime("%H%M")
    return f"{cleaned_title} {stamp}"


def resolve_lyric_language(
    configured_language: str = "bilingual",
    japanese_probability: float = 0.25,
    random_value: Optional[float] = None,
) -> str:
    """Resolve the language used for one song's lyrics.

    Explicit ``english`` and ``japanese`` modes are deterministic. ``bilingual``
    means the same song intentionally mixes Japanese and English lines.
    ``japanese_probability`` is still validated and used later as an approximate
    Japanese-line ratio target for bilingual generation.

    ``random_value`` is retained for backward-compatible call signatures.
    """
    language = configured_language.strip().lower()
    if language in {"english", "japanese"}:
        return language
    if language != "bilingual":
        raise ValueError("configured_language must be english, japanese, or bilingual")
    if not 0.0 <= japanese_probability <= 1.0:
        raise ValueError("japanese_probability must be between 0.0 and 1.0")
    return "bilingual"


def choose_diverse_theme(
    themes: List[Theme],
    recent_theme_names: Optional[List[str]] = None,
    repeat_penalty: float = 0.1,
    jitter_ratio: float = 0.1,
) -> Theme:
    """Choose a theme with weighted randomness and anti-repeat penalties."""
    if not themes:
        raise ValueError("themes must not be empty")

    recent_set = {_normalize_title(t) for t in (recent_theme_names or []) if t and t.strip()}
    fresh_themes = [
        theme for theme in themes
        if _normalize_title(theme.name) not in recent_set
    ]
    candidates = fresh_themes or themes
    if fresh_themes and len(fresh_themes) < len(themes):
        logger.debug("Excluded %d recently selected themes", len(themes) - len(fresh_themes))

    clamped_penalty = max(0.01, min(1.0, repeat_penalty))
    clamped_jitter = max(0.0, min(0.5, jitter_ratio))

    weights: List[float] = []
    for theme in candidates:
        base = max(0.05, float(theme.frequency) * float(theme.recency_score))
        if _normalize_title(theme.name) in recent_set:
            base *= clamped_penalty
        # Add subtle jitter so ties do not repeatedly collapse to the same candidate.
        if clamped_jitter > 0:
            base *= random.uniform(1.0 - clamped_jitter, 1.0 + clamped_jitter)
        weights.append(max(base, 0.01))

    return random.choices(candidates, weights=weights, k=1)[0]


def extract_themes(
    extracted_facts: "List[ExtractedEvidenceFact]",
    limit: int = 10
) -> List[Theme]:
    """
    Analyze extracted knowledge facts to identify recurring themes suitable for music.

    Follows the same pattern as curator.py: accepts a flat list of ExtractedEvidenceFact
    objects (the normalized form returned by normalize_extracted_facts()), not the raw
    ExtractedKnowledgeGraph container.
    """
    logger.info(f"Extracting themes from {len(extracted_facts)} facts")

    concept_groups: Dict[str, List[Any]] = defaultdict(list)
    entity_terms: set[str] = set()

    for fact in extracted_facts:
        statement = getattr(fact, "statement", "")
        # Skip facts whose statement is scraped nav/share chrome — every tag on
        # such a fact is headline-rail noise, not a real concept.
        if not isinstance(statement, str) or not statement.strip() or looks_like_nav_chrome(statement):
            continue

        concepts = set()
        
        for tag in (getattr(fact, "tags", []) or []):
            normalized = normalize_theme_candidate(tag)
            if normalized:
                concepts.add(normalized)

        for entity in (getattr(fact, "entities", []) or []):
            normalized = normalize_theme_candidate(entity)
            if normalized:
                concepts.add(normalized)
                entity_terms.add(normalized)

        for concept in concepts:
            concept_groups[concept].append(fact)

    logger.info(f"Identified {len(concept_groups)} unique concepts")
    # Common words ("scale", "training") are not song themes; keep concepts
    # their own statements use as names (Java, LSTM, フジロック) or as phrases.
    generic = [
        concept for concept, facts in concept_groups.items()
        if not has_named_evidence(
            concept, [getattr(fact, "statement", "") for fact in facts], entity_terms
        )
    ]
    for concept in generic:
        del concept_groups[concept]
    if generic:
        logger.info("Dropped %d generic or unsupported concepts", len(generic))
    import math

    now = datetime.now()
    scored_concepts: List[tuple[str, int, float, List[str]]] = []

    for concept, facts in concept_groups.items():
        frequency = len(facts)
        recency_scores = []
        
        for fact in facts:
            extracted_at = getattr(fact, "extracted_at", None)
            if extracted_at:
                try:
                    extracted_dt = datetime.fromisoformat(extracted_at.replace("Z", "+00:00"))
                    days_ago = (now - extracted_dt.replace(tzinfo=None)).days
                    # Exponential decay over a 30-day window
                    recency = math.exp(-days_ago / 30.0)
                    recency_scores.append(recency)
                except (ValueError, TypeError):
                    recency_scores.append(0.5)
            else:
                recency_scores.append(0.5)

        avg_recency = sum(recency_scores) / len(recency_scores) if recency_scores else 0.5
        evidence_ids = [
            getattr(fact, "evidence_id", None) or getattr(fact, "source_fact_id", "")
            for fact in facts
        ]

        scored_concepts.append((concept, frequency, avg_recency, evidence_ids))
    
    scored_concepts.sort(key=lambda x: x[1] * x[2], reverse=True)
    
    themes = []
    from .service import get_rei_service
    rei_service = get_rei_service()
    
    for i, (concept, frequency, recency, evidence_ids) in enumerate(scored_concepts[:limit]):
        theme_id = f"theme_{concept.replace(' ', '_').replace('-', '_')[:20]}_{i+1:02d}"
        suggested_bpm = None
        suggested_mood = None
        
        if any(kw in concept for kw in ["performance", "optimization", "low-level", "system", "kernel"]):
            suggested_mood = "playful_technical"
            suggested_bpm = rei_service.get_default_bpm(suggested_mood)
        elif any(kw in concept for kw in ["ai", "machine learning", "neural", "model"]):
            suggested_mood = "fun_brooding"
            suggested_bpm = rei_service.get_default_bpm(suggested_mood)
        elif any(kw in concept for kw in ["async", "concurrent", "parallel", "distributed"]):
            suggested_mood = "bratty_bounce"
            suggested_bpm = rei_service.get_default_bpm(suggested_mood)
        
        theme = Theme(
            id=theme_id,
            name=display_theme_name(
                concept, [getattr(fact, "statement", "") for fact in concept_groups[concept]]
            ),
            technical_concepts=[concept],
            evidence_ids=evidence_ids[:50],
            frequency=frequency,
            recency_score=round(recency, 3),
            suggested_bpm=suggested_bpm,
            suggested_mood=suggested_mood
        )
        themes.append(theme)
    
    logger.info(f"Extracted {len(themes)} themes (top {limit})")
    return themes
