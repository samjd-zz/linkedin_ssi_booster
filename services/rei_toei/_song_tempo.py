"""Fit a song's tempo and vocal delivery to how densely its lyric lines are packed.

Long, syllable-heavy lines sound cramped at a mid-tempo groove; a faster tempo
gives Suno room to sing them. The concept BPM is chosen before lyrics exist, so
it is treated as a starting point and only ever raised here.
"""

from __future__ import annotations

import logging
import re
import statistics
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from services.rei_toei._lyric_romaji import _get_kakasi

logger = logging.getLogger(__name__)

DEFAULT_DENSITY_SETTINGS: Dict[str, float] = {
    "base_bpm": 145,
    "base_syllables": 9,
    "bpm_per_syllable": 6.25,
    "max_bpm": 175,
    # One Japanese mora is sung faster than an English syllable.
    "japanese_mora_weight": 0.6,
    "dense_syllables": 12,
    "sparse_syllables": 8,
}
DENSE_DELIVERY = "rapid-fire syllabic vocaloid delivery"
SPARSE_DELIVERY = "spacious punchy hook phrasing"

_JAPANESE_RUN_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff々ー]+")
_KANA_RE = re.compile(r"[\u3041-\u3096\u30a1-\u30fa\u30fc]")
_KANJI_RE = re.compile(r"[\u3400-\u9fff々]")
_SMALL_KANA = frozenset("ゃゅょぁぃぅぇぉゎャュョァィゥェォヮ")
_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+")
_PAREN_RE = re.compile(r"[(（][^()（）]*[)）]")


@dataclass(frozen=True)
class TempoFit:
    """Tempo chosen for the finished lyrics and why."""

    bpm: int
    concept_bpm: int
    median_syllables: float
    delivery: str

    @property
    def raised(self) -> bool:
        return self.bpm > self.concept_bpm


def _english_syllables(word: str) -> int:
    if word.isdigit():
        return 2 * len(word)
    lowered = word.lower().replace("'", "")
    count = len(re.findall(r"[aeiouy]+", lowered))
    if count > 1 and lowered.endswith("e") and not lowered.endswith(("le", "ee")):
        count -= 1
    if count > 1 and lowered.endswith(("es", "ed")) and not lowered.endswith(
        ("ted", "ded", "ses", "zes", "ces", "ges", "ies")
    ):
        count -= 1
    return max(count, 1)


def _japanese_mora(text: str) -> int:
    kakasi = _get_kakasi()
    if kakasi is not None:
        try:
            text = "".join(chunk["hira"] for chunk in kakasi.convert(text))
        except (TypeError, ValueError, KeyError, UnicodeError) as exc:
            logger.debug("Mora reading failed; estimating from script: %s", exc)
    kana = sum(1 for char in _KANA_RE.findall(text) if char not in _SMALL_KANA)
    # Unread kanji average about two mora each.
    return kana + 2 * len(_KANJI_RE.findall(text))


def line_syllables(line: str, japanese_mora_weight: float) -> float:
    """Sung syllables in one lyric line, Japanese mora scaled to English syllables."""
    text = _PAREN_RE.sub(" ", line)
    mora = sum(_japanese_mora(run) for run in _JAPANESE_RUN_RE.findall(text))
    english = sum(_english_syllables(word) for word in _WORD_RE.findall(_JAPANESE_RUN_RE.sub(" ", text)))
    return english + mora * japanese_mora_weight


def sung_line_syllables(lyrics: str, japanese_mora_weight: float) -> List[float]:
    """Syllable counts for sung lines, skipping labels, cues, and vocalizations."""
    counts: List[float] = []
    for raw in lyrics.splitlines():
        line = raw.strip()
        if not line or line[0] in "[(（":
            continue
        count = line_syllables(line, japanese_mora_weight)
        if count:
            counts.append(count)
    return counts


def _settings(overrides: Optional[Mapping[str, Any]]) -> Dict[str, float]:
    settings = dict(DEFAULT_DENSITY_SETTINGS)
    for key, value in (overrides or {}).items():
        if key in settings and isinstance(value, (int, float)) and not isinstance(value, bool):
            settings[key] = float(value)
    return settings


def fit_tempo_to_lyrics(
    concept_bpm: int,
    lyrics: str,
    overrides: Optional[Mapping[str, Any]] = None,
    *,
    dense_delivery: str | None = None,
    sparse_delivery: str | None = None,
) -> TempoFit:
    """Raise the tempo for syllable-dense lyrics and pick a matching vocal delivery.

    Each syllable per line above ``base_syllables`` (median of sung lines) adds
    ``bpm_per_syllable`` to ``base_bpm``, capped at ``max_bpm``. The concept BPM
    is kept when it is already fast enough.
    """
    settings = _settings(overrides)
    counts = sung_line_syllables(lyrics, settings["japanese_mora_weight"])
    if not counts:
        return TempoFit(concept_bpm, concept_bpm, 0.0, "")
    median = float(statistics.median(counts))
    floor = settings["base_bpm"] + (median - settings["base_syllables"]) * settings["bpm_per_syllable"]
    floor_bpm = int(round(min(floor, settings["max_bpm"])))
    bpm = max(concept_bpm, floor_bpm)
    if median >= settings["dense_syllables"]:
        delivery = DENSE_DELIVERY if dense_delivery is None else dense_delivery
    elif median <= settings["sparse_syllables"]:
        delivery = SPARSE_DELIVERY if sparse_delivery is None else sparse_delivery
    else:
        delivery = ""
    return TempoFit(bpm, concept_bpm, round(median, 1), delivery)
