"""Build Suno style tags, description prompts, and template selection."""

import re
from typing import Any, List

from services.rei_toei._models import ReiDomainKnowledge, SongConcept

_SUNO_STYLE_TAG_CHAR_LIMIT = 400  # V4.5+ supports up to 1000 chars; 400 balances richness vs safety
_SUNO_STYLE_TAG_MAX_ITEMS = 16
_BPM_TAG_RE = re.compile(r"\b(\d{2,3})\s*bpm\b", re.IGNORECASE)


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
        excluded_aliases = (
            profile_data.get("exclude_genre_aliases", [])
            if isinstance(profile_data, dict) else []
        )
        if any(
            isinstance(alias, str) and alias.lower() in joined_tags
            for alias in excluded_aliases
        ):
            continue
        aliases = profile_data.get("genre_aliases", []) if isinstance(profile_data, dict) else []
        alias_match = any(
            isinstance(alias, str) and alias.lower() in joined_tags
            for alias in aliases
        )
        if aliases:
            if not alias_match:
                continue
        elif not any(token in joined_tags for token in profile_tokens):
            continue
        matched_phrases.extend(_extract_string_phrases(profile_data, max_items=4))

    return matched_phrases[:6]


def _build_rich_suno_tags(
    concept: SongConcept,
    domain_knowledge: ReiDomainKnowledge,
    template_key: str,
    delivery: str = "",
) -> str:
    """Build richer, bounded Suno style tags from templates + concept + production hints.

    ``delivery`` is a vocal-phrasing descriptor fitted to the finished lyrics; it
    sits right after the BPM tag so the item cap never drops it.
    """
    templates = domain_knowledge.suno_prompt_templates or {}
    template_value = templates.get(template_key, templates.get("industrial_techno_template", ""))
    try:
        rendered_template = str(template_value).format(bpm=concept.bpm, mood=concept.mood)
    except (KeyError, ValueError):
        rendered_template = str(template_value)

    descriptors: List[str] = []
    descriptors.extend(_split_csv_descriptors(rendered_template))
    descriptors.append(f"{concept.bpm} bpm")
    if delivery:
        descriptors.append(delivery)
    descriptors.append(concept.mood.replace("_", " "))
    descriptors.extend(concept.genre_tags[:4])

    if concept.bpm >= 165:
        descriptors.append("breakneck hyperspeed vocaloid energy")
    elif concept.bpm >= 150:
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


def _select_suno_template_key(concept: SongConcept) -> str:
    """Select the Suno style template key from generated genre tags."""
    template_key = "industrial_techno_template"
    joined_tags = " ".join(tag.lower() for tag in concept.genre_tags)
    if any(
        alias in joined_tags
        for alias in (
            "progressive psytrance", "progressive-psytrance",
            "progressive psy-trance", "progressive-psy-trance", "progressive_psytrance",
        )
    ):
        template_key = "progressive_psytrance_template"
    elif any(
        alias in joined_tags
        for alias in ("psychedelic rock", "psychedelic-rock", "psych rock", "psych-rock")
    ):
        template_key = "psychedelic_rock_template"
    elif any(
        alias in joined_tags
        for alias in ("progressive rock", "progressive-rock", "prog rock", "prog-rock")
    ):
        template_key = "progressive_rock_template"
    elif any(
        alias in joined_tags
        for alias in ("jungle", "dnb", "drum and bass", "drum & bass")
    ):
        template_key = "jungle_dnb_template"
    elif "cyberpop" in joined_tags:
        template_key = "cyberpunk_electro_template"
    elif "synthwave" in joined_tags:
        template_key = "dark_synthwave_template"
    elif "glitch" in joined_tags:
        template_key = "glitch_industrial_template"
    return template_key
