"""Simplified-Chinese kanji repair, rejection, and once-per-line warnings."""

import logging

import pytest

from services.rei_toei._hook_translation import clean_translation
from services.rei_toei._lyric_romaji import _generate_hepburn_romaji, is_readable_japanese
from services.rei_toei._suno_cleanup import (
    _SIMPLIFIED_TO_JAPANESE,
    non_japanese_kanji,
    replace_chinese_phrasing,
)


@pytest.mark.parametrize(
    "simplified, japanese",
    [("动", "動"), ("脉", "脈"), ("辉", "輝"), ("发", "発"), ("时", "時"), ("对", "対"), ("说", "説")],
)
def test_requested_simplified_characters_map_to_japanese(simplified, japanese):
    assert replace_chinese_phrasing(simplified) == japanese


@pytest.mark.parametrize(
    "line, expected",
    [
        ("ネオンの脉动が辉く", "ネオンの脈動が輝く"),
        ("ネオンの脈动が灯す", "ネオンの脈動が灯す"),
    ],
)
def test_song_lines_are_repaired(line, expected):
    assert replace_chinese_phrasing(line) == expected


@pytest.mark.parametrize(
    "line, expected",
    [("データ重组", "データ再構成"), ("网络が光る", "ネットワークが光る"),
     ("系统が動く", "システムが動く"), ("记忆の时间", "記憶の時間")],
)
def test_whole_words_win_over_per_character_mapping(line, expected):
    assert replace_chinese_phrasing(line) == expected


def test_every_mapping_target_is_japanese():
    targets = "".join(_SIMPLIFIED_TO_JAPANESE.values())
    assert non_japanese_kanji(targets) == ""


def test_non_japanese_kanji_detects_simplified_only_characters():
    assert non_japanese_kanji("信号が鸟のように飛ぶ") == "鸟"
    assert non_japanese_kanji("回路が焼ける") == ""


def test_clean_translation_repairs_mapped_characters():
    assert clean_translation("ネオンの脉动が辉く") == "ネオンの脈動が輝く"


def test_clean_translation_rejects_chinese_sentence_after_katakana_repair():
    # 数据→データ adds kana, but the raw reply was a Chinese sentence ending in 了.
    assert clean_translation("数据流动了") is None
    assert clean_translation("電子火花在空中") == "電子火花が空に舞う"


@pytest.mark.parametrize("line", ["信号が鸟のように飞ぶ", "新たな探柺"])
def test_clean_translation_rejects_leftover_non_japanese_kanji(line, caplog):
    with caplog.at_level(logging.INFO):
        assert clean_translation(line) is None
    assert "keeping the English line" in caplog.text


def test_clean_translation_rejects_unreadable_line(monkeypatch):
    from services.rei_toei import _hook_translation

    monkeypatch.setattr(_hook_translation, "is_readable_japanese", lambda _line: False)
    assert clean_translation("回路が焼ける") is None


def test_is_readable_japanese():
    assert is_readable_japanese("回路が焼ける")
    assert not is_readable_japanese("新たな探柺")


def test_is_readable_japanese_does_not_warn(caplog):
    with caplog.at_level(logging.WARNING):
        is_readable_japanese("新たな探柺")
    assert "Unreadable" not in caplog.text


@pytest.mark.parametrize("use_sudachi", [True, False])
def test_unreadable_warning_logs_once_per_line_with_text(monkeypatch, caplog, use_sudachi):
    from services.rei_toei import _lyric_romaji

    if not use_sudachi:
        monkeypatch.setattr(_lyric_romaji, "_get_sudachi_dictionary", lambda: None)
    with caplog.at_level(logging.WARNING):
        for _ in range(4):
            assert _generate_hepburn_romaji("新たな探柺") == ""

    warnings = [r for r in caplog.records if "Unreadable" in r.getMessage()]
    assert len(warnings) == 1
    assert "新たな探柺" in warnings[0].getMessage()
    assert "U+67FA (柺)" in warnings[0].getMessage()


def test_unreadable_warning_logs_each_distinct_line(monkeypatch, caplog):
    from services.rei_toei import _lyric_romaji

    monkeypatch.setattr(_lyric_romaji, "_get_sudachi_dictionary", lambda: None)
    with caplog.at_level(logging.WARNING):
        _generate_hepburn_romaji("新たな探柺")
        _generate_hepburn_romaji("古い探柺")
    assert sum("Unreadable" in r.getMessage() for r in caplog.records) == 2
