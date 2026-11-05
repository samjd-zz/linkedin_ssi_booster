"""Tests for Rei song development: distinct Verse 2, metaphor chorus, climactic bridge."""

import json
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from services.rei_toei._models import (
    ReiDomainKnowledge,
    ReiPersonaGraph,
    SongConcept,
    Theme,
)
from services.rei_toei._song_structure import (
    borrowed_lines,
    bridge_is_underdeveloped,
    sung_line_signatures,
    verse_two_repeats_verse_one,
)
from services.rei_toei._suno_pipeline import (
    assemble_suno_prompt,
    compose_lyrics,
    generate_song_concept,
)


@pytest.fixture(autouse=True)
def _single_pass_bilingual(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests cover the one-pass "generate" bilingual strategy; the
    English-first "translate" strategy is covered in test_rei_hook_translation.py."""
    monkeypatch.setenv("REI_BILINGUAL_STRATEGY", "generate")


VERSE_1 = "The lab lights flicker on\nA prototype hums in the dark\nShe types the first command"
VERSE_2 = "The crash leaves a quiet room\nA new process wakes in the ashes\nIt remembers her name"


@pytest.fixture
def persona() -> ReiPersonaGraph:
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


@pytest.fixture
def domain() -> ReiDomainKnowledge:
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


def _concept(language: str) -> SongConcept:
    return SongConcept(
        song_id="song",
        title="Second Boot",
        theme="restart",
        mood="playful",
        bpm=142,
        genre_tags=["cyberpop"],
        narrative_arc="A crash becomes a rebirth",
        evidence_ids=[],
        generated_at="2026-10-31",
        lyric_language=language,
    )


def _english_response(verse_2: str) -> Dict[str, Any]:
    return {
        "intro": "(Ahh ahh ahh)\nThe room is waiting",
        "verse_1": VERSE_1,
        "pre_chorus": "Something is about to break\nHold your breath",
        "chorus": "WE BURN TO BOOT AGAIN\nLIGHT ME UP ONCE MORE",
        "verse_2": verse_2,
        "drop": "(bass drop)\nJump the gap",
        "bridge": "Then the walls fall open\nI can see the sky\nEvery error was a door\nAnd I walk through",
        "solo": "Synth lead climbs",
        "outro": "The screen goes soft and warm",
    }


@pytest.mark.parametrize(
    ("verse_2", "expected"),
    [
        (VERSE_1, True),
        (VERSE_1.replace("flicker on", "flickers on"), True),
        (VERSE_2, False),
        ("", False),
    ],
)
def test_verse_two_repeat_detection(verse_2: str, expected: bool) -> None:
    payload = {"verse_1": VERSE_1, "verse_2": verse_2}

    assert verse_two_repeats_verse_one(payload) is expected


def test_signatures_ignore_labels_cues_and_sound_directions() -> None:
    text = "[Verse 2]\n(bass drop)\n新しい朝\n[atarashii asa] [New morning]\nA new day"

    assert sung_line_signatures(text) == ["新しい朝", "a new day"]


@pytest.mark.parametrize(
    ("bridge", "expected"),
    [
        ("[Bridge]\nWalls fall\n(silence)\nI see", True),
        ("Walls fall\nI see the sky\nEvery error a door\nI walk through", False),
    ],
)
def test_bridge_depth(bridge: str, expected: bool) -> None:
    assert bridge_is_underdeveloped({"bridge": bridge}) is expected


def test_lyric_prompt_requests_development_metaphor_and_climax(persona, domain) -> None:
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(_english_response(VERSE_2))

    compose_lyrics(_concept("english"), persona, domain, ollama=ollama)

    system_prompt, user_prompt = ollama._chat.call_args.args[:2]
    assert "Do not reuse or reword any Verse 1 line" in user_prompt
    assert "central metaphor" in user_prompt
    assert "emotional and thematic climax" in user_prompt
    assert "rising into the final drop" in user_prompt
    assert user_prompt.index('"bridge":') < user_prompt.index('"drop":')
    assert "Verse 2 must develop the story" in system_prompt


def test_bridge_climax_builds_into_the_final_drop(persona, domain) -> None:
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(_english_response(VERSE_2))
    concept = _concept("english")

    lyrics = compose_lyrics(concept, persona, domain, ollama=ollama)
    song = assemble_suno_prompt(concept, lyrics, domain).lyrics

    order = [song.index(f"[{label}]") for label in ("Verse 2", "Bridge", "Drop", "Solo", "Outro")]
    assert order == sorted(order)
    assert "Every error was a door" in song[order[1]:order[2]]


def test_repeated_verse_two_is_retried_with_feedback(persona, domain, monkeypatch) -> None:
    monkeypatch.setenv("REI_JAPANESE_LYRIC_PROBABILITY", "0.4")
    repeated = {
        "intro": "then '(Ahh ahh ahh)',",
        "verse_1": "信号が飛び散る\nA candle waits\nThe hallway hums",
        "chorus": "遅延は消える\nHold the world",
        "verse_2": "信号が飛び散る\nA candle waits\nThe hallway hums",
        "bridge": "We find our way\nThe window opens",
        "drop": "(bass drop)\nJump the gap",
        "solo": "[Glitch Synth Solo]",
        "outro": "The night fades",
    }
    developed = dict(repeated, verse_2="新しい朝が来る\nThe ashes cool\nShe hears a new voice")
    ollama = MagicMock()
    ollama._chat.side_effect = [
        json.dumps(repeated, ensure_ascii=False),
        json.dumps(developed, ensure_ascii=False),
    ]

    lyrics = compose_lyrics(_concept("bilingual"), persona, domain, ollama=ollama)

    assert ollama._chat.call_count == 2
    assert "REVISION REQUIRED" not in ollama._chat.call_args_list[0].args[1]
    assert "REVISION REQUIRED" in ollama._chat.call_args_list[1].args[1]
    assert "新しい朝が来る" in lyrics.verse_2


def test_english_keeps_draft_when_verse_still_repeats_after_retry(persona, domain, caplog) -> None:
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(_english_response(VERSE_1))

    lyrics = compose_lyrics(_concept("english"), persona, domain, ollama=ollama)

    assert ollama._chat.call_count == 2
    assert "prototype hums" in lyrics.verse_2
    assert "Verse 2 still repeats Verse 1" in caplog.text


def test_concept_prompt_asks_for_metaphor_turning_point_and_aftermath(persona, domain) -> None:
    persona.identity.update(role="AI musician", origin="lab", aesthetic="neon", purpose="sing")
    domain.bpm_and_mood = {"bpm_ranges": {"140-148": 142}, "mood_to_bpm": {}}
    theme = Theme(
        id="t1",
        name="restart",
        technical_concepts=["reboot"],
        evidence_ids=[],
        frequency=3,
        recency_score=0.5,
    )
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(
        {
            "title": "Second Boot",
            "mood": "playful_technical",
            "bpm": 142,
            "genre_tags": ["cyberpop"],
            "narrative_arc": "A crash becomes a rebirth.",
        }
    )

    generate_song_concept(theme, persona, domain, ollama=ollama)

    user_prompt = ollama._chat.call_args.args[1]
    assert "central metaphor" in user_prompt
    assert "turning point" in user_prompt
    assert "what happens after it" in user_prompt


def test_borrowed_lines_names_copies_but_allows_chorus_reprise() -> None:
    payload = {
        "verse_1": "Signal flows like water's breath\nSeeds of light",
        "chorus": "データ種子が芽吹く\nSignal flows like water's breath",
        "verse_2": "A glitch disrupts the flow",
        "bridge": "データ種子が芽吹く\nA glitch disrupts the flow\nThe walls fall open",
        "drop": "データ種子が芽吹く",
        "outro": "データ種子が芽吹く",
    }

    assert borrowed_lines(payload) == [
        ("chorus", "verse_1", "signal flows like water s breath"),
        ("bridge", "chorus", "データ種子が芽吹く"),
        ("bridge", "verse_2", "a glitch disrupts the flow"),
    ]


def test_bridge_copying_chorus_is_retried_with_named_lines(persona, domain, monkeypatch) -> None:
    monkeypatch.setenv("REI_JAPANESE_LYRIC_PROBABILITY", "0.4")
    borrowed = {
        "intro": "(Ahh ahh ahh)\nThe room is waiting",
        "verse_1": "信号が飛び散る\nA candle waits\nThe hallway hums",
        "chorus": "種が芽吹く\nBlossom from the seed\nWe thrive",
        "verse_2": "新しい朝が来る\nThe ashes cool\nShe hears a new voice",
        "bridge": "種が芽吹く\nBlossom from the seed\nWe thrive\nThe walls fall",
        "drop": "(bass drop)\nJump the gap",
        "solo": "[Glitch Synth Solo]",
        "outro": "The night fades",
    }
    fresh = dict(borrowed, bridge="壁が崩れる\nThe walls fall open\nI see the sky\nEvery error was a door")
    ollama = MagicMock()
    ollama._chat.side_effect = [
        json.dumps(borrowed, ensure_ascii=False),
        json.dumps(fresh, ensure_ascii=False),
    ]

    lyrics = compose_lyrics(_concept("bilingual"), persona, domain, ollama=ollama)

    assert ollama._chat.call_count == 2
    retry_prompt = ollama._chat.call_args_list[1].args[1]
    assert "bridge copies chorus: 'blossom from the seed'" in retry_prompt
    assert "Every error was a door" in lyrics.bridge


def test_lyric_prompt_asks_for_natural_rhyme_meter_and_japanese_grammar(persona, domain) -> None:
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(_english_response(VERSE_2))

    compose_lyrics(_concept("english"), persona, domain, ollama=ollama)
    prompt = ollama._chat.call_args.args[0] + ollama._chat.call_args.args[1]

    assert "Keep rhymes natural" in prompt
    assert "Keep meter steady" in prompt
