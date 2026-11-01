"""Tests for English-first bilingual lyrics: hook selection, batched translation, Argos fallback."""

import json
import logging
from pathlib import Path
from typing import List, Optional
from unittest.mock import MagicMock

import pytest

from services.rei_toei import _argos_fallback, _hook_translation
from services.rei_toei._config import ReiToeiConfig
from services.rei_toei._hook_translation import (
    HookLine,
    clean_translation,
    insert_hook_translations,
    japanese_line_target,
    parse_batched_translations,
    select_hook_lines,
    to_plain_form,
    translate_hook_texts,
)
from services.rei_toei._models import ReiDomainKnowledge, ReiPersonaGraph, SongConcept
from services.rei_toei._suno_pipeline import assemble_suno_prompt, compose_lyrics

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


class FakeArgos:
    def __init__(self, outputs: List[Optional[str]]) -> None:
        self.outputs = outputs
        self.calls: List[List[str]] = []

    def translate(self, lines: List[str]) -> List[Optional[str]]:
        self.calls.append(list(lines))
        return self.outputs[: len(lines)]


def _concept() -> SongConcept:
    return SongConcept(
        song_id="song", title="Data Seeds", theme="growth", mood="hopeful", bpm=142,
        genre_tags=["cyberpop"], narrative_arc="seeds bloom", evidence_ids=[],
        generated_at="2026-11-01", lyric_language="bilingual",
    )


def _persona() -> ReiPersonaGraph:
    return ReiPersonaGraph(
        schema_version="1", identity={"name": "Rei"}, personality_traits=[],
        musical_expertise={}, production_knowledge={"lyrical_approach": {}},
        communication_style={"tone": "digital"}, knowledge_sources={},
        creative_process={}, constraints={}, comparison_to_sam={},
    )


def _domain() -> ReiDomainKnowledge:
    return ReiDomainKnowledge(
        schema_version="1", music_theory={}, tidal_cycles_syntax={},
        genre_production_techniques={}, bpm_and_mood={}, synth_selection_guidelines={},
        lyrical_structure={}, technical_metaphor_library={}, suno_prompt_templates={},
        production_notes={},
    )


@pytest.fixture
def translate_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("REI_BILINGUAL_STRATEGY", "translate")
    monkeypatch.setenv("REI_JAPANESE_LYRIC_PROBABILITY", "0.15")
    monkeypatch.setenv("REI_ARGOS_MODEL_DIR", str(tmp_path / "no-model"))
    monkeypatch.setattr(_argos_fallback, "_CACHE", {})
    return tmp_path


@pytest.mark.parametrize(
    ("sung", "ratio", "max_lines", "expected"),
    [(24, 0.0, 8, 0), (24, 0.15, 8, 4), (60, 0.25, 8, 8), (10, 0.05, 8, 2), (4, 0.05, 8, 1), (0, 0.5, 8, 0)],
)
def test_japanese_line_target_hits_ratio_after_insertion(sung, ratio, max_lines, expected):
    assert japanese_line_target(sung, ratio, max_lines) == expected


def test_select_hook_lines_starts_with_chorus_and_spreads_across_sections():
    hooks = select_hook_lines(dict(SONG), 0.15, 8)

    assert [(h.field, h.text) for h in hooks] == [
        ("chorus", "Blossom from data seeds"),
        ("verse_1", "Binary leaves of code, seeds of light"),
        ("verse_2", "A glitch disrupts the flow"),
        ("bridge", "Roots of code through broken ground"),
    ]


def test_select_hook_lines_skips_cues_japanese_short_and_duplicate_lines():
    payload = {
        "chorus": "[Chorus]\n(Oh oh oh)\n信号が走る\nGo\nHold the light tonight\nHold the light tonight",
        "verse_1": "[Verse 1]\nHold the light tonight\nA quiet room remembers",
    }

    hooks = select_hook_lines(payload, 0.9, 8)

    assert [h.text for h in hooks] == ["Hold the light tonight", "A quiet room remembers"]
    assert hooks[0].index == 4


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("データの種から咲け", "データの種から咲け"),
        ('1. "光の種"', "光の種"),
        ("夢を描く [yume o egaku]", "夢を描く"),
        ("「夜明けの光」。", "夜明けの光"),
        ("電子火花在空中", "電子火花が空に舞う"),
        ("SQLで探す", "SQLで探す"),
        ("数据流动了", None),
        ("我们的数据", None),
        ("Blossom from data seeds", None),
        ("", None),
        (None, None),
        ("あ" * 60, None),
    ],
)
def test_clean_translation_keeps_only_usable_japanese(raw, expected):
    assert clean_translation(raw) == expected


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ('{"translations": ["光の種", "夢を描く"]}', ["光の種", "夢を描く"]),
        ('["光の種", "夢を描く"]', ["光の種", "夢を描く"]),
        ('{"2": "夢を描く", "1": "光の種"}', ["光の種", "夢を描く"]),
        ('{"translations": [{"ja": "光の種"}, "Not Japanese"]}', ["光の種", None]),
        ('Here you go: {"translations": ["光の種", "夢を描く"]}', ["光の種", "夢を描く"]),
        ('{"translations": ["光の種"]}', [None, None]),
        ("not json", [None, None]),
    ],
)
def test_parse_batched_translations_rejects_misaligned_replies(reply, expected):
    assert parse_batched_translations(reply, 2) == expected


@pytest.mark.parametrize(
    ("line", "expected"),
    [("流れを破壊します", "流れを破壊する"), ("光っています", "光っている"), ("これは夢です", "これは夢"), ("夢を描く", "夢を描く")],
)
def test_to_plain_form_turns_polite_endings_into_lyric_form(line, expected):
    assert to_plain_form(line) == expected


def test_translate_hook_texts_uses_one_call_and_argos_for_rejected_lines(monkeypatch, tmp_path):
    argos = FakeArgos(["グリッチは流れを破壊します"])
    monkeypatch.setattr(_hook_translation, "get_argos_translator", lambda _: argos)
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps({"translations": ["光の種", "数据流动了"]}, ensure_ascii=False)

    translations, counts = translate_hook_texts(
        ["SEEDS OF LIGHT", "A glitch disrupts the flow"], ollama, tmp_path, context="Data Seeds"
    )

    assert translations == ["光の種", "グリッチは流れを破壊する"]
    assert counts == {"ollama": 1, "argos": 1, "failed": 0}
    assert ollama._chat.call_count == 1
    prompt = ollama._chat.call_args.args[1]
    assert "1. Seeds of light" in prompt and "exactly 2" in prompt and "Data Seeds" in prompt
    assert argos.calls == [["A glitch disrupts the flow"]]


def test_translate_hook_texts_falls_back_when_ollama_fails(monkeypatch, tmp_path):
    argos = FakeArgos(["光の種", "Nope"])
    monkeypatch.setattr(_hook_translation, "get_argos_translator", lambda _: argos)
    ollama = MagicMock()
    ollama._chat.side_effect = RuntimeError("Ollama unreachable")

    translations, counts = translate_hook_texts(["Seeds of light", "Hold on"], ollama, tmp_path)

    assert translations == ["光の種", None]
    assert counts == {"ollama": 0, "argos": 1, "failed": 1}


def test_translate_hook_texts_without_argos_leaves_failed_lines_english(monkeypatch, tmp_path):
    monkeypatch.setattr(_hook_translation, "get_argos_translator", lambda _: None)
    ollama = MagicMock()
    ollama._chat.return_value = "{}"

    translations, counts = translate_hook_texts(["Seeds of light"], ollama, tmp_path)

    assert translations == [None]
    assert counts["failed"] == 1


def test_insert_hook_translations_puts_japanese_above_its_english_line():
    payload = {"bridge": "[Bridge]\nRoots of code\nEvery seed is found\nOne last bloom"}
    hooks = [HookLine("bridge", 1, "Roots of code"), HookLine("bridge", 3, "One last bloom")]

    inserted = insert_hook_translations(payload, hooks, ["コードの根", None])
    assert inserted == 1
    assert payload["bridge"] == "[Bridge]\nコードの根\nRoots of code\nEvery seed is found\nOne last bloom"

    payload = {"bridge": "[Bridge]\nRoots of code\nEvery seed is found\nOne last bloom"}
    insert_hook_translations(payload, hooks, ["コードの根", "最後の花"])
    assert payload["bridge"].splitlines() == [
        "[Bridge]", "コードの根", "Roots of code", "Every seed is found", "最後の花", "One last bloom",
    ]


def test_get_argos_translator_returns_none_without_model(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(_argos_fallback, "_CACHE", {})

    with caplog.at_level(logging.INFO):
        assert _argos_fallback.get_argos_translator(tmp_path / "missing") is None

    assert "download-argos-en-ja.sh" in caplog.text


def test_config_rejects_unknown_bilingual_strategy(monkeypatch):
    monkeypatch.setenv("REI_BILINGUAL_STRATEGY", "magic")
    with pytest.raises(ValueError, match="REI_BILINGUAL_STRATEGY"):
        ReiToeiConfig()


def test_config_defaults_to_translate_strategy(monkeypatch):
    monkeypatch.delenv("REI_BILINGUAL_STRATEGY", raising=False)
    config = ReiToeiConfig()
    assert config.bilingual_strategy == "translate"
    assert config.bilingual_max_hook_lines == 8


def test_compose_lyrics_translate_mode_writes_english_then_adds_japanese_hooks(translate_env):
    ollama = MagicMock()
    ollama._chat.side_effect = [
        json.dumps(SONG),
        json.dumps({"translations": ["データの種から咲け", "コードの葉、光の種", "グリッチが流れを乱す", "壊れた地面を貫く根"]}, ensure_ascii=False),
    ]

    lyrics = compose_lyrics(_concept(), _persona(), _domain(), ollama=ollama)
    prompt = assemble_suno_prompt(_concept(), lyrics, _domain())

    assert ollama._chat.call_count == 2
    song_system_prompt = ollama._chat.call_args_list[0].args[0]
    assert "natural English only" in song_system_prompt
    assert "Target:" not in song_system_prompt
    assert lyrics.chorus.splitlines()[1:3] == ["データの種から咲け", "BLOSSOM FROM DATA SEEDS"]
    assert "データの種から咲け\n[deeta no" in prompt.lyrics
    assert "グリッチが流れを乱す\n[guritchi ga nagare o midasu]\nA glitch disrupts the flow" in prompt.lyrics


def test_compose_lyrics_translate_mode_keeps_english_song_when_translation_fails(translate_env, caplog):
    ollama = MagicMock()
    ollama._chat.side_effect = [json.dumps(SONG), "not json"]

    with caplog.at_level(logging.WARNING):
        lyrics = compose_lyrics(_concept(), _persona(), _domain(), ollama=ollama)

    assert ollama._chat.call_count == 2
    assert "Binary leaves of code" in lyrics.verse_1
    assert "No hook lines were translated" in caplog.text
    assert "Bilingual mix rejected" not in caplog.text
