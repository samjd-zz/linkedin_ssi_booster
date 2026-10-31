"""Regression tests for Rei's Japanese pronunciation and Suno lyric cleanup."""

import asyncio
import json
import logging
from unittest.mock import MagicMock

import pytest

from services.rei_toei._models import (
    Lyrics,
    ReiDomainKnowledge,
    ReiPersonaGraph,
    SongConcept,
)
from services.rei_toei._suno_pipeline import (
    _backfill_missing_romaji_cues,
    _generate_hepburn_romaji,
    _learning_annotation_stats,
    _normalize_suno_section,
    _verify_and_correct_romaji_lines,
    assemble_suno_prompt,
    compose_lyrics,
)


@pytest.mark.parametrize(
    ("source", "expected", "incorrect", "meaning"),
    [
        (
            "データがぶつかり、歪む\n[Data ga tsuzurakitari, karumu] [Data crashes]",
            "butsukari",
            "tsuzurakitari",
            "[Data crashes]",
        ),
        (
            "信号が飛び散る\n[Shingō ga tonikzaru] [Signals scatter]",
            "tobichiru",
            "tonikzaru",
            "[Signals scatter]",
        ),
        (
            "信号が飛び散る\n[xkjqz garbage] [Signals scatter]",
            "shingou ga tobichiru",
            "xkjqz",
            "[Signals scatter]",
        ),
        (
            "データが飛ぶ\n[Data ga hobo] [Data flies,]",
            "tobu",
            "hobo",
            "[Data flies,]",
        ),
        (
            "夜明けの光\n[Yukigenke no hikari] [Dawn's light]",
            "yoake",
            "yukigenke",
            "[Dawn's light]",
        ),
        (
            "コードが舞う夜の世界\n[Kōdo ga mao yoru no sekai] [Dance in code]",
            "mau",
            " mao ",
            "[Dance in code]",
        ),
        (
            "遅延は消える、(Saiken wa koezu,) [Latency vanishes,]",
            "chien wa kieru",
            "saiken",
            "[Latency vanishes,]",
        ),
        (
            "無限ループに身を任せ、(Mugen rūpu ni mi o taseru,) [Surrender]",
            "makase",
            "taseru",
            "[Surrender]",
        ),
        (
            "バグが蠢く夜、(Bāgu ga kogaraku yoru,) [Night of bugs]",
            "ugomeku",
            "kogaraku",
            "[Night of bugs]",
        ),
        (
            "コードが崩れる\n[Kōdo ga konreru] [Code crumbles]",
            "kuzureru",
            "konreru",
            "[Code crumbles]",
        ),
        (
            "再起動の瞬間、(Saikidō no shinjigen,) [Restart's moment]",
            "shunkan",
            "shinjigen",
            "[Restart's moment]",
        ),
        (
            "データが暴れ、(Data ga urezero,) [Data roars]",
            "abare",
            "urezero",
            "[Data roars]",
        ),
        (
            "コードの旋律、(Kōdo no ryūdori,) [Melody of code]",
            "senritsu",
            "ryūdori",
            "[Melody of code]",
        ),
        (
            "データが静まる\n[Data ga shizamaru] [Data quiets]",
            "shizumaru",
            "shizamaru",
            "[Data quiets]",
        ),
        (
            "夜明けの光\n(Yukigenke no hikari [Dawn's light])",
            "yoake",
            "yukigenke",
            "[Dawn's light]",
        ),
        (
            "信号が飛び散る\nShingō ga tonikzaru [Signals scatter]",
            "tobichiru",
            "tonikzaru",
            "[Signals scatter]",
        ),
        (
            "遅延は消える（Saiken wa koezu）[Latency vanishes]",
            "chien wa kieru",
            "saiken",
            "[Latency vanishes]",
        ),
    ],
)
def test_repairs_mismatched_cue_formats(source, expected, incorrect, meaning):
    payload = {"verse_1": source}

    assert _verify_and_correct_romaji_lines(payload) == 1
    result = payload["verse_1"].lower()
    assert expected in result
    assert incorrect.lower() not in result
    assert meaning in payload["verse_1"]


@pytest.mark.parametrize(
    "source",
    [
        "君の手を握る\n[Kimi no te o nigiru] [Hold your hand]",
        "信号が飛び散る\n[Shingō ga tobichiru] [Signals scatter]",
        "無限ループに身を任せ (Mugen rūpu ni mi o makase) [Surrender]",
        "データの海\nOcean of data",
        "データの海\n[Ocean of data]",
        "猫と遊ぶ\nI go to the edge",
        "データの海\n[bass drop] [silence]",
    ],
)
def test_preserves_correct_cues_english_and_stage_directions(source):
    payload = {"verse_1": source}

    assert _verify_and_correct_romaji_lines(payload) == 0
    assert payload["verse_1"] == source


@pytest.mark.parametrize(
    ("japanese", "expected"),
    [
        ("信号が飛び散る", "shingou ga tobichiru"),
        ("遅延は消える", "chien wa kieru"),
        ("君の手を握る", "kimi no te o nigiru"),
        ("SQLで探査", "SQL de tansa"),
    ],
)
def test_context_aware_readings_and_particles(japanese, expected):
    assert _generate_hepburn_romaji(japanese) == expected


def test_unknown_kanji_does_not_produce_a_partial_reading(caplog):
    payload = {
        "outro": "新たな探柺\n[Atarashī saisaku] [New exploration]",
    }

    with caplog.at_level(logging.WARNING):
        assert _verify_and_correct_romaji_lines(payload) == 0

    assert payload["outro"] == "新たな探柺\n[Atarashī saisaku] [New exploration]"
    assert "unreadable" in caplog.text.lower()


def test_pykakasi_fallback_rejects_partially_readable_kanji(monkeypatch, caplog):
    from services.rei_toei import _lyric_romaji

    monkeypatch.setattr(_lyric_romaji, "_get_sudachi_dictionary", lambda: None)
    with caplog.at_level(logging.WARNING):
        assert _generate_hepburn_romaji("新たな探柺") == ""

    assert "unreadable" in caplog.text.lower()


def test_pykakasi_fallback_remains_available_without_sudachi(monkeypatch):
    from services.rei_toei import _lyric_romaji

    monkeypatch.setattr(_lyric_romaji, "_get_sudachi_dictionary", lambda: None)
    assert _generate_hepburn_romaji("回路が焼ける") == "kairo ga yake ru"


def test_missing_sudachi_logs_the_fallback(monkeypatch, caplog):
    from services.rei_toei import _lyric_romaji

    monkeypatch.setattr(_lyric_romaji, "_SUDACHI_AVAILABLE", False)
    _lyric_romaji._get_sudachi_dictionary.cache_clear()
    try:
        with caplog.at_level(logging.WARNING):
            assert _generate_hepburn_romaji("回路") == "kairo"
    finally:
        _lyric_romaji._get_sudachi_dictionary.cache_clear()
    assert "sudachi is unavailable" in caplog.text.lower()


def test_legacy_sudachi_dictionary_create_method_is_supported(monkeypatch):
    from sudachipy import dictionary
    from sudachipy.tokenizer import Tokenizer
    from services.rei_toei import _lyric_romaji

    sudachi = dictionary.Dictionary()
    tokenizer = sudachi.tokenizer() if hasattr(sudachi, "tokenizer") else sudachi.create()

    class LegacyDictionary:
        def create(self) -> Tokenizer:
            return tokenizer

    monkeypatch.setattr(_lyric_romaji, "_get_sudachi_dictionary", LegacyDictionary)
    assert _generate_hepburn_romaji("信号が飛び散る") == "shingou ga tobichiru"


def test_missing_converter_preserves_existing_cue_and_warns(monkeypatch, caplog):
    from services.rei_toei import _lyric_romaji

    monkeypatch.setattr(_lyric_romaji, "_get_kakasi", lambda: None)
    payload = {"verse_1": "信号が飛び散る\n[Wrong reading] [Signals scatter]"}
    with caplog.at_level(logging.WARNING):
        assert _verify_and_correct_romaji_lines(payload) == 0

    assert "[Wrong reading] [Signals scatter]" in payload["verse_1"]
    assert "pykakasi" in caplog.text.lower()


def test_single_word_romaji_counts_as_a_cue_without_duplicate_backfill():
    payload = {"verse_1": "回路\n[kairo]"}

    assert _learning_annotation_stats(payload)["annotation_pairs"] == 1
    assert _backfill_missing_romaji_cues(payload) == 0
    assert payload["verse_1"] == "回路\n[kairo]"


def test_backfill_keeps_english_translation_and_adds_single_word_romaji():
    payload = {"verse_1": "回路\n[Circuit]"}

    assert _backfill_missing_romaji_cues(payload) == 1
    assert payload["verse_1"] == "回路\n[kairo]\n[Circuit]"


@pytest.mark.parametrize(
    ("source", "expected_lyric", "expected_cue", "corrected", "added"),
    [
        ("コードが舞う (Kōdo ga mao)", "コードが舞う", "[koodo ga mau]", 1, 0),
        ("コードが舞う (Kōdo ga mau)", "コードが舞う", "[Kōdo ga mau]", 0, 0),
        ("コードが舞う（Kōdo ga mao）", "コードが舞う", "[koodo ga mau]", 1, 0),
        ("Kōdo ga mao (コードが舞う)", "コードが舞う", "[koodo ga mau]", 1, 0),
        ("Kōdo ga mau (コードが舞う)", "コードが舞う", "[Kōdo ga mau]", 0, 0),
        ("コードが舞う [Kōdo ga mao]", "コードが舞う", "[koodo ga mau]", 1, 0),
        ("コードが舞う [Kōdo ga mau]", "コードが舞う", "[Kōdo ga mau]", 0, 0),
        ("コードが舞う (Code dances)", "Code dances (コードが舞う)", "[koodo ga mau]", 0, 1),
        ("コードが舞う [Code dances]", "コードが舞う [Code dances]", "[koodo ga mau]", 0, 1),
        (
            "Signal enters the field (フィールドにサインが混じる)",
            "Signal enters the field (フィールドにサインが混じる)",
            "[fiirudo ni sain ga majiru]",
            0,
            1,
        ),
        ("SQLで探査 (SQL de tansa)", "SQLで探査", "[SQL de tansa]", 0, 0),
        ("SQL de tansa (SQLで探査)", "SQLで探査", "[SQL de tansa]", 0, 0),
        (
            "コードが舞う (Code dances)\n[Kōdo ga mao]",
            "Code dances (コードが舞う)",
            "[koodo ga mau]",
            1,
            0,
        ),
    ],
)
def test_inline_pronunciations_and_translations_do_not_duplicate_cues(
    source, expected_lyric, expected_cue, corrected, added
):
    payload = {"verse_1": source}

    assert _verify_and_correct_romaji_lines(payload) == corrected
    assert _backfill_missing_romaji_cues(payload) == added
    assert _learning_annotation_stats(payload)["annotation_pairs"] == 1
    result = _normalize_suno_section(payload["verse_1"], "Verse 1")
    assert expected_lyric in result
    assert result.count(expected_cue) == 1


def test_parenthetical_single_word_cue_is_canonicalized():
    result = _normalize_suno_section("回路\n(kairo [Circuit])", "Verse 1")

    assert "回路\n[kairo] [Circuit]" in result


@pytest.mark.parametrize(
    "source",
    [
        "データの海 [bass drop] [silence]",
        "データの海 (bass drop) [silence]",
        "データの海 [bass drop] (silence)",
        "データの海 [Ahh ahh] [silence]",
    ],
)
def test_inline_stage_cues_are_preserved_during_romaji_backfill(source):
    payload = {"verse_1": source}

    assert _verify_and_correct_romaji_lines(payload) == 0
    assert _learning_annotation_stats(payload)["annotation_pairs"] == 0
    assert _backfill_missing_romaji_cues(payload) == 1
    assert _learning_annotation_stats(payload)["annotation_pairs"] == 1
    result = _normalize_suno_section(payload["verse_1"], "Verse 1")
    assert source in result
    assert "\n[deeta no umi]" in result


def test_formatter_removes_quoted_instructions_but_keeps_real_lyrics():
    result = _normalize_suno_section(
        "then '(Ahh ahh ahh)',\n"
        "then '(bass drop)',\n"
        "then '4 lines of atmospheric resolution and fade text',\n"
        "Then the lights go down\n"
        "Then 4 lines of code ignite",
        "Outro",
    )

    assert "(Ahh ahh ahh)" in result
    assert "(bass drop)" in result
    assert "then '(" not in result.lower()
    assert "atmospheric resolution and fade text" not in result
    assert "Then the lights go down" in result
    assert "Then 4 lines of code ignite" in result


@pytest.mark.parametrize(
    "source",
    [
        "SQLで探査 (SQL de saisaku) [Exploring with SQL]",
        "SQL\nで探査\n[SQL de saisaku] [Exploring with SQL]",
    ],
)
def test_formatter_keeps_acronyms_attached_to_japanese(source):
    result = _normalize_suno_section(source, "Verse 1")

    assert "SQLで探査\n" in result
    assert "SQL\nで探査" not in result
    assert "[Exploring with SQL]" in result


def test_formatter_does_not_join_unrelated_english_lines():
    source = "I\nがんばる\nSQL\nThe lights come on"

    assert source in _normalize_suno_section(source, "Verse 1")


@pytest.mark.parametrize("acronym", ["GPU", "GPT-4", "AI/ML"])
@pytest.mark.parametrize("separator", ["", "\n"])
def test_formatter_keeps_technical_acronyms_with_japanese(acronym, separator):
    source = f"{acronym}{separator}で探査 ({acronym} de tansa) [Explore]"

    assert f"{acronym}で探査\n" in _normalize_suno_section(source, "Verse 1")


def test_romaji_first_english_translation_is_not_mistaken_for_a_cue():
    source = "Signal enters the field (フィールドにサインが混じる)"

    assert source in _normalize_suno_section(source, "Verse 1")


def test_console_fallback_cleans_only_identifiable_song_sections(monkeypatch):
    from services.console_grounding import _rei_console

    original = (
        "Title: Signal\nGenre Tags: cyberpop\n\n"
        "[Verse 1]\n信号が飛び散る\n[Shingō ga tonikzaru] [Signals scatter]\n"
        "[Drop]\nthen '(bass drop)',\n"
        "[Outro]\nthen '4 lines of atmospheric resolution and fade text',\n"
        "夜明けの光\n[Yukigenke no hikari] [Dawn's light]\n\n"
        "Suno Prompt: bright synthwave"
    )
    monkeypatch.setattr(_rei_console, "_build_rei_system_prompt", lambda *_: "system")
    monkeypatch.setattr(_rei_console, "_rei_chat", lambda *_, **__: original)

    reply, history = asyncio.run(
        _rei_console._handle_llm_song_generation(
            "Make a song", MagicMock(), MagicMock(), MagicMock(), []
        )
    )

    assert reply.startswith("Title: Signal\nGenre Tags: cyberpop")
    assert "[shingou ga tobichiru] [Signals scatter]" in reply
    assert "[yoake no hikari] [Dawn's light]" in reply
    assert "(bass drop)" in reply and "then '(" not in reply.lower()
    assert "atmospheric resolution and fade text" not in reply
    assert reply.endswith("Suno Prompt: bright synthwave")
    assert history[-1] == {"role": "assistant", "content": reply}


def test_console_fallback_leaves_unstructured_replies_unchanged(monkeypatch):
    from services.console_grounding import _rei_console

    original = "Here's an idea about 信号.\nWe can expand it into a song."
    monkeypatch.setattr(_rei_console, "_build_rei_system_prompt", lambda *_: "system")
    monkeypatch.setattr(_rei_console, "_rei_chat", lambda *_, **__: original)

    reply, _ = asyncio.run(
        _rei_console._handle_llm_song_generation(
            "Make a song", MagicMock(), MagicMock(), MagicMock(), []
        )
    )

    assert reply == original


def test_composition_and_suno_assembly_repair_the_preview(monkeypatch):
    monkeypatch.setenv("REI_JAPANESE_LYRIC_PROBABILITY", "0.4")
    concept = SongConcept(
        song_id="song",
        title="Signal",
        theme="SQL",
        mood="playful",
        bpm=142,
        genre_tags=["cyberpop"],
        narrative_arc="A signal finds home",
        evidence_ids=[],
        generated_at="2026-10-30",
        lyric_language="bilingual",
    )
    persona = ReiPersonaGraph(
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
    domain = ReiDomainKnowledge(
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
    response = {
        "intro": "then '(Ahh ahh ahh)',",
        "verse_1": "信号が飛び散る\n[Shingō ga tonikzaru] [Signals scatter]\nA candle waits",
        "chorus": "遅延は消える、(Saiken wa koezu,) [Latency vanishes,]\nHold the world",
        "verse_2": "SQL\nで探査\n[SQL de saisaku] [Exploring with SQL]\nShe checks the map",
        "bridge": "We find our way\nThe window opens",
        "drop": "then '(bass drop)',",
        "outro": "then '4 lines of atmospheric resolution and fade text',\nThe night fades",
    }
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(response, ensure_ascii=False)

    lyrics = compose_lyrics(concept, persona, domain, ollama=ollama)
    prompt = assemble_suno_prompt(concept, lyrics, domain)

    assert ollama._chat.call_count == 1
    assert "tobichiru" in lyrics.verse_1.lower()
    assert "chien wa kieru" in lyrics.chorus.lower()
    assert "SQLで探査" in lyrics.verse_2
    assert "SQL de tansa" in prompt.lyrics
    assert "[Signals scatter]" in prompt.lyrics
    assert "[Latency vanishes,]" in prompt.lyrics
    assert "(Ahh ahh ahh)" in prompt.lyrics
    assert "(bass drop)" in prompt.lyrics
    assert "then '(" not in prompt.lyrics.lower()
    assert "atmospheric resolution and fade text" not in prompt.lyrics

    direct_prompt = assemble_suno_prompt(
        concept, Lyrics(**response, evidence_ids=[]), domain
    )
    assert direct_prompt.lyrics == prompt.lyrics
