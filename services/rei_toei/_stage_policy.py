"""Validated, explicitly selected song-section and stage-cue profiles."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from services.rei_toei._style_policy import StylePolicy, parse_style_policy
# These are Lyrics field names and parser aliases, not required musical sections.
FIELD_LABELS = {
    "intro": "Instrumental Build", "verse_1": "Verse 1",
    "pre_chorus": "Pre-Chorus", "chorus": "Chorus", "verse_2": "Verse 2",
    "bridge": "Bridge", "drop": "Drop", "solo": "Solo",
    "breakdown": "Breakdown", "outro": "Outro",
}
_DEFAULT_KNOWLEDGE = Path(__file__).resolve().parents[2] / "data/avatar/rei_toei_domain_knowledge.json"


@dataclass(frozen=True)
class SectionRule:
    field: str
    label: str
    required: bool
    content: str
    cues: tuple[str, ...]

    def guidance(self) -> str:
        cues = " ".join(f"[{cue}]" for cue in self.cues)
        body = "sung lines" if self.content == "sung" else "bracketed instrumental directions only"
        return f"[{self.label}] {cues} header, then {body}, one per line".replace("  ", " ")


@dataclass(frozen=True)
class StagePolicy:
    name: str
    sections: tuple[SectionRule, ...]
    intro_verse_label: str | None
    intro_primer: str | None
    optional_cues: tuple[str, ...]
    style: StylePolicy = StylePolicy()

    @property
    def required_fields(self) -> tuple[str, ...]:
        return tuple(rule.field for rule in self.sections if rule.required)

    def rule(self, field: str) -> SectionRule | None:
        return next((rule for rule in self.sections if rule.field == field), None)

    def aliases(self) -> dict[str, str]:
        aliases = {label.casefold(): field for field, label in FIELD_LABELS.items()}
        aliases.update({
            "intro": "intro", "intro verse": "intro_verse", "verse1": "verse_1",
            "verse2": "verse_2", "pre chorus": "pre_chorus", "prechorus": "pre_chorus",
        })
        aliases.update({rule.label.casefold(): rule.field for rule in self.sections})
        if self.intro_verse_label:
            aliases[self.intro_verse_label.casefold()] = "intro_verse"
        return aliases

    def header_pattern(self) -> re.Pattern[str]:
        labels = sorted(self.aliases(), key=len, reverse=True)
        return re.compile(r"(?im)^[ \t]*\[(?P<label>" + "|".join(map(re.escape, labels)) + r")\][ \t]*")

    def canonicalize(self, text: str) -> str:
        aliases = self.aliases()
        return self.header_pattern().sub(
            lambda match: (
                "[Intro Verse]" if aliases[match["label"].casefold()] == "intro_verse"
                else f"[{FIELD_LABELS[aliases[match['label'].casefold()]]}]"
            ),
            text,
        )

    def prompt_guidance(self) -> str:
        lines = [
            f"Stage-cue profile: {self.name}. Use only these JSON fields, in this order.",
            "Required fields: " + ", ".join(self.required_fields) + ".",
            "Optional fields may be omitted or empty. Do not invent disabled sections.",
            "Never sing or translate an instrumental cue.",
        ]
        for rule in self.sections:
            lines.append(f"- {rule.field} ({'required' if rule.required else 'optional'}): {rule.guidance()}")
        if self.optional_cues:
            lines.append("Optional sound cues: " + ", ".join(f"[{cue}]" for cue in self.optional_cues) + ".")
        if self.rule("intro"):
            lines.append(
                f"Intro primer: {self.intro_primer} immediately after the intro header."
                if self.intro_primer else "No mandatory intro vocalization primer."
            )
            if self.intro_verse_label:
                lines.append(f"Separate sung opening lines under [{self.intro_verse_label}].")
        return "\n".join(lines)


def _label(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip() or re.search(r"[\[\]()\r\n]", value):
        raise ValueError(f"{path} must be a nonempty label without brackets, parentheses, or newlines")
    return value.strip()


def _parse_profile(name: str, raw: Any) -> StagePolicy:
    path = f"lyrical_structure.stage_cues.profiles.{name}"
    if not isinstance(raw, Mapping) or not isinstance(raw.get("sections"), Mapping) or not raw["sections"]:
        raise ValueError(f"{path}.sections must be a nonempty object")
    sections: list[SectionRule] = []
    labels: set[str] = set()
    canonical = {label.casefold(): field for field, label in FIELD_LABELS.items()}
    canonical.update({"intro": "intro", "intro verse": "intro_verse"})
    for field, settings in raw["sections"].items():
        section_path = f"{path}.sections.{field}"
        if field not in FIELD_LABELS or not isinstance(settings, Mapping):
            raise ValueError(f"{section_path} must describe a supported Lyrics field")
        label = _label(settings.get("label"), f"{section_path}.label")
        if label.casefold() in labels or canonical.get(label.casefold(), field) != field:
            raise ValueError(f"{section_path}.label conflicts with another section")
        labels.add(label.casefold())
        required, content = settings.get("required"), settings.get("content")
        if not isinstance(required, bool) or not isinstance(content, str) or content not in {"sung", "instrumental"}:
            raise ValueError(f"{section_path} needs boolean required and content sung or instrumental")
        cues = settings.get("cues", [])
        if not isinstance(cues, list):
            raise ValueError(f"{section_path}.cues must be a list of unbracketed labels")
        parsed_cues = tuple(_label(cue, f"{section_path}.cues") for cue in cues)
        if len(set(cue.casefold() for cue in parsed_cues)) != len(parsed_cues):
            raise ValueError(f"{section_path}.cues contains duplicate labels")
        sections.append(SectionRule(field, label, required, content, parsed_cues))
    intro_verse = raw.get("intro_verse_label")
    if intro_verse is not None:
        intro_verse = _label(intro_verse, f"{path}.intro_verse_label")
        if intro_verse.casefold() in labels or canonical.get(intro_verse.casefold(), "intro_verse") != "intro_verse":
            raise ValueError(f"{path}.intro_verse_label conflicts with another section")
    primer = raw.get("intro_primer")
    if primer is not None and (
        not isinstance(primer, str) or not re.fullmatch(r"\([^()\[\]\r\n]+\)", primer)
    ):
        raise ValueError(f"{path}.intro_primer must be a parenthesized vocalization or null")
    if not any(rule.required and rule.content == "sung" for rule in sections):
        raise ValueError(f"{path} must require at least one sung section")
    if (primer or intro_verse) and not any(rule.field == "intro" for rule in sections):
        raise ValueError(f"{path} defines intro settings without an intro section")
    all_headers = labels | {label.casefold() for label in canonical}
    if intro_verse:
        all_headers.add(intro_verse.casefold())
    if any(cue.casefold() in all_headers for rule in sections for cue in rule.cues):
        raise ValueError(f"{path} uses a section header as an instrumental cue")
    optional = raw.get("optional_cues", [])
    if not isinstance(optional, list):
        raise ValueError(f"{path}.optional_cues must be a list")
    optional_cues = tuple(_label(cue, f"{path}.optional_cues") for cue in optional)
    style = parse_style_policy(raw.get("style"), f"{path}.style")
    allowed_cues = {cue.casefold() for rule in sections for cue in rule.cues}
    allowed_cues.update(cue.casefold() for cue in optional_cues)
    if any(target.casefold() not in allowed_cues for target in style.cue_aliases.values()):
        raise ValueError(f"{path}.style.cue_aliases targets must be configured cues")
    return StagePolicy(name, tuple(sections), intro_verse, primer, optional_cues, style)


def load_stage_policy(lyrical_structure: Mapping[str, Any] | None = None) -> StagePolicy:
    """Resolve and validate profiles; legacy knowledge uses the shipped JSON policy."""
    if lyrical_structure is not None and not isinstance(lyrical_structure, Mapping):
        raise ValueError("Rei lyrical_structure must be an object")
    legacy = lyrical_structure is not None and "stage_cues" not in lyrical_structure
    if lyrical_structure is None or legacy:
        with _DEFAULT_KNOWLEDGE.open(encoding="utf-8") as handle:
            settings = json.load(handle).get("lyrical_structure", {}).get("stage_cues")
    else:
        settings = lyrical_structure["stage_cues"]
    if not isinstance(settings, Mapping) or not isinstance(settings.get("profiles"), Mapping):
        raise ValueError("lyrical_structure.stage_cues must contain a profiles object")
    profiles = {}
    for name, raw in settings["profiles"].items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Stage-cue profile names must be nonempty strings")
        profiles[name] = _parse_profile(name, raw)
    active = settings.get("active_profile")
    if not isinstance(active, str) or active not in profiles:
        raise ValueError("lyrical_structure.stage_cues.active_profile must name a configured profile")
    return replace(profiles[active], style=StylePolicy()) if legacy else profiles[active]
