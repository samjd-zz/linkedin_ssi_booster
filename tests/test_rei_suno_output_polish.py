"""Regression tests for Suno cue, vocalization, and chorus cleanup."""

import json
from unittest.mock import MagicMock

import pytest

from services.rei_toei._lyric_checks import MIN_CHORUS_SUNG_LINES, sung_line_count
from services.rei_toei._models import ReiDomainKnowledge, ReiPersonaGraph, SongConcept
from services.rei_toei._song_tidy import tidy_song_sections
from services.rei_toei._suno_cleanup import split_inline_stage_cues, tag_instrument_cues
from services.rei_toei._suno_pipeline import compose_lyrics
from services.rei_toei._suno_quality import bracket_solo_directions


def test_parenthetical_fade_and_chill_directions_become_tags() -> None:
    payload = {"outro": "[Outro]\n(Fade out)\n(Chill)\nThe city sleeps"}

    tidy_song_sections(payload)

    assert payload["outro"] == "[Outro]\n[Fade Out]\n[Chill]\nThe city sleeps"


def test_punctuation_placeholders_are_removed_before_lyric_validation() -> None:
    payload = {
        "verse_1": "[Verse 1]\n.\nThe windows lose their blue\nA quiet street waits",
        "outro": "[Outro]\n...\nThe lamps grow soft and gold",
    }

    tidy_song_sections(payload)

    assert "." not in payload["verse_1"]
    assert "..." not in payload["outro"]
    assert "The windows lose their blue" in payload["verse_1"]


def test_inline_stage_cues_move_to_their_own_lines() -> None:
    source = "Signals converge [Silence] [Chaos]"

    assert split_inline_stage_cues(source) == "Signals converge\n[Silence]\n[Chaos]"


def test_tag_instrument_cues_brackets_parenthetical_directions() -> None:
    assert tag_instrument_cues("(Fade out)\n(Chill)") == "[Fade Out]\n[Chill]"


def test_japanese_spelled_vocalization_is_preserved_in_latin_characters() -> None:
    payload = {"verse_1": "（アッハ アッハ アッハ）ネオンが脈打つ"}

    tidy_song_sections(payload)

    assert payload["verse_1"] == "(Ahh ahh ahh)\nネオンが脈打つ"


def test_solo_direction_closes_an_unmatched_parenthesis() -> None:
    assert bracket_solo_directions(
        "[Epic Guitar Solo (Sweeping arpeggios, neon lights flicker]"
    ) == "[Solo]\n[Epic Guitar Solo (Sweeping arpeggios, neon lights flicker)]"


def _persona() -> ReiPersonaGraph:
    return ReiPersonaGraph(
        schema_version="1",
        identity={"name": "Rei"},
        personality_traits=[],
        musical_expertise={},
        production_knowledge={"lyrical_approach": {}},
        communication_style={"tone": "digital"},
        knowledge_sources={},
        creative_process={},
        constraints={},
        comparison_to_sam={},
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
        suno_prompt_templates={},
        production_notes={},
    )


def _concept() -> SongConcept:
    return SongConcept(
        song_id="test",
        title="Neon Return",
        theme="restart",
        mood="hopeful",
        bpm=145,
        genre_tags=["cyberpop"],
        narrative_arc="A city wakes after a blackout",
        evidence_ids=[],
        generated_at="2026-11-05",
        lyric_language="english",
    )


def _lyrics(chorus: str) -> dict[str, str]:
    return {
        "intro": "(Ahh ahh ahh)\nThe dark begins to glow",
        "verse_1": "The windows lose their blue\nA quiet street waits",
        "pre_chorus": "One light starts to rise\nThe rooftops catch its fire",
        "chorus": chorus,
        "verse_2": "The morning fills the lanes\nA thousand doors unlock",
        "bridge": "The last lights wake the river\nWe carry sparks beyond the hill",
        "drop": "(bass drop)\nThe whole town starts to move",
        "solo": "[Glitch Synth Solo]",
        "outro": "The lamps grow soft and gold\nThe city holds the dawn",
    }


def test_single_line_chorus_is_retried_until_it_meets_minimum() -> None:
    ollama = MagicMock()
    ollama._chat.side_effect = [
        json.dumps(_lyrics("WE COME ALIVE")),
        json.dumps(_lyrics(
            "WE COME ALIVE\nTHE WINDOWS ANSWER BACK\nWE CARRY MORNING HOME\nTHE NIGHT RELEASES US"
        )),
    ]

    lyrics = compose_lyrics(_concept(), _persona(), _domain(), ollama=ollama)

    assert ollama._chat.call_count == 2
    assert f"at least {MIN_CHORUS_SUNG_LINES} distinct" in ollama._chat.call_args.args[1]
    assert sung_line_count(lyrics.chorus) >= MIN_CHORUS_SUNG_LINES


def test_short_chorus_after_retries_fails_without_a_canned_replacement() -> None:
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(_lyrics("WE COME ALIVE"))

    with pytest.raises(RuntimeError, match="Chorus remained under"):
        compose_lyrics(_concept(), _persona(), _domain(), ollama=ollama)

    assert ollama._chat.call_count == 5


def test_punctuation_only_required_section_is_retried() -> None:
    invalid = _lyrics(
        "WE COME ALIVE\nTHE WINDOWS ANSWER BACK\nWE CARRY MORNING HOME\nTHE NIGHT RELEASES US"
    )
    invalid["verse_1"] = "."
    ollama = MagicMock()
    ollama._chat.side_effect = [
        json.dumps(invalid),
        json.dumps(_lyrics(
            "WE COME ALIVE\nTHE WINDOWS ANSWER BACK\nWE CARRY MORNING HOME\nTHE NIGHT RELEASES US"
        )),
    ]

    lyrics = compose_lyrics(_concept(), _persona(), _domain(), ollama=ollama)

    assert ollama._chat.call_count == 2
    assert "verse_1" in ollama._chat.call_args.args[1]
    assert all(line.strip() != "." for line in lyrics.verse_1.splitlines())
