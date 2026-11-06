"""Required-section quality gate for Rei lyric drafts."""

import json
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from services.rei_toei._lyric_prompts import build_lyric_prompts
from services.rei_toei._song_structure import (
    missing_required_sections,
    missing_sections_feedback,
)
from services.rei_toei._stage_policy import load_stage_policy
from services.rei_toei._suno_pipeline import compose_lyrics
from services.rei_toei._loaders import load_rei_domain_knowledge, load_rei_persona
from services.rei_toei._models import SongConcept


def _complete() -> Dict[str, Any]:
    return {
        "intro": "[Instrumental Build]\n(Ahh ahh ahh)\n[Intro Verse]\nThe room is waiting",
        "verse_1": "[Verse 1]\nA candle waits\nThe hallway hums",
        "pre_chorus": "[Pre-Chorus]\nSomething is about to break",
        "chorus": "[Chorus]\nWE BURN TO BOOT AGAIN\nLIGHT ME UP ONCE MORE",
        "verse_2": "[Verse 2]\nThe ashes cool\nShe hears a new voice",
        "bridge": "[Bridge]\nThen the walls fall open\nI can see the sky\nEvery error was a door\nAnd I walk through",
        "drop": "[Drop]\n[Heavy Bass Drop]\nJump the gap\nRide the wire",
        "solo": "[Solo]\n[Glitch Synth Solo]\n[Melodic Synth Solo]",
        "outro": "[Outro]\nThe screen goes soft and warm\nThe signal sleeps",
    }


def test_required_fields_cover_every_song_section() -> None:
    assert set(load_stage_policy().required_fields) == {
        "intro", "verse_1", "chorus", "verse_2", "bridge", "drop", "solo", "outro",
    }


def test_complete_draft_passes() -> None:
    assert missing_required_sections(_complete()) == []


@pytest.mark.parametrize("field", load_stage_policy().required_fields)
def test_absent_or_blank_section_is_missing(field: str) -> None:
    absent = _complete()
    del absent[field]
    blank = dict(_complete(), **{field: "   "})

    assert missing_required_sections(absent) == [field]
    assert missing_required_sections(blank) == [field]


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("intro", "[Instrumental Build]\n(Ahh ahh ahh)", "intro_verse"),
        ("intro", "[Instrumental Build]\n(Ahh ahh ahh)\n[Intro Verse]", "intro_verse"),
        ("drop", "[Drop]\n[Heavy Bass Drop]", "drop"),
        ("solo", "[Solo]", "solo"),
        ("outro", "[Outro]", "outro"),
        ("outro", "[Outro]\n(Shine shine)", "outro"),
        ("bridge", "[Bridge]", "bridge"),
    ],
)
def test_label_or_cue_only_section_is_missing(field: str, value: str, expected: str) -> None:
    assert missing_required_sections(dict(_complete(), **{field: value})) == [expected]


def test_pre_chorus_stays_optional() -> None:
    draft = _complete()
    del draft["pre_chorus"]

    assert missing_required_sections(draft) == []


def test_feedback_names_each_missing_section() -> None:
    feedback = missing_sections_feedback(["intro_verse", "drop", "solo", "outro"])

    assert "REVISION REQUIRED" in feedback
    assert "[Intro Verse]" in feedback
    assert "[Heavy Bass Drop]" in feedback
    assert "[Solo]" in feedback
    assert "[Outro]" in feedback


def _concept() -> SongConcept:
    return SongConcept(
        song_id="song",
        title="Signal",
        theme="Agents",
        mood="playful",
        bpm=142,
        genre_tags=["cyberpop"],
        narrative_arc="A signal finds home",
        evidence_ids=[],
        generated_at="2026-11-04",
        lyric_language="english",
    )


def test_prompt_distinguishes_required_and_optional_fields() -> None:
    _, user_prompt = build_lyric_prompts(
        _concept(), load_rei_persona(), load_rei_domain_knowledge(), None,
        lyric_language="english", generation_language="english", translate_mode=False,
        japanese_target_percent=0,
    )

    assert "outro (required)" in user_prompt
    assert "pre_chorus (optional)" in user_prompt


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("outro", None),
        ("drop", "[Drop]\n[Heavy Bass Drop]\nHeavy bass drop!"),
    ],
)
def test_compose_retries_missing_or_emptied_section_with_feedback(field: str, value: Any) -> None:
    incomplete = _complete()
    if value is None:
        del incomplete[field]
    else:
        incomplete[field] = value
    ollama = MagicMock()
    ollama._chat.side_effect = [json.dumps(incomplete), json.dumps(_complete())]

    lyrics = compose_lyrics(
        _concept(), load_rei_persona(), load_rei_domain_knowledge(), ollama=ollama
    )

    assert ollama._chat.call_count == 2
    retry_prompt = ollama._chat.call_args_list[1].args[1]
    assert "REVISION REQUIRED" in retry_prompt
    assert f"- {field}:" in retry_prompt
    assert "Jump the gap" in (lyrics.drop or "")
    assert "The signal sleeps" in (lyrics.outro or "")


def test_final_draft_missing_framing_sections_fails_without_backfill() -> None:
    incomplete = _complete()
    del incomplete["outro"]
    incomplete["solo"] = "[Solo]"
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(incomplete)

    with pytest.raises(RuntimeError, match="Missing required fields.*solo.*outro"):
        compose_lyrics(
            _concept(), load_rei_persona(), load_rei_domain_knowledge(), ollama=ollama
        )

    assert ollama._chat.call_count == 5


def test_final_draft_missing_a_core_section_fails_without_replacement() -> None:
    incomplete = _complete()
    del incomplete["bridge"]
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(incomplete)

    with pytest.raises(RuntimeError, match="Missing required fields.*bridge"):
        compose_lyrics(
            _concept(), load_rei_persona(), load_rei_domain_knowledge(), ollama=ollama
        )

    assert ollama._chat.call_count == 5
