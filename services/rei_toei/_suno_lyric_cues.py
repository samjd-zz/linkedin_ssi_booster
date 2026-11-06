"""Normalize Suno stage directions and sung vocalization cues."""

from __future__ import annotations

import re
from typing import List, Optional

from services.rei_toei._lyric_romaji import _is_stage_cue_phrase
from services.rei_toei._suno_cleanup import (
    _INSTRUMENT_CUE_TAGS,
    _LAYOUT_PLACEHOLDERS,
    _PARENTHETICAL_DIRECTION_CUES,
    _PRODUCTION_DIRECTION_RE,
    _is_vocalization,
    bracket_chaos_cues,
    strip_leading_semicolons,
)

_INTRO_HEADER_RE = re.compile(r"\[\s*(?:instrumental\s+build|intro(?:\s+verse)?)\s*\]", re.IGNORECASE)
_INTRO_LABEL_ECHO_RE = re.compile(
    r"[\[(（]\s*(?:instrumental\s+build|intro(?:\s+verse)?)\s*[\])）]", re.IGNORECASE
)
_VOCAL_WRAPPER_RE = re.compile(r"\[(?P<bracket>[^\[\]]+)\]|[(（](?P<paren>[^()（）]+)[)）]")
_TRAILING_ECHO_RE = re.compile(r"^(?P<lead>.*\S)\s*[(（](?P<echo>[^()（）]+)[)）]\s*$")
_INLINE_STAGE_TAG_RE = re.compile(r"\[(?P<cue>[^\[\]]+)\]")
_LEADING_VOCALIZATION_RE = re.compile(
    r"^\s*[（(](?P<vocal>[^()（）]+)[）)]\s*(?P<tail>.*)$"
)
_JAPANESE_VOCALIZATION_REPLACEMENTS = (
    ("アッハ", "Ahh"),
    ("アハ", "Ahh"),
    ("アー", "Ahh"),
    ("オオ", "Oh oh"),
    ("オー", "Oh"),
    ("オ", "Oh"),
    ("ウー", "Ooh"),
    ("ララ", "La la"),
    ("ンー", "Mm"),
)
_SUNG_INTERJECTIONS = frozenset({
    "yeah", "hey", "na", "da", "woo", "uh", "eh", "ha", "yo", "ay", "wo", "ooh",
})


def tag_instrument_cues(text: str, *, production_directions: bool = False) -> str:
    """Turn instrument cues and section-specific production directions into tags."""
    lines: List[str] = []
    for line in bracket_chaos_cues(text).splitlines():
        stripped = line.strip()
        if stripped.startswith(("(", "（")) and stripped.endswith((")", "）")):
            cue_text = re.sub(r"\s+", " ", stripped[1:-1]).strip()
            cue = cue_text.lower()
            if cue in _LAYOUT_PLACEHOLDERS:
                lines.append("")
                continue
            tag = _INSTRUMENT_CUE_TAGS.get(cue)
            if tag:
                lines.append(tag)
                continue
            if cue.endswith(" solo") and _is_stage_cue_phrase(cue_text):
                lines.append(f"[{cue_text}]")
                continue
            if (
                production_directions
                and not _is_vocalization(cue_text)
                and _PRODUCTION_DIRECTION_RE.search(cue_text)
            ):
                lines.append(f"[{cue_text}]")
                continue
        lines.append(line)
    return "\n".join(lines)


def bracket_parenthetical_direction_cues(text: str) -> str:
    """Convert exact, known parenthetical direction labels into square-bracket tags."""
    lines: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("(", "（")) and stripped.endswith((")", "）")):
            cue = re.sub(r"\s+", " ", stripped[1:-1]).strip().casefold()
            tag = _INSTRUMENT_CUE_TAGS.get(cue) if cue in _PARENTHETICAL_DIRECTION_CUES else None
            if tag:
                indent = line[: len(line) - len(line.lstrip())]
                lines.append(f"{indent}{tag}")
                continue
        lines.append(line)
    return "\n".join(lines)


def split_inline_stage_cues(text: str) -> str:
    """Move recognized bracketed sound cues onto their own lines."""
    lines: List[str] = []
    for line in text.splitlines():
        if not line.strip():
            lines.append(line)
            continue
        cues: List[str] = []

        def move_cue(match: "re.Match[str]") -> str:
            cue = re.sub(r"\s+", " ", match.group("cue")).strip()
            canonical = _INSTRUMENT_CUE_TAGS.get(cue.casefold())
            if canonical:
                cues.append(canonical)
            elif _is_stage_cue_phrase(cue):
                cues.append(f"[{cue}]")
            else:
                return match.group(0)
            return ""

        lyric = _INLINE_STAGE_TAG_RE.sub(move_cue, line).rstrip()
        if lyric.strip():
            lines.append(lyric)
        lines.extend(cues)
    return "\n".join(lines)


def _normalized_vocalization(text: str) -> Optional[str]:
    """Normalize common Japanese-script spellings of sung vocalizations."""
    candidate = text.strip()
    for japanese, latin in _JAPANESE_VOCALIZATION_REPLACEMENTS:
        candidate = candidate.replace(japanese, f" {latin} ")
    candidate = re.sub(r"\s+", " ", candidate).strip()
    if not _is_vocalization(candidate):
        return None
    if candidate == text.strip():
        return candidate
    words = candidate.split()
    return " ".join([words[0].capitalize(), *(word.lower() for word in words[1:])])


def _is_word_echo(text: str) -> bool:
    """True for ``Shine shine``-style ad-libs: one real word repeated, not a vocalization."""
    words = re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", text)
    if len(words) < 2 or len({word.casefold() for word in words}) != 1:
        return False
    if re.sub(r"[\s,.!?~-]+", "", text) != "".join(words):
        return False
    word = words[0].casefold()
    return word not in _SUNG_INTERJECTIONS and not _is_vocalization(word)


def strip_word_echoes(line: str) -> str:
    """Drop ``(Shine shine)`` ad-libs on their own line or after a lyric."""
    stripped = line.strip()
    whole = _VOCAL_WRAPPER_RE.fullmatch(stripped)
    if whole and whole.group("paren") and _is_word_echo(whole.group("paren")):
        return ""
    match = _TRAILING_ECHO_RE.match(line)
    if match and _is_word_echo(match.group("echo")):
        return match.group("lead").rstrip()
    return line


def tidy_vocalization_cues(text: str, *, intro: bool = False) -> str:
    """Normalize sung vocalizations and remove repeated-word echoes."""
    kept: List[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        if line.strip():
            line = strip_word_echoes(line)
            if not line.strip():
                continue
        stripped = line.strip()
        if intro and not _INTRO_HEADER_RE.fullmatch(stripped):
            stripped = _INTRO_LABEL_ECHO_RE.sub(" ", stripped).strip()
            if stripped.casefold() in {"instrumental build", "intro verse"}:
                stripped = ""
            if not stripped and line.strip():
                continue
        leading_vocalization = _LEADING_VOCALIZATION_RE.fullmatch(stripped)
        if leading_vocalization:
            vocal = _normalized_vocalization(leading_vocalization.group("vocal"))
            if vocal:
                key = re.sub(r"[\s,.-]+", " ", vocal).casefold()
                if not intro or key not in seen:
                    kept.append(f"({vocal})")
                    if intro:
                        seen.add(key)
                tail = strip_leading_semicolons(leading_vocalization.group("tail").strip())
                if tail:
                    kept.append(tail)
                continue
        inner = _VOCAL_WRAPPER_RE.fullmatch(stripped)
        bracketed = inner.group("bracket") if inner else None
        candidate = (bracketed or (inner.group("paren") if inner else None)
                     or (stripped if intro else ""))
        vocal = _normalized_vocalization(candidate) if candidate else None
        if vocal:
            if intro:
                key = re.sub(r"[\s,.-]+", " ", vocal).casefold()
                if key in seen:
                    continue
                seen.add(key)
            kept.append(f"({vocal})")
            continue
        kept.append(stripped if intro else line)
    return "\n".join(kept)
