"""Suno-facing lyric cleanup: inline glosses, Chinese phrasing, emoji, cue tags, intro split."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

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
# Traditional/simplified words, longer keys first so 數據 wins over 數; whole
# words also run before the per-character simplified fallback below.
_CHINESE_PHRASE_REPLACEMENTS = {
    # Chinese "在空中" (in the air) has no verb in Japanese; "空に舞う" does.
    "在空中": "が空に舞う",
    "數據": "データ",
    "数据": "データ",
    "資料庫": "データベース",
    "網絡": "ネットワーク",
    "網路": "ネットワーク",
    "网络": "ネットワーク",
    "連接": "接続",
    "连接": "接続",
    "系統": "システム",
    "系统": "システム",
    "和谐": "調和",
    "梦想": "夢",
    "信息": "情報",
    "重组": "再構成",
    "資訊": "情報",
    "訊號": "信号",
    "程式": "プログラム",
    "重塑": "再構築",
    "號": "号",
    "數": "数",
    "體": "体",
    "據": "拠",
}
# Simplified-Chinese characters the translator leaks into otherwise Japanese
# lines (ネオンの脉动が辉く); each maps to its Japanese shinjitai form.
_SIMPLIFIED_TO_JAPANESE = str.maketrans({
    "动": "動", "脉": "脈", "辉": "輝", "发": "発", "时": "時", "对": "対", "说": "説",
    "电": "電", "脑": "脳", "进": "進", "运": "運", "闪": "閃", "爱": "愛", "环": "環",
    "线": "線", "终": "終", "结": "結", "构": "構", "变": "変", "换": "換", "转": "転",
    "开": "開", "关": "関", "门": "門", "间": "間", "题": "題", "记": "記", "忆": "憶",
    "见": "見", "觉": "覚", "视": "視", "观": "観", "现": "現", "实": "実", "风": "風",
    "飞": "飛", "乐": "楽", "归": "帰", "组": "組", "织": "織", "经": "経", "络": "絡",
    "传": "伝", "层": "層", "级": "級", "长": "長", "东": "東", "读": "読", "语": "語",
    "话": "話", "认": "認", "识": "識", "战": "戦", "连": "連", "统": "統", "响": "響",
    "满": "満", "锁": "鎖", "扩": "拡", "击": "撃",
})
_CJK_IDEOGRAPH_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0002fa1f]")
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
    "heavy bass drop": "[Heavy Bass Drop]",
    "synth drop": "[Synthesizer Drop]",
    "glitch noise": "[Glitch Noise]",
    "silence": "[Silence]",
    "guitar solo": "[Guitar Solo]",
    "synth solo": "[Synth Solo]",
    "drum solo": "[Drum Solo]",
    "instrumental solo": "[Instrumental Solo]",
    "instrumental": "[Instrumental]",
}
_PRODUCTION_DIRECTION_RE = re.compile(
    r"\b(?:ambient|bass|beat|beats|build|distort(?:ed|ion)?|drum|"
    r"fade|filter|frequency|glitch|guitar|mix|noise|pad|pads|"
    r"percussion|pulse|pulsing|release|reverb|rhythm|signal|"
    r"static|strings|surge|sustain(?:ed)?|swell|synth|synthesizer|"
    r"tempo|texture|vocal)\b",
    re.IGNORECASE,
)
# Layout placeholders the model copies from the prompt; they become real blank lines.
_LAYOUT_PLACEHOLDERS = {"blank line", "blank", "empty line", "line break", "stanza break"}
_INTRO_VERSE_LABEL = "Intro Verse"
# Emoji and pictographs plus their joiners, presentation selectors, keycaps and
# flag tags. Japanese marks such as ー, 々, 〜 and ・ are outside these ranges.
_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "\u2600-\u27BF"
    "\u2B00-\u2BFF"
    "\u231A\u231B\u23E9-\u23F3\u23F8-\u23FA"
    "\u200D\u20E3\uFE0E\uFE0F"
    "\U000E0020-\U000E007F"
    "]+"
)
_ASCII_WORD_CHAR_RE = re.compile(r"[A-Za-z0-9]")
_SPACE_RUN_RE = re.compile(r"[ \t]{2,}")
_SPACE_AFTER_OPENER_RE = re.compile(r"([\[(（「『])\s+")
_SPACE_BEFORE_CLOSER_RE = re.compile(r"\s+([\])）」』,.!?;:、。])")
_CHAOS_CUE = r"chaos[ \t]*[.!?…！？。]*"
_CHAOS_PARENTHESES = rf"(?:\([ \t]*{_CHAOS_CUE}[ \t]*\)|（[ \t]*{_CHAOS_CUE}[ \t]*）)"
_CHAOS_TAG_RE = re.compile(rf"\[[ \t]*(?:{_CHAOS_PARENTHESES}|{_CHAOS_CUE})[ \t]*\]", re.IGNORECASE)
_CHAOS_PAREN_RE = re.compile(_CHAOS_PARENTHESES, re.IGNORECASE)
_CHAOS_LINE_RE = re.compile(
    rf"^(?P<indent>[ \t]*)[*_`]*[ \t]*{_CHAOS_CUE}[ \t]*[*_`]*[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
_CHAOS_REPEAT_LINE_RE = re.compile(
    rf"^(?P<indent>[ \t]*){_CHAOS_CUE}[ \t]*(?:\[[ \t]*chaos[ \t]*\][ \t]*)+$",
    re.IGNORECASE | re.MULTILINE,
)
_SUNG_BASS_DROP_RE = re.compile(
    r"(?:heavy[ \t]+)?bass[ \t]+drop[ \t]*[.!?,…！？。、，]*", re.IGNORECASE
)
_JAPANESE_BASS_DROP_RE = re.compile(
    r"(?:重低音(?:の)?|(?:ヘビー)?ベース)ドロップ[ \t]*[.!?,…！？。、，]*"
)
_CUE_WITH_SUFFIX_RE = re.compile(
    r"^\s*(?:\[(?P<bracket>[^\[\]]+)\]|\((?P<parenthetical>[^()]+)\)|"
    r"(?P<bare>[^\[\]()]+?))\s*"
    r"(?P<suffix>\[[^\[\]]+\]|\([^()]+\))?\s*$"
)
_INTRO_HEADER_RE = re.compile(r"\[\s*(?:instrumental\s+build|intro(?:\s+verse)?)\s*\]", re.IGNORECASE)
_INTRO_LABEL_ECHO_RE = re.compile(
    r"[\[(（]\s*(?:instrumental\s+build|intro(?:\s+verse)?)\s*[\])）]", re.IGNORECASE
)
_VOCAL_WRAPPER_RE = re.compile(r"\[(?P<bracket>[^\[\]]+)\]|[(（](?P<paren>[^()（）]+)[)）]")
_TRAILING_ECHO_RE = re.compile(r"^(?P<lead>.*\S)\s*[(（](?P<echo>[^()（）]+)[)）]\s*$")
# Repeated sung interjections that are kept like vocalizations.
_SUNG_INTERJECTIONS = frozenset({
    "yeah", "hey", "na", "da", "woo", "uh", "eh", "ha", "yo", "ay", "wo", "ooh",
})
# "[romaji cue] [English meaning]" on one line.
_ROMAJI_GLOSS_RE = re.compile(r"\[(?P<romaji>[^\[\]]+)\]\s*\[(?P<gloss>[^\[\]]+)\]")
_GLOSS_FUNCTION_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "to", "of", "in", "on",
    "into", "through", "we", "i", "you", "it", "my", "our", "your", "their",
})
_TRAILING_TAGS_RE = re.compile(r"^(?P<lead>.+?)(?P<tags>(?:[ \t]*\[[^\[\]]+\])+)[ \t]*$")


def has_emoji(text: str) -> bool:
    """True when text contains an emoji or pictograph."""
    return bool(_EMOJI_RE.search(text))


def _emoji_gap(match: "re.Match[str]") -> str:
    """Keep two words apart when an emoji sat directly between them."""
    text, start, end = match.string, match.start(), match.end()
    before = text[start - 1] if start else ""
    after = text[end] if end < len(text) else ""
    joined = _ASCII_WORD_CHAR_RE.match(before) and _ASCII_WORD_CHAR_RE.match(after)
    return " " if joined else ""


def strip_emoji(line: str) -> str:
    """Remove emoji from one line and tidy the spacing they leave behind."""
    if not _EMOJI_RE.search(line):
        return line
    cleaned = _SPACE_RUN_RE.sub(" ", _EMOJI_RE.sub(_emoji_gap, line))
    cleaned = _SPACE_AFTER_OPENER_RE.sub(r"\1", cleaned)
    return _SPACE_BEFORE_CLOSER_RE.sub(r"\1", cleaned).strip()


def strip_emoji_lines(text: str) -> str:
    """Strip emoji from every line, dropping lines that held only emoji."""
    if not _EMOJI_RE.search(text):
        return text
    kept: List[str] = []
    for line in text.splitlines():
        cleaned = strip_emoji(line)
        if cleaned or not line.strip():
            kept.append(cleaned)
    return "\n".join(kept)


def bracket_chaos_cues(text: str) -> str:
    """Keep exact chaos directions in brackets, without changing lyric sentences."""
    text = _CHAOS_TAG_RE.sub("[Chaos]", text)
    text = _CHAOS_PAREN_RE.sub("[Chaos]", text)
    text = _CHAOS_REPEAT_LINE_RE.sub(r"\g<indent>[Chaos]", text)
    return _CHAOS_LINE_RE.sub(r"\g<indent>[Chaos]", text)


def _after_romaji_cue(japanese: str, line: str) -> str | None:
    match = _CUE_WITH_SUFFIX_RE.fullmatch(line)
    if not match:
        return None
    candidate = match.group("bracket") or match.group("parenthetical") or match.group("bare")
    if not candidate or not _is_probable_romaji(japanese, candidate.strip()):
        return None
    return match.group("suffix") or ""


def strip_sung_bass_drop_cues(text: str) -> str:
    """Remove standalone bass-drop lyrics and their adjacent pronunciation cues."""
    source = text.splitlines()
    kept: List[str] = []
    index = 0
    while index < len(source):
        line = source[index]
        tagged = _TRAILING_TAGS_RE.fullmatch(line.strip())
        candidate = (tagged.group("lead") if tagged else line).strip().strip("*_`").strip()
        tags = tagged.group("tags").strip() if tagged else ""
        index += 1
        if _SUNG_BASS_DROP_RE.fullmatch(candidate):
            if tags:
                kept.append(tags)
            continue
        if _JAPANESE_BASS_DROP_RE.fullmatch(candidate):
            if tags:
                suffix = _after_romaji_cue(candidate, tags)
                if suffix is None:
                    kept.append(tags)
                elif suffix:
                    kept.append(suffix)
            while index < len(source) and _SUNG_BASS_DROP_RE.fullmatch(
                source[index].strip().strip("*_`").strip()
            ):
                index += 1
            if index < len(source):
                suffix = _after_romaji_cue(candidate, source[index])
                if suffix is not None:
                    if suffix:
                        kept.append(suffix)
                    index += 1
            continue
        kept.append(line)
    return "\n".join(kept)


def replace_chinese_phrasing(text: str) -> str:
    """Swap traditional-Chinese characters and Chinese syntax for Japanese."""
    cleaned = _CHINESE_BY_RESHAPE_RE.sub(r"\g<agent>で再構築", text)
    for old, new in _CHINESE_PHRASE_REPLACEMENTS.items():
        cleaned = cleaned.replace(old, new)
    return cleaned.translate(_SIMPLIFIED_TO_JAPANESE)


def non_japanese_kanji(line: str) -> str:
    """Return ideographs outside the Japanese (Shift-JIS) set, e.g. simplified 动."""
    found = []
    for char in _CJK_IDEOGRAPH_RE.findall(line):
        try:
            char.encode("cp932")
        except UnicodeEncodeError:
            found.append(char)
    return "".join(dict.fromkeys(found))


def has_chinese_grammar(line: str, kana_source: Optional[str] = None) -> bool:
    """True for a kana-free line that uses Chinese grammar words such as 在 or 了.

    ``kana_source`` judges kana on the raw text when repairs (数据→データ) added it.
    """
    source = line if kana_source is None else kana_source
    return not _KANA_RE.search(source) and bool(_CHINESE_GRAMMAR_RE.search(line))


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


def _is_vocalization(text: str) -> bool:
    """Keep sung ad-libs such as ``Ahh ahh ahh`` in parentheses."""
    return bool(re.fullmatch(r"(?:ah+|oh+|ooh+|whoa+|la+|mm+)(?:[\s,.-]+(?:ah+|oh+|ooh+|whoa+|la+|mm+))*", text, re.IGNORECASE))


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
    """Put sung vocalizations in parentheses; in intros, drop echoed section labels.

    ``[Ahh ahh ahh]`` becomes ``(Ahh ahh ahh)`` in any section. In an intro,
    ``(Instrumental Build)`` or ``[Intro Verse]`` copied inside a line is removed,
    bare vocalizations are parenthesized, and repeated vocalizations are dropped.
    Repeated-word ad-libs such as ``(Shine shine)`` are dropped everywhere.
    """
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
        inner = _VOCAL_WRAPPER_RE.fullmatch(stripped)
        bracketed = inner.group("bracket") if inner else None
        candidate = (bracketed or (inner.group("paren") if inner else None)
                     or (stripped if intro else ""))
        if candidate and _is_vocalization(candidate.strip()):
            vocal = candidate.strip()
            if intro:
                key = re.sub(r"[\s,.-]+", " ", vocal).casefold()
                if key in seen:
                    continue
                seen.add(key)
            kept.append(f"({vocal})")
            continue
        kept.append(stripped if intro else line)
    return "\n".join(kept)


def unbracket_romaji_glosses(text: str) -> str:
    """Move an English meaning out of brackets so Suno sings it.

    ``[akai sureddo ga yami o hodoku] [Red threads unravel the dark]`` under its
    Japanese line becomes the Romaji cue plus a sung ``Red threads unravel the
    dark`` line, unless the next line already sings it. Production cues such as
    ``[Synth sweep]`` stay bracketed.
    """
    source = text.splitlines()
    out: List[str] = []
    japanese = ""
    for index, line in enumerate(source):
        stripped = line.strip()
        match = _ROMAJI_GLOSS_RE.fullmatch(stripped)
        if match and japanese and _is_probable_romaji(japanese, match.group("romaji").strip()):
            gloss = match.group("gloss").strip()
            words = re.findall(r"[A-Za-z']+", gloss)
            sentence_like = any(word.lower() in _GLOSS_FUNCTION_WORDS for word in words)
            if not _is_stage_cue_phrase(gloss) and (
                sentence_like or not _PRODUCTION_DIRECTION_RE.search(gloss)
            ):
                romaji = match.group("romaji").strip()
                first_word = romaji.split(maxsplit=1)[0]
                if not (len(first_word) > 1 and first_word.isupper()):
                    romaji = romaji[:1].lower() + romaji[1:]
                out.append(f"[{romaji}]")
                following = next((item.strip() for item in source[index + 1 :] if item.strip()), "")
                key = re.sub(r"[^a-z0-9]+", " ", gloss.lower()).strip()
                if re.sub(r"[^a-z0-9]+", " ", following.lower()).strip() != key:
                    out.append(gloss)
                japanese = ""
                continue
        if stripped:
            japanese = stripped if _JAPANESE_CHAR_RE.search(stripped) else ""
        out.append(line)
    return "\n".join(out)


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
