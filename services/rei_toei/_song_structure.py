"""Song-structure checks for Rei lyric drafts (verse development, bridge depth)."""

from __future__ import annotations

import difflib
import re
from typing import Any, Dict, List

VERSE_REPEAT_THRESHOLD = 0.5
NEAR_DUPLICATE_RATIO = 0.85
MIN_BRIDGE_SUNG_LINES = 4

_CUE_ONLY_RE = re.compile(r"^(?:\[[^\[\]]*\]\s*)+$|^\([^()]*\)$")
_SIGNATURE_STRIP_RE = re.compile(r"[^\w\u3040-\u30ff\u3400-\u9fff]+")


def sung_line_signatures(text: Any) -> List[str]:
    """Return normalized sung lines, skipping labels, cues, and sound directions."""
    if not isinstance(text, str):
        return []
    signatures: List[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or _CUE_ONLY_RE.fullmatch(line):
            continue
        signature = _SIGNATURE_STRIP_RE.sub(" ", line).strip().lower()
        if signature:
            signatures.append(signature)
    return signatures


def _is_repeat(line: str, previous: List[str]) -> bool:
    return any(
        line == earlier
        or difflib.SequenceMatcher(None, line, earlier).ratio() >= NEAR_DUPLICATE_RATIO
        for earlier in previous
    )


def verse_two_repeats_verse_one(
    section_payload: Dict[str, Any],
    threshold: float = VERSE_REPEAT_THRESHOLD,
) -> bool:
    """True when most of Verse 2's sung lines copy or near-copy Verse 1."""
    verse_one = sung_line_signatures(section_payload.get("verse_1"))
    verse_two = sung_line_signatures(section_payload.get("verse_2"))
    if not verse_one or not verse_two:
        return False
    repeated = sum(1 for line in verse_two if _is_repeat(line, verse_one))
    return repeated / len(verse_two) >= threshold


def bridge_is_underdeveloped(section_payload: Dict[str, Any]) -> bool:
    """True when the bridge is too short to build a real climax."""
    return len(sung_line_signatures(section_payload.get("bridge"))) < MIN_BRIDGE_SUNG_LINES
