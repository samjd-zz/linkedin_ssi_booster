"""Regression tests for full Romaji coverage and joined verb endings."""

import pytest

from services.rei_toei._lyric_romaji import (
    _generate_hepburn_romaji,
    _verify_and_correct_romaji_lines,
)
from services.rei_toei._suno_pipeline import (
    _append_normalized_section,
    _backfill_missing_romaji_cues,
)


@pytest.mark.parametrize(
    ("japanese", "expected"),
    [
        ("セグメント化される", "segumentoka sareru"),
        ("記憶に刻まれる", "kioku ni kizamareru"),
        ("光って消えた", "hikatte kieta"),
        ("止まらない", "tomaranai"),
        ("見られなかった", "mirarenakatta"),
        ("読んだり書いたり", "yondari kaitari"),
        ("SQLで探査", "SQL de tansa"),
        ("駅で待って", "eki de matte"),
    ],
)
def test_generate_hepburn_romaji_joins_verb_endings(japanese: str, expected: str) -> None:
    assert _generate_hepburn_romaji(japanese) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("セグメント化される\n[segumentoka sa reru]", "セグメント化される\n[segumentoka sareru]"),
        (
            "波形が光り輝く\n[hakei ga hikari kagayaku]\nWaveforms shine bright,",
            "波形が光り輝く\n[hakei ga hikarikagayaku]\nWaveforms shine bright,",
        ),
        (
            "記憶に刻まれる\n[Kioku ni kizama reru] [Etched in memory]",
            "記憶に刻まれる\n[Kioku ni kizamareru] [Etched in memory]",
        ),
        ("コードが舞う\n[Kōdo ga ma u]", "コードが舞う\n[Kōdo ga mau]"),
    ],
)
def test_existing_cues_with_split_verb_endings_are_joined(source: str, expected: str) -> None:
    payload = {"verse_1": source}

    assert _verify_and_correct_romaji_lines(payload) == 1
    assert payload["verse_1"] == expected


@pytest.mark.parametrize(
    "source",
    [
        "セグメント化される\n[segumentoka sareru]",
        "コードが舞う\n[Kōdo ga mau]",
        "メモリに記憶し,\n[memori ni kioku shi,]",
        "接続点から始まる\n[setsuzoku ten kara hajimaru]",
    ],
)
def test_correctly_spaced_cues_are_left_alone(source: str) -> None:
    payload = {"verse_1": source}

    assert _verify_and_correct_romaji_lines(payload) == 0
    assert payload["verse_1"] == source


def test_formatted_suno_section_joins_split_verb_endings() -> None:
    blocks: list[str] = []
    result = _append_normalized_section(
        blocks, "セグメント化される\n[segumentoka sa reru]", "Verse 1"
    )

    assert "[segumentoka sareru]" in result
    assert "sa reru" not in result
    assert blocks == [result]


def test_backfill_cues_every_uncued_japanese_line() -> None:
    japanese_lines = [
        "データ流れる",
        "波形が光る",
        "記憶に刻まれる",
        "無限ループ",
        "遅延が生じる",
        "コードが舞う",
        "信号が混乱する",
        "最後は静寂",
    ]
    payload = {"verse_1": "\n".join(japanese_lines)}

    added = _backfill_missing_romaji_cues(payload)

    lines = payload["verse_1"].splitlines()
    assert added == len(japanese_lines)
    assert len(lines) == len(japanese_lines) * 2
    for index in range(0, len(lines), 2):
        assert lines[index] == japanese_lines[index // 2]
        assert lines[index + 1].startswith("[") and lines[index + 1].endswith("]")


def test_backfill_keeps_english_lines_sung_and_skips_cued_lines() -> None:
    payload = {
        "verse_1": "データ流れる\n[deeta nagareru]\nData streams\n波形が光る\nWaveforms shine",
    }

    added = _backfill_missing_romaji_cues(payload)

    assert added == 1
    assert payload["verse_1"] == (
        "データ流れる\n[deeta nagareru]\nData streams\n"
        "波形が光る\n[hakei ga hikaru]\nWaveforms shine"
    )
