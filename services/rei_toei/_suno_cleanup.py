"""Suno-facing lyric cleanup: inline glosses, Chinese phrasing, cue tags, intro split."""

from __future__ import annotations

import re
from typing import List, Tuple

from services.rei_toei._lyric_romaji import (
    _ENGLISH_CHAR_RE,
    _JAPANESE_CHAR_RE,
    _canonical_reading,
    _drop_non_japanese_glosses,
    _generate_hepburn_romaji,
    _is_probable_romaji,
    _is_stage_cue_phrase,
)
from services.rei_toei._romaji_brackets import _looks_like_romaji_line

# English line ending in a parenthetical that holds Japanese (optionally followed
# by Romaji/pinyin or a nested gloss), e.g. "Signal flux pulse (信號流脈 shingō ryūme),".
_INLINE_GLOSS_RE = re.compile(
    r"^(?P<lead>[^()（）\[\]]*[A-Za-z][^()（）\[\]]*?)\s*"
    r"[(（](?P<inner>(?:[^()（）]|[(（][^()（）]*[)）])+)[)）]"
    r"(?P<tail>[\s.,!?;:…]*)$"
)
# "由X重塑" is Chinese "reshaped by X"; Japanese puts the agent first: "Xで再構築".
_CHINESE_BY_RESHAPE_RE = re.compile(r"(?<![理自経])由(?P<agent>[^\s、。，,]+?)重塑")
# Traditional/Taiwanese forms; longer keys first so 數據 wins over 數.
_CHINESE_PHRASE_REPLACEMENTS = {
    # Chinese "在空中" (in the air) has no verb in Japanese; "空に舞う" does.
    "在空中": "が空に舞う",
    "數據": "データ",
    "資料庫": "データベース",
    "網絡": "ネットワーク",
    "網路": "ネットワーク",
    "連接": "接続",
    "系統": "システム",
    "資訊": "情報",
    "訊號": "信号",
    "程式": "プログラム",
    "重塑": "再構築",
    "號": "号",
    "數": "数",
    "體": "体",
    "據": "拠",
}
# Chinese-only grammar in a kana-free line: locative 在, aspect 了, and
# simplified pronouns/particles. Japanese compounds such as 存在, 現在, 完了
# and 了解 are excluded.
_CHINESE_GRAMMAR_RE = re.compile(
    r"(?<![存現不滞実所健潜自駐散点介偏遍])在(?![庫籍住宅学職任来])"
    r"|(?<![完終修満読魅校])了(?![解承])"
    r"|[们这那吗呢么吧]"
)
_KANA_RE = re.compile(r"[\u3040-\u30ff\uff66-\uff9f]")
# Own-line instrument cues Suno should play, not sing.
_INSTRUMENT_CUE_TAGS = {
    "bass drop": "[Heavy Bass Drop]",
    "synth drop": "[Synthesizer Drop]",
    "glitch noise": "[Glitch Noise]",
    "silence": "[Silence]",
    "guitar solo": "[Guitar Solo]",
    "synth solo": "[Synth Solo]",
    "drum solo": "[Drum Solo]",
    "instrumental solo": "[Instrumental Solo]",
    "instrumental": "[Instrumental]",
}
# Layout placeholders the model copies from the prompt; they become real blank lines.
_LAYOUT_PLACEHOLDERS = {"blank line", "blank", "empty line", "line break", "stanza break"}
_INTRO_VERSE_LABEL = "Intro Verse"


def replace_chinese_phrasing(text: str) -> str:
    """Swap traditional-Chinese characters and Chinese syntax for Japanese."""
    cleaned = _CHINESE_BY_RESHAPE_RE.sub(r"\g<agent>で再構築", text)
    for old, new in _CHINESE_PHRASE_REPLACEMENTS.items():
        cleaned = cleaned.replace(old, new)
    return cleaned


def has_chinese_grammar(line: str) -> bool:
    """True for a kana-free line that uses Chinese grammar words such as 在 or 了."""
    return not _KANA_RE.search(line) and bool(_CHINESE_GRAMMAR_RE.search(line))


def _split_gloss_line(line: str) -> List[str]:
    match = _INLINE_GLOSS_RE.fullmatch(line.strip())
    if not match or _JAPANESE_CHAR_RE.search(match.group("lead")):
        return [line]
    inner = replace_chinese_phrasing(_drop_non_japanese_glosses(match.group("inner")))
    japanese_chars = list(_JAPANESE_CHAR_RE.finditer(inner))
    if not japanese_chars:
        return [line]
    # Keep only the Japanese phrase; trailing Romaji/pinyin is regenerated later.
    japanese = inner[:japanese_chars[-1].end()].strip(" ,、")
    lead = match.group("lead").strip()
    if _is_probable_romaji(japanese, lead):
        return [line]
    tail = match.group("tail").strip()
    return [f"{lead}{tail}", japanese]


def _is_phonetic_duplicate(japanese: str, line: str) -> bool:
    """True for a Romaji/pinyin cue line that only spells out ``japanese``."""
    stripped = line.strip()
    if not stripped or _JAPANESE_CHAR_RE.search(stripped):
        return False
    bracketed = stripped.startswith("[") and stripped.endswith("]")
    inner = stripped[1:-1].strip() if bracketed else stripped
    if not inner or "[" in inner or _is_stage_cue_phrase(inner):
        return False
    if _is_probable_romaji(japanese, inner):
        return True
    expected = _canonical_reading(_generate_hepburn_romaji(japanese))
    if bracketed and expected and expected in _canonical_reading(inner):
        return True
    return bracketed and _looks_like_romaji_line(inner)


def split_inline_glosses(text: str) -> str:
    """Move Japanese glossed in parentheses after English onto its own sung line.

    Romaji/pinyin cue lines directly below the gloss are dropped, so the
    Japanese phrase appears once with no phonetic duplicate.
    """
    source = text.splitlines()
    lines: List[str] = []
    index = 0
    while index < len(source):
        split = _split_gloss_line(source[index])
        lines.extend(split)
        index += 1
        if len(split) == 2:
            while index < len(source) and _is_phonetic_duplicate(split[1], source[index]):
                index += 1
    return "\n".join(lines)


def tag_instrument_cues(text: str) -> str:
    """Turn own-line instrument cues like ``(bass drop)`` into Suno meta tags."""
    lines: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("(", "（")) and stripped.endswith((")", "）")):
            cue = re.sub(r"\s+", " ", stripped[1:-1]).strip().lower()
            if cue in _LAYOUT_PLACEHOLDERS:
                lines.append("")
                continue
            tag = _INSTRUMENT_CUE_TAGS.get(cue)
            if tag:
                lines.append(tag)
                continue
        lines.append(line)
    return "\n".join(lines)


def _is_intro_cue_line(line: str) -> bool:
    stripped = line.strip()
    return (
        not stripped
        or stripped.startswith(("(", "（"))
        or (stripped.startswith("[") and stripped.endswith("]"))
        or not (_ENGLISH_CHAR_RE.search(stripped) or _JAPANESE_CHAR_RE.search(stripped))
    )


def split_intro_block(block: str) -> Tuple[str, str]:
    """Split an Instrumental Build block into its cue lines and any sung intro verse.

    Returns ``(instrumental_block, intro_verse_block)``; the second is empty when
    the intro holds only vocalizations and cues.
    """
    header, _, body = block.partition("\n")
    lines = body.splitlines()
    first_sung = next(
        (index for index, line in enumerate(lines) if not _is_intro_cue_line(line)),
        None,
    )
    if first_sung is None:
        return block, ""
    cues = "\n".join(lines[:first_sung]).strip("\n")
    sung = "\n".join(lines[first_sung:]).strip("\n")
    instrumental = f"{header}\n{cues}" if cues else header
    return instrumental, f"[{_INTRO_VERSE_LABEL}]\n{sung}"
