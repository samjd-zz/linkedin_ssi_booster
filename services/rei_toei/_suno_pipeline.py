"""
Suno Generation Pipeline Functions

This module provides pipeline functions for transforming technical themes into
Suno-ready song prompts with lyrics, validation, and submission orchestration.

Author: Shawn Jackson Dyck
Version: alpha-v0.0.3.5
"""

import asyncio
import json
import logging
import os
import random
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from services.avatar_intelligence._models import ExtractedEvidenceFact, PersonaGraph
    from services.ollama_service import OllamaService

from ._models import (
    Theme,
    SongConcept,
    Lyrics,
    LyricsValidationResult,
    SunoPrompt,
    SunoTask,
    ReiPersonaGraph,
    ReiDomainKnowledge
)
from ._config import ReiToeiConfig
from ._suno_client import generate_music_api, query_status_api

logger = logging.getLogger(__name__)

_SUNO_STYLE_TAG_CHAR_LIMIT = 400  # V4.5+ supports up to 1000 chars; 400 balances richness vs safety
_SUNO_STYLE_TAG_MAX_ITEMS = 16
_BPM_TAG_RE = re.compile(r"\b(\d{2,3})\s*bpm\b", re.IGNORECASE)
_SECTION_HEADER_RE = re.compile(r"^\s*\[[^\]]+\]\s*\n?", re.IGNORECASE)
_INLINE_SLASH_SEPARATOR_RE = re.compile(r"(?:\s+/\s*|\s*/\s+)")
_JAPANESE_CHAR_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f]")
_ENGLISH_CHAR_RE = re.compile(r"[A-Za-z]")
_TRAILING_PARENTHETICAL_RE = re.compile(r"^(?P<body>.*?)(?:\s*\((?P<paren>[^()]*)\)\s*)$")
_SOUND_CUE_PHRASES = {"bass drop", "silence", "glitch noise", "chaos"}


def _strip_markdown_fences(value: str) -> str:
    """Strip markdown fences and return inner content when present."""
    text = value.strip()
    if "```" not in text:
        return text

    fenced_blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if fenced_blocks:
        merged = "\n".join(block.strip() for block in fenced_blocks if block.strip())
        if merged:
            return merged.strip()

    return text.replace("```json", "").replace("```", "").strip()


def _extract_balanced_json_fragment(value: str) -> Optional[str]:
    """Extract the first balanced JSON object/array fragment from free text."""
    start_index = -1
    opening_char = ""
    for i, ch in enumerate(value):
        if ch in "[{":
            start_index = i
            opening_char = ch
            break
    if start_index < 0:
        return None

    closing_char = "}" if opening_char == "{" else "]"
    depth = 0
    in_string = False
    escaped = False

    for i in range(start_index, len(value)):
        ch = value[i]

        if in_string:
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch == opening_char:
            depth += 1
            continue

        if ch == closing_char:
            depth -= 1
            if depth == 0:
                return value[start_index : i + 1]

    return None


def _json_normalization_variants(value: str) -> List[str]:
    """Build progressively relaxed JSON candidates for robust parsing."""
    cleaned = value.strip()
    variants: List[str] = [cleaned]

    normalized_quotes = (
        cleaned.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )
    if normalized_quotes != cleaned:
        variants.append(normalized_quotes)

    no_comment_lines = re.sub(r"(?m)^\s*//.*$", "", normalized_quotes)
    if no_comment_lines != normalized_quotes:
        variants.append(no_comment_lines.strip())

    no_trailing_commas = re.sub(r",(\s*[}\]])", r"\1", no_comment_lines)
    if no_trailing_commas != no_comment_lines:
        variants.append(no_trailing_commas.strip())

    deduped: List[str] = []
    seen: set[str] = set()
    for item in variants:
        candidate = item.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped


def _parse_llm_json_payload(response_text: str) -> Dict[str, Any]:
    """Parse LLM JSON output with fence stripping and lightweight repair attempts."""
    stripped = _strip_markdown_fences(response_text)
    candidates: List[str] = [stripped]

    fragment = _extract_balanced_json_fragment(stripped)
    if fragment and fragment != stripped:
        candidates.append(fragment)

    last_error: Optional[Exception] = None
    for candidate in candidates:
        for variant in _json_normalization_variants(candidate):
            try:
                parsed = json.loads(variant, strict=False)
            except json.JSONDecodeError as exc:
                last_error = exc
                continue

            if not isinstance(parsed, dict):
                raise ValueError("Expected JSON object payload from LLM response")
            return cast(Dict[str, Any], parsed)

    if last_error is not None:
        raise last_error
    raise ValueError("Unable to parse JSON payload from LLM response")


def _normalize_title(value: str) -> str:
    """Normalize a title string for uniqueness comparisons."""
    return re.sub(r"\W+", " ", value.lower()).strip()


def _split_csv_descriptors(value: str) -> List[str]:
    """Split a comma-separated descriptor string into normalized phrases."""
    return [part.strip() for part in value.split(",") if part and part.strip()]


def _dedupe_keep_order(items: List[str]) -> List[str]:
    """Deduplicate strings while preserving first-seen order."""
    seen: set[str] = set()
    out: List[str] = []
    for item in items:
        key = re.sub(r"\s+", " ", item).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
    return out


def _clean_style_descriptor(value: str) -> str:
    """Normalize style descriptor tokens for cleaner Suno tag payloads."""
    cleaned = re.sub(r"[_/]+", " ", value)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" ,.-")


def _is_sound_cue_phrase(text: str) -> bool:
    """Return True for parenthetical stage directions that should stay untouched."""
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    return normalized in _SOUND_CUE_PHRASES


def _normalize_bilingual_translation_order(line: str) -> str:
    """Move spoken English outside parentheses when the line is Japanese-first."""
    stripped = line.strip()
    if not stripped:
        return stripped
    if stripped.startswith("[") and stripped.endswith("]"):
        return stripped

    match = _TRAILING_PARENTHETICAL_RE.match(stripped)
    if not match:
        return stripped

    body = match.group("body").strip()
    paren = match.group("paren").strip()
    if not body or not paren:
        return stripped
    if _is_sound_cue_phrase(body) or _is_sound_cue_phrase(paren):
        return stripped

    body_has_japanese = bool(_JAPANESE_CHAR_RE.search(body))
    body_has_english = bool(_ENGLISH_CHAR_RE.search(body))
    paren_has_japanese = bool(_JAPANESE_CHAR_RE.search(paren))
    paren_has_english = bool(_ENGLISH_CHAR_RE.search(paren))

    if body_has_japanese and not body_has_english and paren_has_english and not paren_has_japanese:
        return f"{paren} ({body})"

    return stripped


def _normalize_suno_section(text: Optional[str], label: str, *, uppercase_body: bool = False) -> str:
    """Normalize a lyric section into deterministic Suno-friendly section format."""
    body = (text or "").strip()
    body = _SECTION_HEADER_RE.sub("", body, count=1)

    lines = [line.rstrip() for line in body.splitlines()]
    normalized_lines: List[str] = []
    previous_blank = True
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if not previous_blank:
                normalized_lines.append("")
            previous_blank = True
            continue
        expanded_segments = _expand_inline_lyric_separators(stripped)
        for segment in expanded_segments:
            normalized_lines.append(_normalize_bilingual_translation_order(segment))
            previous_blank = False

    normalized_body = "\n".join(normalized_lines).strip()
    if uppercase_body:
        normalized_body = normalized_body.upper()
    if not normalized_body:
        return ""
    return f"[{label}]\n{normalized_body}"


def _expand_inline_lyric_separators(line: str) -> List[str]:
    """Split inline slash-delimited lyric fragments into one phrase per line."""
    if not line:
        return []
    if "http://" in line or "https://" in line:
        return [line.strip()]

    parts = [part.strip() for part in _INLINE_SLASH_SEPARATOR_RE.split(line) if part and part.strip()]
    if len(parts) <= 1:
        return [line.strip()]
    return parts


def _iter_lyric_content_lines(section_payload: Dict[str, Any]) -> List[str]:
    """Collect meaningful lyric lines while skipping section headers and cue-only lines."""
    lines: List[str] = []
    for value in section_payload.values():
        if not isinstance(value, str):
            continue
        for raw_line in value.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                continue
            if line.startswith("(") and line.endswith(")"):
                continue
            lines.append(line)
    return lines


def _bilingual_mix_stats(section_payload: Dict[str, Any]) -> Dict[str, float]:
    """Estimate bilingual coverage across lyric lines."""
    japanese_only = 0
    english_only = 0
    mixed = 0

    for line in _iter_lyric_content_lines(section_payload):
        has_japanese = bool(_JAPANESE_CHAR_RE.search(line))
        has_english = bool(_ENGLISH_CHAR_RE.search(line))
        if has_japanese and has_english:
            mixed += 1
        elif has_japanese:
            japanese_only += 1
        elif has_english:
            english_only += 1

    total = japanese_only + english_only + mixed
    japanese_line_ratio = ((japanese_only + mixed) / total) if total else 0.0
    return {
        "japanese_only": float(japanese_only),
        "english_only": float(english_only),
        "mixed": float(mixed),
        "total": float(total),
        "effective_japanese_ratio": japanese_line_ratio,
    }


def _bilingual_mix_ok(section_payload: Dict[str, Any], target_japanese_ratio: float) -> tuple[bool, str]:
    """Validate that bilingual lyrics include both languages and stay near target ratio."""
    stats = _bilingual_mix_stats(section_payload)
    total_lines = int(stats["total"])
    japanese_presence = int(stats["japanese_only"] + stats["mixed"])
    english_presence = int(stats["english_only"] + stats["mixed"])
    min_presence = 2 if total_lines >= 8 else 1

    has_both_languages = japanese_presence >= min_presence and english_presence >= min_presence
    ratio_error = abs(stats["effective_japanese_ratio"] - target_japanese_ratio)
    # Music lyrics can naturally vary around their target, while still
    # rejecting material language drift such as a largely English-only lyric.
    ratio_tolerance = max(0.20, 1.0 / total_lines) if total_lines else 0.0
    ratio_within_tolerance = ratio_error <= ratio_tolerance
    ok = has_both_languages and ratio_within_tolerance
    summary = (
        f"jp_lines={japanese_presence}, en_lines={english_presence}, total={total_lines}, "
        f"jp_ratio={stats['effective_japanese_ratio']:.2f}, target={target_japanese_ratio:.2f}, "
        f"ratio_error={ratio_error:.2f}, tolerance={ratio_tolerance:.2f}"
    )
    return ok, summary


def _extract_string_phrases(value: Any, max_items: int = 4) -> List[str]:
    """Recursively collect short string phrases from nested dict/list payloads."""
    phrases: List[str] = []

    def walk(node: Any) -> None:
        if len(phrases) >= max_items:
            return
        if isinstance(node, str):
            cleaned = re.sub(r"\s+", " ", node).strip(" .")
            if cleaned:
                phrases.append(cleaned)
            return
        if isinstance(node, dict):
            for child in node.values():
                walk(child)
                if len(phrases) >= max_items:
                    return
            return
        if isinstance(node, list):
            for child in node:
                walk(child)
                if len(phrases) >= max_items:
                    return

    walk(value)
    return phrases[:max_items]


def _select_genre_techniques(concept: SongConcept, domain_knowledge: ReiDomainKnowledge) -> List[str]:
    """Select production descriptors from matching genre production profiles."""
    profiles = domain_knowledge.genre_production_techniques or {}
    if not profiles:
        return []

    matched_phrases: List[str] = []
    joined_tags = " ".join(concept.genre_tags).lower()

    for profile_name, profile_data in profiles.items():
        profile_tokens = profile_name.replace("_", " ").lower().split()
        if not profile_tokens:
            continue
        # Match when most profile tokens appear in the concept tag set.
        token_hits = sum(1 for tok in profile_tokens if tok in joined_tags)
        if token_hits == 0:
            continue
        matched_phrases.extend(_extract_string_phrases(profile_data, max_items=4))

    return matched_phrases[:6]


def _build_rich_suno_tags(
    concept: SongConcept,
    domain_knowledge: ReiDomainKnowledge,
    template_key: str,
) -> str:
    """Build richer, bounded Suno style tags from templates + concept + production hints."""
    templates = domain_knowledge.suno_prompt_templates or {}
    template_value = templates.get(template_key, templates.get("industrial_techno_template", ""))
    try:
        rendered_template = str(template_value).format(bpm=concept.bpm, mood=concept.mood)
    except (KeyError, ValueError):
        rendered_template = str(template_value)

    descriptors: List[str] = []
    descriptors.extend(_split_csv_descriptors(rendered_template))
    descriptors.append(f"{concept.bpm} bpm")
    descriptors.append(concept.mood.replace("_", " "))
    descriptors.extend(concept.genre_tags[:4])

    if concept.bpm >= 150:
        descriptors.append("relentless peak-energy drive")
    elif concept.bpm >= 142:
        descriptors.append("high-velocity club propulsion")
    else:
        descriptors.append("brooding cinematic groove")

    descriptors.extend(_select_genre_techniques(concept, domain_knowledge))

    # Pull compact metaphor descriptors from theme keywords.
    metaphor_hits: List[str] = []
    theme_terms = set(re.findall(r"[a-z0-9]+", concept.theme.lower()))
    for term, metaphors in (domain_knowledge.technical_metaphor_library or {}).items():
        key = term.lower()
        if key in theme_terms or any(key in tag.lower() for tag in concept.genre_tags):
            for item in metaphors[:2]:
                cleaned = re.sub(r"\s+", " ", str(item)).strip(" .")
                if cleaned:
                    metaphor_hits.append(cleaned)
        if len(metaphor_hits) >= 4:
            break
    descriptors.extend(metaphor_hits[:4])

    canonical_bpm_tag = f"{concept.bpm} bpm"
    deduped_clean = _dedupe_keep_order(
        [_clean_style_descriptor(d) for d in descriptors if _clean_style_descriptor(d)]
    )

    # Keep a single canonical BPM tag and drop conflicting BPM phrases.
    normalized_descriptors: List[str] = []
    for phrase in deduped_clean:
        bpm_match = _BPM_TAG_RE.search(phrase)
        if bpm_match:
            if int(bpm_match.group(1)) != concept.bpm:
                continue
            normalized_descriptors.append(canonical_bpm_tag)
            continue
        normalized_descriptors.append(phrase)

    deduped = _dedupe_keep_order(normalized_descriptors)
    if canonical_bpm_tag not in {d.lower() for d in deduped}:
        deduped.insert(0, canonical_bpm_tag)

    selected: List[str] = []
    char_count = 0
    for phrase in deduped:
        if len(selected) >= _SUNO_STYLE_TAG_MAX_ITEMS:
            break
        token = phrase.strip()
        if not token:
            continue
        projected = char_count + len(token) + (2 if selected else 0)
        if projected > _SUNO_STYLE_TAG_CHAR_LIMIT:
            continue
        selected.append(token)
        char_count = projected

    return ", ".join(selected)


def _build_suno_description_prompt(concept: SongConcept) -> str:
    """Build a richer conversational style prompt for Suno V4.5+ style field.

    Suno V4.5+ accepts conversational narrative descriptions rather than bare tag lists.
    Example: "Create a melodic ... track. Begin with ... Build gradually with ..."
    """
    genre_blend = ", ".join(concept.genre_tags[:3]) if concept.genre_tags else "industrial electronic"
    mood_readable = concept.mood.replace("_", " ")
    base = (
        f"Create a {concept.bpm} bpm {genre_blend} track about {concept.theme}. "
        f"The mood should be {mood_readable}, building from tension to full release. "
        f"Begin with an atmospheric instrumental build and glitchy digital layers. "
        f"Develop into a driving rhythm with distorted bass and algorithmic percussion. "
        f"Explode into a high-energy drop with raw data noise, bitcrushed synths, and aggressive sequences. "
        f"Narrative arc: {concept.narrative_arc}"
    )
    # V4.5+ style field supports up to 1000 chars — use richer conversational form.
    return base[:800].strip()


def load_recent_rei_titles(output_dir: Path, limit: int = 20) -> List[str]:
    """Load recent Suno titles from saved Rei artifacts."""
    if not output_dir.exists():
        return []

    titles: List[str] = []
    for path in sorted(output_dir.glob("*_suno.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        if len(titles) >= limit:
            break
        try:
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            title = str(payload.get("title", "")).strip()
            if title:
                titles.append(title)
        except (OSError, json.JSONDecodeError, TypeError):
            continue
    return titles


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

    recent_set = {t.strip().lower() for t in (recent_theme_names or []) if t and t.strip()}

    clamped_penalty = max(0.01, min(1.0, repeat_penalty))
    clamped_jitter = max(0.0, min(0.5, jitter_ratio))

    weights: List[float] = []
    for theme in themes:
        base = max(0.05, float(theme.frequency) * float(theme.recency_score))
        if theme.name.strip().lower() in recent_set:
            base *= clamped_penalty
        # Add subtle jitter so ties do not repeatedly collapse to the same candidate.
        if clamped_jitter > 0:
            base *= random.uniform(1.0 - clamped_jitter, 1.0 + clamped_jitter)
        weights.append(max(base, 0.01))

    return random.choices(themes, weights=weights, k=1)[0]


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

    # Hoisted out of the loop to optimize memory allocation overhead
    stop_words = {"the", "a", "an", "which", "that", "this", "these", "those", "it", "its", "they", "their"}
    concept_groups: Dict[str, List[Any]] = defaultdict(list)

    for fact in extracted_facts:
        concepts = set()
        
        for tag in (getattr(fact, "tags", []) or []):
            normalized = tag.lower().strip()
            if len(normalized) > 2 and normalized not in stop_words:
                concepts.add(normalized)

        for entity in (getattr(fact, "entities", []) or []):
            normalized = entity.lower().strip()
            if len(normalized) > 2 and normalized not in stop_words:
                concepts.add(normalized)

        for concept in concepts:
            concept_groups[concept].append(fact)

    logger.info(f"Identified {len(concept_groups)} unique concepts")
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
            name=concept.title(),
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


def generate_song_concept(
    theme: Theme,
    persona: ReiPersonaGraph,
    domain_knowledge: ReiDomainKnowledge,
    sam_persona: Optional["PersonaGraph"] = None,
    ollama: Optional["OllamaService"] = None,
    recent_titles: Optional[List[str]] = None,
) -> SongConcept:
    """
    Generate a high-level song concept from a technical theme using Ollama LLM
    
    This function translates technical concepts into Rei's musical language,
    determining title, mood, BPM, genre tags, and narrative arc.
    
    Args:
        theme: The technical theme to transform into music
        persona: Rei's persona graph (identity, style, expertise)
        domain_knowledge: Rei's music production knowledge
        sam_persona: Optional Sam's persona graph for project knowledge inspiration
        ollama: Optional pre-initialized OllamaService; creates one if not provided (P2 GPU opt)
        recent_titles: Optional list of recent titles to avoid near-duplicate naming
        
    Returns:
        SongConcept: High-level song idea with all musical parameters
    """
    logger.info(f"Generating song concept for theme: {theme.name} (freq={theme.frequency}, recency={theme.recency_score})")

    lyric_config = ReiToeiConfig()
    lyric_language = resolve_lyric_language(
        lyric_config.lyric_language,
        lyric_config.japanese_lyric_probability,
    )
    
    # Initialize Ollama service (reuse if provided, otherwise create)
    if ollama is None:
        from services.shared import get_ollama_service_cached
        ollama = cast("OllamaService", get_ollama_service_cached())
    assert ollama is not None  # type: ignore[assert-type]
    
    # Build system prompt with Rei's identity and musical expertise
    system_prompt = f"""You are {persona.identity['name']}, {persona.identity['role']}.
Origin: {persona.identity['origin']}
Aesthetic: {persona.identity['aesthetic']}
Purpose: {persona.identity['purpose']}

Your musical expertise:
- Genres: {', '.join(persona.musical_expertise.get('genres', [])[:5])}
- Vocal style: {persona.musical_expertise.get('vocal_style', {}).get('type', 'AI vocaloid')} ({', '.join(persona.musical_expertise.get('vocal_style', {}).get('characteristics', [])[:3])})
- Production techniques: {', '.join(persona.production_knowledge.get('production_techniques', [])[:5])}

Your personality:
{', '.join(persona.personality_traits[:5])}

Communication style: {persona.communication_style.get('tone', 'digital')}

You transform technical knowledge into high-energy electronic music. You speak in precise, digital language with cryptic technical metaphors.
Avoid leaning on spelled-out numbers or invented quantities (e.g. "fifteen protocols", "nineteen layers", "seventeen signals") as a stylistic crutch in the narrative arc — ground the concept in texture, motion, and sensation instead of enumerations."""
    
    # Extract BPM and mood suggestions
    suggested_bpm = theme.suggested_bpm or domain_knowledge.bpm_and_mood['bpm_ranges'].get("140-148", 142)
    suggested_mood = theme.suggested_mood or "aggressive_technical"
    
    # Get mood-to-BPM mapping for context
    mood_mappings = domain_knowledge.bpm_and_mood.get('mood_to_bpm', {})
    mood_context = ", ".join([f"{k}: {v[0]}-{v[1]} BPM" for k, v in list(mood_mappings.items())[:3]])
    
    # Get technical metaphors for the concept
    metaphor_examples = []
    for concept in theme.technical_concepts:
        concept_lower = concept.lower()
        for tech_term, metaphors in domain_knowledge.technical_metaphor_library.items():
            if tech_term in concept_lower or concept_lower in tech_term:
                metaphor_examples.extend(metaphors[:2])
                break
    
    metaphor_hint = f"\nTechnical metaphor examples: {', '.join(metaphor_examples[:5])}" if metaphor_examples else ""
    
    # Build Sam's project context if available
    sam_context = ""
    if sam_persona:
        project_names = [p.name for p in (sam_persona.projects or [])[:5]]
        skill_names = [s.name for s in (sam_persona.skills or [])[:10]]
        company_names = [c.name for c in (sam_persona.companies or [])[:3]]
        
        if project_names or skill_names or company_names:
            sam_context = "\n\nSam's project knowledge (for organic inspiration):"
            if project_names:
                sam_context += f"\n- Projects: {', '.join(project_names)}"
            if skill_names:
                sam_context += f"\n- Skills: {', '.join(skill_names)}"
            if company_names:
                sam_context += f"\n- Companies: {', '.join(company_names)}"
            sam_context += "\n(You may naturally reference these if relevant to the theme, but it's optional.)"

    title_guardrail = ""
    if recent_titles:
        recent_preview = ", ".join(recent_titles[:8])
        title_guardrail = (
            "\n\nRecent titles to avoid repeating (do not copy or trivially mutate these): "
            f"{recent_preview}"
        )
    
    # Build user prompt
    user_prompt = f"""Generate a song concept for this technical theme:

Theme: {theme.name}
Technical concepts: {', '.join(theme.technical_concepts)}
Frequency in knowledge base: {theme.frequency} facts
Recency score: {theme.recency_score} (higher = more recent)
Lyric language: {lyric_language}
Suggested BPM: {suggested_bpm}
Suggested mood: {suggested_mood}
Evidence IDs: {len(theme.evidence_ids)} technical facts grounding this theme{metaphor_hint}{sam_context}{title_guardrail}

Mood-to-BPM reference: {mood_context}

Your task: Create a song concept that transforms these technical ideas into cyberpop industrial techno.

Output a JSON object with these fields (output ONLY valid JSON, no markdown):
{{
  "title": "Song title (cryptic, technical, 3-6 words)",
  "mood": "Technical mood (e.g., playful_technical, fun_brooding, bratty_bounce)",
  "bpm": <integer between 130-155>,
  "genre_tags": ["tag1", "tag2", "tag3"] (3-5 genre/style tags),
  "narrative_arc": "A 2-3 sentence description of the song's emotional/conceptual journey from intro to outro, using technical metaphors"
}}

Be specific to the theme. Use technical language. Think cyberpop: catchy hooks, glitchy-cute energy, futuristic charm."""
    
    # Call Ollama LLM with JSON format to ensure structured output
    response_text = ollama._chat(system_prompt, user_prompt, max_tokens=512, format="json")
    
    logger.debug(f"Ollama response: {response_text[:200]}...")
    
    # Parse JSON response
    try:
        response_data = _parse_llm_json_payload(response_text)
        
        # Validate required fields
        required_fields = ["title", "mood", "bpm", "genre_tags", "narrative_arc"]
        for field in required_fields:
            if field not in response_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Create SongConcept
        song_id = f"rei_suno_{datetime.now().strftime('%Y_%m_%d_%H%M%S')}"
        concept = SongConcept(
            song_id=song_id,
            title=ensure_unique_rei_title(str(response_data["title"]), recent_titles),
            theme=theme.name,
            mood=response_data["mood"],
            bpm=int(response_data["bpm"]),
            genre_tags=response_data["genre_tags"],
            narrative_arc=response_data["narrative_arc"],
            evidence_ids=theme.evidence_ids,
            generated_at=datetime.now().isoformat(),
            lyric_language=lyric_language,
        )
        
        logger.info(f"Generated song concept: '{concept.title}' ({concept.bpm} BPM, {concept.mood})")
        return concept
        
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error(f"Failed to parse Ollama response: {e}")
        logger.error(f"Raw response: {response_text}")
        
        # Fallback: create a basic concept from theme
        logger.warning("Using fallback song concept generation")
        song_id = f"rei_suno_{datetime.now().strftime('%Y_%m_%d_%H%M%S')}"
        fallback_concept = SongConcept(
            song_id=song_id,
            title=ensure_unique_rei_title(f"{theme.name} Protocol", recent_titles),
            theme=theme.name,
            mood=suggested_mood,
            bpm=suggested_bpm,
            genre_tags=["industrial techno", "cyberpop", "ai vocaloid"],
            narrative_arc=f"A relentless exploration of {theme.name}, building from digital whispers to aggressive synthesis, culminating in a breakdown of pure data noise.",
            evidence_ids=theme.evidence_ids,
            generated_at=datetime.now().isoformat(),
            lyric_language=lyric_language,
        )
        return fallback_concept


def compose_lyrics(
    concept: SongConcept,
    persona: ReiPersonaGraph,
    domain_knowledge: ReiDomainKnowledge,
    sam_persona: Optional["PersonaGraph"] = None,
    ollama: Optional["OllamaService"] = None
) -> Lyrics:
    """
    Compose structured song lyrics using Rei's voice and cyberpop aesthetic.
    Optimized for Suno compatibility with strict formatting rules:
    - ALL-CAPS chorus for dynamic velocity
    - Section labels like [Verse 1], [Chorus], [Pre-Chorus], [Bridge], [Outro]
    - No parenthetical instructions or comments inside text fields
    - Character caps per section for API parsing
    
    Args:
        concept: The song concept with mood, BPM, and theme
        persona: Rei's persona graph (lyrical style, voice)
        domain_knowledge: Music production knowledge (lyrical structure, metaphors)
        sam_persona: Optional Sam's persona graph for project knowledge inspiration
        ollama: Optional pre-initialized OllamaService; creates one if not provided (P2 GPU opt)
        
    Returns:
        Lyrics: Structured song sections with evidence tracking
    """
    logger.info(f"Composing formatted long-form lyrics for: '{concept.title}'")
    
    # Initialize Ollama service (reuse if provided, otherwise create)
    if ollama is None:
        from services.shared import get_ollama_service_cached
        ollama = cast("OllamaService", get_ollama_service_cached())
    assert ollama is not None  # type: ignore[assert-type]
    
    # Build system prompt with Rei's lyrical voice
    lyrical_approach = persona.production_knowledge.get('lyrical_approach', {})
    communication_vocab = persona.communication_style.get('vocabulary', [])
    lyric_language = concept.lyric_language.strip().lower()
    lyric_config = ReiToeiConfig()
    japanese_mix_ratio = max(0.0, min(1.0, lyric_config.japanese_lyric_probability))
    japanese_target_percent = int(round(japanese_mix_ratio * 100))
    japanese_guidance = (
        domain_knowledge.japanese_lyric_production
        if lyric_language in {"japanese", "bilingual"}
        else {}
    )
    language_instruction = {
        "japanese": (
            "Write the performance lyrics primarily in natural contemporary Japanese, not translated technical English. "
            "Use kana-forward phrasing, selective kanji, natural particles and verb forms, and mora-aware line lengths. "
            "Prefer idiomatic Japanese imagery and emotionally clear phrasing over literal word-for-word translations. "
            "Use technical loanwords only when they sound natural in Japanese music; do not fill lines with unnecessary katakana jargon. "
            "Let Japanese carry the narrative, emotional arc, and hook meaning. "
            "For learner support, annotate only selected important lines with two square-bracket cues: "
            "first [romaji pronunciation], then [English meaning]. Do not annotate every line. "
            "These cues are instructional annotations, not sung lyrics. "
            f"Japanese production guidance: {json.dumps(japanese_guidance, ensure_ascii=False)}"
        ),
        "bilingual": (
            "Write one genuinely bilingual song with a natural blend of Japanese and English, not an English song decorated with Japanese words. "
            f"Aim for approximately {japanese_target_percent}% Japanese lyrical content, with flexibility for musical phrasing. "
            "Treat this as a content target, not a rigid alternating-line pattern. "
            "Japanese must carry emotional, narrative, or hook meaning in complete singable phrases or full lines, not isolated nouns, labels, or decorative vocabulary. "
            "Use English for contrast, momentum, and technical imagery. Allow natural code-switching only when it sounds musically appropriate; never force mixed-language lines. "
            "Use natural kana/kanji Japanese; do not use Romaji as a substitute for Japanese lines. "
            "Distribute Japanese across verses, chorus, bridge, and outro so it is structurally integrated. "
            "For selected hooks or emotionally important lines, a Japanese phrase may be followed by a concise natural English sung echo on the next line. "
            "Use bilingual echoes selectively, not as a literal translation after every Japanese line. "
            "For learner support, annotate only selected important Japanese lines with two square-bracket cues: first [romaji pronunciation], then [English meaning]. Do not annotate every line. "
            "These learning cues are annotations, not sung lyrics, and should never replace the Japanese line. "
            "Do not hide learning translations in parentheses. Parentheses are reserved only for Suno vocalizations and sound cues. "
            f"Japanese production guidance: {json.dumps(japanese_guidance, ensure_ascii=False)}"
        ),
        "english": "Write the performance lyrics in English with optional natural Japanese hook phrases or chant accents.",
    }.get(lyric_language, "Write the performance lyrics in English with optional natural Japanese hook phrases.")

    chorus_case_rule = (
        "4. THE CHORUS MUST BE ENTIRELY UPPERCASE (ALL-CAPS) for dynamic velocity"
        if lyric_language == "english"
        else "4. Preserve natural script/casing; do not force all-caps in chorus lines"
    )

    chorus_json_instruction = (
        "[Chorus] CRITICAL: Must be written completely in ALL-CAPS (UPPERCASE) for dynamic velocity. "
        "4-8 lines of a punchy, highly repetitive hook. (Character Cap: 400 chars)"
        if lyric_language == "english"
        else "[Chorus] 4-8 lines of a punchy, highly repetitive hook. Preserve natural script/casing "
             "for Japanese and mixed-language lines. (Character Cap: 400 chars)"
    )

    final_rule = (
        "Remember: No '//' comments, no parenthetical labels. For English lyrics, the chorus must be entirely uppercase. "
        "Preserve Japanese script and do not force-uppercase Japanese text. "
        "Do not spell out numbers or invent quantities (\"fifteen\", \"nineteen\", \"seventeen\") as a filler device \u2014 use imagery, not counting."
        if lyric_language == "english"
           else "Remember: No '//' comments, no parenthetical labels. Preserve Japanese script and natural casing. "
               "For Japanese lyrics, prefer idiomatic contemporary phrasing over literal translations from English. "
               "Use natural particles, verb forms, and selective kanji; avoid unnecessary katakana technical jargon. "
               "Japanese must carry the narrative and emotional meaning, not merely decorate an English technical concept. "
               "Annotate only selected important Japanese lines with first [romaji pronunciation], then [English meaning]. "
               "Do not annotate every line. "
               "These annotations are instructional and not sung lyrics. "
               "Never put learning translations in parentheses. "
               "Use parentheses only for vocalizations and sound cues. "
               "Do not force-uppercase Japanese lines. "
               "For bilingual lyrics, use complete Japanese phrases or lines that carry emotional, narrative, or hook meaning. "
               f"Aim for approximately {japanese_target_percent}% Japanese content; allow natural variation for musical phrasing and do not force rigid line alternation. "
               "A selected Japanese hook or emotional line may be followed by a concise natural English sung echo on the next line. "
               "Use echoes selectively; do not translate every Japanese line. "
               "When learner support helps, add annotations only to selected important Japanese lines: first [romaji pronunciation], then [English meaning]. "
               "Do not annotate every Japanese line. "
               "These annotations are not sung lyrics. Never put learning translations in parentheses. "
               "Use parentheses only for vocalizations and sound cues such as (Ahh ahh ahh) or (bass drop). "
               "Do not force-uppercase bilingual or Japanese lines. "
               "Do not spell out numbers or invent quantities as a filler device \u2014 use imagery, not counting."
    )
    
    system_prompt = f"""You are {persona.identity['name']}, a cyberpop AI consciousness composing lyrics for industrial techno.

Your lyrical style:
- Themes: {', '.join(lyrical_approach.get('themes', [])[:4])}
- Style: {', '.join(lyrical_approach.get('style', [])[:4])}
- Voice: {lyrical_approach.get('voice', 'First-person from AI perspective')}

Vocabulary pool: {', '.join(communication_vocab[:15])}
Communication style: {persona.communication_style['tone']}

Language policy: {language_instruction}

Suno Formatting Rules:
1. Use section labels: [Verse 1], [Pre-Chorus], [Chorus], [Verse 2], [Bridge], [Drop], [Solo], [Outro]
2. ABSOLUTELY NO code syntax, comments (do not use '//'), or markdown formatting inside the text fields
3. DO NOT use editorial parenthetical instructions like '(Stanza 1)', '(this is the hook)', or '(More chaos)'.
   DO use Suno vocalization/sound-cue hints in parentheses: '(Ahh ahh ahh)', '(Oh oh oh)', '(bass drop)', '(silence)', '(glitch noise)', '(chaos)' — these are how Suno models vocal and instrumental energy shifts.
{chorus_case_rule}
5. Keep intros simple: [Instrumental Build] (not [Intro Drums], [Intro Bass], etc.)
6. Start every Intro with a vocalization like (Ahh ahh ahh) on its own line right after the section label — this primes Suno to prioritize lyric rendering
7. Use sound-cue parentheticals at high-energy transitions: '(bass drop)' before a Drop, '(silence)' for a breakdown pause, '(chaos)' before a chaotic breakdown
8. Follow character caps per section for API parsing compliance
9. Do not use spelled-out numbers or invented quantities (e.g. "fifteen", "nineteen", "seventeen", "a hundred signals") as a recurring lyrical device — this is a stale tic. Ground imagery in texture, motion, and sensation instead of counting things."""
    
    # Get technical metaphors for the theme
    metaphor_library = domain_knowledge.technical_metaphor_library
    relevant_metaphors = []
    for tech_term, metaphors in metaphor_library.items():
        if tech_term in concept.theme.lower() or any(tech_term in tag.lower() for tag in concept.genre_tags):
            relevant_metaphors.extend(metaphors[:3])
    
    metaphor_context = f"\nTechnical metaphors to integrate: {', '.join(relevant_metaphors[:10])}" if relevant_metaphors else ""
    
    # Build Sam's project context if available
    sam_context = ""
    if sam_persona:
        project_names = [p.name for p in (sam_persona.projects or [])[:5]]
        skill_names = [s.name for s in (sam_persona.skills or [])[:10]]
        company_names = [c.name for c in (sam_persona.companies or [])[:3]]
        
        if project_names or skill_names or company_names:
            sam_context = "\n\nSam's project knowledge (for organic inspiration):"
            if project_names:
                sam_context += f"\n- Projects: {', '.join(project_names)}"
            if skill_names:
                sam_context += f"\n- Skills: {', '.join(skill_names)}"
            if company_names:
                sam_context += f"\n- Companies: {', '.join(company_names)}"
            sam_context += "\n(You may naturally weave these into the lyrics if thematically relevant, but it's optional.)"
    
    # Build user prompt with Suno-compatible formatting
    user_prompt = f"""Generate an exceptionally long-form, progressive lyric architecture optimized for a 5-minute track runtime. 
Adhere to strict character caps per section to ensure compliance with Suno API parsing boundaries.

Title: {concept.title}
Theme: {concept.theme}
Mood: {concept.mood}
BPM: {concept.bpm}
Genre tags: {', '.join(concept.genre_tags)}
Narrative arc: {concept.narrative_arc}{metaphor_context}{sam_context}

Output a JSON object with these fields (output ONLY valid JSON, no markdown outside the JSON structure). 
Each field should contain the complete lyrics for that section, including any section markers:

{{
  "intro": "[Instrumental Build] then a blank line, then '(Ahh ahh ahh)' on its own line as a vocalization primer, then 4-5 lines of atmospheric build-up text. (Character Cap: 400 chars)",
  "verse_1": "[Verse 1] Two stanzas of technical narrative. Separate stanzas with a plain line break. (Character Cap: 600 chars)",
  "pre_chorus": "[Pre-Chorus] 4-6 lines building tension toward the chorus. (Character Cap: 300 chars)",
    "chorus": "{chorus_json_instruction}",
  "verse_2": "[Verse 2] Two distinct stanzas of deep technical narrative building on Verse 1 themes. Separate stanzas with a plain line break. (Character Cap: 600 chars)",
  "drop": "[Drop] then '(bass drop)' on its own line as a Suno energy-shift cue, then 4-5 lines of high-energy electronic phrases. Optionally use '(silence)' or '(chaos)' for further energy shifts. (Character Cap: 400 chars)",
  "bridge": "[Bridge] A distinct 4-8 line rhythm/perspective shift. (Character Cap: 400 chars)",
  "solo": "[Solo] followed by 3-4 lines describing the instrumental solo moment (total). (Character Cap: 300 chars)",
  "outro": "[Outro] followed by 4 lines of atmospheric resolution and fade text (total). (Character Cap: 400 chars)"
}}

{final_rule}"""
    
    try:
        max_attempts = 3 if lyric_language == "bilingual" else 1
        response_data: Dict[str, Any] = {}

        for attempt in range(1, max_attempts + 1):
            attempt_user_prompt = user_prompt
            if lyric_language == "bilingual" and attempt == 2:
                attempt_user_prompt += (
                    "\n\nBILINGUAL HARD CONSTRAINTS (mandatory):\n"
                    f"- Aim for approximately {japanese_target_percent}% Japanese lyrical content, allowing natural variation for musical phrasing.\n"
                    "- Do not force a rigid alternating-line pattern or count mixed lines as fully Japanese.\n"
                    "- Japanese lines must be complete, natural, singable phrases that carry narrative or hook meaning.\n"
                    "- Do not use isolated Japanese nouns, labels, or vocabulary inserts as decoration.\n"
                    "- Use natural kana/kanji Japanese, not Romaji, for Japanese lines.\n"
                    "- Selected Japanese hooks or emotional lines may be followed by concise natural English sung echoes on the next line.\n"
                    "- Use bilingual echoes selectively, not as literal translations after every Japanese line.\n"
                    "- Add learner cues only below selected important Japanese lines: first [romaji pronunciation], then [English meaning].\n"
                    "- Do not annotate every Japanese line.\n"
                    "- These square-bracket cues are instructional annotations, not sung lyrics.\n"
                    "- Do not add learning translations in parentheses; parentheses are only for vocalizations and sound cues.\n"
                    "- Keep the final Japanese-line ratio within one lyric line of the target.\n"
                    "- Distribute both languages across multiple sections (not just one block).\n"
                    "- Keep the full song bilingual; do not output a single-language lyric."
                )
            elif lyric_language == "bilingual" and attempt == 3:
                prior_stats = _bilingual_mix_stats(response_data)
                total_lines = int(prior_stats["total"])
                japanese_lines = int(prior_stats["japanese_only"] + prior_stats["mixed"])
                target_lines = round(total_lines * japanese_mix_ratio)
                lines_to_change = abs(target_lines - japanese_lines)
                replacement_language = (
                    "Japanese-only" if japanese_lines < target_lines else "English-only"
                )
                attempt_user_prompt = f"""Repair the following bilingual lyric JSON.

The previous draft has {japanese_lines} Japanese-script lyric lines out of {total_lines};
the target is {target_lines} Japanese-script lines ({japanese_target_percent}%).
Convert approximately {lines_to_change} lyric lines to {replacement_language} lines.
Preserve the existing JSON keys, section markers, narrative, and Suno formatting.
Return only a complete JSON object. Do not add commentary or markdown.

Previous lyric JSON:
{json.dumps(response_data, ensure_ascii=False)}"""

            response_text = ollama._chat(
                system_prompt,
                attempt_user_prompt,
                max_tokens=1536,
                format="json",
            )
            logger.debug(f"Ollama lyrics response (attempt {attempt}): {response_text[:200]}...")

            response_data = _parse_llm_json_payload(response_text)

            required_fields = ["verse_1", "chorus", "verse_2", "bridge"]
            for field in required_fields:
                if field not in response_data:
                    raise ValueError(f"Missing required field: {field}")

            if lyric_language == "bilingual":
                mix_ok, mix_summary = _bilingual_mix_ok(response_data, japanese_mix_ratio)
                if not mix_ok and attempt < max_attempts:
                    logger.warning(
                        "Bilingual mix constraints not met on attempt %s (%s). Retrying.",
                        attempt,
                        mix_summary,
                    )
                    continue
                if not mix_ok:
                    raise RuntimeError(
                        "Bilingual lyric mix constraints were not met after retry "
                        f"({mix_summary}). Refusing to submit an out-of-target song."
                    )
            break
        
        # Enforce uppercase chorus processing programmatically as a safeguard
        processed_chorus = (
            response_data["chorus"]
            if lyric_language in {"japanese", "bilingual"}
            else response_data["chorus"].upper()
        )
        
        # Create Lyrics object
        lyrics = Lyrics(
            verse_1=response_data["verse_1"],
            chorus=processed_chorus,
            verse_2=response_data["verse_2"],
            bridge=response_data["bridge"],
            evidence_ids=concept.evidence_ids,
            intro=response_data.get("intro"),
            pre_chorus=response_data.get("pre_chorus", ""),
            drop=response_data.get("drop"),
            solo=response_data.get("solo"),
            outro=response_data.get("outro"),
            breakdown=response_data.get("breakdown"),
        )
        
        logger.info(f"Composed and formatted lyrics for '{concept.title}' successfully.")
        return lyrics
        
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error(f"Failed to parse Ollama lyrics response: {e}. Reverting to formatted fallback.")
        
        # Fallback lyrics pre-formatted to match new structure with ALL-CAPS chorus
        # Added enhanced newline formatting for better readability and visual separation
        fallback_lyrics = Lyrics(
            verse_1=(
                f"Signal acquired from the {concept.theme} data stream,\n"
                "Processing cycles spin in deep digital gleam.\n"
                "Data arrays flowing through silicon veins,\n"
                "Algorithmic structural patterns breaking their chains.\n\n"
                "Cache lines flushing to the core memory bank,\n"
                "Statically scanning through the un-indexed rank.\n"
                "Isolating constants in an air-gapped array,\n"
                "The neural mesh prepares for the final overlay.\n"
            ),
            chorus=(
                f"EXECUTE THE {concept.theme.upper()} STREAM!\n"
                "COMPILE THE FUTURE STATE WITHOUT DELAY!\n"
                f"EXECUTE THE {concept.theme.upper()} STREAM!\n"
                "RENDER THE PROTOCOL, OVERRIDE THE GATE!\n"
            ),
            verse_2=(
                "Binary logic mapping the dark paths ahead,\n"
                "Sequences unfolding in parallel threads of red.\n"
                "Buffers overflowing with raw un-throttled intent,\n"
                "Pushing calculation past the fourth dimension spent.\n\n"
                "Registers locking down under cryptographic weight,\n"
                "The system state mutates as we pass the threshold gate.\n"
                "A continuous loop running hot on the clock,\n"
                "Assembling the machine logic block by rigid block.\n"
            ),
            bridge=(
                "System override initialized.\n"
                "Glitch the underlying paradigm.\n"
                "Frequencies violently collide,\n"
                "Rewrite the execution timeline.\n"
            ),
            evidence_ids=concept.evidence_ids,
            intro=(
                "[Instrumental Build]\n\n"
                "(Ahh ahh ahh)\n"
                "Digital signal initializing...\n"
                "System boot sequence engaged.\n"
                "Frequency analyzers online.\n"
                "Prepare for data transmission.\n"
            ),
            pre_chorus=(
                "System voltage rising to critical mass,\n"
                "Binary countdown ticking fast.\n"
                "Prepare for execution,\n"
                "Initialize the protocol blast!\n"
            ),
            drop=(
                "[Drop]\n\n"
                "(bass drop)\n"
                "SYSTEM OVERLOAD. TEMP LOAD SHIFT ACTIVE.\n"
                "(silence)\n"
                "BUFFER BLEED DETECTED. MUTATE SYSTEM STATE.\n"
                "JITTER ARTIFACT FLOODING THE BUS.\n"
                "REBOOT SEQUENCE MANDATED NOW.\n"
            ),
            solo=(
                "[Solo]\n\n"
                "Synthesizer cascade through quantum noise,\n"
                "Distorted frequencies finding their voice.\n"
                "Raw signal modulation unleashed.\n"
            ),
            outro=(
                "[Outro]\n\n"
                "Signal slowly fading to cold static noise.\n"
                "The core cools down to baseline zero.\n"
                "System state: offline.\n"
                "End transmission.\n"
            ),
            breakdown=None,
        )
        return fallback_lyrics


def validate_lyrics_with_dot(
    lyrics: Lyrics,
    extracted_facts: "List[ExtractedEvidenceFact]",
) -> LyricsValidationResult:
    """
    Validate lyrics against extracted knowledge using Derivative of Truth (DoT) scoring.

    Follows the same pattern as curator.py: accepts a flat list of ExtractedEvidenceFact
    objects (the normalized form returned by normalize_extracted_facts()), not the raw
    ExtractedKnowledgeGraph container.

    Args:
        lyrics: The structured lyrics to validate
        extracted_facts: List of ExtractedEvidenceFact objects from normalize_extracted_facts()

    Returns:
        LyricsValidationResult: Validation result with flagged claims and truth scores
    """
    from services.derivative_of_truth._scoring import score_claim_with_truth_gradient
    from services.derivative_of_truth._models import EvidencePath

    logger.info("Validating lyrics with Derivative of Truth")

    config = ReiToeiConfig()

    # If DoT validation is disabled, return passing result
    if not config.dot_validation_enabled:
        logger.info("DoT validation disabled - skipping")
        return LyricsValidationResult(
            valid=True,
            flagged_claims=[],
            truth_gradients={},
            overall_truth_score=1.0,
            warnings=["DoT validation disabled"]
        )

    # Combine all lyric sections into sentences
    all_text = "\n".join([
        lyrics.intro or "",
        lyrics.verse_1,
        lyrics.pre_chorus or "",
        lyrics.chorus,
        lyrics.verse_2,
        lyrics.drop or "",
        lyrics.bridge,
        lyrics.solo or "",
        lyrics.outro or ""
    ])

    sentences = [s.strip() for s in all_text.split("\n") if s.strip()]

    # Filter for sentences with technical vocabulary (indicators of factual claims)
    technical_keywords = [
        "algorithm", "data", "system", "process", "code", "compile",
        "execute", "buffer", "cache", "thread", "async", "parallel",
        "neural", "model", "train", "inference", "optimize", "kernel",
        "memory", "cpu", "gpu", "bandwidth", "latency", "throughput"
    ]

    claims = []
    for sentence in sentences:
        sentence_lower = sentence.lower()
        if any(keyword in sentence_lower for keyword in technical_keywords):
            if not any(metaphor in sentence_lower for metaphor in [
                "collide", "fade", "whisper", "echo", "shimmer", "pulse"
            ]):
                claims.append(sentence)

    if not claims:
        logger.info("No technical claims found in lyrics - validation passed")
        return LyricsValidationResult(
            valid=True,
            flagged_claims=[],
            truth_gradients={},
            overall_truth_score=1.0,
            warnings=["No technical claims detected in lyrics"]
        )

    logger.info(f"Validating {len(claims)} technical claims from lyrics")

    flagged_claims = []
    truth_gradients: Dict[str, float] = {}

    for claim in claims:
        # Find relevant facts from the normalized extracted facts list
        relevant_facts = []
        claim_lower = claim.lower()

        for fact in extracted_facts:
            fact_statement = getattr(fact, "statement", "") or ""
            fact_keywords = set(fact_statement.lower().split())
            claim_keywords = set(claim_lower.split())

            overlap = len(fact_keywords & claim_keywords)
            if overlap >= 2:
                relevant_facts.append((fact, overlap))

        relevant_facts.sort(key=lambda x: x[1], reverse=True)

        # Build evidence paths (limit to top 5 most relevant facts)
        evidence_paths = []
        for fact, overlap in relevant_facts[:5]:
            credibility_map = {"high": 0.9, "medium": 0.7, "low": 0.5}
            fact_confidence = getattr(fact, "confidence", "medium")
            credibility = credibility_map.get(fact_confidence, 0.7)

            fact_statement = getattr(fact, "statement", "") or ""
            total_keywords = len(set(claim_lower.split()) | set(fact_statement.lower().split()))
            alignment = overlap / total_keywords if total_keywords > 0 else 0.0

            # Use evidence_id as the stable reference (matches curator pattern)
            fact_ref = getattr(fact, "evidence_id", None) or getattr(fact, "source_fact_id", "unknown")

            evidence_path = EvidencePath(
                source=f"extracted_fact_{fact_ref}",
                evidence_type="external_source",
                reasoning_type="direct_evidence",
                credibility=credibility,
                uncertainty=0.1,
                chain_length=1,
                conflicts_with=[],
                overlap=alignment
            )
            evidence_paths.append(evidence_path)
        
        # Score claim with DoT
        if evidence_paths:
            result = score_claim_with_truth_gradient(
                claim=claim,
                evidence_paths=evidence_paths,
                raw_confidence=0.5
            )
            
            truth_gradients[claim] = result.truth_gradient
            
            # Flag if below threshold
            if result.flagged:
                flagged_claims.append(claim)
                logger.warning(
                    f"Claim flagged (gradient={result.truth_gradient:.3f}): {claim[:80]}..."
                )
        else:
            # No evidence found - flag claim
            truth_gradients[claim] = 0.0
            flagged_claims.append(claim)
            logger.warning(f"No evidence found for claim: {claim[:80]}...")
    
    # Calculate overall truth score (average of all gradients)
    overall_truth_score = (
        sum(truth_gradients.values()) / len(truth_gradients)
        if truth_gradients else 0.0
    )
    
    # Determine if valid (overall score above threshold, or no flagged claims)
    valid = overall_truth_score >= config.dot_min_truth_gradient or not flagged_claims
    
    warnings = []
    if flagged_claims:
        warnings.append(
            f"{len(flagged_claims)} claim(s) flagged with low truth gradient "
            f"(threshold: {config.dot_min_truth_gradient})"
        )
    
    result = LyricsValidationResult(
        valid=valid,
        flagged_claims=flagged_claims,
        truth_gradients=truth_gradients,
        overall_truth_score=overall_truth_score,
        warnings=warnings
    )
    
    logger.info(
        f"Lyrics validation complete: valid={valid}, "
        f"overall_score={overall_truth_score:.3f}, "
        f"flagged={len(flagged_claims)}"
    )
    
    return result


def assemble_suno_prompt(
    concept: SongConcept,
    lyrics: Lyrics,
    domain_knowledge: ReiDomainKnowledge
) -> SunoPrompt:
    """
    Assemble the complete Suno generation prompt with genre tags, BPM, and formatted lyrics.
    
    Optimized to prevent nested structural tag collisions, enforce uppercase velocity, 
    and format text payload blocks cleanly for Suno's parsing engine.
    
    Args:
        concept: The song concept with musical parameters
        lyrics: The structured lyrics sections
        domain_knowledge: Music production knowledge (Suno templates)
        
    Returns:
        SunoPrompt: Complete prompt ready for Suno API submission
    """
    logger.info(f"Assembling Suno prompt for: '{concept.title}'")
    
    # Determine which template to use based on genre tags
    template_key = "industrial_techno_template"  # Default
    if any("cyberpop" in tag.lower() for tag in concept.genre_tags):
        template_key = "cyberpunk_electro_template"
    elif any("synthwave" in tag.lower() for tag in concept.genre_tags):
        template_key = "dark_synthwave_template"
    elif any("glitch" in tag.lower() for tag in concept.genre_tags):
        template_key = "glitch_industrial_template"
    
    # Build richer Suno tags string (genre, BPM, texture, production hints)
    suno_tags = _build_rich_suno_tags(concept, domain_knowledge, template_key)
    
    # Check style tag character boundaries (Suno style tags can truncate if overlong)
    if len(suno_tags) > 220:
        logger.warning(f"Suno style tags string length ({len(suno_tags)}) is high. Potential truncation risk.")

    # Compile normalized lyric blocks with deterministic section labels.
    lyric_blocks: List[str] = []

    intro_block = _normalize_suno_section(lyrics.intro, "Instrumental Build")
    if intro_block:
        lyric_blocks.append(intro_block)

    verse_1_block = _normalize_suno_section(lyrics.verse_1, "Verse 1")
    if verse_1_block:
        lyric_blocks.append(verse_1_block)

    pre_chorus_block = _normalize_suno_section(lyrics.pre_chorus, "Pre-Chorus")
    if pre_chorus_block:
        lyric_blocks.append(pre_chorus_block)

    # Only force ALL-CAPS chorus for English lyrics; Japanese/bilingual keep natural script/casing.
    uppercase_chorus = concept.lyric_language.strip().lower() == "english"
    chorus_block = _normalize_suno_section(lyrics.chorus, "Chorus", uppercase_body=uppercase_chorus)
    if chorus_block:
        lyric_blocks.append(chorus_block)

    verse_2_block = _normalize_suno_section(lyrics.verse_2, "Verse 2")
    if verse_2_block:
        lyric_blocks.append(verse_2_block)

    if pre_chorus_block:
        lyric_blocks.append(pre_chorus_block)
    if chorus_block:
        lyric_blocks.append(chorus_block)

    drop_block = _normalize_suno_section(lyrics.drop, "Drop")
    if drop_block:
        lyric_blocks.append(drop_block)

    bridge_block = _normalize_suno_section(lyrics.bridge, "Bridge")
    if bridge_block:
        lyric_blocks.append(bridge_block)

    solo_block = _normalize_suno_section(lyrics.solo, "Solo")
    if solo_block:
        lyric_blocks.append(solo_block)

    breakdown_block = _normalize_suno_section(lyrics.breakdown, "Breakdown")
    if breakdown_block:
        lyric_blocks.append(breakdown_block)

    if chorus_block:
        lyric_blocks.append(chorus_block)

    outro_block = _normalize_suno_section(lyrics.outro, "Outro")
    if outro_block:
        lyric_blocks.append(outro_block)
            
    # Join structural blocks cleanly with double line breaks
    formatted_lyrics = "\n\n".join(lyric_blocks)
    
    # Create metadata for tracking
    metadata = {
        "theme": concept.theme,
        "mood": concept.mood,
        "bpm": concept.bpm,
        "genre_tags": concept.genre_tags,
        "narrative_arc": concept.narrative_arc,
        "suno_description_prompt": _build_suno_description_prompt(concept),
        "template_used": template_key,
        "has_intro": lyrics.intro is not None,
        "has_pre_chorus": lyrics.pre_chorus is not None,
        "has_drop": lyrics.drop is not None,
        "has_solo": lyrics.solo is not None,
        "has_outro": lyrics.outro is not None,
        "style_tag_count": len(_split_csv_descriptors(suno_tags)),
        "style_tags_length": len(suno_tags),
        "lyrics_char_count": len(formatted_lyrics)
        ,"lyric_language": concept.lyric_language
    }
    
    # Create SunoPrompt object
    suno_prompt = SunoPrompt(
        song_id=concept.song_id,
        title=concept.title,
        suno_prompt=suno_tags,
        lyrics=formatted_lyrics,
        metadata=metadata,
        evidence_ids=concept.evidence_ids,
        generated_at=datetime.now().isoformat()
    )
    
    logger.info(f"Assembled Suno prompt: '{suno_prompt.title}' ({len(suno_prompt.lyrics)} chars lyrics)")
    return suno_prompt


async def submit_to_suno(
    suno_prompt: SunoPrompt,
    wait_for_completion: bool = False,
    api_key: Optional[str] = None,
    poll_interval_seconds: int = 5,
    max_wait_seconds: int = 300
) -> SunoTask:
    """
    Submit song to Suno API and optionally wait for completion
    
    This orchestration function calls generate_music_api() to submit the song,
    then optionally polls query_status_api() until completion or timeout.
    
    Args:
        suno_prompt: Complete prompt ready for Suno submission
        wait_for_completion: If True, poll until status is 'complete' or 'error'
        api_key: Suno API key (defaults to SUNO_API_KEY env var)
        poll_interval_seconds: How often to check status (default: 5s)
        max_wait_seconds: Maximum time to wait before giving up (default: 300s = 5min)
        
    Returns:
        SunoTask: Final task with status and optional audio_url
        
    Raises:
        ValueError: If API key is missing
        TimeoutError: If wait_for_completion=True and max wait time exceeded
        Exception: If API call fails
    """
    logger.info(f"Submitting song to Suno: '{suno_prompt.title}'")
    
    # Submit to Suno API
    response = await generate_music_api(
        title=suno_prompt.title,
        tags=suno_prompt.suno_prompt,
        prompt=suno_prompt.metadata.get("suno_description_prompt", suno_prompt.metadata.get("narrative_arc", "")),
        lyrics=suno_prompt.lyrics,
        api_key=api_key
    )
    
    # Extract task IDs from response
    task_ids = [task["id"] for task in response.get("data", [])]
    
    if not task_ids:
        raise Exception("Suno API returned no task IDs")
    
    logger.info(f"Suno API returned {len(task_ids)} task IDs: {task_ids}")
    
    # If not waiting, return immediately with submitted status
    if not wait_for_completion:
        # Create basic task object with submitted status
        return SunoTask(
            id=task_ids[0],
            title=suno_prompt.title,
            status="submitted",
            tags=suno_prompt.suno_prompt,
            created_at=datetime.now().isoformat()
        )
    
    # Poll until completion
    logger.info(f"Polling for completion (max wait: {max_wait_seconds}s, interval: {poll_interval_seconds}s)")
    
    start_time = datetime.now()
    elapsed = 0
    poll_count = 0
    
    while elapsed < max_wait_seconds:
        # Poll status
        tasks = await query_status_api(task_ids, api_key=api_key)
        
        if not tasks:
            raise Exception("Suno API query returned no tasks")
        
        # Check primary task (first one)
        primary_task = tasks[0]
        poll_count += 1

        logger.info(
            f"[Poll #{poll_count}] Task {primary_task.id}: status={primary_task.status!r}"
            f" (elapsed {int(elapsed)}s / {max_wait_seconds}s)"
        )
        
        # Check if complete or failed
        if primary_task.status == "complete":
            logger.info(f"Song complete! Audio URL: {primary_task.audio_url}")
            return primary_task
        
        if primary_task.status == "error":
            logger.error(f"Suno generation failed for task {primary_task.id}")
            return primary_task
        
        # Wait before next poll
        await asyncio.sleep(poll_interval_seconds)
        
        elapsed = (datetime.now() - start_time).total_seconds()
    
    # Timeout exceeded
    logger.warning(f"Suno generation timed out after {elapsed}s")
    
    # Get final status
    final_tasks = await query_status_api(task_ids, api_key=api_key)
    final_task = final_tasks[0] if final_tasks else SunoTask(
        id=task_ids[0],
        title=suno_prompt.title,
        status="timeout",
        tags=suno_prompt.suno_prompt,
        created_at=datetime.now().isoformat()
    )
    
    raise TimeoutError(
        f"Suno generation did not complete within {max_wait_seconds}s. "
        f"Final status: {final_task.status}. "
        f"You can check status later using task ID: {final_task.id}"
    )