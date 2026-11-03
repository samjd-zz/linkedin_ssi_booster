"""Deterministic repairs for required song sections and instrumental directions."""

from __future__ import annotations

import logging
import re

from services.rei_toei._lyric_romaji import _is_stage_cue_phrase
from services.rei_toei._suno_cleanup import tag_instrument_cues

logger = logging.getLogger(__name__)

_SECTION_RE = re.compile(
    r"(?im)^[ \t]*\[(?P<label>Instrumental Build|Intro Verse|Intro|Verse\s*\d*|"
    r"Pre-Chorus|Chorus|Drop|Bridge|Solo|Breakdown|Outro)\][ \t]*"
)
_SOLO_HEADER_RE = re.compile(r"^\s*\[Solo\][ \t]*\n?", re.IGNORECASE)
_BRACKETED_DIRECTIONS_RE = re.compile(r"(?:\[[^\[\]]+\]\s*)+")


def bracket_solo_directions(text: str | None) -> str:
    """Make every Solo line an instrumental direction, without nested brackets."""
    body = _SOLO_HEADER_RE.sub("", tag_instrument_cues(text or ""), count=1)
    lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or _BRACKETED_DIRECTIONS_RE.fullmatch(stripped):
            lines.append(stripped)
            continue
        instruction = stripped.strip("()（）").replace("[", " ").replace("]", " ")
        instruction = " ".join(instruction.split())
        if instruction:
            lines.append(f"[{instruction}]")
    body = "\n".join(lines).strip()
    return f"[Solo]\n{body}" if body else ""


def _is_sung(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and stripped[0] not in "[(（" and any(char.isalpha() for char in stripped)


def _existing_hook(sections: list[tuple[str, str]]) -> str:
    candidates = [section for section in sections if section[0].casefold() == "chorus"]
    candidates.extend(
        section for section in sections
        if section[0].casefold().startswith("verse")
    )
    for _, body in candidates:
        lines = body.splitlines()
        for index, line in enumerate(lines):
            if not _is_sung(line):
                continue
            hook = [line.strip()]
            for cue in lines[index + 1:]:
                stripped = cue.strip()
                if not _BRACKETED_DIRECTIONS_RE.fullmatch(stripped):
                    break
                if _is_stage_cue_phrase(stripped.strip("[]")):
                    break
                hook.append(stripped)
            return "\n".join(hook)
    raise ValueError("Cannot repair Intro Verse: the song has no sung chorus or verse hook")


def ensure_suno_quality(text: str) -> str:
    """Ensure a sung intro and a canonical bass-drop cue using existing content."""
    headers = list(_SECTION_RE.finditer(text))
    sections: list[tuple[str, str]] = []
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        sections.append((header.group("label"), text[header.end():end].strip()))

    intro_index = next(
        (i for i, (label, _) in enumerate(sections) if label.casefold() == "intro verse"),
        None,
    )
    if intro_index is None:
        hook = _existing_hook(sections)
        position = 1 if sections and sections[0][0].casefold() == "instrumental build" else 0
        sections.insert(position, ("Intro Verse", hook))
        logger.warning("Suno quality repair: added Intro Verse from an existing lyric hook")
    elif not any(_is_sung(line) for line in sections[intro_index][1].splitlines()):
        body = sections[intro_index][1]
        sections[intro_index] = ("Intro Verse", "\n".join(filter(None, (body, _existing_hook(sections)))))
        logger.warning("Suno quality repair: filled an empty Intro Verse from an existing lyric hook")

    if not any(label.casefold() == "drop" for label, _ in sections):
        preceding = [
            i for i, (label, _) in enumerate(sections)
            if label.casefold() in {"bridge", "chorus"} or label.casefold().startswith("verse")
        ]
        position = preceding[-1] + 1 if preceding else len(sections)
        sections.insert(position, ("Drop", ""))
        logger.warning("Suno quality repair: added an instrumental Drop")

    blocks: list[str] = []
    for label, body in sections:
        if label.casefold() == "intro verse":
            label = "Intro Verse"
        if label.casefold() == "drop":
            lines = tag_instrument_cues(body).splitlines()
            if not lines or lines[0].strip() != "[Heavy Bass Drop]":
                logger.warning("Suno quality repair: added the Heavy Bass Drop cue")
            lines = [
                line for line in lines
                if line.strip().casefold() not in {"[heavy bass drop]", "[bass drop]"}
            ]
            body = "\n".join(["[Heavy Bass Drop]", *lines]).strip()
            label = "Drop"
        if label.casefold() == "solo":
            block = bracket_solo_directions(body)
            if block:
                blocks.append(block)
        else:
            blocks.append(f"[{label}]\n{body}".rstrip())
    return "\n\n".join(blocks)
