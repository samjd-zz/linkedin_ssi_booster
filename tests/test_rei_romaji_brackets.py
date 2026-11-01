"""Tests that Romaji stays bracketed so Suno does not sing pronunciation lines."""

import pytest

from services.rei_toei._romaji_brackets import bracket_bare_romaji_lines
from services.rei_toei._suno_pipeline import _append_normalized_section


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "コードセクスに\nkoodosekusu ni\ncodex stutters,",
            "コードセクスに\n[koodosekusu ni]\ncodex stutters,",
        ),
        (
            "再起動する\nSaikidō suru\nrestarts,",
            "再起動する\n[Saikidō suru]\nrestarts,",
        ),
        (
            "電子の暴走\nDenshi no bousō\nelectrons run wild,",
            "電子の暴走\n[Denshi no bousō]\nelectrons run wild,",
        ),
        (
            "境界を越えて\n[kyoukai o koete]\nKokoro no code\nBeyond the boundary",
            "境界を越えて\n[kyoukai o koete]\n[Kokoro no code]\nBeyond the boundary",
        ),
        (
            "新たな連結\n[aratana renketsu]\nAtarashii ryokin\nnew connections,",
            "新たな連結\n[aratana renketsu]\n[Atarashii ryokin]\nnew connections,",
        ),
        (
            "新たな連結\n[aratana renketsu]\naratana renketsu",
            "新たな連結\n[aratana renketsu]\n[aratana renketsu]",
        ),
        (
            "新たなる旋律\n[aratanaru senritsu]\nAtarashara tetrillu\nnew melody.",
            "新たなる旋律\n[aratanaru senritsu]\n[Atarashara tetrillu]\nnew melody.",
        ),
    ],
)
def test_bare_romaji_is_bracketed_without_removing_lines(source: str, expected: str) -> None:
    payload = {"verse_1": source}

    assert bracket_bare_romaji_lines(payload) == 1
    assert payload["verse_1"] == expected


@pytest.mark.parametrize(
    "source",
    [
        "データ流れる\nData streams,\nSegmented into parts.",
        "データ流れる\n[deeta nagareru]\nData streams,\nSegmented into parts.",
        "データ流れる\n[deeta nagareru]\nRemote signals\nCalling home",
        "夢の中\nMake some noise\nTake me home",
        "データの海\nOcean of data",
        "データの海\n(bass drop)\nHold on tight",
        "Signal enters the field\nWe run tonight",
    ],
)
def test_english_lyrics_and_stage_cues_are_left_alone(source: str) -> None:
    payload = {"verse_1": source}

    assert bracket_bare_romaji_lines(payload) == 0
    assert payload["verse_1"] == source


def test_assembled_section_brackets_pinyin_after_chinese_word() -> None:
    source = "(Choir whisper) データ重组\nShūzeng shùjī\nreconstituted data"

    result = _append_normalized_section([], source, "Outro")

    assert "Shūzeng" not in result
    assert "データ再構成\n[deeta saikousei]\nreconstituted data" in result


def test_assembled_section_never_leaves_bare_romaji() -> None:
    source = (
        "コードセクスに\nkoodosekusu ni\ncodex stutters,\n\n"
        "データの風が吹く\ndeeta no kaze ga fuku\ndata whispers."
    )

    result = _append_normalized_section([], source, "Verse 1")

    assert result == (
        "[Verse 1]\nコードセクスに\n[koodosekusu ni]\ncodex stutters,\n\n"
        "データの風が吹く\n[deeta no kaze ga fuku]\ndata whispers."
    )


def test_assembled_section_keeps_extra_guesses_bracketed() -> None:
    source = (
        "境界を越えて\n[kyoukai o koete]\nKokoro no code\nBeyond the boundary\n\n"
        "新たな連結\n[aratana renketsu]\nAtarashii ryokin\nnew connections,"
    )

    result = _append_normalized_section([], source, "Chorus")

    assert "[Kokoro no code]\nBeyond the boundary" in result
    assert "[Atarashii ryokin]\nnew connections," in result
    assert "\nKokoro no code" not in result
    assert "\nAtarashii ryokin" not in result
