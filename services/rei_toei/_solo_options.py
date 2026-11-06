"""Prompt guidance for configurable instrumental solo styles."""

from collections.abc import Mapping
from typing import Any

from services.rei_toei._stage_policy import load_stage_policy


def build_solo_style_guidance(lyrical_structure: Mapping[str, Any]) -> str:
    """Describe optional solo choices without requiring any particular style."""
    if not isinstance(lyrical_structure, Mapping):
        raise ValueError("Rei lyrical_structure must be an object containing solo options")
    if "solo" not in lyrical_structure:
        return ""
    solo = lyrical_structure["solo"]
    if not isinstance(solo, dict):
        raise ValueError("Rei lyrical_structure.solo must be an object")
    if "instrumental_options" not in solo:
        return ""
    configured = solo["instrumental_options"]
    if not isinstance(configured, list):
        raise ValueError("Rei lyrical_structure.solo.instrumental_options must be a list")

    options: list[str] = []
    for option in configured:
        if (
            not isinstance(option, str)
            or not option.strip()
            or any(char in option for char in "[]\r\n")
        ):
            raise ValueError("Rei solo options must be nonempty, unbracketed single-line names")
        options.append(option.strip())
    if not options:
        return ""
    rule = load_stage_policy(lyrical_structure).rule("solo")
    if rule is None or rule.content != "instrumental":
        return ""

    labels = ", ".join(f"[{option}]" for option in options)
    return (
        f"OPTIONAL SOLO PALETTE: {labels}. "
        "When including a solo, choose a style that fits the song's genre, mood, story, "
        "and dynamics, or invent another fitting style. Honor any requested instrument. "
        f"Put the chosen style as its own square-bracketed cue beneath [{rule.label}], with any "
        "instrumental directions in separate brackets. Do not copy the full list or "
        "force a guitar solo into every song."
    )
