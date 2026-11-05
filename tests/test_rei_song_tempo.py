"""Tempo and vocal delivery fitted to finished Rei lyrics."""

import json
from pathlib import Path

import pytest

from services.rei_toei._models import Lyrics, ReiDomainKnowledge, SongConcept
from services.rei_toei._song_tempo import (
    DENSE_DELIVERY,
    SPARSE_DELIVERY,
    fit_tempo_to_lyrics,
    line_syllables,
    sung_line_syllables,
)
from services.rei_toei._suno_pipeline import assemble_suno_prompt
from services.rei_toei._suno_tags import _build_rich_suno_tags

DENSE_SONG = """[Instrumental Build]
(Ahh ahh ahh)

[Verse 1]
Dawn breaks on Harvard Place, students and pros converge,
思想が会う所でチームが形成され、挑戦は明け方に解ける
[shisou ga au tokoro de chiimu ga keisei sare, chousen wa akegata ni tokeru]
Teams form where minds meet, challenges unravel by dawn.
Entrepreneurs share dreams, mentors guide the quest,
Prototypes rise from chaos, tech's future is tested.

[Chorus]
SKEPTICISM WHISPERS, DOUBTS LINGER, BUT CURIOSITY FIGHTS BACK,
IN THE CRUCIBLE OF CHILLIWACK, FORGE YOUR FUTURE WITH GRIT.
FROM SCATTERED THOUGHTS, INNOVATION FLOWS IN THIS VALLEY'S SOIL.
"""

SPARSE_SONG = """[Verse 1]
Signal wakes inside the core
The buffer heartbeat starts to rise
データの波が走る
[deeta no nami ga hashiru]
We turn the noise into a shape

[Chorus]
BREAK THE CIRCUIT NOW
RENDER THE LIGHT
(Oh oh oh)
"""


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Signal wakes inside the core", 7),
        ("BREAK THE CIRCUIT NOW", 5),
        ("Over 24 hours", 7),
        ("Render the light (shine shine)", 4),
    ],
)
def test_english_line_syllables(line: str, expected: float) -> None:
    assert line_syllables(line, 0.6) == expected


def test_japanese_mora_are_weighted() -> None:
    # で-ー-た-の-な-み-が-は-し-る = 10 mora (long-vowel mark counts).
    assert line_syllables("データの波が走る", 1.0) == pytest.approx(10)
    assert line_syllables("データの波が走る", 0.6) == pytest.approx(6.0)


def test_labels_cues_romaji_and_vocalizations_are_not_counted() -> None:
    counts = sung_line_syllables(SPARSE_SONG, 0.6)

    assert len(counts) == 6


def test_dense_lyrics_raise_tempo_to_about_170() -> None:
    fit = fit_tempo_to_lyrics(145, DENSE_SONG)

    assert 165 <= fit.bpm <= 175
    assert fit.raised
    assert fit.delivery == DENSE_DELIVERY


def test_sparse_lyrics_keep_concept_tempo() -> None:
    fit = fit_tempo_to_lyrics(145, SPARSE_SONG)

    assert fit.bpm == 145
    assert not fit.raised
    assert fit.delivery == SPARSE_DELIVERY


def test_tempo_is_never_lowered() -> None:
    assert fit_tempo_to_lyrics(172, SPARSE_SONG).bpm == 172


def test_tempo_is_capped_and_tunable() -> None:
    wordy = "\n".join(["Every single syllable is crammed into this enormous overflowing lyric line"] * 4)

    assert fit_tempo_to_lyrics(140, wordy).bpm == 175
    assert fit_tempo_to_lyrics(140, wordy, {"max_bpm": 160}).bpm == 160


def test_bad_overrides_fall_back_to_defaults() -> None:
    fit = fit_tempo_to_lyrics(145, DENSE_SONG, {"max_bpm": "fast", "base_bpm": True})

    assert 165 <= fit.bpm <= 175


def test_no_sung_lines_keeps_concept() -> None:
    fit = fit_tempo_to_lyrics(150, "[Solo]\n[Glitch Synth Solo]")

    assert fit.bpm == 150 and fit.median_syllables == 0.0 and fit.delivery == ""


def test_domain_knowledge_holds_density_calibration() -> None:
    data = json.loads(Path("data/avatar/rei_toei_domain_knowledge.json").read_text(encoding="utf-8"))
    settings = data["bpm_and_mood"]["lyric_density_to_bpm"]

    assert settings["base_bpm"] == 145
    assert settings["max_bpm"] == 175


def _concept(bpm: int = 145) -> SongConcept:
    return SongConcept(
        song_id="song",
        title="Fraser Forge",
        theme="Hackathon",
        mood="playful_technical",
        bpm=bpm,
        genre_tags=["cyberpop", "industrial techno"],
        narrative_arc="Teams forge ideas overnight",
        evidence_ids=[],
        generated_at="2026-11-05",
    )


def _domain() -> ReiDomainKnowledge:
    return ReiDomainKnowledge(
        schema_version="1",
        music_theory={},
        tidal_cycles_syntax={},
        genre_production_techniques={},
        bpm_and_mood={},
        synth_selection_guidelines={},
        lyrical_structure={},
        technical_metaphor_library={},
        suno_prompt_templates={
            "cyberpunk_electro_template": "144 bpm, cyberpop electro, {mood} sweet AI vocaloid",
        },
        production_notes={},
    )


def test_delivery_tag_follows_bpm_and_fast_tempo_gets_breakneck_energy() -> None:
    tags = _build_rich_suno_tags(_concept(170), _domain(), "cyberpunk_electro_template", delivery=DENSE_DELIVERY)
    items = tags.split(", ")

    assert items[items.index("170 bpm") + 1] == DENSE_DELIVERY
    assert "breakneck hyperspeed vocaloid energy" in items
    assert "144 bpm" not in items


def _lyrics(verse: str, chorus: str) -> Lyrics:
    return Lyrics(
        verse_1=verse,
        chorus=chorus,
        verse_2=verse,
        bridge=verse,
        evidence_ids=[],
        intro="[Instrumental Build]\n(Ahh ahh ahh)\nThe forge is warming up tonight",
        drop="[Drop]\n[Heavy Bass Drop]\n" + verse,
        solo="[Solo]\n[Glitch Synth Solo]",
        outro=verse,
    )


def test_assembly_raises_bpm_for_dense_lyrics_and_updates_concept() -> None:
    concept = _concept(145)
    dense_verse = (
        "Dawn breaks on Harvard Place, students and pros converge,\n"
        "Teams form where minds meet, challenges unravel by dawn.\n"
        "Prototypes rise from chaos, technology's future is tested."
    )
    prompt = assemble_suno_prompt(
        concept,
        _lyrics(dense_verse, "SKEPTICISM WHISPERS, DOUBTS LINGER, BUT CURIOSITY FIGHTS BACK"),
        _domain(),
    )

    assert concept.bpm >= 165
    assert f"{concept.bpm} bpm" in prompt.suno_prompt
    assert DENSE_DELIVERY in prompt.suno_prompt
    assert prompt.metadata["bpm"] == concept.bpm
    assert prompt.metadata["concept_bpm"] == 145
    assert prompt.metadata["vocal_delivery"] == DENSE_DELIVERY


def test_assembly_keeps_bpm_for_short_lines() -> None:
    concept = _concept(145)
    prompt = assemble_suno_prompt(
        concept, _lyrics("Signal wakes\nThe core is warm", "BREAK THE CIRCUIT NOW"), _domain()
    )

    assert concept.bpm == 145
    assert "145 bpm" in prompt.suno_prompt
    assert prompt.metadata["concept_bpm"] == 145
