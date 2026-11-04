"""Tests for deterministic lyric tidy-ups (echo parentheses, stray drops, bridge copies, 、)."""

import json
from unittest.mock import MagicMock

import pytest

from services.rei_toei._hook_translation import clean_translation
from services.rei_toei._song_tidy import strip_echo_parenthetical, tidy_song_sections


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("PULSE CODE (PULSE CODE)", "PULSE CODE"),
        ("PULSE CODE (Pulse Code)", "PULSE CODE"),
        ("Hold the light (the light)", "Hold the light"),
        ("Hold the light (Oh oh oh)", "Hold the light (Oh oh oh)"),
        ("Signal flux pulse (信号)", "Signal flux pulse (信号)"),
        ("(chaos)", "(chaos)"),
    ],
)
def test_strip_echo_parenthetical_only_removes_repeats(line, expected):
    assert strip_echo_parenthetical(line) == expected


def test_tidy_fixes_the_agent_pulse_code_song():
    payload = {
        "pre_chorus": "[Pre-Chorus]\n重要なクラッシュ、突然のバースト、\nA critical crash, a sudden burst,",
        "chorus": "[Chorus]\nPULSE CODE (PULSE CODE)\nSIGNALS DANCE, LOGIC FLOWS DEEP",
        "bridge": (
            "[Bridge]\nPULSE CODE (Pulse Code)\n(chaos)\nThe truth unfolds in binary grace\n"
            "(bass drop)\nElectricity hums with clarity\n[Heavy Bass Drop]"
        ),
        "drop": "[Drop]\n(bass drop)\nFrequencies resonate",
    }

    tidy_song_sections(payload)

    assert payload["chorus"].splitlines()[1] == "PULSE CODE"
    assert payload["bridge"].splitlines() == [
        "[Bridge]", "(chaos)", "The truth unfolds in binary grace", "Electricity hums with clarity",
    ]
    assert payload["drop"] == "[Drop]\n(bass drop)\nFrequencies resonate"
    # Japanese loses its dangling 、; English punctuation is left alone.
    assert payload["pre_chorus"].splitlines()[1:] == [
        "重要なクラッシュ、突然のバースト", "A critical crash, a sudden burst,",
    ]


def test_tidy_keeps_bridge_that_only_repeats_the_chorus():
    payload = {"chorus": "[Chorus]\nPulse code", "bridge": "[Bridge]\nPulse code"}
    tidy_song_sections(payload)
    assert payload["bridge"] == "[Bridge]\nPulse code"


def test_tidy_strips_emoji_before_hooks_are_chosen():
    payload = {"verse_1": "[Verse 1]\n✨✨\nGlitching signals ⚡\n\n霧の中、📐が浮かぶ"}

    tidy_song_sections(payload)

    assert payload["verse_1"] == "[Verse 1]\nGlitching signals\n\n霧の中、が浮かぶ"


def test_clean_translation_drops_dangling_comma():
    assert clean_translation("重要なクラッシュ、突然のバースト、") == "重要なクラッシュ、突然のバースト"


def test_compose_lyrics_tidies_before_translation(monkeypatch, tmp_path):
    from services.rei_toei import _argos_fallback
    from services.rei_toei._suno_pipeline import compose_lyrics
    from tests.test_rei_hook_translation import SONG, _concept, _domain, _persona

    monkeypatch.setenv("REI_BILINGUAL_STRATEGY", "translate")
    monkeypatch.setenv("REI_JAPANESE_LYRIC_PROBABILITY", "0.0")
    monkeypatch.setenv("REI_ARGOS_MODEL_DIR", str(tmp_path))
    monkeypatch.setattr(_argos_fallback, "_CACHE", {})
    song = dict(SONG)
    song["chorus"] = "[Chorus]\nPulse code (pulse code)\nNew cyberforms arise"
    song["bridge"] = SONG["bridge"] + "\n(bass drop)\nPulse code"
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(song)

    lyrics = compose_lyrics(_concept(), _persona(), _domain(), ollama=ollama)

    assert "PULSE CODE\n" in lyrics.chorus and "(PULSE CODE)" not in lyrics.chorus
    assert "bass drop" not in lyrics.bridge.lower()
    assert "Pulse code" not in lyrics.bridge


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("A fragmented mind cries for light. (34 chars)", "A fragmented mind cries for light."),
        ("COMMAND REIGNS SUPREME IN THE DATA VORTEX (38 chars, UPPERCASE)",
         "COMMAND REIGNS SUPREME IN THE DATA VORTEX"),
        ("A new order, syntax rectified. ()", "A new order, syntax rectified."),
        ("LOUD LINE (ALL-CAPS)", "LOUD LINE"),
        ("No leak here (Oh oh)", "No leak here (Oh oh)"),
        ("Count it (3 times)", "Count it (3 times)"),
    ],
)
def test_character_count_notes_leave_no_empty_parentheses(raw: str, expected: str) -> None:
    from services.rei_toei._suno_pipeline import _normalize_suno_section

    assert _normalize_suno_section(raw, "Verse 1").splitlines()[1] == expected
