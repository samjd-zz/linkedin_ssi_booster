"""Japanese lyric readings and learner-cue verification."""

from __future__ import annotations

import difflib
import logging
import re
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from sudachipy.dictionary import Dictionary as SudachiDictionary

try:
    import pykakasi
    _PYKAKASI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYKAKASI_AVAILABLE = False

try:
    from sudachipy import dictionary as sudachi_dictionary
    _SUDACHI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SUDACHI_AVAILABLE = False

logger = logging.getLogger(__name__)

_KAKASI_INSTANCE: Optional[Any] = None
_JAPANESE_CHAR_RE = re.compile(
    r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f\U00020000-\U0002fa1f]"
)
_CJK_CHAR_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0002fa1f]")
_ENGLISH_CHAR_RE = re.compile(r"[A-Za-z]")
_ROMAJI_MARKER_RE = re.compile(
    r"(?:\b(?:wa|ha|ga|o|wo|ni|de|no|to|kara|made|e|he|mo|yo|ne|suru|shita|nai|eru|iru|aru)\b|[āīūēōĀĪŪĒŌ])",
    re.IGNORECASE,
)
_SOUND_CUE_PHRASES = {"bass drop", "silence", "glitch noise", "chaos"}
_STAGE_CUE_RE = re.compile(
    r"^(?:instrumental(?: build)?|verse\s*\d*|pre-chorus|chorus|drop|bridge|"
    r"solo|breakdown|outro|intro|(?:guitar|drum|synth|instrumental)\s+solo|"
    r"(?:ah+|oh+)(?:[\s,]+(?:ah+|oh+))*)$",
    re.IGNORECASE,
)
_INLINE_LEARNING_CUE_RE = re.compile(
    r"^(?P<japanese>.*[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f].*?)\s*"
    r"[\(（](?P<romaji>[^()（）]*)[\)）]\s*\[(?P<meaning>[^\[\]]+)\](?P<tail>.*)$"
)
_BRACKET_LEARNING_CUE_RE = re.compile(
    r"^(?P<japanese>.*[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f].*?)\s*"
    r"\[(?P<romaji>[^\[\]]+)\]\s*\[(?P<meaning>[^\[\]]+)\]$"
)
_BRACKET_PAREN_LEARNING_CUE_RE = re.compile(
    r"^(?P<japanese>.*[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f].*?)\s*"
    r"\[(?P<romaji>[^\[\]]+)\]\s*[\(（](?P<meaning>[^()（）]*)[\)）](?P<tail>.*)$"
)
_INLINE_EXPLICIT_CUE_PATTERNS = (
    _INLINE_LEARNING_CUE_RE,
    _BRACKET_LEARNING_CUE_RE,
    _BRACKET_PAREN_LEARNING_CUE_RE,
)
_ROMAJI_FIRST_RE = re.compile(
    r"^(?P<romaji>[A-Za-z][A-Za-z'\-\sāīūēōĀĪŪĒŌ]+?)\s+"
    r"[\(（](?P<japanese>[^()（）]*[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f]"
    r"[^()（）]*)[\)）]$"
)
_INLINE_SINGLE_CUE_PATTERNS = (
    re.compile(
        r"^(?P<japanese>.*[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f].*?)\s*"
        r"[\(（](?P<romaji>[^()（）]+)[\)）]$"
    ),
    re.compile(
        r"^(?P<japanese>.*[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f].*?)\s*"
        r"\[(?P<romaji>[^\[\]]+)\]$"
    ),
    _ROMAJI_FIRST_RE,
)
_JAPANESE_PAREN_RE = re.compile(
    r"^.*?[\(（](?P<japanese>[^()（）]*[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f]"
    r"[^()（）]*)[\)）]$"
)
_EXPLICIT_CUE_PATTERNS = (
    re.compile(r"^\s*\[(?P<romaji>[^\[\]]+)\]\s*\[[^\[\]]+\]\s*$"),
    re.compile(r"^\s*\((?P<romaji>[^()]*)\)\s*\[[^\[\]]+\]\s*$"),
    re.compile(r"^\s*\[(?P<romaji>[^\[\]]+)\]\s*\([^()]*\)\s*$"),
    re.compile(r"^\s*\((?P<romaji>[^\[\]()]+?)\s*\[[^\[\]]+\]\s*\)\s*$"),
)
_BARE_MEANING_CUE_RE = re.compile(
    r"^\s*(?P<romaji>[^\[\]()]+?)\s+\[[^\[\]]+\]\s*$"
)
_SINGLE_CUE_PATTERNS = (
    re.compile(r"^\s*\[(?P<romaji>[^\[\]]+)\]\s*$"),
    re.compile(r"^\s*\((?P<romaji>[^()]*)\)\s*$"),
    re.compile(r"^\s*(?P<romaji>[^\[\]()]+?)\s*$"),
)
_ACRONYM_PATTERN = r"[A-Z][A-Z0-9]{1,}(?:[-/][A-Z0-9]+)*"
_SPLIT_ACRONYM_RE = re.compile(
    rf"(?m)^(?P<acronym>{_ACRONYM_PATTERN})[ \t]*\n[ \t]*"
    r"(?P<continuation>(?:から|まで|で|が|を|は|へ|に|と|の|も)"
    r"(?=[\u3040-\u30ff\u3400-\u9fff])[^\n]*)$"
)


def _is_sound_cue_phrase(text: str) -> bool:
    return re.sub(r"\s+", " ", text).strip().lower() in _SOUND_CUE_PHRASES


def _is_stage_cue_phrase(text: str) -> bool:
    return _is_sound_cue_phrase(text) or bool(_STAGE_CUE_RE.fullmatch(text.strip()))


def _is_explicit_romaji_cue(text: str) -> bool:
    return bool(
        _ENGLISH_CHAR_RE.search(text)
        and not _JAPANESE_CHAR_RE.search(text)
        and not _is_stage_cue_phrase(text)
    )


def _looks_like_romaji_cue(text: str) -> bool:
    stripped = text.strip()
    if not stripped or _JAPANESE_CHAR_RE.search(stripped):
        return False
    if not _ENGLISH_CHAR_RE.search(stripped) or _is_sound_cue_phrase(stripped):
        return False
    return bool(_ROMAJI_MARKER_RE.search(stripped))


def _join_split_japanese_acronyms(text: str) -> str:
    return _SPLIT_ACRONYM_RE.sub(r"\g<acronym>\g<continuation>", text)


def _split_english_lead_from_japanese(text: str) -> tuple[str, str]:
    stripped = text.strip()
    japanese_match = _JAPANESE_CHAR_RE.search(stripped)
    if not japanese_match:
        return "", stripped

    raw_prefix = stripped[:japanese_match.start()]
    prefix = raw_prefix.strip()
    japanese = stripped[japanese_match.start():].strip()
    if not prefix or not _ENGLISH_CHAR_RE.search(prefix):
        return "", stripped

    acronym = re.search(rf"\b{_ACRONYM_PATTERN}$", prefix)
    if acronym and (
        not raw_prefix[-1].isspace()
        or japanese.startswith(("から", "まで", "で", "が", "を", "は", "へ", "に", "と", "の", "も"))
    ):
        return prefix[:acronym.start()].rstrip(" .,!?:;"), stripped[acronym.start():]
    return prefix.rstrip(" .,!?:;"), japanese


def _get_kakasi() -> Optional[Any]:
    global _KAKASI_INSTANCE
    if not _PYKAKASI_AVAILABLE:
        return None
    if _KAKASI_INSTANCE is None:
        _KAKASI_INSTANCE = pykakasi.kakasi()
    return _KAKASI_INSTANCE


@lru_cache(maxsize=1)
def _get_sudachi_dictionary() -> Optional[SudachiDictionary]:
    if not _SUDACHI_AVAILABLE:
        logger.warning("Sudachi is unavailable; Japanese readings may be less accurate.")
        return None
    try:
        return sudachi_dictionary.Dictionary()
    except (OSError, RuntimeError, ValueError) as exc:
        logger.warning("Sudachi dictionary unavailable; using pykakasi alone: %s", exc)
        return None


def _warn_unreadable(text: str) -> None:
    characters = sorted({f"U+{ord(char):04X}" for char in text if _CJK_CHAR_RE.fullmatch(char)})
    logger.warning(
        "Unreadable Japanese character(s) %s; pronunciation cue requires review.",
        ", ".join(characters) or "(unknown)",
    )


def _pykakasi_reading(text: str, kakasi: Any) -> str:
    try:
        chunks = kakasi.convert(text)
    except (TypeError, ValueError, UnicodeError) as exc:
        logger.warning("Japanese pronunciation conversion failed: %s", exc)
        return ""

    source_chars = "".join(_JAPANESE_CHAR_RE.findall(text))
    converted_chars = "".join(
        _JAPANESE_CHAR_RE.findall("".join(str(chunk.get("orig", "")) for chunk in chunks))
    )
    unreadable = "".join(
        str(chunk.get("orig", ""))
        for chunk in chunks
        if _JAPANESE_CHAR_RE.search(str(chunk.get("orig", "")))
        and not chunk.get("hepburn")
    )
    if unreadable or source_chars != converted_chars:
        _warn_unreadable(unreadable or source_chars)
        return ""
    words = [str(chunk["hepburn"]) for chunk in chunks if chunk.get("hepburn")]
    return re.sub(r"\s+([,.!?])", r"\1", " ".join(words)).strip()


def _generate_hepburn_romaji(japanese_text: str) -> str:
    """Romanize a Japanese phrase using contextual readings when available."""
    if not japanese_text.strip():
        return ""
    kakasi = _get_kakasi()
    if kakasi is None:
        logger.warning("pykakasi is unavailable; pronunciation cue requires review.")
        return ""
    sudachi = _get_sudachi_dictionary()
    if sudachi is None:
        return _pykakasi_reading(japanese_text, kakasi)

    try:
        if hasattr(sudachi, "tokenizer"):
            tokenizer = sudachi.tokenizer()
        else:
            tokenizer = sudachi.create()
        morphemes = tokenizer.tokenize(japanese_text)
    except (OSError, RuntimeError, ValueError) as exc:
        logger.warning("Sudachi tokenization failed; using pykakasi alone: %s", exc)
        return _pykakasi_reading(japanese_text, kakasi)

    words: list[str] = []
    punctuation = {"、": ",", "。": ".", "！": "!", "？": "?"}
    for morpheme in morphemes:
        surface = morpheme.surface()
        if not surface or surface.isspace():
            continue
        if not _JAPANESE_CHAR_RE.search(surface):
            words.append(punctuation.get(surface, surface))
            continue

        reading = morpheme.reading_form()
        if _CJK_CHAR_RE.search(reading):
            _warn_unreadable(reading)
            return ""
        if morpheme.part_of_speech()[0] == "助詞" and surface in {"は", "へ", "を"}:
            words.append({"は": "wa", "へ": "e", "を": "o"}[surface])
            continue
        romanized = _pykakasi_reading(reading, kakasi)
        if not romanized:
            _warn_unreadable(surface)
            return ""
        words.append(romanized.replace(" ", ""))

    return re.sub(r"\s+([,.!?])", r"\1", " ".join(words)).strip()


def _strip_cue_noise(line: str) -> str:
    cleaned = re.sub(r"^\[[^\]]*\]\s*", "", line.strip())
    return cleaned.strip("()（）").strip(" '\"‘’“”「」『』")


def _japanese_lyric_phrase(line: str) -> str:
    stripped = line.strip()
    for pattern in (*_INLINE_EXPLICIT_CUE_PATTERNS, *_INLINE_SINGLE_CUE_PATTERNS, _JAPANESE_PAREN_RE):
        match = pattern.fullmatch(stripped)
        if match:
            stripped = match.group("japanese")
            break
    _, phrase = _split_english_lead_from_japanese(_strip_cue_noise(stripped))
    return phrase


def _normalize_romaji_for_match(text: str) -> str:
    folded = (
        text.lower()
        .replace("ā", "aa").replace("ī", "ii").replace("ū", "uu")
        .replace("ē", "ee").replace("ō", "ou")
    )
    folded = re.sub(r"[^a-z0-9\s]", " ", folded)
    particle_map = {"wa": "ha", "e": "he", "o": "wo"}
    return " ".join(particle_map.get(token, token) for token in folded.split())


def _canonical_reading(text: str) -> str:
    return _normalize_romaji_for_match(text).replace(" ", "").replace("ou", "oo")


def _is_romaji_attempt(text: str, expected: str) -> bool:
    if _is_stage_cue_phrase(text):
        return False
    if _JAPANESE_CHAR_RE.search(text) or not _ENGLISH_CHAR_RE.search(text):
        return False
    candidate = _canonical_reading(text)
    reading = _canonical_reading(expected)
    if not candidate or not reading:
        return False
    ratio = difflib.SequenceMatcher(None, candidate, reading).ratio()
    return ratio >= 0.8 or (ratio >= 0.5 and _looks_like_romaji_cue(text))


def _is_probable_romaji(japanese: str, candidate: str) -> bool:
    expected = _generate_hepburn_romaji(_japanese_lyric_phrase(japanese))
    return bool(expected and _is_romaji_attempt(candidate, expected))


def _match_inline_romaji_cue(line: str) -> Optional[re.Match[str]]:
    for pattern in _INLINE_SINGLE_CUE_PATTERNS:
        match = pattern.fullmatch(line)
        if match and _is_probable_romaji(match.group("japanese"), match.group("romaji")):
            return match
    return None


def _has_inline_romaji_cue(line: str) -> bool:
    for pattern in _INLINE_EXPLICIT_CUE_PATTERNS:
        match = pattern.fullmatch(line)
        if match:
            return _is_explicit_romaji_cue(match.group("romaji"))
    return _match_inline_romaji_cue(line) is not None


def _is_adjacent_romaji_cue(japanese: str, line: str) -> bool:
    for pattern in _EXPLICIT_CUE_PATTERNS:
        match = pattern.fullmatch(line)
        if match:
            candidate = match.group("romaji").strip()
            return _is_explicit_romaji_cue(candidate)
    for pattern in (_BARE_MEANING_CUE_RE, *_SINGLE_CUE_PATTERNS):
        match = pattern.fullmatch(line)
        if match:
            return _is_probable_romaji(japanese, match.group("romaji").strip())
    return False


def _correct_match(
    line: str,
    match: re.Match[str],
    japanese: str,
    *,
    explicit: bool,
) -> tuple[str, bool]:
    candidate = match.group("romaji").strip()
    if not _is_explicit_romaji_cue(candidate):
        return line, False
    expected = _generate_hepburn_romaji(_japanese_lyric_phrase(japanese))
    if not expected or (not explicit and not _is_romaji_attempt(candidate, expected)):
        return line, False
    if _canonical_reading(candidate) == _canonical_reading(expected):
        return line, False
    return line[:match.start("romaji")] + expected + line[match.end("romaji"):], True


def _verify_and_correct_romaji_lines(section_payload: Dict[str, Any]) -> int:
    """Check explicit cues and conservatively identify unmarked Romaji lines."""
    corrected = 0
    for field, value in section_payload.items():
        if not isinstance(value, str) or not _JAPANESE_CHAR_RE.search(value):
            continue
        lines = value.splitlines()
        changed = False
        for index, line in enumerate(lines):
            if not _JAPANESE_CHAR_RE.search(line):
                continue
            inline = False
            for pattern, explicit in (
                *((pattern, True) for pattern in _INLINE_EXPLICIT_CUE_PATTERNS),
                *((pattern, False) for pattern in _INLINE_SINGLE_CUE_PATTERNS),
            ):
                match = pattern.fullmatch(line)
                if match is None:
                    continue
                if explicit and not _is_explicit_romaji_cue(match.group("romaji")):
                    continue
                if not explicit and not _is_probable_romaji(
                    match.group("japanese"), match.group("romaji")
                ):
                    continue
                updated, was_corrected = _correct_match(
                    line, match, match.group("japanese"), explicit=explicit
                )
                if was_corrected:
                    lines[index] = updated
                    corrected += 1
                    changed = True
                inline = True
                break
            if inline or index + 1 >= len(lines) or line.strip().startswith("["):
                continue

            candidate = lines[index + 1]
            if not candidate.strip() or _JAPANESE_CHAR_RE.search(candidate):
                continue
            patterns = (
                *((pattern, True) for pattern in _EXPLICIT_CUE_PATTERNS),
                (_BARE_MEANING_CUE_RE, False),
                *((pattern, False) for pattern in _SINGLE_CUE_PATTERNS),
            )
            for pattern, explicit in patterns:
                match = pattern.fullmatch(candidate)
                if match is None:
                    continue
                updated, was_corrected = _correct_match(
                    candidate, match, line, explicit=explicit
                )
                if was_corrected:
                    lines[index + 1] = updated
                    corrected += 1
                    changed = True
                break
        if changed:
            section_payload[field] = "\n".join(lines)
    return corrected
