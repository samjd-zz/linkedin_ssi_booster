"""Detect garbled LLM output (token salad) before it reaches the user.

Some local runtimes (notably IPEX-LLM on Intel iGPUs) occasionally decode
long, prefix-cached prompts into random vocabulary fragments: mixed scripts
glued together, code identifiers, and stray punctuation. These heuristics
flag that failure mode without penalising normal English, Japanese teaching
replies, or technical prose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

GARBLE_MIN_ANOMALIES = 6
GARBLE_DENSITY_THRESHOLD = 3.0  # anomalies per 100 non-space characters

_LOWER_LATIN = r"a-z\u00DF-\u024F"
# Han only: Japanese legitimately glues English to kana ("Pythonで", "LLMの").
_HAN = r"\u3400-\u9FFF\uF900-\uFAFF"
_FOREIGN_SCRIPT = r"\u0400-\u04FF\u0590-\u06FF\u0900-\u097F\u0E00-\u0E7F\uAC00-\uD7AF"

_SCRIPT_SWITCH_RE = re.compile(rf"(?:[{_LOWER_LATIN}]{{2}}[{_HAN}])|(?:[{_HAN}][{_LOWER_LATIN}]{{2}})")
_FOREIGN_RUN_RE = re.compile(rf"[{_FOREIGN_SCRIPT}]+")
_CODE_IDENT_RE = re.compile(r"(?<![A-Za-z])(?:[A-Z][a-z]+){2,}[A-Z]?[a-z]*|\b[a-z]+(?:[A-Z][a-z]+){2,}")
_DOT_MEMBER_RE = re.compile(r"(?<![\w.])\.[a-z][A-Za-z]{2,}")
_SYMBOL_CLUSTER_RE = re.compile(r"[\"'();\[\]{}<>=$#*\\|]{3,}")
_ACCENTED_WORD_RE = re.compile(r"\b[a-z]*[\u00E0-\u00FF][a-z]*\b")


@dataclass(frozen=True)
class GarbleReport:
    """Anomaly counts behind a garbled/clean verdict."""

    script_switches: int
    foreign_runs: int
    code_tokens: int
    symbol_clusters: int
    accented_words: int
    chars: int

    @property
    def anomalies(self) -> int:
        return (
            self.script_switches
            + self.foreign_runs
            + self.code_tokens
            + self.symbol_clusters
            + self.accented_words
        )

    @property
    def density(self) -> float:
        return self.anomalies * 100.0 / max(1, self.chars)

    @property
    def is_garbled(self) -> bool:
        return self.anomalies >= GARBLE_MIN_ANOMALIES and self.density >= GARBLE_DENSITY_THRESHOLD


def analyse_garble(text: str) -> GarbleReport:
    """Count token-salad signals in ``text``."""
    code_tokens = len(_CODE_IDENT_RE.findall(text)) + len(_DOT_MEMBER_RE.findall(text))
    return GarbleReport(
        script_switches=len(_SCRIPT_SWITCH_RE.findall(text)),
        foreign_runs=len(_FOREIGN_RUN_RE.findall(text)),
        code_tokens=code_tokens,
        symbol_clusters=len(_SYMBOL_CLUSTER_RE.findall(text)),
        accented_words=len(_ACCENTED_WORD_RE.findall(text)),
        chars=len(re.sub(r"\s+", "", text)),
    )


def looks_garbled(text: str) -> bool:
    """Return True when ``text`` looks like decoder token salad."""
    return bool(text) and analyse_garble(text).is_garbled
