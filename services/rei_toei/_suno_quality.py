"""Deterministic repairs for required song sections and instrumental directions."""

from __future__ import annotations

import logging
import re

from services.rei_toei._lyric_romaji import _is_stage_cue_phrase
from services.rei_toei._suno_cleanup import (
    _is_vocalization,
    bracket_chaos_cues,
    split_intro_block,
    strip_sung_bass_drop_cues,
    tag_instrument_cues,
)
from services.rei_toei._stage_policy import FIELD_LABELS, StagePolicy, load_stage_policy

logger = logging.getLogger(__name__)

_SOLO_HEADER_RE = re.compile(r"^\s*\[Solo\][ \t]*\n?", re.IGNORECASE)
_BRACKETED_DIRECTIONS_RE = re.compile(r"(?:\[[^\[\]]+\]\s*)+")


def bracket_solo_directions(text: str | None, *, label: str = "Solo") -> str:
    """Make every instrumental-section line a direction, without nested brackets."""
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
    return f"[{label}]\n{body}" if body else ""


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


def remove_required_cues(text: str, cues: tuple[str, ...]) -> str:
    """Remove configured cue duplicates, including inline or parenthesized variants."""
    for cue in cues:
        escaped = r"(?:heavy\s+)?bass\s+drop" if cue.casefold() == "heavy bass drop" else re.escape(cue)
        text = re.sub(rf"[\[(]\s*{escaped}\s*[\])]", "", text, flags=re.IGNORECASE)
        text = re.sub(rf"(?im)^[ \t]*{escaped}[ \t]*$", "", text)
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def _without_opening_vocalizations(body: str, primer: str | None) -> str:
    lines = []
    opening = True
    for line in body.splitlines():
        value = line.strip()
        if opening and (
            (primer and value.casefold() == primer.casefold())
            or (value.startswith("(") and _is_vocalization(value.strip("()")))
        ):
            continue
        if _is_sung(value):
            opening = False
        lines.append(line)
    return "\n".join(lines).strip()


def ensure_suno_quality(text: str, policy: StagePolicy | None = None) -> str:
    """Repair configured section labels, intro primer, and mandatory stage cues."""
    policy = policy or load_stage_policy()
    headers = list(policy.header_pattern().finditer(text))
    if not headers:
        intro = policy.rule("intro")
        if intro and intro.required and intro.content == "sung":
            _existing_hook([])
        return text
    payload: dict[str, str] = {}
    opening_verse = ""
    aliases = policy.aliases()
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        field = aliases[header["label"].casefold()]
        rule = policy.rule("intro" if field == "intro_verse" else field)
        if rule is None:
            continue
        body = bracket_chaos_cues(text[header.end():end].strip())
        if rule.content != "instrumental":
            body = strip_sung_bass_drop_cues(body)
        if field == "intro_verse":
            opening_verse = "\n".join(filter(None, (
                opening_verse, _without_opening_vocalizations(body, policy.intro_primer),
            )))
            continue
        payload[field] = "\n".join(filter(None, (payload.get(field, ""), body)))

    intro = policy.rule("intro")
    if intro and intro.required and intro.content == "sung" and not any(
        _is_sung(line) for line in (payload.get("intro", "") + "\n" + opening_verse).splitlines()
    ):
        hook = _existing_hook([(FIELD_LABELS[field], body) for field, body in payload.items()])
        opening_verse = "\n".join(filter(None, (opening_verse, hook)))
        logger.warning("Suno quality repair: filled %s from an existing lyric hook", policy.intro_verse_label or intro.label)

    blocks: list[str] = []
    for rule in policy.sections:
        body = payload.get(rule.field, "")
        if rule.field == "intro" and not policy.intro_verse_label:
            body = "\n".join(filter(None, (body, opening_verse)))
            opening_verse = ""
        if not body and not (rule.required and rule.cues) and not (rule.field == "intro" and opening_verse):
            continue
        body = tag_instrument_cues(body)
        for cue in rule.cues:
            if f"[{cue}]".casefold() not in body.casefold():
                logger.warning("Suno quality repair: added [%s] in %s", cue, rule.label)
        body = remove_required_cues(body, rule.cues)
        if rule.field == "intro":
            body = _without_opening_vocalizations(body, policy.intro_primer)
        body = "\n".join([*(f"[{cue}]" for cue in rule.cues), body]).strip()
        if rule.content == "instrumental":
            block = bracket_solo_directions(body, label=rule.label)
        else:
            block = f"[{rule.label}]\n{body}".rstrip()
        if rule.field == "intro":
            if policy.intro_verse_label and rule.content == "sung":
                if opening_verse:
                    block += f"\n\n[{policy.intro_verse_label}]\n{opening_verse}"
                else:
                    build, verse = split_intro_block(block)
                    block = build + (f"\n\n{verse.replace('[Intro Verse]', f'[{policy.intro_verse_label}]', 1)}" if verse else "")
            if policy.intro_primer:
                header, _, tail = block.partition("\n")
                block = f"{header}\n{policy.intro_primer}\n{tail}".rstrip()
        if block:
            blocks.append(block)
    return "\n\n".join(blocks)
