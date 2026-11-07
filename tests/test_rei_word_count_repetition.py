"""Word-count placeholders must become actual sung repetitions."""

import copy
import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from services.rei_toei._hook_translation import select_hook_lines
from services.rei_toei._loaders import load_rei_domain_knowledge, load_rei_persona
from services.rei_toei._lyric_prompts import build_lyric_prompts
from services.rei_toei._models import LyricCompositionError, ReiDomainKnowledge
from services.rei_toei._song_tidy import tidy_song_sections
from services.rei_toei._stage_policy import SectionRule, StagePolicy, load_stage_policy
from services.rei_toei._suno_pipeline import (
    _append_normalized_section,
    _normalize_freeform_suno_reply,
    _normalize_suno_section,
    assemble_suno_prompt,
    compose_lyrics,
)
from tests.test_rei_lyric_retries import _concept, _draft


@pytest.fixture
def acoustic_domain() -> ReiDomainKnowledge:
    knowledge = copy.deepcopy(load_rei_domain_knowledge())
    knowledge.lyrical_structure["stage_cues"]["active_profile"] = "acoustic"
    return knowledge


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("JAVA FLOW (3-7 WORDS)", "JAVA FLOW\nJAVA FLOW"),
        ("Java flow (3-7 words)", "Java flow\nJava flow"),
        ("JAVA FLOW ( 3 - 7 WoRdS )", "JAVA FLOW\nJAVA FLOW"),
        ("JAVA FLOW (3–7 WORDS)", "JAVA FLOW\nJAVA FLOW"),
        ("JAVA FLOW (3 to 7 words)", "JAVA FLOW\nJAVA FLOW"),
        ("JAVA FLOW （3-7 WORDS）", "JAVA FLOW\nJAVA FLOW"),
        ("JAVA FLOW (3-7 WORDS) (3-7 WORDS)", "JAVA FLOW\nJAVA FLOW\nJAVA FLOW"),
        ("JAVA FLOW\n(3-7 WORDS)", "JAVA FLOW\nJAVA FLOW"),
        ("JAVA FLOW\n\n(3-7 WORDS)", "JAVA FLOW\n\nJAVA FLOW"),
        ("JAVA FLOW (3-7 WORDS), WE RISE", "JAVA FLOW\nJAVA FLOW, WE RISE"),
        ("光の海（3-7 WORDS）", "光の海\n光の海"),
        ("光の海\n[hikari no umi]\n(3-7 WORDS)", "光の海\n[hikari no umi]\n光の海"),
    ],
)
def test_suno_section_writes_the_lyric_instead_of_the_count_marker(
    source: str, expected: str,
) -> None:
    assert _normalize_suno_section(source, "Chorus") == f"[Chorus]\n{expected}"


@pytest.mark.parametrize("hook", ["JAVA FLOW", "Kokoro no Code", "hikari no umi"])
def test_assembled_suno_section_keeps_both_sung_copies(hook: str) -> None:
    result = _append_normalized_section([], f"{hook} (3-7 WORDS)", "Chorus")

    assert result == f"[Chorus]\n{hook}\n{hook}"
    assert _append_normalized_section([], result, "Chorus") == result


def test_japanese_repetition_retains_sung_lines_and_pronunciation_cues() -> None:
    result = _append_normalized_section(
        [], "光の海\n[hikari no umi]\n(3-7 WORDS)", "Chorus"
    )

    assert result.count("光の海") == 2
    assert result.count("[hikari no umi]") == 2
    assert "3-7" not in result
    assert _append_normalized_section([], result, "Chorus") == result


def test_intro_repetition_remains_under_the_sung_intro_verse() -> None:
    source = (
        "[Instrumental Build]\n(Ahh ahh ahh)\n"
        "[Intro Verse]\nJAVA FLOW (3-7 WORDS)"
    )

    result = _append_normalized_section([], source, "Instrumental Build")

    assert result == "[Instrumental Build]\n(Ahh ahh ahh)\n\n[Intro Verse]\nJAVA FLOW\nJAVA FLOW"
    assert _append_normalized_section([], result, "Instrumental Build") == result


def test_repetition_does_not_duplicate_a_stage_cue() -> None:
    source = "[Chorus]\nJAVA FLOW [Silence] (3-7 WORDS)"

    result = _append_normalized_section([], source, "Chorus")

    assert result == "[Chorus]\nJAVA FLOW\nJAVA FLOW\n[Silence]"


@pytest.mark.parametrize(
    ("source", "expected_lines"),
    [
        (
            "光の海\n[hikari no umi]\nKokoro no Code (3-7 WORDS)",
            ["Kokoro no Code", "Kokoro no Code"],
        ),
        (
            "光の海\n[hikari no umi]\nhikari no umi (3-7 WORDS)",
            ["hikari no umi", "hikari no umi"],
        ),
        (
            "光の海\nKokoro no Code (3-7 WORDS)",
            ["Kokoro no Code", "Kokoro no Code"],
        ),
        (
            "心のコード\nKokoro no Code (3-7 WORDS)",
            ["Kokoro no Code", "Kokoro no Code"],
        ),
        (
            "心のコード\nKokoro no Code\n\n(3-7 WORDS)",
            ["Kokoro no Code", "Kokoro no Code"],
        ),
        (
            "光の海\n[hikari no umi]\nKokoro no Code (3-7 WORDS), WE RISE",
            ["Kokoro no Code", "Kokoro no Code, WE RISE"],
        ),
    ],
)
def test_repeated_sung_hook_after_japanese_is_not_mistaken_for_romaji(
    source: str, expected_lines: list[str],
) -> None:
    result = _append_normalized_section([], source, "Chorus")
    sung = [line for line in result.splitlines() if line.strip() and not line.startswith("[")]

    assert sung[-2:] == expected_lines
    assert _append_normalized_section([], result, "Chorus") == result


def test_tidy_expands_before_hook_selection_without_changing_parenthetical_echoes() -> None:
    payload = {
        "chorus": "[Chorus]\nJAVA FLOW (3-7 WORDS)\nWE RISE TOGETHER",
        "verse_1": "A quiet night (A quiet night)\n(Shine shine)\n(Ahh ahh ahh)",
    }

    tidy_song_sections(payload)

    assert payload["chorus"] == "[Chorus]\nJAVA FLOW\nJAVA FLOW\nWE RISE TOGETHER"
    assert payload["verse_1"] == "A quiet night\n(Ahh ahh ahh)"
    assert select_hook_lines(payload, 0.9, 8)[0].text == "JAVA FLOW"
    original = dict(payload)
    tidy_song_sections(payload)
    assert payload == original


@pytest.mark.parametrize(
    "source",
    [
        "(3-7 WORDS)\nJAVA FLOW",
        "[Chorus]\n(3-7 WORDS)",
        "JAVA FLOW\n[Silence]\n(3-7 WORDS)",
        "JAVA FLOW\n[Verse 2]\n(3-7 WORDS)",
    ],
)
def test_marker_without_a_preceding_sung_lyric_fails_explicitly(source: str) -> None:
    with pytest.raises(ValueError, match="word-count.*preceding sung"):
        _normalize_suno_section(source, "Chorus")


def test_marker_in_an_instrumental_section_is_not_sung() -> None:
    with pytest.raises(ValueError, match="word-count.*instrumental"):
        _append_normalized_section([], "[Solo]\nSynth swell (3-7 WORDS)", "Solo")


def test_custom_section_header_prevents_repeating_a_previous_section() -> None:
    policy = StagePolicy(
        "custom",
        (
            SectionRule("chorus", "Chorus", True, "sung", ()),
            SectionRule("verse_2", "ai", True, "sung", ()),
        ),
        None, None, (),
    )
    payload = {"chorus": "愛\n[ai]\n(3-7 WORDS)"}

    with pytest.raises(ValueError, match="word-count.*preceding sung"):
        tidy_song_sections(payload, policy)


@pytest.mark.parametrize(
    "source",
    [
        "JAVA FLOW (2-4 WORDS)",
        "JAVA FLOW (3-7 LINES)",
        "JAVA FLOW (JAVA FLOW)",
        "(Oh oh oh)",
    ],
)
def test_other_parenthetical_text_is_not_a_word_count_marker(source: str) -> None:
    assert _normalize_suno_section(source, "Chorus") == f"[Chorus]\n{source}"


def test_compose_expands_before_validation_and_suno_assembly(
    acoustic_domain: ReiDomainKnowledge,
) -> None:
    draft = dict(_draft(), chorus="HOLD THE DOOR FOR MORNING (3-7 WORDS)\nWE WILL FIND OUR WAY")
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(draft)
    concept = _concept()

    lyrics = compose_lyrics(concept, load_rei_persona(), acoustic_domain, ollama=ollama)
    result = assemble_suno_prompt(concept, lyrics, acoustic_domain)

    assert ollama._chat.call_count == 1
    assert lyrics.chorus == (
        "HOLD THE DOOR FOR MORNING\nHOLD THE DOOR FOR MORNING\nWE WILL FIND OUR WAY"
    )
    assert lyrics.chorus in result.lyrics
    assert "(3-7 WORDS)" not in result.lyrics


def test_bilingual_translation_receives_repeated_words_not_a_marker(
    acoustic_domain: ReiDomainKnowledge, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REI_BILINGUAL_STRATEGY", "translate")
    draft = dict(_draft(), chorus="HOLD THE DOOR FOR MORNING (3-7 WORDS)\nWE WILL FIND OUR WAY")
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(draft)

    with patch(
        "services.rei_toei._suno_pipeline.apply_bilingual_hooks",
        return_value={"inserted": 1},
    ) as translate:
        lyrics = compose_lyrics(
            _concept("bilingual"), load_rei_persona(), acoustic_domain, ollama=ollama
        )

    assert translate.call_args.args[0]["chorus"] == (
        "HOLD THE DOOR FOR MORNING\nHOLD THE DOOR FOR MORNING\nWE WILL FIND OUR WAY"
    )
    assert "(3-7 WORDS)" not in lyrics.chorus


def test_real_bilingual_translation_keeps_both_repetitions_sung(
    acoustic_domain: ReiDomainKnowledge, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REI_BILINGUAL_STRATEGY", "translate")
    monkeypatch.setenv("REI_JAPANESE_LYRIC_PROBABILITY", "0.05")
    monkeypatch.setenv("REI_BILINGUAL_MAX_HOOK_LINES", "2")
    draft = dict(_draft(), chorus="KOKORO NO CODE (3-7 WORDS)\nWE WILL FIND OUR WAY")
    ollama = MagicMock()
    ollama._chat.side_effect = [
        json.dumps(draft), json.dumps({"1": "心のコード", "2": "雨が降る"}, ensure_ascii=False),
    ]
    concept = _concept("bilingual")

    lyrics = compose_lyrics(concept, load_rei_persona(), acoustic_domain, ollama=ollama)
    result = assemble_suno_prompt(concept, lyrics, acoustic_domain)

    assert ollama._chat.call_count == 2
    assert "心のコード\n[kokoro no koodo]\nKOKORO NO CODE\nKOKORO NO CODE" in result.lyrics
    assert "(3-7 WORDS)" not in result.lyrics


def test_unresolvable_marker_retries_with_explicit_feedback(
    acoustic_domain: ReiDomainKnowledge, caplog: pytest.LogCaptureFixture,
) -> None:
    invalid = dict(_draft(), chorus="(3-7 WORDS)\nHOLD THE DOOR\nWE WILL FIND OUR WAY")
    ollama = MagicMock()
    ollama._chat.side_effect = [json.dumps(invalid), json.dumps(_draft())]

    with caplog.at_level(logging.WARNING):
        lyrics = compose_lyrics(_concept(), load_rei_persona(), acoustic_domain, ollama=ollama)

    assert ollama._chat.call_count == 2
    assert lyrics.chorus == _draft()["chorus"]
    assert "word-count" in caplog.text
    assert "preceding sung" in caplog.text
    assert "write the hook words again" in ollama._chat.call_args.args[1].lower()


def test_unresolvable_marker_exhausts_retries_without_translation(
    acoustic_domain: ReiDomainKnowledge, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REI_BILINGUAL_STRATEGY", "translate")
    invalid = dict(_draft(), chorus="(3-7 WORDS)\nHOLD THE DOOR\nWE WILL FIND OUR WAY")
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(invalid)

    with patch("services.rei_toei._suno_pipeline.apply_bilingual_hooks") as translate:
        with pytest.raises(LyricCompositionError, match="word-count.*preceding sung"):
            compose_lyrics(
                _concept("bilingual"), load_rei_persona(), acoustic_domain, ollama=ollama
            )

    assert ollama._chat.call_count == 5
    translate.assert_not_called()


def test_freeform_song_expands_marker_and_is_idempotent(
    acoustic_domain: ReiDomainKnowledge,
) -> None:
    policy = load_stage_policy(acoustic_domain.lyrical_structure)
    source = "[Verse 1]\nRain at the window\n[Chorus]\nJAVA FLOW (3-7 WORDS)\nWE RISE"

    result = _normalize_freeform_suno_reply(source, policy)

    assert "[Chorus]\nJAVA FLOW\nJAVA FLOW\nWE RISE" in result
    assert _normalize_freeform_suno_reply(result, policy) == result


@pytest.mark.parametrize(
    ("lyric_language", "generation_language", "translate_mode"),
    [
        ("english", "english", False),
        ("bilingual", "english", True),
        ("bilingual", "bilingual", False),
        ("japanese", "japanese", False),
    ],
)
def test_lyric_prompt_requests_written_out_hook_repetition(
    acoustic_domain: ReiDomainKnowledge, lyric_language: str,
    generation_language: str, translate_mode: bool,
) -> None:
    system, user = build_lyric_prompts(
        _concept(lyric_language), load_rei_persona(), acoustic_domain, None,
        lyric_language=lyric_language, generation_language=generation_language,
        translate_mode=translate_mode, japanese_target_percent=33,
    )

    assert "(3-7 words)" not in (system + user).lower()
    assert "write the hook words again" in user.lower()
