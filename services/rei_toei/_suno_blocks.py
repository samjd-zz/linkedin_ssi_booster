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
from services.rei_toei._suno_sections import (
    _normalize_suno_section,
    _PROMPT_SCHEMA_LEAKAGE_RE,
)

logger = logging.getLogger(__name__)

_FREEFORM_SECTION_HEADER_RE = re.compile(
    r"(?im)^[ \t]*\[(?P<label>Instrumental Build|Intro Verse|Intro|Verse\s*\d*|Pre-Chorus|"
    r"Chorus|Drop|Bridge|Solo|Breakdown|Outro)\][ \t]*"
)
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
) -> str:
    """Normalize and append a Suno lyric section when it has content."""
    # Emoji go first so Romaji cues generated below never copy them.
    text = strip_emoji_lines(text or "")
    if label.casefold() == "solo":
        text = _PROMPT_SCHEMA_LEAKAGE_RE.sub("", _normalize_serialized_lyric_text(text))
        block = bracket_solo_directions(text)
        if block:
            lyric_blocks.append(block)
        return block
    block = _normalize_suno_section(text, label, uppercase_body=uppercase_body)
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
            instrumental, intro_verse = split_intro_block(block)
            block = f"{instrumental}\n\n{intro_verse}" if intro_verse else instrumental
        lyric_blocks.append(block)
    return block


def _normalize_freeform_suno_reply(reply: str) -> str:
    """Clean recognizable song sections without rewriting surrounding prose."""
    headers = list(_FREEFORM_SECTION_HEADER_RE.finditer(reply))
    if not headers:
        return reply
    metadata = _FREEFORM_METADATA_RE.search(reply, headers[0].end())
    end = metadata.start() if metadata else len(reply)
    headers = [header for header in headers if header.start() < end]

    blocks: List[str] = []
    for index, header in enumerate(headers):
        next_start = headers[index + 1].start() if index + 1 < len(headers) else end
        label = header.group("label")
        if label.casefold() == "intro":
            label = "Instrumental Build"
        body = reply[header.end():next_start].strip("\r\n")
        if not _append_normalized_section(blocks, body, label):
            blocks.append(f"[{label}]")

    formatted = "\n\n".join(blocks)
    if any(header.group("label").casefold() == "chorus"
           or header.group("label").casefold().startswith("verse") for header in headers):
        formatted = ensure_suno_quality(formatted)
    suffix = reply[end:]
    return reply[:headers[0].start()] + formatted + ("\n\n" if suffix else "") + suffix


def _build_suno_lyric_blocks(concept: SongConcept, lyrics: Lyrics) -> List[str]:
    """Compile each generated lyric section once in Suno song order."""
    lyric_blocks: List[str] = []

    _append_normalized_section(lyric_blocks, lyrics.intro, "Instrumental Build")
    _append_normalized_section(lyric_blocks, lyrics.verse_1, "Verse 1")
    _append_normalized_section(lyric_blocks, lyrics.pre_chorus, "Pre-Chorus")

    uppercase_chorus = concept.lyric_language.strip().lower() == "english"
    _append_normalized_section(
        lyric_blocks,
        lyrics.chorus,
        "Chorus",
        uppercase_body=uppercase_chorus,
    )

    _append_normalized_section(lyric_blocks, lyrics.verse_2, "Verse 2")

    # The bridge climax builds into the final drop.
    _append_normalized_section(lyric_blocks, lyrics.bridge, "Bridge")
    _append_normalized_section(lyric_blocks, lyrics.drop, "Drop")
    _append_normalized_section(lyric_blocks, lyrics.solo, "Solo")
    _append_normalized_section(lyric_blocks, lyrics.breakdown, "Breakdown")
    _append_normalized_section(lyric_blocks, lyrics.outro, "Outro")
    return lyric_blocks
