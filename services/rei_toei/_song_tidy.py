"""Deterministic tidy-ups on a composed lyric payload before translation and assembly."""

from __future__ import annotations

import re
from typing import Any, Dict

from services.rei_toei._lyric_romaji import _JAPANESE_CHAR_RE
from services.rei_toei._suno_cleanup import (
    bracket_chaos_cues,
    strip_emoji_lines,
    strip_sung_bass_drop_cues,
)
from services.rei_toei._suno_quality import bracket_solo_directions

# "PULSE CODE (PULSE CODE)": an echo of the line in parentheses, which Suno sings.
_ECHO_RE = re.compile(r"^(?P<lead>.*\S)\s*[(（](?P<echo>[^()（）]+)[)）]\s*$")
# Own-line drop cues: "(bass drop)", "[Heavy Bass Drop]", "[Synthesizer Drop]".
_DROP_CUE_RE = re.compile(r"^[\[(（][^\[\]()（）]*\bdrop\b[^\[\]()（）]*[\])）]$", re.IGNORECASE)
_SIGNATURE_RE = re.compile(r"[^\w\u3040-\u30ff\u3400-\u9fff]+")
_TRAILING_COMMA_CHARS = "、，, "
DROP_FIELDS = frozenset({"drop"})
SUNG_LYRIC_FIELDS = frozenset({
    "intro", "verse_1", "pre_chorus", "chorus", "verse_2", "bridge", "drop",
    "breakdown", "outro",
})


def _signature(line: str) -> str:
    return _SIGNATURE_RE.sub(" ", line).strip().lower()


def strip_echo_parenthetical(line: str) -> str:
    """Drop a parenthetical that only repeats the end of its own line."""
    match = _ECHO_RE.match(line)
    if not match:
        return line
    lead, echo = _signature(match.group("lead")), _signature(match.group("echo"))
    if echo and (lead == echo or lead.endswith(" " + echo)):
        return line[: len(line) - len(line.lstrip())] + match.group("lead").strip()
    return line


def _is_sung(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and stripped[0] not in "[(（"


def tidy_song_sections(payload: Dict[str, Any]) -> None:
    """Tidy lyric cues, emoji, echoes, bridge repetition, and dangling punctuation."""
    for field, value in payload.items():
        if not isinstance(value, str):
            continue
        value = strip_emoji_lines(value)
        if field in SUNG_LYRIC_FIELDS or field == "solo":
            value = bracket_chaos_cues(value)
        lines = []
        for line in value.splitlines():
            if field not in DROP_FIELDS and _DROP_CUE_RE.match(line.strip()):
                continue
            line = strip_echo_parenthetical(line)
            if _is_sung(line) and _JAPANESE_CHAR_RE.search(line):
                line = line.rstrip(_TRAILING_COMMA_CHARS)
            lines.append(line)
        text = "\n".join(lines)
        if field in SUNG_LYRIC_FIELDS:
            text = strip_sung_bass_drop_cues(text)
        payload[field] = (
            bracket_solo_directions(text) if field == "solo" else text
        )

    chorus = payload.get("chorus")
    bridge = payload.get("bridge")
    if not isinstance(chorus, str) or not isinstance(bridge, str):
        return
    chorus_lines = {_signature(line) for line in chorus.splitlines() if _is_sung(line)}
    kept = [
        line for line in bridge.splitlines()
        if not (_is_sung(line) and _signature(line) in chorus_lines)
    ]
    if any(_is_sung(line) for line in kept):
        payload["bridge"] = "\n".join(kept)
