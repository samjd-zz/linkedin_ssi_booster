"""Expand leaked word-count markers into actual sung lyric repetitions."""

from __future__ import annotations

import re
from typing import Any

from services.rei_toei._stage_policy import StagePolicy

_WORD_COUNT = r"3\s*(?:[-–—]|to)\s*7\s+words?"
_WORD_COUNT_MARKER_RE = re.compile(
    rf"(?:\(\s*{_WORD_COUNT}\s*\)|（\s*{_WORD_COUNT}\s*）)", re.IGNORECASE
)
_ANNOTATION_RE = re.compile(r"\[[^\[\]]*\]|[(（][^()（）]*[)）]")


class WordCountMarkerError(ValueError):
    """A leaked word-count marker cannot be converted into sung lyrics."""


def _sung_fragment(text: str) -> str:
    lyric = _ANNOTATION_RE.sub(" ", text).strip()
    return lyric if any(character.isalpha() for character in lyric) else ""


def is_repeated_sung_line(line: str, following: str) -> bool:
    """Recognize a written-out lyric repeat, optionally followed by more words."""
    first = " ".join(line.casefold().split())
    second = " ".join(following.casefold().split())
    if not first or not second or first[0] in "[(（" or second[0] in "[(（":
        return False
    return second == first or (
        second.startswith(first) and second[len(first):len(first) + 1] in " ,.;:!?、。！？"
    )


def expand_word_count_markers(
    text: str, *, sung: bool = True, section_headers: re.Pattern[str] | None = None,
) -> str:
    """Replace each word-count marker with the preceding sung phrase."""
    if not _WORD_COUNT_MARKER_RE.search(text):
        return text
    if not sung:
        raise WordCountMarkerError("A word-count marker appeared in an instrumental section")

    # Romaji verification also uses the repeat detector, so defer this import.
    from services.rei_toei._lyric_romaji import _is_adjacent_romaji_cue, _JAPANESE_CHAR_RE

    lines: list[str] = []
    preceding = ""
    for line in text.splitlines():
        parts = _WORD_COUNT_MARKER_RE.split(line)
        if len(parts) == 1:
            lines.append(line)
            if section_headers is not None and section_headers.fullmatch(line):
                preceding = ""
                continue
            lyric = _sung_fragment(line)
            if lyric:
                preceding = lyric
            elif line.strip() and not (
                preceding
                and _JAPANESE_CHAR_RE.search(preceding)
                and _is_adjacent_romaji_cue(preceding, line)
            ):
                preceding = ""
            continue

        prefix = parts[0]
        lyric = _sung_fragment(prefix) if prefix.strip() else preceding
        if not lyric:
            raise WordCountMarkerError("Cannot expand word-count marker without a preceding sung lyric")
        if prefix.strip():
            lines.append(prefix.rstrip())
        indent = line[: len(line) - len(line.lstrip())]
        for suffix in parts[1:]:
            repeated = f"{indent}{lyric}{suffix}".rstrip()
            lines.append(repeated)
            lyric = _sung_fragment(repeated)
        preceding = lyric
    return "\n".join(lines)


def expand_payload_word_count_markers(
    payload: dict[str, Any], policy: StagePolicy,
) -> None:
    """Expand markers in enabled sung sections and reject instrumental ones."""
    section_headers = policy.header_pattern()
    for field, value in payload.items():
        rule = policy.rule(field)
        if rule is not None and isinstance(value, str):
            payload[field] = expand_word_count_markers(
                value, sung=rule.content == "sung", section_headers=section_headers
            )
