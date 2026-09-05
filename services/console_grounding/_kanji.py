"""Deterministic Kanji teaching aids for the Sam console."""

from __future__ import annotations

import logging
from typing import Any

from services.console_grounding._models import ProjectFact

logger = logging.getLogger(__name__)

try:
    import pykakasi
    _PYKAKASI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYKAKASI_AVAILABLE = False

_KAKASI_INSTANCE: Any | None = None


def _get_kakasi() -> Any | None:
    global _KAKASI_INSTANCE
    if not _PYKAKASI_AVAILABLE:
        return None
    if _KAKASI_INSTANCE is None:
        _KAKASI_INSTANCE = pykakasi.kakasi()
    return _KAKASI_INSTANCE


def _hepburn(text: str) -> str:
    kakasi = _get_kakasi()
    if kakasi is None or not text.strip():
        return ""
    try:
        chunks = kakasi.convert(text)
    except Exception as exc:
        logger.debug("Kanji Hepburn conversion failed: %s", exc)
        return ""
    return " ".join(
        chunk["hepburn"] for chunk in chunks if chunk.get("hepburn")
    ).strip()


def build_kanji_teaching_context(
    facts: list[ProjectFact],
    limit: int = 12,
) -> str:
    """Build LLM context with domain-backed Kanji, meanings, and Hepburn readings."""
    domain_facts = [
        fact for fact in facts
        if fact.source.startswith("domain:") or fact.company == "Domain Knowledge"
    ]
    if not domain_facts:
        return ""

    meaning_by_character: dict[str, str] = {}
    entries: list[tuple[str, str, ProjectFact]] = []
    for fact in domain_facts:
        for character in fact.project + fact.details + "".join(sorted(fact.tags)):
            if not ("\u4e00" <= character <= "\u9fff") or character in meaning_by_character:
                continue
            meaning = ""
            marker = f"{character} "
            details = fact.details.strip()
            if marker in details and "meaning" in details.lower():
                tail = details[details.find(marker) + len(marker):]
                meaning = tail.split(";", 1)[0].strip()
            meaning_by_character[character] = meaning
            entries.append((character, meaning, fact))
            if len(entries) >= limit:
                break
        if len(entries) >= limit:
            break

    if not entries:
        return ""

    lines = [
        "Kanji teaching aids from loaded domain knowledge:",
        "Use these domain facts for meanings and examples; use the Hepburn readings as pronunciation cues.",
    ]
    for character, meaning, fact in entries:
        reading = _hepburn(character)
        line = f"- {character}"
        if reading:
            line += f" | Hepburn: {reading}"
        if meaning:
            line += f" | Domain meaning: {meaning}"
        line += f" | Domain note: {fact.details}"
        lines.append(line)
    return "\n".join(lines)
