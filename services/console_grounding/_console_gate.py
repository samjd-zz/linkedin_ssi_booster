"""Rebuild a console reply after the truth gate, keeping its line layout."""

from __future__ import annotations

import re
from typing import Iterable

_INNER_SPACES_RE = re.compile(r"(?<=\S) {2,}")


def remove_gated_sentences(text: str, removed_sentences: Iterable[str]) -> str:
    """Return ``text`` without the removed sentences, preserving newlines and list indents.

    The gate joins kept sentences with single spaces, which flattens lists and
    paragraphs; removing the exact sentences from the original keeps the layout.
    """
    result = text
    for sentence in removed_sentences:
        if sentence:
            result = result.replace(sentence, "", 1)
    lines: list[str] = []
    for line in result.splitlines():
        line = _INNER_SPACES_RE.sub(" ", line.rstrip())
        if not line.strip():
            if lines and lines[-1]:
                lines.append("")
            continue
        lines.append(line)
    return "\n".join(lines).strip()
