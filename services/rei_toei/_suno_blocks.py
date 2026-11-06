"""Assemble normalised Suno lyric blocks from structured or freeform lyrics."""

import logging
import re
from typing import List, Optional

from services.rei_toei._lyric_checks import _backfill_missing_romaji_cues
from services.rei_toei._lyric_romaji import _verify_and_correct_romaji_lines
from services.rei_toei._models import Lyrics, SongConcept
from services.rei_toei._romaji_brackets import bracket_bare_romaji_lines
from services.rei_toei._suno_cleanup import (
    split_inline_glosses,
    split_intro_block,
    strip_emoji_lines,
    tag_instrument_cues,
    tidy_vocalization_cues,
    unbracket_romaji_glosses,
)
from services.rei_toei._suno_json import _normalize_serialized_lyric_text
from services.rei_toei._suno_quality import bracket_solo_directions, ensure_suno_quality
from services.rei_toei._suno_quality import remove_required_cues
from services.rei_toei._stage_policy import FIELD_LABELS, StagePolicy, load_stage_policy
from services.rei_toei._suno_sections import (
    _normalize_suno_section,
    _PROMPT_SCHEMA_LEAKAGE_RE,
)

logger = logging.getLogger(__name__)

_FREEFORM_METADATA_RE = re.compile(
    r"(?im)^[ \t]*(?:\*\*)?(?:Suno Prompt|Style Tags|Genre Tags|Tags)"
    r"\s*(?:\*\*)?\s*:(?:\*\*)?"
)


def _append_normalized_section(
    lyric_blocks: List[str],
    text: Optional[str],
    label: str,
    *,
    uppercase_body: bool = False,
    instrumental: bool | None = None,
    required_cues: tuple[str, ...] = (),
) -> str:
    """Normalize and append a Suno lyric section when it has content."""
    # Emoji go first so Romaji cues generated below never copy them.
    text = strip_emoji_lines(text or "")
    had_content = bool(text.strip())
    if instrumental is None:
        instrumental = label.casefold() == "solo"
    if instrumental:
        text = _PROMPT_SCHEMA_LEAKAGE_RE.sub("", _normalize_serialized_lyric_text(text))
        text = re.sub(rf"^\s*\[{re.escape(label)}\]\s*", "", text, count=1, flags=re.IGNORECASE)
        block = bracket_solo_directions(text, label=label)
        if block:
            lyric_blocks.append(block)
        return block
    block = _normalize_suno_section(text, label, uppercase_body=uppercase_body)
    block = remove_required_cues(block, required_cues)
    if not block and required_cues and had_content:
        block = f"[{label}]"
    if block:
        payload = {"section": block}
        bracket_bare_romaji_lines(payload)
        corrected = _verify_and_correct_romaji_lines(payload)
        if corrected:
            logger.info("Corrected %d formatted Romaji cue(s) in %s.", corrected, label)
        _backfill_missing_romaji_cues(payload)
        # Glosses split last so any Romaji under a gloss line is dropped with
        # it: the moved Japanese line is sung without a phonetic duplicate.
        block = split_inline_glosses(payload["section"])
        block = unbracket_romaji_glosses(block)
        is_instrumental_build = label.casefold() == "instrumental build"
        if is_instrumental_build:
            block = tidy_vocalization_cues(block, intro=True)
        block = tag_instrument_cues(
            block,
            production_directions=label.casefold()
            in {"drop", "outro", "instrumental build"},
        )
        if not is_instrumental_build:
            block = tidy_vocalization_cues(block)
        if is_instrumental_build:
            build, intro_verse = split_intro_block(block)
            block = f"{build}\n\n{intro_verse}" if intro_verse else build
        if required_cues:
            header, _, body = block.partition("\n")
            block = "\n".join([header, *(f"[{cue}]" for cue in required_cues), body]).rstrip()
        lyric_blocks.append(block)
    return block


def _normalize_freeform_suno_reply(reply: str, policy: StagePolicy | None = None) -> str:
    """Clean recognizable song sections without rewriting surrounding prose."""
    policy = policy or load_stage_policy()
    headers = list(policy.header_pattern().finditer(reply))
    if not headers:
        return reply
    metadata = _FREEFORM_METADATA_RE.search(reply, headers[0].end())
    end = metadata.start() if metadata else len(reply)
    headers = [header for header in headers if header.start() < end]

    blocks: List[str] = []
    for index, header in enumerate(headers):
        next_start = headers[index + 1].start() if index + 1 < len(headers) else end
        label = header.group("label")
        field = policy.aliases()[label.casefold()]
        rule = policy.rule("intro" if field == "intro_verse" else field)
        if rule is None:
            continue
        label = "Intro Verse" if field == "intro_verse" else FIELD_LABELS[field]
        body = reply[header.end():next_start].strip("\r\n")
        if not _append_normalized_section(
            blocks, body, label,
            instrumental=rule.content == "instrumental",
            required_cues=rule.cues,
        ):
            blocks.append(f"[{label}]")

    formatted = "\n\n".join(blocks)
    if any(policy.aliases()[header["label"].casefold()] in {"chorus", "verse_1", "verse_2"}
           for header in headers):
        formatted = ensure_suno_quality(formatted, policy)
    suffix = reply[end:]
    return reply[:headers[0].start()] + formatted + ("\n\n" if suffix else "") + suffix


def _build_suno_lyric_blocks(
    concept: SongConcept, lyrics: Lyrics, policy: StagePolicy | None = None,
) -> List[str]:
    """Compile each generated lyric section once in Suno song order."""
    policy = policy or load_stage_policy()
    lyric_blocks: List[str] = []
    for rule in policy.sections:
        text = getattr(lyrics, rule.field)
        _append_normalized_section(
            lyric_blocks, policy.canonicalize(text) if text else text,
            FIELD_LABELS[rule.field],
            uppercase_body=rule.field == "chorus" and concept.lyric_language.strip().lower() == "english",
            instrumental=rule.content == "instrumental",
            required_cues=rule.cues,
        )
    return lyric_blocks
