"""Validated musical direction and draft-quality settings for stage profiles."""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from services.rei_toei._models import ReiDomainKnowledge, SongConcept
if TYPE_CHECKING:
    from services.rei_toei._song_tempo import TempoFit

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StylePolicy:
    genre_tags: tuple[str, ...] = ()
    template: str | None = None
    bpm_range: tuple[int, int, int] | None = None
    arrangement: str = ""
    energy: str = ""
    dense_delivery: str | None = None
    sparse_delivery: str | None = None
    density: Mapping[str, float] = field(default_factory=dict)
    min_chorus_lines: int = 2
    min_bridge_lines: int = 4
    max_borrowed_lines: int = 1
    verse_repeat_threshold: float = 0.5
    uppercase_chorus: bool = True
    remove_bridge_echoes: bool = True
    cue_aliases: Mapping[str, str] = field(default_factory=dict)

    def guidance(self) -> str:
        if not self.genre_tags:
            return ""
        lines = [
            "Selected musical style: " + ", ".join(self.genre_tags) + ".",
            "This profile overrides conflicting genre hints and persona genre preferences.",
            f"Arrangement: {self.arrangement}",
            f"Chorus minimum: {self.min_chorus_lines} sung lines; "
            f"bridge development target: {self.min_bridge_lines} sung lines when enabled.",
            f"Allow at most {self.max_borrowed_lines} borrowed lines across narrative sections.",
        ]
        if self.bpm_range:
            low, high, default = self.bpm_range
            lines.append(f"Initial tempo: {low}-{high} BPM, suggested {default}. "
                         "Finished lyric density may raise the tempo above this range.")
        return "\n".join(lines)


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip() or any(c in value for c in "\r\n[]"):
        raise ValueError(f"{path} must be a nonempty single-line string without brackets")
    return value.strip()


def _number(value: Any, path: str, low: float, high: float) -> float:
    if (
        isinstance(value, bool) or not isinstance(value, (int, float))
        or not low <= value <= high or not math.isfinite(value)
    ):
        raise ValueError(f"{path} must be a finite number between {low} and {high}")
    return float(value)


def _integer(value: Any, path: str, low: int, high: int) -> int:
    number = _number(value, path, low, high)
    if not number.is_integer():
        raise ValueError(f"{path} must be an integer")
    return int(number)


def parse_style_policy(raw: Any, path: str) -> StylePolicy:
    """Reject invalid configuration before any generation request."""
    from services.rei_toei._song_tempo import DEFAULT_DENSITY_SETTINGS
    if raw is None:
        return StylePolicy()
    if not isinstance(raw, Mapping):
        raise ValueError(f"{path} must be an object")
    allowed = {
        "genre_tags", "template", "bpm", "arrangement", "energy", "dense_delivery",
        "sparse_delivery", "density", "quality", "cue_aliases",
    }
    if set(raw) - allowed:
        raise ValueError(f"{path} contains unknown settings: {sorted(set(raw) - allowed)}")
    tags = raw.get("genre_tags", [])
    if not isinstance(tags, list) or not tags:
        raise ValueError(f"{path}.genre_tags must be a nonempty list")
    genres = tuple(_text(tag, f"{path}.genre_tags") for tag in tags)
    template = _text(raw.get("template"), f"{path}.template")
    bpm = raw.get("bpm")
    if not isinstance(bpm, Mapping) or set(bpm) != {"min", "max", "default"}:
        raise ValueError(f"{path}.bpm needs min, max and default")
    low, high, default = (
        _integer(bpm[key], f"{path}.bpm.{key}", 30, 300)
        for key in ("min", "max", "default")
    )
    if not low <= default <= high:
        raise ValueError(f"{path}.bpm must satisfy min <= default <= max")
    quality = raw.get("quality", {})
    if not isinstance(quality, Mapping):
        raise ValueError(f"{path}.quality must be an object")
    quality_defaults = {
        "min_chorus_lines": 2, "min_bridge_lines": 4, "max_borrowed_lines": 1,
        "verse_repeat_threshold": 0.5, "uppercase_chorus": True,
        "remove_bridge_echoes": True,
    }
    if set(quality) - quality_defaults.keys():
        raise ValueError(f"{path}.quality contains unknown settings")
    settings = {**quality_defaults, **quality}
    for key in ("uppercase_chorus", "remove_bridge_echoes"):
        if not isinstance(settings[key], bool):
            raise ValueError(f"{path}.quality.{key} must be boolean")
    density = raw.get("density", {})
    if not isinstance(density, Mapping) or set(density) - DEFAULT_DENSITY_SETTINGS.keys():
        raise ValueError(f"{path}.density must contain supported density settings")
    parsed_density = {
        key: _number(value, f"{path}.density.{key}", 0.01, 300)
        for key, value in density.items()
    }
    merged_density = {**DEFAULT_DENSITY_SETTINGS, **parsed_density}
    if (
        merged_density["base_bpm"] > merged_density["max_bpm"]
        or merged_density["sparse_syllables"] > merged_density["dense_syllables"]
    ):
        raise ValueError(f"{path}.density has inverted tempo or syllable bounds")
    aliases = raw.get("cue_aliases", {})
    if not isinstance(aliases, Mapping):
        raise ValueError(f"{path}.cue_aliases must be an object")
    parsed_aliases = {
        _text(alias, f"{path}.cue_aliases"): _text(target, f"{path}.cue_aliases.{alias}")
        for alias, target in aliases.items()
    }
    return StylePolicy(
        genre_tags=genres, template=template, bpm_range=(low, high, default),
        arrangement=_text(raw.get("arrangement"), f"{path}.arrangement"),
        energy=_text(raw["energy"], f"{path}.energy") if "energy" in raw else "",
        dense_delivery=_text(raw["dense_delivery"], f"{path}.dense_delivery")
        if "dense_delivery" in raw else None,
        sparse_delivery=_text(raw["sparse_delivery"], f"{path}.sparse_delivery")
        if "sparse_delivery" in raw else None,
        density=parsed_density, cue_aliases=parsed_aliases,
        min_chorus_lines=_integer(settings["min_chorus_lines"], f"{path}.quality.min_chorus_lines", 1, 32),
        min_bridge_lines=_integer(settings["min_bridge_lines"], f"{path}.quality.min_bridge_lines", 0, 32),
        max_borrowed_lines=_integer(settings["max_borrowed_lines"], f"{path}.quality.max_borrowed_lines", 0, 100),
        verse_repeat_threshold=_number(settings["verse_repeat_threshold"], f"{path}.quality.verse_repeat_threshold", 0.01, 1),
        uppercase_chorus=settings["uppercase_chorus"],
        remove_bridge_echoes=settings["remove_bridge_echoes"],
    )


def apply_song_style(concept: SongConcept, style: StylePolicy, *, initial_tempo: bool = False) -> None:
    if style.genre_tags and tuple(concept.genre_tags) != style.genre_tags:
        logger.info("Selected profile replaces genre tags %s with %s", concept.genre_tags, style.genre_tags)
        concept.genre_tags = list(style.genre_tags)
    if initial_tempo and style.bpm_range:
        low, high, _ = style.bpm_range
        fitted = max(low, min(high, concept.bpm))
        if fitted != concept.bpm:
            logger.info("Selected profile adjusts initial tempo %d -> %d BPM", concept.bpm, fitted)
            concept.bpm = fitted


def style_template_key(style: StylePolicy, domain: ReiDomainKnowledge, fallback: str) -> str:
    if style.template is None:
        return fallback
    template = domain.suno_prompt_templates.get(style.template)
    if not isinstance(template, str) or not template.strip():
        raise ValueError(f"Selected style template {style.template!r} is missing or not a string")
    try:
        template.format(bpm=style.bpm_range[2] if style.bpm_range else 142, mood="expressive")
    except (KeyError, IndexError, ValueError) as exc:
        raise ValueError(f"Selected style template {style.template!r} has invalid placeholders") from exc
    return style.template


def fit_style_tempo(
    concept: SongConcept, lyrics: str, domain: ReiDomainKnowledge, style: StylePolicy,
) -> TempoFit:
    from services.rei_toei._song_tempo import fit_tempo_to_lyrics

    settings = {**(domain.bpm_and_mood or {}).get("lyric_density_to_bpm", {}), **style.density}
    tempo = fit_tempo_to_lyrics(
        concept.bpm, lyrics, settings,
        dense_delivery=style.dense_delivery, sparse_delivery=style.sparse_delivery,
    )
    if tempo.raised:
        logger.info("Raised tempo %d -> %d BPM for %.1f median syllables per sung line.",
                    tempo.concept_bpm, tempo.bpm, tempo.median_syllables)
        concept.bpm = tempo.bpm
    return tempo
