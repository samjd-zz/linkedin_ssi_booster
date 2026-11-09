"""Validate lyric drafts: language mix, Chinese leakage, learner cues, and distinctness."""

import re
from typing import Any, Dict, List

from services.rei_toei._lyric_repetition import is_repeated_sung_line
from services.rei_toei._lyric_romaji import (
    _ENGLISH_CHAR_RE,
    _generate_hepburn_romaji,
    _has_inline_romaji_cue,
    _is_adjacent_romaji_cue,
    _JAPANESE_CHAR_RE,
    _japanese_lyric_phrase,
)
from services.rei_toei._stage_policy import StagePolicy
from services.rei_toei._suno_cleanup import has_chinese_grammar, replace_chinese_phrasing

_KANA_RE = re.compile(r"[\u3040-\u30ff\uff66-\uff9f]")
_CJK_IDEOGRAPH_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
MIN_CHORUS_SUNG_LINES = 2
# Fullwidth Chinese comma/particle markers that essentially never appear in
# genuine Japanese lyrics (Japanese uses 、 not ，, and の not 的).
_CHINESE_ONLY_MARKER_RE = re.compile(r"[，的]")


def sung_line_count(section: Any) -> int:
    """Count lyric lines while ignoring stage cues and parenthetical vocalizations."""
    if not isinstance(section, str):
        return 0
    return sum(
        1
        for raw_line in section.splitlines()
        if (line := raw_line.strip())
        and line[0] not in "[(（"
        and (_ENGLISH_CHAR_RE.search(line) or _JAPANESE_CHAR_RE.search(line))
    )


def distinct_sung_line_count(section: Any) -> int:
    """Count sung lines once each, ignoring case, punctuation, and repeated hooks."""
    if not isinstance(section, str):
        return 0
    signatures = {
        re.sub(r"[\W_]+", " ", line).strip().casefold()
        for raw_line in section.splitlines()
        if (line := raw_line.strip())
        and line[0] not in "[(（"
        and (_ENGLISH_CHAR_RE.search(line) or _JAPANESE_CHAR_RE.search(line))
    }
    return len(signatures - {""})


def chorus_line_deficit(section: Any, policy: StagePolicy) -> int | None:
    """Return the distinct sung-line count when an enabled Chorus needs more lines."""
    rule = policy.rule("chorus")
    if not rule or rule.content != "sung" or not section:
        return None
    count = distinct_sung_line_count(section)
    return count if count < policy.style.min_chorus_lines else None


def chorus_revision_feedback(line_count: int, minimum: int = MIN_CHORUS_SUNG_LINES) -> str:
    """Build a targeted retry instruction for an undersized Chorus."""
    return (
        "\n\nREVISION REQUIRED: The previous Chorus had only "
        f"{line_count} distinct sung line(s). Write at least {minimum} distinct, "
        "emotionally connected sung lines in the Chorus; repeating the "
        "hook does not count as a new line. Keep sound cues on their own bracketed lines."
    )


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
    # Mixed lines contribute half a line rather than counting as fully Japanese
    # and fully English at the same time. This keeps bilingual echoes musical.
    japanese_line_ratio = ((japanese_only + (mixed * 0.5)) / total) if total else 0.0
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
    # Music lyrics need room for hooks, echoes, and section-level variation.
    # Keep a broad floor while still rejecting extreme language drift.
    ratio_tolerance = max(0.33, 1.0 / total_lines) if total_lines else 0.0
    ratio_within_tolerance = ratio_error <= ratio_tolerance
    ok = has_both_languages and ratio_within_tolerance
    summary = (
        f"jp_lines={japanese_presence}, en_lines={english_presence}, total={total_lines}, "
        f"jp_ratio={stats['effective_japanese_ratio']:.2f}, target={target_japanese_ratio:.2f}, "
        f"ratio_error={ratio_error:.2f}, tolerance={ratio_tolerance:.2f}"
    )
    return ok, summary


def _has_japanese_script(section_payload: Dict[str, Any]) -> bool:
    """Require kana or kanji in lyric content; Romaji alone is not Japanese text."""
    return any(
        isinstance(value, str) and _JAPANESE_CHAR_RE.search(value)
        for value in section_payload.values()
    )


def _line_looks_like_chinese_not_japanese(line: str) -> bool:
    """Flag CJK lines that contain explicit Chinese markers or long non-Japanese sentences."""
    if not _CJK_IDEOGRAPH_RE.search(line):
        return False
    # If hiragana/katakana is present, it is valid Japanese
    if _KANA_RE.search(line):
        return False
    # Explicit Chinese punctuation/particles (e.g., ， or 的) or grammar (在, 了)
    if _CHINESE_ONLY_MARKER_RE.search(line) or has_chinese_grammar(line):
        return True
    
    # Allow short kanji compound phrases (up to 8 kanji); only flag long un-inflected hanzi runs
    ideograph_count = len(_CJK_IDEOGRAPH_RE.findall(line))
    return ideograph_count > 8


def _has_chinese_leakage(section_payload: Dict[str, Any]) -> bool:
    """Detect Chinese-script leakage disguised as Japanese in lyric content."""
    for value in section_payload.values():
        if not isinstance(value, str):
            continue
        for raw_line in value.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            # Forms the formatter repairs (信號, 在空中) need no retry.
            if _line_looks_like_chinese_not_japanese(replace_chinese_phrasing(line)):
                return True
    return False


def _learning_annotation_stats(section_payload: Dict[str, Any]) -> Dict[str, int]:
    """Count Japanese lyric lines and adjacent Romaji/meaning cue pairs."""
    japanese_lines = 0
    annotation_pairs = 0
    for value in section_payload.values():
        if not isinstance(value, str):
            continue
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            if line.startswith("[") and line.endswith("]"):
                continue
            if _JAPANESE_CHAR_RE.search(line):
                japanese_lines += 1
                if _has_inline_romaji_cue(line):
                    annotation_pairs += 1
                    continue
                if index + 1 >= len(lines):
                    continue
                repeated = (
                    index + 2 < len(lines)
                    and is_repeated_sung_line(lines[index + 1], lines[index + 2])
                )
                if not repeated and _is_adjacent_romaji_cue(line, lines[index + 1]):
                    annotation_pairs += 1

    return {
        "japanese_lines": japanese_lines,
        "annotation_pairs": annotation_pairs,
    }


def _required_learning_annotation_pairs(japanese_lines: int) -> int:
    """Choose a song-friendly learner cue target for Japanese lyric lines."""
    if japanese_lines <= 0:
        return 0
    if japanese_lines < 6:
        return 1
    return min(6, max(3, round(japanese_lines / 4)))


def _learning_annotations_ok(
    section_payload: Dict[str, Any],
    lyric_language: str,
) -> tuple[bool, str]:
    """Require a few learner cues when Japanese lyrics are actually present."""
    stats = _learning_annotation_stats(section_payload)
    japanese_lines = stats["japanese_lines"]
    if lyric_language not in {"japanese", "bilingual"} or japanese_lines == 0:
        return True, "no Japanese learner annotations required"

    required_pairs = _required_learning_annotation_pairs(japanese_lines)
    actual_pairs = stats["annotation_pairs"]
    ok = actual_pairs >= required_pairs
    return ok, (
        f"japanese_lines={japanese_lines}, annotation_pairs={actual_pairs}, "
        f"required_pairs={required_pairs}"
    )


def _backfill_missing_romaji_cues(section_payload: Dict[str, Any]) -> int:
    """Insert deterministic ``[romaji]`` pronunciation cues after uncued Japanese lines.

    compose_lyrics prompts the LLM for learner cues, but small models routinely
    drop them. Rather than spending another generation round-trip, synthesize
    Hepburn Romaji for every Japanese line that lacks a cue. Returns the number
    of cues added (0 when no converter is available or every line is cued).
    """
    added = 0
    for field, value in section_payload.items():
        if not isinstance(value, str) or not _JAPANESE_CHAR_RE.search(value):
            continue
        lines = value.splitlines()
        rebuilt: List[str] = []
        for index, raw_line in enumerate(lines):
            rebuilt.append(raw_line)
            line = raw_line.strip()
            if (
                not line
                or not _JAPANESE_CHAR_RE.search(line)
                or (line.startswith("[") and line.endswith("]"))
            ):
                continue
            # Skip lines that already carry an inline cue
            if _has_inline_romaji_cue(line):
                continue
            following = (item.strip() for item in lines[index + 1:] if item.strip())
            next_line = next(following, "")
            repeated = is_repeated_sung_line(next_line, next(following, ""))
            if next_line and not repeated and _is_adjacent_romaji_cue(line, next_line):
                continue
            romaji = _generate_hepburn_romaji(_japanese_lyric_phrase(line))
            if romaji and _ENGLISH_CHAR_RE.search(romaji):
                rebuilt.append(f"[{romaji}]")
                added += 1
        if len(rebuilt) != len(lines):
            section_payload[field] = "\n".join(rebuilt)
    return added


def _sections_are_distinct(section_payload: Dict[str, Any]) -> bool:
    """Reject drafts where most lyric sections are copied from one another."""
    fields = ("verse_1", "pre_chorus", "chorus", "verse_2", "drop", "bridge", "solo", "outro")
    signatures = {
        re.sub(r"[^\w\u3040-\u30ff\u3400-\u9fff]+", " ", str(section_payload.get(field, ""))).strip().lower()
        for field in fields
        if section_payload.get(field)
    }
    populated = sum(1 for field in fields if section_payload.get(field))
    return populated < 4 or len(signatures) >= max(3, populated // 2)
