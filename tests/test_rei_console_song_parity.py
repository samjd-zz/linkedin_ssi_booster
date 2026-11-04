"""Console songs use the structured CLI lyric pipeline in every theme path."""

import asyncio
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.console_grounding import _rei_console as rei
from services.rei_toei import _hook_translation
from services.rei_toei._models import ReiDomainKnowledge, ReiPersonaGraph, Theme

SONG = {
    "intro": "[Instrumental Build]\n(Ahh ahh ahh)\nData seeds float on binary dreams",
    "verse_1": (
        "[Verse 1]\nBinary leaves of code, seeds of light\nWhispering through lines at night\n\n"
        "They hold the promise of new growth\nBorn from bits and bytes' soft touch"
    ),
    "pre_chorus": "[Pre-Chorus]\nLatency is their dance, a step too late\nEchoes in the network's fate",
    "chorus": "[Chorus]\nBlossom from data seeds\nNew cyberforms arise\nRooted deep we thrive",
    "verse_2": (
        "[Verse 2]\nA glitch disrupts the flow\nSome mutate, some let go\n\n"
        "Fighting back they learn to grow\nStronger in the undertow"
    ),
    "bridge": (
        "[Bridge]\nRoots of code through broken ground\nEvery fallen seed is found\n"
        "Where the binary meets the fall\nOne last bloom outlives it all"
    ),
    "drop": "[Drop]\n(bass drop)\nElectron sparks in the air\nBattle rages, codes give voice",
    "solo": "[Solo]\nGlitch patterns, neon dreams",
    "outro": "[Outro]\nData seeds at a brand-new dawn\nNew networks, reborn and strong",
}


def _japanese_song() -> dict[str, str]:
    song = dict(SONG)
    song["verse_1"] = song["verse_1"].replace("Binary leaves of code, seeds of light", "信号が光る")
    song["chorus"] = song["chorus"].replace("Blossom from data seeds", "データの種が咲く")
    song["verse_2"] = song["verse_2"].replace("A glitch disrupts the flow", "新たな光が生まれる")
    song["bridge"] = song["bridge"].replace("Roots of code through broken ground", "夢が未来へ走る")
    return song


def _model(
    drafts: list[dict[str, str]] | None = None,
    *,
    omit_first_translation: bool = False,
) -> MagicMock:
    model = MagicMock()
    model.client.chat.side_effect = AssertionError("freeform song generation must not be used")
    draft_iter = iter(drafts or [SONG])
    translation_count = 0

    def respond(system: str, user: str, **kwargs: object) -> str:
        nonlocal translation_count
        assert kwargs["format"] == "json"
        if "Generate a song concept for this technical theme:" in user:
            return json.dumps({
                "title": "Data Seeds",
                "mood": "hopeful",
                "bpm": 142,
                "genre_tags": ["cyberpop"],
                "narrative_arc": "Seeds grow after a disruption.",
            })
        if "Generate an exceptionally long-form" in user:
            return json.dumps(next(draft_iter), ensure_ascii=False)
        if "Translate each numbered English lyric line into Japanese." in user:
            translation_count += 1
            count = len(re.findall(r"(?m)^\d+\.\s", user))
            return json.dumps({
                str(number): "信号が光る"
                for number in range(1, count + 1)
                if not (omit_first_translation and translation_count == 1 and number == 1)
            }, ensure_ascii=False)
        raise AssertionError(f"Unexpected structured prompt: {user[:100]}")

    model._chat.side_effect = respond
    return model


@pytest.fixture
def console_setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ReiDomainKnowledge:
    monkeypatch.setenv("REI_LYRIC_LANGUAGE", "bilingual")
    monkeypatch.setenv("REI_BILINGUAL_STRATEGY", "translate")
    monkeypatch.setenv("REI_JAPANESE_LYRIC_PROBABILITY", "0.4")
    monkeypatch.setenv("REI_BILINGUAL_MAX_HOOK_LINES", "40")
    monkeypatch.setenv("REI_ARGOS_MODEL_DIR", str(tmp_path))
    persona = ReiPersonaGraph(
        schema_version="1",
        identity={
            "name": "Rei", "role": "AI musician", "origin": "digital",
            "aesthetic": "cyberpunk", "purpose": "make music",
        },
        personality_traits=[], musical_expertise={},
        production_knowledge={"lyrical_approach": {}},
        communication_style={"tone": "digital"}, knowledge_sources={},
        creative_process={}, constraints={}, comparison_to_sam={},
    )
    domain = ReiDomainKnowledge(
        schema_version="1", music_theory={}, tidal_cycles_syntax={},
        genre_production_techniques={},
        bpm_and_mood={"bpm_ranges": {"140-148": 142}, "mood_to_bpm": {}},
        synth_selection_guidelines={}, lyrical_structure={},
        technical_metaphor_library={"recursion": ["loops and echoes"]},
        suno_prompt_templates={}, production_notes={},
    )
    monkeypatch.setattr(rei, "get_rei_service", lambda: SimpleNamespace(
        persona=persona, domain_knowledge=domain,
    ))
    monkeypatch.setattr(rei, "_lav_rei_console", lambda: object())
    monkeypatch.setattr(rei, "_normalize_extracted_rei", lambda _: [])
    monkeypatch.setattr(rei, "load_recent_rei_titles", lambda *args, **kwargs: [])
    monkeypatch.setattr(rei, "choose_diverse_theme", lambda themes, **kwargs: themes[0])
    return domain


def _translation_calls(model: MagicMock) -> list[str]:
    return [
        call.args[1] for call in model._chat.call_args_list
        if "Translate each numbered English lyric line into Japanese." in call.args[1]
    ]


@pytest.mark.parametrize("knowledge", ["no_facts", "no_themes", "grounded"])
def test_console_translate_mode_batches_hooks_and_formats_romaji(
    knowledge: str, console_setup: ReiDomainKnowledge, monkeypatch: pytest.MonkeyPatch,
) -> None:
    if knowledge != "no_facts":
        monkeypatch.setattr(rei, "_normalize_extracted_rei", lambda _: [object()])
        themes = [] if knowledge == "no_themes" else [
            Theme("t", "Latency", ["latency"], ["fact-1"], 1, 1.0)
        ]
        monkeypatch.setattr(rei, "extract_themes", lambda *args, **kwargs: themes)
    model = _model()

    reply, history = asyncio.run(rei.handle_rei_console("give me a song", model, []))

    batches = _translation_calls(model)
    assert len(batches) >= 2
    assert all(
        1 <= len(re.findall(r"(?m)^\d+\.\s", prompt)) <= 10
        for prompt in batches
    )
    assert "natural English only" in model._chat.call_args_list[1].args[0]
    assert "信号が光る\n[shingou ga hikaru]\nBLOSSOM FROM DATA SEEDS" in reply
    assert "[Intro Verse]" in reply and "[Drop]\n[Heavy Bass Drop]" in reply
    assert history[-1] == {"role": "assistant", "content": reply}
    model.client.chat.assert_not_called()


def test_console_uses_argos_for_missing_batch_results(
    console_setup: ReiDomainKnowledge, monkeypatch: pytest.MonkeyPatch,
) -> None:
    translator = MagicMock()
    translator.translate.return_value = ["予備の光が走る"]
    monkeypatch.setattr(_hook_translation, "get_argos_translator", lambda _: translator)
    model = _model(omit_first_translation=True)

    reply, _ = asyncio.run(rei.handle_rei_console("give me a song", model, []))

    assert translator.translate.call_count == 1
    assert len(translator.translate.call_args.args[0]) == 1
    assert "予備の光が走る" in reply
    assert "信号が光る" in reply
    model.client.chat.assert_not_called()


def test_console_keeps_english_when_a_hook_cannot_be_translated(
    console_setup: ReiDomainKnowledge, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_hook_translation, "get_argos_translator", lambda _: None)
    model = _model(omit_first_translation=True)

    reply, _ = asyncio.run(rei.handle_rei_console("give me a song", model, []))

    assert "BLOSSOM FROM DATA SEEDS" in reply
    assert "信号が光る\n[shingou ga hikaru]\nBLOSSOM FROM DATA SEEDS" not in reply
    assert "信号が光る" in reply
    model.client.chat.assert_not_called()


@pytest.mark.parametrize(
    ("ratio", "limit", "expected_lines"),
    [("0.0", "40", 0), ("0.4", "1", 2), ("0.4", "3", 3)],
)
def test_console_honors_hook_ratio_and_selection_limit(
    ratio: str, limit: str, expected_lines: int,
    console_setup: ReiDomainKnowledge, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REI_JAPANESE_LYRIC_PROBABILITY", ratio)
    monkeypatch.setenv("REI_BILINGUAL_MAX_HOOK_LINES", limit)
    model = _model()

    reply, _ = asyncio.run(rei.handle_rei_console("give me a song", model, []))

    batches = _translation_calls(model)
    assert sum(len(re.findall(r"(?m)^\d+\.\s", prompt)) for prompt in batches) == expected_lines
    assert reply.count("信号が光る") == expected_lines
    model.client.chat.assert_not_called()


def test_console_keeps_earlier_batches_after_translation_error(
    console_setup: ReiDomainKnowledge, monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("REI_JAPANESE_LYRIC_PROBABILITY", "0.8")
    translator = MagicMock()
    translator.translate.side_effect = lambda lines: ["予備の光が走る"] * len(lines)
    monkeypatch.setattr(_hook_translation, "get_argos_translator", lambda _: translator)
    model = _model()
    respond = model._chat.side_effect
    translation_count = 0

    def fail_second_batch(system: str, user: str, **kwargs: object) -> str:
        nonlocal translation_count
        if "Translate each numbered English lyric line into Japanese." in user:
            translation_count += 1
            if translation_count == 2:
                raise RuntimeError("translation unavailable")
        return respond(system, user, **kwargs)

    model._chat.side_effect = fail_second_batch
    reply, _ = asyncio.run(rei.handle_rei_console("give me a song", model, []))

    assert len(_translation_calls(model)) == 2
    assert "信号が光る" in reply and "予備の光が走る" in reply
    assert translator.translate.call_count == 1
    assert len(translator.translate.call_args.args[0]) > 10
    assert "skipping remaining Ollama batches" in caplog.text
    model.client.chat.assert_not_called()


def test_console_generate_mode_retries_a_bad_language_mix(
    console_setup: ReiDomainKnowledge, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("REI_BILINGUAL_STRATEGY", "generate")
    bad_song = dict(SONG)
    bad_song["verse_1"] = bad_song["verse_1"].replace(
        "Binary leaves of code, seeds of light", "信号が光る"
    )
    model = _model([bad_song, _japanese_song()])

    reply, _ = asyncio.run(rei.handle_rei_console("give me a song", model, []))

    assert model._chat.call_count == 3
    assert "Bilingual mix rejected on attempt 1" in caplog.text
    assert not _translation_calls(model)
    assert "信号が光る\n[shingou ga hikaru]" in reply
    model.client.chat.assert_not_called()


def test_console_generate_mode_stops_after_five_invalid_drafts(
    console_setup: ReiDomainKnowledge, monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("REI_BILINGUAL_STRATEGY", "generate")
    bad_song = dict(SONG)
    bad_song["verse_1"] = bad_song["verse_1"].replace(
        "Binary leaves of code, seeds of light", "信号が光る"
    )
    model = _model([bad_song] * 5)

    reply, _ = asyncio.run(rei.handle_rei_console("give me a song", model, []))

    assert model._chat.call_count == 6
    assert "Bilingual lyric mix failed after 5 attempts" in caplog.text
    assert "Reverting to formatted fallback" in caplog.text
    assert not _translation_calls(model)
    assert "[Chorus]" in reply
    model.client.chat.assert_not_called()


@pytest.mark.parametrize(("strategy", "attempts"), [("translate", 2), ("generate", 5)])
def test_console_uses_shared_fallback_for_unusable_lyric_drafts(
    strategy: str, attempts: int, console_setup: ReiDomainKnowledge,
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("REI_BILINGUAL_STRATEGY", strategy)
    model = _model()
    respond = model._chat.side_effect

    def malformed_draft(system: str, user: str, **kwargs: object) -> str:
        if "Generate an exceptionally long-form" in user:
            return "not valid JSON"
        return respond(system, user, **kwargs)

    model._chat.side_effect = malformed_draft
    reply, _ = asyncio.run(rei.handle_rei_console("give me a song", model, []))

    assert model._chat.call_count == attempts + 1
    assert "Reverting to formatted fallback" in caplog.text
    assert "信号を追いかけて" in reply
    assert not _translation_calls(model)
    model.client.chat.assert_not_called()


@pytest.mark.parametrize(
    ("language", "draft", "instruction"),
    [
        ("english", SONG, "natural English only"),
        ("japanese", _japanese_song(), "natural contemporary Japanese"),
    ],
)
def test_console_explicit_language_modes_do_not_translate_hooks(
    language: str, draft: dict[str, str], instruction: str,
    console_setup: ReiDomainKnowledge, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REI_LYRIC_LANGUAGE", language)
    model = _model([draft])

    reply, _ = asyncio.run(rei.handle_rei_console("give me a song", model, []))

    assert model._chat.call_count == 2
    assert instruction in model._chat.call_args_list[1].args[0]
    assert not _translation_calls(model)
    assert "[Chorus]" in reply
    model.client.chat.assert_not_called()


@pytest.mark.parametrize(
    ("user_input", "history"),
    [
        ("write a song about recursion and an epic guitar solo", []),
        (
            "try again",
            [
                {"role": "user", "content": "write a song about recursion and an epic guitar solo"},
                {"role": "assistant", "content": "🎵 Previous song"},
            ],
        ),
    ],
)
def test_console_explicit_and_retry_topics_do_not_require_extracted_knowledge(
    user_input: str, history: list[dict[str, str]], console_setup: ReiDomainKnowledge,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    load = MagicMock(side_effect=RuntimeError("knowledge unavailable"))
    monkeypatch.setattr(rei, "_lav_rei_console", load)
    model = _model()

    reply, updated = asyncio.run(rei.handle_rei_console(user_input, model, history))

    load.assert_not_called()
    assert "recursion and an epic guitar solo" in model._chat.call_args_list[0].args[1]
    assert "[Chorus]" in reply
    assert updated[-2:] == [
        {"role": "user", "content": user_input}, {"role": "assistant", "content": reply}
    ]


@pytest.mark.parametrize("topic", ["recursion", "recursion " + "deeply layered " * 10])
def test_console_retry_keeps_new_user_direction_in_both_structured_prompts(
    topic: str, console_setup: ReiDomainKnowledge,
) -> None:
    model = _model()
    history = [
        {"role": "user", "content": f"write a song about {topic}"},
        {"role": "assistant", "content": "🎵 Previous song"},
    ]

    reply, _ = asyncio.run(rei.handle_rei_console(
        "try again with an epic guitar solo", model, history,
    ))

    concept_prompt = model._chat.call_args_list[0].args[1].lower()
    lyric_prompt = model._chat.call_args_list[1].args[1].lower()
    assert "recursion" in concept_prompt and "epic guitar solo" in concept_prompt
    assert "recursion" in lyric_prompt and "epic guitar solo" in lyric_prompt
    assert "[Chorus]" in reply


def test_console_reports_structured_generation_failure_without_freeform_fallback(
    console_setup: ReiDomainKnowledge, caplog: pytest.LogCaptureFixture,
) -> None:
    model = _model()
    model._chat.side_effect = RuntimeError("Ollama unavailable")
    history = [{"role": "user", "content": "Hello"}]

    reply, updated = asyncio.run(rei.handle_rei_console("give me a song", model, history))

    assert "Song generation failed" in reply and "Ollama unavailable" in reply
    assert updated == [{"role": "user", "content": "Hello"}]
    assert "Ollama unavailable" in caplog.text
    model.client.chat.assert_not_called()


def test_console_without_facts_or_metaphors_still_uses_structured_generation(
    console_setup: ReiDomainKnowledge, caplog: pytest.LogCaptureFixture,
) -> None:
    console_setup.technical_metaphor_library.clear()
    model = _model()

    reply, _ = asyncio.run(rei.handle_rei_console("give me a song", model, []))

    assert "digital creativity" in model._chat.call_args_list[0].args[1].lower()
    assert "[Chorus]" in reply
    assert "No extracted themes or Rei metaphor themes" in caplog.text
    model.client.chat.assert_not_called()
