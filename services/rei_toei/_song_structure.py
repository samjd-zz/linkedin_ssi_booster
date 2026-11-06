"""Song-structure checks for Rei lyric drafts (verse development, bridge depth)."""

from __future__ import annotations

import difflib
import re
from typing import Any, Dict, List, Tuple

from services.rei_toei._stage_policy import StagePolicy, load_stage_policy

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


def missing_required_sections(
    payload: Dict[str, Any], policy: StagePolicy | None = None,
) -> List[str]:
    """Name missing content according to the selected domain-knowledge profile."""
    policy = policy or load_stage_policy()
    missing: List[str] = []
    headers = policy.header_pattern()
    for rule in policy.sections:
        if not rule.required:
            continue
        field = rule.field
        value = payload.get(field)
        if rule.content == "sung":
            present = bool(sung_line_signatures(value))
        else:
            present = isinstance(value, str) and bool(headers.sub("", value).strip())
        if not present:
            missing.append(
                "intro_verse"
                if field == "intro" and policy.intro_verse_label and isinstance(value, str) and value.strip()
                else field
            )
    return missing


def missing_sections_feedback(missing: List[str], policy: StagePolicy | None = None) -> str:
    """Retry instruction naming each empty or absent required section."""
    policy = policy or load_stage_policy()
    hints = []
    for field in missing:
        rule = policy.rule("intro" if field == "intro_verse" else field)
        if rule is None:
            raise ValueError(f"Unknown missing section for stage profile {policy.name}: {field}")
        hint = rule.guidance()
        if rule.field == "intro":
            hint += f"; primer {policy.intro_primer or 'not required'}"
            if policy.intro_verse_label:
                hint += f"; [{policy.intro_verse_label}] with sung opening lines"
        hints.append(f"- {rule.field}: {hint}")
    return (
        "\n\nREVISION REQUIRED: The previous draft omitted or left empty these required "
        "fields. Return the complete JSON with every field filled:\n" + "\n".join(hints)
    )
