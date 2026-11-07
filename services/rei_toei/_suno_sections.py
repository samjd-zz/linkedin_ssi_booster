"""Normalise Suno lyric sections: headers, prompt leakage, cues, and script repairs."""

import re
from typing import List, Optional

from services.rei_toei._lyric_romaji import (
    _BRACKET_LEARNING_CUE_RE,
    _BRACKET_PAREN_LEARNING_CUE_RE,
    _ENGLISH_CHAR_RE,
    _generate_hepburn_romaji,
    _INLINE_LEARNING_CUE_RE,
    _is_probable_romaji,
    _is_sound_cue_phrase,
    _is_stage_cue_phrase,
    _JAPANESE_CHAR_RE,
    _japanese_lyric_phrase,
    _join_split_japanese_acronyms,
    _looks_like_romaji_cue,
    _match_inline_romaji_cue,
    _normalize_romaji_for_match,
    _split_english_lead_from_japanese,
)
from services.rei_toei._suno_cleanup import (
    bracket_chaos_cues,
    replace_chinese_phrasing,
    strip_sung_bass_drop_cues,
)
from services.rei_toei._suno_json import (
    _INTRO_HEADER_INSTRUCTION_RE,
    _normalize_serialized_lyric_text,
)

_SECTION_HEADER_RE = re.compile(
    r"^\s*\[(?:Instrumental Build|Intro Verse|Intro|Verse\s*\d*|Pre-Chorus|"
    r"Chorus|Drop|Bridge|Solo|Breakdown|Outro)\]\s*\n?",
    re.IGNORECASE,
)
_EMBEDDED_SECTION_LABEL_RE = re.compile(
    r"\s*\[(?:Instrumental Build|Intro Verse|Verse\s*\d*|Pre-Chorus|Chorus|Drop|Bridge|Solo|Breakdown|Outro)\]\s*",
    re.IGNORECASE,
)
_INLINE_SLASH_SEPARATOR_RE = re.compile(r"(?:\s+/\s*|\s*/\s+)")
_TRAILING_PARENTHETICAL_RE = re.compile(r"^(?P<body>.*?)(?:\s*\((?P<paren>[^()]*)\)\s*)$")
_LEARNING_PLACEHOLDER_RE = re.compile(
    r"^\[(?:romaji pronunciation|actual pronunciation)\]\s+"
    r"\[(?:english meaning|actual english meaning)\](?::\s*.*)?$",
    re.IGNORECASE,
)
_PROMPT_SCHEMA_LEAKAGE_RE = re.compile(
    r"(?:"
    r"\(?Character Cap:\s*\d+\s*(?:chars?)?\)?|"
    # "(34 chars)" or "(38 chars, UPPERCASE)": drop the whole note, not just the count.
    r"\s*[(（][^()（）\n]*\b\d+\s*(?:chars?|characters)\b[^()（）\n]*[)）]|"
    r"\b\d+\s*chars?\b|"
    r"\s*[(（]\s*[)）]|"
    r"\s*[(（]\s*(?:all[- ]?caps|uppercase)\s*[)）]|"
    r"Two stanzas of (?:deep )?technical narrative(?: building on [^\n]+)?\.?|"
    r"followed by \d+(?:-\d+)? lines (?:describing|of)[^\n]*|"
    r"(?:then )?on its own line as a vocalization primer(?:, then)?|"
    r"then a blank line, then[^\n]*|"
    r"^\s*then\s*$"
    r")",
    re.IGNORECASE,
)
_PROMPT_CUE_INSTRUCTION_RE = re.compile(
    r"(?:then\s+)?(?P<cue>['\"]?(?:\((?:bass drop|heavy bass drop|silence|chaos|glitch noise)\)"
    r"|\[(?:bass drop|heavy bass drop|silence|chaos|glitch noise)\])['\"]?)\s+"
    r"on its own line(?: as (?:a )?(?:Suno )?energy-shift cue)?(?:, then)?[^\n]*",
    re.IGNORECASE,
)
_PROMPT_METADATA_RE = re.compile(
    r"\(\s*(?:Kanji|English):[^)]*\)",
    re.IGNORECASE,
)
_THEN_CUE_LINE_RE = re.compile(
    r"^(?:and\s+)?then\s+['\"]?(?P<cue>\([^()]+\)|\[[^\[\]]+\])['\"]?\s*[,.;]?\s*$",
    re.IGNORECASE,
)
_THEN_CUE_PREFIX_RE = re.compile(r"^(?:and\s+)?then\s+(?=['\"]?[\(\[])", re.IGNORECASE)
_THEN_SCHEMA_LINE_RE = re.compile(
    r"^(?:and\s+)?then\s+['\"]?\s*\d+(?:-\d+)?\s+lines\s+(?:of|describing)\s+"
    r"(?:atmospheric resolution|the instrumental solo moment)\b[^\n]*$",
    re.IGNORECASE,
)
_NON_JAPANESE_SCRIPT_CONTAMINATION_RE = re.compile(r"[\u0900-\u0d7f]+")
_SCRIPT_CONTAMINATION_REPLACEMENTS = {
    "サーಜ್": "サージ",
    "サーಜ": "サージ",
    "ಜ್": "ジ",
    "ಜ": "ジ",
}
_LEADING_CUE_RE = re.compile(r"^(?P<lead>\s*\[)(?P<romaji>[^\[\]]+)(?P<rest>\][^\n]*)$")


def _strip_intro_header_instructions(text: str) -> str:
    """Remove copied intro placement instructions and their Japanese reading cues."""
    lines: List[str] = []
    removed_japanese = False
    for line in text.splitlines():
        if removed_japanese:
            removed_japanese = False
            cue = _LEADING_CUE_RE.fullmatch(line)
            if (
                cue
                and cue.group("rest").strip() == "]"
                and not _JAPANESE_CHAR_RE.search(line)
                and _looks_like_romaji_cue(cue.group("romaji"))
                and not _is_stage_cue_phrase(cue.group("romaji"))
            ):
                continue
        cleaned = _INTRO_HEADER_INSTRUCTION_RE.sub("", line).rstrip()
        if cleaned != line.rstrip() and not cleaned.strip():
            removed_japanese = bool(_JAPANESE_CHAR_RE.search(line))
            continue
        lines.append(cleaned)
    return "\n".join(lines)


def _clean_learning_tail(text: str) -> str:
    """Return a trailing sung echo after an inline learner cue, if meaningful."""
    cleaned = text.strip()
    cleaned = cleaned.lstrip(" .,;:!?。、，；：！？")
    if not _ENGLISH_CHAR_RE.search(cleaned):
        return ""
    return cleaned


def _format_learning_cue_block(
    japanese: str,
    romaji: str,
    meaning: str,
    *,
    prefix: str = "",
    tail: str = "",
) -> str:
    """Format a Japanese learner cue with optional sung lines around it."""
    japanese = japanese.strip()
    romaji = romaji.strip()
    if not _is_probable_romaji(japanese, romaji):
        # LLM-provided Romaji is garbled or missing; fall back to a real
        # Hepburn conversion instead of surfacing bad data to the listener.
        corrected = _generate_hepburn_romaji(japanese)
        if corrected:
            romaji = corrected

    lines: List[str] = []
    if prefix:
        lines.append(prefix)
    lines.append(japanese)
    lines.append(f"[{romaji}] [{meaning.strip()}]")
    cleaned_tail = _clean_learning_tail(tail)
    if cleaned_tail:
        lines.append(cleaned_tail)
    return "\n".join(lines)


def _clean_script_contamination(text: str) -> str:
    """Remove stray non-Japanese script fragments from Japanese lyric lines."""
    cleaned_lines: List[str] = []
    rewritten = ""
    for line in text.splitlines():
        cleaned = line
        if rewritten:
            # The cue under a rewritten line spelled the old words; regenerate it.
            cleaned = _refresh_stale_cue(rewritten, line)
            rewritten = ""
        elif _JAPANESE_CHAR_RE.search(cleaned):
            cleaned = replace_chinese_phrasing(cleaned)
            for old, new in _SCRIPT_CONTAMINATION_REPLACEMENTS.items():
                cleaned = cleaned.replace(old, new)
            cleaned = _NON_JAPANESE_SCRIPT_CONTAMINATION_RE.sub("", cleaned)
            if cleaned != line:
                rewritten = cleaned
        cleaned_lines.append(cleaned)
    return "\n".join(cleaned_lines)


def _refresh_stale_cue(japanese: str, line: str) -> str:
    """Replace the Romaji in a ``[romaji]`` cue line with the repaired line's reading."""
    match = _LEADING_CUE_RE.fullmatch(line)
    if (
        not match
        or _JAPANESE_CHAR_RE.search(line)
        or _is_stage_cue_phrase(match.group("romaji"))
    ):
        return line
    reading = _generate_hepburn_romaji(_japanese_lyric_phrase(japanese))
    if not reading:
        return line
    return f"{match.group('lead')}{reading}{match.group('rest')}"


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


def _normalize_learning_annotation_order(line: str) -> str:
    """Put Japanese, pronunciation, and meaning cues in the canonical order."""
    stripped = line.strip()
    if stripped in {"()", "（ ）", "（　）"}:
        return ""
    if _LEARNING_PLACEHOLDER_RE.fullmatch(stripped):
        return ""

    inline_match = _INLINE_LEARNING_CUE_RE.fullmatch(stripped)
    if inline_match:
        if _is_stage_cue_phrase(inline_match.group("romaji")):
            return stripped
        prefix, japanese = _split_english_lead_from_japanese(inline_match.group("japanese"))
        romaji = inline_match.group("romaji").strip()
        meaning = inline_match.group("meaning").strip()
        return _format_learning_cue_block(
            japanese,
            romaji,
            meaning,
            prefix=prefix,
            tail=inline_match.group("tail"),
        )

    bracket_match = _BRACKET_LEARNING_CUE_RE.fullmatch(stripped)
    if bracket_match:
        if _is_stage_cue_phrase(bracket_match.group("romaji")):
            return stripped
        prefix, japanese = _split_english_lead_from_japanese(bracket_match.group("japanese"))
        romaji = bracket_match.group("romaji").strip()
        meaning = bracket_match.group("meaning").strip()
        return _format_learning_cue_block(japanese, romaji, meaning, prefix=prefix)

    bracket_paren_match = _BRACKET_PAREN_LEARNING_CUE_RE.fullmatch(stripped)
    if bracket_paren_match:
        if _is_stage_cue_phrase(bracket_paren_match.group("romaji")):
            return stripped
        prefix, japanese = _split_english_lead_from_japanese(bracket_paren_match.group("japanese"))
        romaji = bracket_paren_match.group("romaji").strip()
        meaning = bracket_paren_match.group("meaning").strip()
        return _format_learning_cue_block(
            japanese,
            romaji,
            meaning,
            prefix=prefix,
            tail=bracket_paren_match.group("tail"),
        )

    single_cue = _match_inline_romaji_cue(stripped)
    if single_cue:
        prefix, japanese = _split_english_lead_from_japanese(single_cue.group("japanese"))
        romaji = single_cue.group("romaji").strip()
        return "\n".join(part for part in (prefix, japanese, f"[{romaji}]") if part)

    # Remove cue-like annotations that contain no Japanese lyric line to attach to.
    if stripped.startswith("[") and "]" in stripped and ":" in stripped:
        label = stripped.split("]", 1)[0].lstrip("[").strip().lower()
        if label in {"romaji pronunciation", "actual pronunciation"}:
            return ""

    return stripped


def _normalize_suno_section(text: Optional[str], label: str, *, uppercase_body: bool = False) -> str:
    """Normalize a lyric section into deterministic Suno-friendly section format."""
    body = _strip_intro_header_instructions(
        _join_split_japanese_acronyms(_normalize_serialized_lyric_text(text or ""))
    )
    body = _SECTION_HEADER_RE.sub("", body, count=1)
    # Replace Chinese forms before any Romaji check reads the Japanese lines.
    body = _clean_script_contamination(body)
    body = _EMBEDDED_SECTION_LABEL_RE.sub("\n", body)

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
        if _THEN_SCHEMA_LINE_RE.fullmatch(stripped):
            continue
        then_cue = _THEN_CUE_LINE_RE.fullmatch(stripped)
        if then_cue:
            stripped = then_cue.group("cue")
        else:
            stripped = _THEN_CUE_PREFIX_RE.sub("", stripped).strip()
        stripped = _PROMPT_CUE_INSTRUCTION_RE.sub(r"\g<cue>", stripped).strip()
        stripped = _PROMPT_METADATA_RE.sub("", stripped).strip()
        if _PROMPT_SCHEMA_LEAKAGE_RE.search(stripped):
            cleaned_stripped = _PROMPT_SCHEMA_LEAKAGE_RE.sub("", stripped).strip()
            if not cleaned_stripped:
                continue
            stripped = cleaned_stripped
        stripped = stripped.strip("'\"").strip()
        stripped = stripped.replace("**", "").replace("__", "")
        stripped = stripped.replace("`", "")
        expanded_segments = _expand_inline_lyric_separators(stripped)
        for segment in expanded_segments:
            normalized_segment = _normalize_learning_annotation_order(segment)
            if not normalized_segment:
                continue
            if (
                normalized_segment.startswith("(")
                and normalized_segment.endswith(")")
                and _JAPANESE_CHAR_RE.search(normalized_segment)
                and not _looks_like_romaji_cue(normalized_segment[1:-1])
            ):
                normalized_segment = normalized_segment[1:-1].strip()
            normalized_segment = _clean_script_contamination(normalized_segment)
            if (
                normalized_segment.startswith("(")
                and normalized_segment.endswith(")")
                and normalized_lines
                and _JAPANESE_CHAR_RE.search(normalized_lines[-1])
            ):
                parenthetical_text = normalized_segment[1:-1].strip()
                inner_cue_match = re.fullmatch(
                    r"(?P<romaji>[^\[\]]+?)\s*\[(?P<meaning>[^\[\]]+)\]\s*",
                    parenthetical_text,
                )
                if inner_cue_match:
                    normalized_lines.append(
                        f"[{inner_cue_match.group('romaji').strip()}] "
                        f"[{inner_cue_match.group('meaning').strip()}]"
                    )
                    previous_blank = False
                    continue
                if _is_probable_romaji(normalized_lines[-1], parenthetical_text):
                    safe_inner = re.sub(r"[\[\]]", " ", parenthetical_text)
                    safe_inner = re.sub(r"\s{2,}", " ", safe_inner).strip()
                    normalized_lines.append(f"[{safe_inner}]")
                    previous_blank = False
                    continue
            # Drop near-duplicate Romaji cue lines — small models often emit
            # several degraded attempts of the same cue ("Bitto to b",
            # "Bitto to btu, ...") directly below the real one.
            if (
                normalized_lines
                and "\n" not in normalized_segment
                and not normalized_segment.startswith("[")
                and not normalized_segment.startswith("(")
                and not _JAPANESE_CHAR_RE.search(normalized_segment)
                and _looks_like_romaji_cue(normalized_segment)
            ):
                prev_text = normalized_lines[-1].strip().strip("[]")
                if prev_text and not _JAPANESE_CHAR_RE.search(prev_text):
                    cand_tokens = set(_normalize_romaji_for_match(normalized_segment).split())
                    prev_tokens = set(_normalize_romaji_for_match(prev_text).split())
                    if cand_tokens and (
                        len(cand_tokens & prev_tokens) / len(cand_tokens) >= 0.6
                    ):
                        continue
            normalized_lines.append(_normalize_bilingual_translation_order(normalized_segment))
            previous_blank = False

    normalized_body = bracket_chaos_cues("\n".join(normalized_lines).strip())
    normalized_body = strip_sung_bass_drop_cues(normalized_body)
    if uppercase_body:
        normalized_body = normalized_body.upper()
    normalized_body = bracket_chaos_cues(normalized_body)
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
