"""Repeated-word parenthetical ad-libs are stripped; real vocalizations stay."""

import pytest

from services.rei_toei._song_tidy import tidy_song_sections
from services.rei_toei._suno_cleanup import strip_word_echoes, tidy_vocalization_cues


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("(Shine shine)", ""),
        ("(Safe safe)", ""),
        ("(Thunder thunder)", ""),
        ("  (Shatter shatter)", ""),
        ("(Spark, spark!)", ""),
        ("（Rise rise）", ""),
        ("Stability flickers (Blaze blaze)", "Stability flickers"),
        ("(Oh oh oh)", "(Oh oh oh)"),
        ("(OH OH OH)", "(OH OH OH)"),
        ("(Ahh ahh ahh)", "(Ahh ahh ahh)"),
        ("(Yeah yeah)", "(Yeah yeah)"),
        ("(Na na na)", "(Na na na)"),
        ("(Shine)", "(Shine)"),
        ("(Shine bright)", "(Shine bright)"),
        ("Flares of stability, a new dawn", "Flares of stability, a new dawn"),
        ("[Heavy Bass Drop]", "[Heavy Bass Drop]"),
    ],
)
def test_strip_word_echoes(line: str, expected: str) -> None:
    assert strip_word_echoes(line) == expected


def test_tidy_vocalization_cues_drops_word_echo_lines_outside_intro() -> None:
    outro = (
        "安定の光、新しい朝の始まり\n"
        "[antei no hikari, atarashii asa no hajimari]\n"
        "Flares of stability, a new dawn\n"
        "(Shine shine)\n"
        "Packets fly, networks thrive\n"
        "(Safe safe)\n"
        "(Oh oh oh)"
    )

    assert tidy_vocalization_cues(outro) == (
        "安定の光、新しい朝の始まり\n"
        "[antei no hikari, atarashii asa no hajimari]\n"
        "Flares of stability, a new dawn\n"
        "Packets fly, networks thrive\n"
        "(Oh oh oh)"
    )


def test_tidy_vocalization_cues_keeps_intro_primer_but_drops_intro_echoes() -> None:
    intro = "(Ahh ahh ahh)\nFrequencies pulse, signals crash\n(Shatter shatter)"

    assert tidy_vocalization_cues(intro, intro=True) == (
        "(Ahh ahh ahh)\nFrequencies pulse, signals crash"
    )


def test_tidy_song_sections_strips_echoes_from_sung_sections() -> None:
    payload = {
        "verse_2": "Reboot protocols, reset attempts\n(Rise rise)\nA bridge forms, secure and tight",
        "drop": "[Heavy Bass Drop]\nRising waveforms, steady flow\n(Thunder thunder)",
        "chorus": "SYNTHESIZED ORDER\n(OH OH OH)",
    }

    tidy_song_sections(payload)

    assert payload["verse_2"] == "Reboot protocols, reset attempts\nA bridge forms, secure and tight"
    assert payload["drop"] == "[Heavy Bass Drop]\nRising waveforms, steady flow"
    assert payload["chorus"] == "SYNTHESIZED ORDER\n(OH OH OH)"
