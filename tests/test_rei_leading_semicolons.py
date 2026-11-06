"""Tests for stripping stray leading semicolons from Rei lyric lines."""

import pytest

from services.rei_toei._song_tidy import tidy_song_sections
from services.rei_toei._suno_blocks import _append_normalized_section
from services.rei_toei._suno_cleanup import strip_leading_semicolons


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("; signals dance through neon veins", "signals dance through neon veins"),
        ("; (Ahh ahh ahh) neon pulses", "(Ahh ahh ahh) neon pulses"),
        ("[; Epic Guitar Solo]", "[Epic Guitar Solo]"),
        ("；（アッハ）ネオンが脈打つ", "（アッハ）ネオンが脈打つ"),
        (";; DATA FLOWS!", "DATA FLOWS!"),
        ("  ; indented line", "  indented line"),
    ],
)
def test_strip_leading_semicolons_cleans_line_start(line: str, expected: str) -> None:
    assert strip_leading_semicolons(line) == expected


def test_strip_leading_semicolons_keeps_mid_line_semicolons() -> None:
    assert strip_leading_semicolons("Neon fades; harmony remains") == "Neon fades; harmony remains"


def test_strip_leading_semicolons_drops_semicolon_only_lines() -> None:
    text = "[Outro]\n;\nNeon glow\n；\n[;]"
    assert strip_leading_semicolons(text) == "[Outro]\nNeon glow"


def test_strip_leading_semicolons_keeps_blank_lines() -> None:
    assert strip_leading_semicolons("[Verse 1]\nLine one\n\nLine two") == "[Verse 1]\nLine one\n\nLine two"


def test_tidy_song_sections_strips_semicolons_before_translation() -> None:
    payload = {
        "verse_1": "[Verse 1]\n; signals dance through neon veins\nNeon flickers",
        "chorus": "[Chorus]\n; DATA FLOWS! LIGHTS GLITCH!",
        "solo": "[Solo]\n[; Epic Guitar Solo]",
    }
    tidy_song_sections(payload)

    assert ";" not in payload["verse_1"]
    assert "signals dance through neon veins" in payload["verse_1"]
    assert payload["chorus"].endswith("DATA FLOWS! LIGHTS GLITCH!")
    assert "[Epic Guitar Solo]" in payload["solo"]


def test_section_builder_strips_semicolons_from_japanese_lines() -> None:
    blocks: list[str] = []
    block = _append_normalized_section(blocks, "[Outro]\n；ネオンが脈打つ\n; Neon pulses", "Outro")

    assert "；" not in block and "\n;" not in block
    assert "ネオンが脈打つ" in block
    assert "Neon pulses" in block
