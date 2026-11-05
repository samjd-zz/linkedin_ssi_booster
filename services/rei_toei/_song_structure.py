"""Song-structure checks for Rei lyric drafts (verse development, bridge depth)."""

from __future__ import annotations

import difflib
import re
from typing import Any, Dict, List, Tuple

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


# Sections that must not lift lines from the sections listed for them. The
# Chorus may return in the Drop and Outro, so those pairs are not checked.
_BORROW_SOURCES = {
    "chorus": ("verse_1", "pre_chorus"),
    "verse_2": ("verse_1", "chorus"),
    "bridge": ("verse_1", "pre_chorus", "chorus", "verse_2"),
}
MAX_BORROWED_LINES = 1


def borrowed_lines(section_payload: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    """Return ``(section, source, line)`` for sung lines copied from an earlier section."""
    found: List[Tuple[str, str, str]] = []
    for section, sources in _BORROW_SOURCES.items():
        for line in sung_line_signatures(section_payload.get(section)):
            for source in sources:
                if _is_repeat(line, sung_line_signatures(section_payload.get(source))):
                    found.append((section, source, line))
                    break
    return found


def borrowed_lines_feedback(found: List[Tuple[str, str, str]]) -> str:
    """Revision note naming the copied lines so the retry can replace them."""
    examples = "; ".join(f"{section} copies {source}: '{line}'" for section, source, line in found[:6])
    return (
        "\n\nREVISION REQUIRED: Sections reuse lines from earlier sections "
        f"({examples}). Write new lines for each of them. The Chorus must not "
        "repeat Verse 1, Verse 2 must not repeat Verse 1 or the Chorus, and the "
        "Bridge must be all-new climax material."
    )


# Sections every lyric draft must fill before it can be accepted.
REQUIRED_LYRIC_FIELDS = (
    "intro", "verse_1", "chorus", "verse_2", "bridge", "drop", "solo", "outro",
)
# Sections that need sung lines, not just a label and cues.
_SUNG_REQUIRED_FIELDS = frozenset({"intro", "verse_1", "chorus", "verse_2", "bridge", "drop", "outro"})
# Framing sections a final draft may borrow from the fallback song; the
# verses, chorus, and bridge must come from the model.
BACKFILLABLE_SECTIONS = frozenset({"intro", "intro_verse", "drop", "solo", "outro"})
_SECTION_LABEL_RE = re.compile(
    r"^\[\s*(?:instrumental\s+build|intro(?:\s+verse)?|verse\s*\d*|pre-?\s*chorus|"
    r"chorus|bridge|drop|solo|outro)\s*\]$",
    re.IGNORECASE,
)


def missing_required_sections(payload: Dict[str, Any]) -> List[str]:
    """Name required sections that are absent, blank, or hold only labels/cues.

    The intro must carry a sung Intro Verse after its vocalization primer;
    Solo only needs one instrumental direction beyond its label.
    """
    missing: List[str] = []
    for field in REQUIRED_LYRIC_FIELDS:
        value = payload.get(field)
        if field in _SUNG_REQUIRED_FIELDS:
            present = bool(sung_line_signatures(value))
        else:
            present = isinstance(value, str) and any(
                line.strip() and not _SECTION_LABEL_RE.match(line.strip())
                for line in value.splitlines()
            )
        if not present:
            missing.append("intro_verse" if field == "intro" and isinstance(value, str) and value.strip() else field)
    return missing


_MISSING_SECTION_HINTS = {
    "intro": "intro: [Instrumental Build], (Ahh ahh ahh), then [Intro Verse] with 2-4 sung lines",
    "intro_verse": "intro: add [Intro Verse] with 2-4 sung lines after (Ahh ahh ahh)",
    "drop": "drop: [Drop], [Heavy Bass Drop], then 4-5 sung lines",
    "solo": "solo: [Solo] followed by 3-4 bracketed instrumental directions",
    "outro": "outro: [Outro] followed by 4 closing lines",
}


def missing_sections_feedback(missing: List[str]) -> str:
    """Retry instruction naming each empty or absent required section."""
    hints = [f"- {_MISSING_SECTION_HINTS.get(field, f'{field}: write this section in full')}" for field in missing]
    return (
        "\n\nREVISION REQUIRED: The previous draft omitted or left empty these required "
        "fields. Return the complete JSON with every field filled:\n" + "\n".join(hints)
    )
