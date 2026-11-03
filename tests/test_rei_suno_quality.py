"""Required Suno sections and instrumental-only Solo directions."""

import pytest

from services.rei_toei._models import Lyrics, ReiDomainKnowledge, SongConcept
from services.rei_toei._song_tidy import tidy_song_sections
from services.rei_toei._suno_quality import ensure_suno_quality
from services.rei_toei._suno_pipeline import (
    _append_normalized_section,
    _normalize_freeform_suno_reply,
    assemble_suno_prompt,
)


@pytest.fixture
def domain() -> ReiDomainKnowledge:
    return ReiDomainKnowledge(
        schema_version="1", music_theory={}, tidal_cycles_syntax={},
        genre_production_techniques={}, bpm_and_mood={}, synth_selection_guidelines={},
        lyrical_structure={}, technical_metaphor_library={}, suno_prompt_templates={},
        production_notes={},
    )


@pytest.fixture
def concept() -> SongConcept:
    return SongConcept(
        song_id="test", title="Tokyo Skyline", theme="city lights", mood="playful",
        bpm=142, genre_tags=["cyberpop"], narrative_arc="Night becomes dawn",
        evidence_ids=[], generated_at="2026-11-02", lyric_language="bilingual",
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "Synthesizer whispers in the mix\nPulsing beats sync with digital pix",
            "[Solo]\n[Synthesizer whispers in the mix]\n[Pulsing beats sync with digital pix]",
        ),
        ("[Solo]\n[Synth lead rises]", "[Solo]\n[Synth lead rises]"),
        ("[Synth Solo]\n(Filter sweep)", "[Solo]\n[Synth Solo]\n[Filter sweep]"),
        ("シンセが響く", "[Solo]\n[シンセが響く]"),
    ],
)
def test_solo_directions_are_bracketed_without_lyric_cues(
    source: str, expected: str,
) -> None:
    assert _append_normalized_section([], source, "Solo") == expected
    assert _append_normalized_section([], expected, "Solo") == expected


@pytest.mark.parametrize("intro", [None, "", "[Instrumental Build]\n(Ahh ahh ahh)"])
def test_missing_sections_are_repaired_from_existing_hook(
    domain: ReiDomainKnowledge, concept: SongConcept, intro: str | None,
) -> None:
    lyrics = Lyrics(
        verse_1="The night opens", chorus="Tokyo skyline, you are mine",
        verse_2="The morning arrives", bridge="We rise together", evidence_ids=[],
        intro=intro, solo="Synth lead rises", outro="The lights fade",
    )
    result = assemble_suno_prompt(concept, lyrics, domain)
    assert "[Intro Verse]\nTokyo skyline, you are mine" in result.lyrics
    assert "[Drop]\n[Heavy Bass Drop]" in result.lyrics
    assert result.lyrics.index("[Intro Verse]") < result.lyrics.index("[Verse 1]")
    assert result.lyrics.index("[Bridge]") < result.lyrics.index("[Drop]") < result.lyrics.index("[Solo]")
    assert result.metadata["has_intro"] is True
    assert result.metadata["has_drop"] is True
    assert lyrics.intro == intro and lyrics.drop is None
    if intro:
        assert "[Instrumental Build]\n(Ahh ahh ahh)" in result.lyrics


def test_existing_intro_and_drop_are_preserved_without_duplicate_cues(
    domain: ReiDomainKnowledge, concept: SongConcept,
) -> None:
    lyrics = Lyrics(
        verse_1="The night opens", chorus="Stay on this frequency",
        verse_2="The morning arrives", bridge="We rise together", evidence_ids=[],
        intro="(Ahh ahh ahh)\nParticles of light",
        drop="[Heavy Bass Drop]\n[Heavy Bass Drop]\nFeel the pulse",
    )
    result = assemble_suno_prompt(concept, lyrics, domain)
    assert "[Intro Verse]\nParticles of light" in result.lyrics
    assert result.lyrics.count("[Heavy Bass Drop]") == 1
    assert "[Drop]\n[Heavy Bass Drop]\nFeel the pulse" in result.lyrics
    assert _append_normalized_section([], "[Heavy Bass Drop]\nFeel the pulse", "Drop") == (
        "[Drop]\n[Heavy Bass Drop]\nFeel the pulse"
    )


def test_solo_is_not_counted_as_sung_content_before_hook_translation() -> None:
    payload = {"solo": "Synthesizer whispers in the mix\nPulsing beats sync with digital pix"}
    tidy_song_sections(payload)
    assert payload["solo"] == (
        "[Solo]\n[Synthesizer whispers in the mix]\n[Pulsing beats sync with digital pix]"
    )


def test_freeform_song_repairs_sections_and_keeps_surrounding_metadata(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = (
        "Title: Tokyo Skyline\n[Verse 1]\nParticles of light\n"
        "[Chorus]\nStay on this frequency\n[Bridge]\nWe rise together\n"
        "[Solo]\nSynthesizer whispers in the mix\n"
        "Style Tags: cyberpop, 142 bpm"
    )
    result = _normalize_freeform_suno_reply(source)
    assert result.startswith("Title: Tokyo Skyline\n")
    assert result.endswith("Style Tags: cyberpop, 142 bpm")
    assert "[Intro Verse]\nStay on this frequency" in result
    assert "[Drop]\n[Heavy Bass Drop]" in result
    assert "[Solo]\n[Synthesizer whispers in the mix]" in result
    caplog.clear()
    assert _normalize_freeform_suno_reply(result) == result
    assert "Suno quality repair" not in caplog.text


def test_existing_intro_verse_survives_freeform_normalization() -> None:
    source = "[Intro Verse]\nA quiet city\n[Verse 1]\nA new signal\n[Chorus]\nWake up"
    result = _normalize_freeform_suno_reply(source)
    assert result.count("[Intro Verse]") == 1
    assert "[Intro Verse]\nA quiet city" in result


def test_unstructured_reply_is_unchanged() -> None:
    source = "I can help you compose a song about Tokyo."
    assert _normalize_freeform_suno_reply(source) == source


def test_missing_hook_fails_explicitly(
    domain: ReiDomainKnowledge, concept: SongConcept,
) -> None:
    lyrics = Lyrics(verse_1="", chorus="", verse_2="", bridge="", evidence_ids=[])
    with pytest.raises(ValueError, match="Intro Verse"):
        assemble_suno_prompt(concept, lyrics, domain)


def test_reused_japanese_hook_keeps_its_existing_pronunciation_cue() -> None:
    source = "[Verse 1]\nCity lights\n[Chorus]\n光の海\n[hikari no umi]\nA sea of light"
    result = ensure_suno_quality(source)
    assert "[Intro Verse]\n光の海\n[hikari no umi]" in result
    assert "[Chorus]\n光の海\n[hikari no umi]\nA sea of light" in result
    assert ensure_suno_quality(result) == result


def test_empty_intro_verse_uses_a_verse_hook_and_canonical_labels() -> None:
    source = "[intro verse]\n[Whisper]\n[Verse 1]\nCity lights\n[Chorus]\n..."
    result = ensure_suno_quality(source)
    assert "[Intro Verse]\n[Whisper]\nCity lights" in result
    assert "[intro verse]" not in result
    assert "[Drop]\n[Heavy Bass Drop]" in result


def test_solo_instruction_with_inline_tags_has_no_nested_brackets() -> None:
    assert _append_normalized_section([], "Synth [lead] rises", "Solo") == (
        "[Solo]\n[Synth lead rises]"
    )
