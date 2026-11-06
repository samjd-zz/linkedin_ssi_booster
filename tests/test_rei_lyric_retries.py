"""Lyric generation retries invalid drafts without substituting canned lyrics."""

import copy
import json
from unittest.mock import MagicMock, patch

import pytest

from services.rei_toei._loaders import load_rei_domain_knowledge, load_rei_persona
from services.rei_toei._models import ReiDomainKnowledge, SongConcept
from services.rei_toei._suno_pipeline import compose_lyrics


def _concept(language: str = "english") -> SongConcept:
    return SongConcept(
        song_id="retries", title="Morning Window", theme="a room after rain",
        mood="hopeful", bpm=100, genre_tags=["acoustic"],
        narrative_arc="The rain stops and the room wakes",
        evidence_ids=["fact-1"], generated_at="2026-11-06", lyric_language=language,
    )


def _draft() -> dict[str, str]:
    return {
        "verse_1": "Rain taps against the window\nA candle waits",
        "chorus": "HOLD THE DOOR FOR MORNING\nWE WILL FIND OUR WAY",
        "verse_2": "The puddles catch the sunlight\nShe opens every curtain",
        "outro": "The house is warm again",
    }


@pytest.fixture
def domain() -> ReiDomainKnowledge:
    knowledge = copy.deepcopy(load_rei_domain_knowledge())
    knowledge.lyrical_structure["stage_cues"]["active_profile"] = "acoustic"
    return knowledge


@pytest.mark.parametrize("failure", ["json", "non_object", "schema", "missing", "chorus"])
def test_fifth_attempt_can_recover_from_invalid_drafts(
    domain: ReiDomainKnowledge, failure: str,
) -> None:
    invalid = _draft()
    if failure == "json":
        response = "not valid JSON"
    elif failure == "non_object":
        response = "[]"
    else:
        if failure == "schema":
            invalid["verse_1"] = "Two stanzas of original lines (Character Cap: 500)"
        elif failure == "missing":
            del invalid["outro"]
        else:
            invalid["chorus"] = "WE COME ALIVE"
        response = json.dumps(invalid)
    ollama = MagicMock()
    ollama._chat.side_effect = [response] * 4 + [json.dumps(_draft())]

    lyrics = compose_lyrics(_concept(), load_rei_persona(), domain, ollama=ollama)

    assert ollama._chat.call_count == 5
    assert lyrics.verse_1 == _draft()["verse_1"]
    assert lyrics.chorus == _draft()["chorus"]
    assert lyrics.evidence_ids == ["fact-1"]


@pytest.mark.parametrize("language", ["english", "japanese", "bilingual"])
def test_invalid_drafts_fail_after_five_attempts_without_hook_translation(
    domain: ReiDomainKnowledge, language: str, caplog: pytest.LogCaptureFixture,
) -> None:
    ollama = MagicMock()
    ollama._chat.return_value = "not valid JSON"

    with patch("services.rei_toei._suno_pipeline.apply_bilingual_hooks") as translate:
        with pytest.raises(RuntimeError, match="after 5 attempts"):
            compose_lyrics(_concept(language), load_rei_persona(), domain, ollama=ollama)

    assert ollama._chat.call_count == 5
    translate.assert_not_called()
    assert "No song was generated" in caplog.text
    assert "fallback" not in caplog.text.lower()


def test_malformed_retry_does_not_restore_an_undersized_chorus(
    domain: ReiDomainKnowledge,
) -> None:
    invalid = dict(_draft(), chorus="WE COME ALIVE")
    ollama = MagicMock()
    ollama._chat.side_effect = [json.dumps(invalid)] + ["not valid JSON"] * 4

    with pytest.raises(RuntimeError, match="after 5 attempts"):
        compose_lyrics(_concept(), load_rei_persona(), domain, ollama=ollama)

    assert ollama._chat.call_count == 5
