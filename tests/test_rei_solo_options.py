"""Rei's configurable, persona-aligned instrumental solo palette."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from services.console_grounding._rei_console import _build_rei_system_prompt
from services.rei_toei._loaders import load_rei_domain_knowledge, load_rei_persona
from services.rei_toei._lyric_romaji import _is_stage_cue_phrase
from services.rei_toei._models import ReiDomainKnowledge, ReiPersonaGraph, SongConcept
from services.rei_toei._suno_cleanup import tag_instrument_cues
from services.rei_toei._suno_pipeline import (
    _append_normalized_section,
    _normalize_freeform_suno_reply,
    assemble_suno_prompt,
    compose_lyrics,
)
from services.rei_toei._suno_quality import ensure_suno_quality


SOLO_OPTIONS = (
    "Epic Guitar Solo",
    "Melodic Synth Solo",
    "Arpeggiated Synth Solo",
    "Glitch Synth Solo",
    "Industrial Percussion Solo",
    "Modulated Bass Solo",
)


@pytest.fixture
def rei(monkeypatch: pytest.MonkeyPatch) -> tuple[ReiPersonaGraph, ReiDomainKnowledge]:
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    monkeypatch.setenv("REI_LYRIC_LANGUAGE", "english")
    return load_rei_persona(), load_rei_domain_knowledge()


def _compose(
    persona: ReiPersonaGraph, domain: ReiDomainKnowledge, solo: str,
) -> tuple[SongConcept, MagicMock, str]:
    concept = SongConcept(
        song_id="palette-test", title="A New Horizon", theme="finding a new path",
        mood="hopeful", bpm=142, genre_tags=["cyberpop"],
        narrative_arc="Leave the old world and find a way home",
        evidence_ids=[], generated_at="2026-11-03", lyric_language="english",
    )
    payload = {
        "intro": "[Instrumental Build]\n(Ahh ahh ahh)\n[Intro Verse]\nAn open door",
        "verse_1": "The lights come on\nA traveler sees the sky",
        "pre_chorus": "The road begins to turn",
        "chorus": "WE FIND A WAY HOME",
        "verse_2": "The rain has finally stopped\nA new horizon glows",
        "bridge": "The darkness lifts\nWe hold the sky\nThe journey changes\nWe start again",
        "drop": "[Heavy Bass Drop]\nRun into the light",
        "solo": f"[Solo]\n[{solo}]\n[A bright melodic passage]",
        "outro": "The night fades",
    }
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(payload)
    lyrics = compose_lyrics(concept, persona, domain, ollama=ollama)
    assert ollama._chat.call_count == 1
    result = assemble_suno_prompt(concept, lyrics, domain)
    return concept, ollama, result.lyrics


def test_loaded_palette_is_available_to_both_generation_paths(
    rei: tuple[ReiPersonaGraph, ReiDomainKnowledge],
) -> None:
    persona, domain = rei
    assert domain.lyrical_structure["solo"]["instrumental_options"] == list(SOLO_OPTIONS)
    _, ollama, _ = _compose(persona, domain, SOLO_OPTIONS[0])
    structured_prompt = ollama._chat.call_args.args[1]
    console_prompt = _build_rei_system_prompt(persona, domain)

    for prompt in (structured_prompt, console_prompt):
        assert all(f"[{option}]" in prompt for option in SOLO_OPTIONS)
        assert "optional" in prompt.lower()
        assert "song" in prompt.lower()
        assert "requested" in prompt.lower()


@pytest.mark.parametrize("solo", ["Epic Guitar Solo", "Glitch Synth Solo", "Modulated Bass Solo"])
def test_model_choice_survives_suno_assembly_without_forcing_guitar(
    rei: tuple[ReiPersonaGraph, ReiDomainKnowledge], solo: str,
) -> None:
    _, ollama, result = _compose(*rei, solo)
    assert f"[Solo]\n[{solo}]\n[A bright melodic passage]" in result
    if solo != "Epic Guitar Solo":
        assert "[Epic Guitar Solo]" not in result
    assert ollama._chat.call_count == 1


def test_custom_palette_replaces_defaults_in_both_prompts(
    rei: tuple[ReiPersonaGraph, ReiDomainKnowledge],
) -> None:
    persona, domain = rei
    domain.lyrical_structure = {
        "solo": {"instrumental_options": [" Theremin Solo ", "Modulated Bass Solo"]}
    }
    _, ollama, result = _compose(persona, domain, "Theremin Solo")
    for prompt in (ollama._chat.call_args.args[1], _build_rei_system_prompt(persona, domain)):
        assert "[Theremin Solo]" in prompt
        assert "[Modulated Bass Solo]" in prompt
        assert "[Epic Guitar Solo]" not in prompt
    assert "[Solo]\n[Theremin Solo]" in result


@pytest.mark.parametrize(
    "structure",
    [{}, {"solo": {}}, {"solo": {"instrumental_options": []}}],
)
def test_missing_or_empty_optional_palette_keeps_existing_generation_working(
    rei: tuple[ReiPersonaGraph, ReiDomainKnowledge], structure: dict,
) -> None:
    persona, domain = rei
    domain.lyrical_structure = structure
    _, ollama, result = _compose(persona, domain, "Synth Solo")
    assert "[Synth Solo]" in result
    assert "[Epic Guitar Solo]" not in ollama._chat.call_args.args[1]
    assert "[Epic Guitar Solo]" not in _build_rei_system_prompt(persona, domain)


@pytest.mark.parametrize(
    "structure",
    [
        {"solo": []},
        {"solo": {"instrumental_options": "Epic Guitar Solo"}},
        {"solo": {"instrumental_options": [42]}},
        {"solo": {"instrumental_options": [" "]}},
        {"solo": {"instrumental_options": ["[Nested Solo]"]}},
        {"solo": {"instrumental_options": ["First\nSecond"]}},
    ],
)
def test_invalid_palette_fails_before_calling_model(
    rei: tuple[ReiPersonaGraph, ReiDomainKnowledge], structure: dict,
) -> None:
    persona, domain = rei
    domain.lyrical_structure = structure
    concept = SongConcept(
        song_id="test", title="Test", theme="test", mood="hopeful", bpm=142,
        genre_tags=["cyberpop"], narrative_arc="change", evidence_ids=[],
        generated_at="2026-11-03", lyric_language="english",
    )
    ollama = MagicMock()
    with pytest.raises(ValueError, match="solo"):
        compose_lyrics(concept, persona, domain, ollama=ollama)
    ollama._chat.assert_not_called()
    with pytest.raises(ValueError, match="solo"):
        _build_rei_system_prompt(persona, domain)


@pytest.mark.parametrize("solo", [*SOLO_OPTIONS, "Theremin Solo"])
def test_solo_tags_are_stage_cues_not_copied_into_intro(solo: str) -> None:
    assert _is_stage_cue_phrase(solo)
    assert tag_instrument_cues(f"({solo})") == f"[{solo}]"
    song = f"[Chorus]\nBurning brighter\n[{solo}]\n[Verse 1]\nA wider road"
    result = ensure_suno_quality(song)
    intro = result.split("[Chorus]", 1)[0]
    assert "[Intro Verse]\nBurning brighter" in intro
    assert f"[{solo}]" not in intro
    assert f"[Chorus]\nBurning brighter\n[{solo}]" in result


@pytest.mark.parametrize(
    "lyric", ["(I can go solo)", "(We dance solo)", "(I play guitar solo)", "(Ahh ahh ahh)"],
)
def test_sung_parentheticals_are_not_treated_as_solo_cues(lyric: str) -> None:
    assert tag_instrument_cues(lyric) == lyric


@pytest.mark.parametrize("solo", SOLO_OPTIONS)
def test_solo_cues_survive_structured_and_freeform_cleanup(solo: str) -> None:
    block = f"[Solo]\n[{solo}]\n[An evolving instrumental phrase]"
    assert _append_normalized_section([], block, "Solo") == block
    source = f"[Verse 1]\nThe road opens\n[Chorus]\nBurning brighter\n{block}"
    result = _normalize_freeform_suno_reply(source)
    assert block in result
    assert _normalize_freeform_suno_reply(result) == result
