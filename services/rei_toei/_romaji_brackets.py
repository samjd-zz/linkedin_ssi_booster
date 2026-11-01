"""Keep Romaji pronunciation lines bracketed so Suno does not sing them."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List

from services.rei_toei._lyric_romaji import (
    _ENGLISH_CHAR_RE,
    _JAPANESE_CHAR_RE,
    _canonical_reading,
    _generate_hepburn_romaji,
    _is_probable_romaji,
    _is_stage_cue_phrase,
    _japanese_lyric_phrase,
)

_ROMAJI_TOKEN_RE = re.compile(
    r"^(?:(?:ch|sh|ts|[kgsztdnhbpmrjfwyv])y?[aiueo]|[aiueo]|n|"
    r"([kgstpcdbfhjmrz])(?=\1)|t(?=ch))+$"
)
_ENGLISH_VECTOR_MODEL = "en_core_web_md"
_ENGLISH_FUNCTION_WORDS = {
    "a", "an", "and", "are", "be", "for", "i", "in", "is", "it", "me", "my",
    "of", "on", "or", "the", "this", "that", "us", "we", "will", "with",
    "you", "your",
    # English words that happen to spell valid Romaji syllables.
    "came", "come", "done", "fire", "gone", "here", "hide", "home", "line",
    "made", "make", "mine", "more", "name", "nine", "one", "ride", "same",
    "some", "sure", "take", "time", "tone", "wire", "zone",
}


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _has_romanization_marks(text: str) -> bool:
    """Macrons and pinyin tone marks rarely appear in English translations."""
    return any(
        unicodedata.combining(char)
        for char in unicodedata.normalize("NFKD", text)
    ) and bool(re.search(r"[A-Za-z]", text))


def _looks_like_romaji_line(text: str) -> bool:
    """Spot Romaji or pinyin-like guesses without matching ordinary English."""
    if _has_romanization_marks(text):
        return True
    tokens = re.findall(r"[a-z]+", _fold(text))
    if not tokens or any(token in _ENGLISH_FUNCTION_WORDS for token in tokens):
        return False
    valid = [token for token in tokens if _ROMAJI_TOKEN_RE.fullmatch(token)]
    return len(valid) / len(tokens) > 0.5 and any(len(token) >= 4 for token in valid)


def _is_unknown_english_word(word: str) -> bool:
    """True when spaCy's English vectors do not know the word; False if unsure."""
    from services.spacy_nlp import _load_model

    nlp = _load_model(_ENGLISH_VECTOR_MODEL)
    vocab = getattr(nlp, "vocab", None)
    if vocab is None or not len(vocab.vectors):
        return False
    return not vocab.has_vector(word)


def _looks_like_extra_romaji_guess(text: str) -> bool:
    """Looser check for a line already sitting between a cue and its translation."""
    if _looks_like_romaji_line(text):
        return True
    tokens = re.findall(r"[a-z]+", _fold(text))
    if not tokens or any(token in _ENGLISH_FUNCTION_WORDS for token in tokens):
        return False
    first = tokens[0]
    return (
        len(first) >= 6
        and bool(_ROMAJI_TOKEN_RE.fullmatch(first))
        and _is_unknown_english_word(first)
    )


def _is_bare_text(line: str) -> bool:
    stripped = line.strip()
    return bool(
        stripped
        and not stripped.startswith(("[", "("))
        and not _JAPANESE_CHAR_RE.search(stripped)
        and _ENGLISH_CHAR_RE.search(stripped)
        and not _is_stage_cue_phrase(stripped)
    )


def _is_bracket_cue(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("[") and stripped.endswith("]") and not _JAPANESE_CHAR_RE.search(stripped)


def _is_japanese_lyric(line: str) -> bool:
    stripped = line.strip()
    return bool(_JAPANESE_CHAR_RE.search(stripped)) and not _is_bracket_cue(stripped)


def _bracketed_reading(japanese: str, candidate: str) -> str:
    expected = _generate_hepburn_romaji(_japanese_lyric_phrase(japanese))
    if expected and _canonical_reading(candidate) != _canonical_reading(expected):
        return f"[{expected}]"
    return f"[{candidate.strip()}]"


def _bracket_lines(lines: List[str]) -> tuple[List[str], int]:
    result: List[str] = []
    changes = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        result.append(line)
        index += 1
        if not _is_japanese_lyric(line) or index >= len(lines):
            continue

        following = lines[index]
        translation_follows = index + 1 < len(lines) and _is_bare_text(lines[index + 1])
        if _is_bare_text(following) and (
            _is_probable_romaji(line, following)
            or (translation_follows and _looks_like_romaji_line(following))
        ):
            result.append(_bracketed_reading(line, following))
            changes += 1
            index += 1
        elif _is_bracket_cue(following):
            result.append(following)
            index += 1
            if index >= len(lines) or not _is_bare_text(lines[index]):
                continue
            stray = lines[index]
            has_sung_line_after = index + 1 < len(lines) and _is_bare_text(lines[index + 1])
            if _is_probable_romaji(line, stray) or (
                has_sung_line_after and _looks_like_extra_romaji_guess(stray)
            ):
                # Keep the model's extra line, but bracket it so Suno skips it.
                result.append(f"[{stray.strip()}]")
                changes += 1
                index += 1
    return result, changes


def bracket_bare_romaji_lines(section_payload: Dict[str, Any]) -> int:
    """Bracket bare Romaji below Japanese lines, including extra guesses after a cue.

    No lines are removed. Returns the number of lines bracketed.
    """
    changes = 0
    for field, value in section_payload.items():
        if not isinstance(value, str) or not _JAPANESE_CHAR_RE.search(value):
            continue
        lines, changed = _bracket_lines(value.splitlines())
        if changed:
            section_payload[field] = "\n".join(lines)
            changes += changed
    return changes
