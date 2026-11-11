"""Suno-facing cleanup: inline glosses, Chinese phrasing, cue tags, intro split."""

import pytest

from services.rei_toei._suno_cleanup import (
    has_chinese_grammar,
    has_emoji,
    replace_chinese_phrasing,
    split_inline_glosses,
    split_intro_block,
    strip_emoji,
    strip_emoji_lines,
    tag_instrument_cues,
)
from services.rei_toei._suno_pipeline import _append_normalized_section
from services.rei_toei._suno_json import _has_prompt_schema_leakage
from services.rei_toei._suno_sections import _normalize_suno_section


@pytest.mark.parametrize(
    "instruction",
    [
        "immediately after the intro header",
        "Immediately after the intro header.",
        "directly after the intro header",
        "right after the [Intro Verse] header",
        "インロヘッダの直後",
        "イントロヘッダーの直後",
    ],
)
def test_intro_header_instructions_are_detected_and_removed(instruction: str) -> None:
    source = f"[Intro Verse]\n{instruction}\nThe city wakes"
    assert _has_prompt_schema_leakage({"intro": source})
    assert _normalize_suno_section(source, "Intro Verse") == "[Intro Verse]\nThe city wakes"


def test_translated_intro_instruction_and_its_romaji_are_removed() -> None:
    source = (
        "[Intro Verse]\nインロヘッダの直後\n[inrohedda no chokugo]\n"
        "immediately after the intro header\nThe city wakes"
    )
    expected = "[Intro Verse]\nThe city wakes"
    assert _normalize_suno_section(source, "Intro Verse") == expected
    assert _append_normalized_section([], source, "Intro Verse") == expected
    assert _append_normalized_section([], expected, "Intro Verse") == expected


def test_suno_section_drops_punctuation_placeholders_and_dangling_intro_line() -> None:
    source = "[Intro Verse]\n.\nStart with  .\nNeon flickers, binary dreams."

    assert _normalize_suno_section(source, "Intro Verse") == (
        "[Intro Verse]\nNeon flickers, binary dreams."
    )


def test_intro_instruction_removal_preserves_primer_and_stage_cues() -> None:
    source = (
        "[Instrumental Build]\n(Ahh ahh ahh) immediately after the intro header.\n"
        "[Atmospheric Pads]"
    )
    assert _append_normalized_section([], source, "Instrumental Build") == (
        "[Instrumental Build]\n(Ahh ahh ahh)\n[Atmospheric Pads]"
    )


def test_intro_instruction_matching_preserves_real_lyrics() -> None:
    source = "Immediately after the rain, I breathe\nイントロが響く\n[Whisper]"
    assert not _has_prompt_schema_leakage({"intro": source})
    assert _normalize_suno_section(source, "Intro Verse") == f"[Intro Verse]\n{source}"


@pytest.mark.parametrize("following", ["[Whisper]", "[inrohedda no chokugo] The city wakes"])
def test_removing_translated_instruction_keeps_unrelated_following_content(
    following: str,
) -> None:
    source = f"インロヘッダの直後\n{following}"
    assert following in _normalize_suno_section(source, "Intro Verse")


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Signal flux pulse (信號流脈 shingō ryūme)", "Signal flux pulse\n信号流脈"),
        ("Data flux pulse (信號流脈 shingō ryūme),", "Data flux pulse,\n信号流脈"),
        (
            "Digital fabric, stronger than before (より強い yóri tsuyoi).",
            "Digital fabric, stronger than before.\nより強い",
        ),
        ("Unity's our shield (データ (data))", "Unity's our shield\nデータ"),
    ],
)
def test_inline_glosses_move_japanese_to_its_own_line(line: str, expected: str) -> None:
    assert split_inline_glosses(line) == expected


@pytest.mark.parametrize(
    "line",
    [
        "Echoes of SQL in every line rings. (Silence)",
        "Mugen ruupu (無限ループ)",
        "データの流れ (deeta no nagare)",
        "(Ahh ahh ahh)",
    ],
)
def test_non_gloss_lines_are_unchanged(line: str) -> None:
    assert split_inline_glosses(line) == line


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("信號流脈", "信号流脈"),
        ("由程式重塑", "プログラムで再構築"),
        ("數據の海", "データの海"),
        ("自由の歌", "自由の歌"),
    ],
)
def test_chinese_phrasing_becomes_japanese(source: str, expected: str) -> None:
    assert replace_chinese_phrasing(source) == expected


def test_instrument_cues_become_meta_tags_but_vocalizations_stay() -> None:
    source = "(bass drop)\n(Ahh ahh ahh)\n(guitar solo)\n(chaos)\nSignals surge"

    assert tag_instrument_cues(source) == (
        "[Heavy Bass Drop]\n(Ahh ahh ahh)\n[Guitar Solo]\n[Chaos]\nSignals surge"
    )


@pytest.mark.parametrize(
    ("section", "source", "expected"),
    [
        (
            "Drop",
            "[Drop]\n[Heavy Bass Drop]\n(Frequency sync, glitch surge)\n"
            "信号が融合し、ノイズは沈静化\n[shingou ga yuugou shi]",
            "[Drop]\n[Heavy Bass Drop]\n[Frequency sync, glitch surge]\n"
            "信号が融合し、ノイズは沈静化\n[shingou ga yuugou shi, noizu wa chinsei ka]",
        ),
        (
            "Outro",
            "[Outro]\n(Chill synth pads, fade)\n信号が融合し、パターン形成",
            "[Outro]\n[Chill synth pads, fade]\n信号が融合し、パターン形成\n[shingou ga yuugou shi, pataan keisei]",
        ),
        (
            "Drop",
            "[Drop]\n(Ahh ahh ahh)\n(Oh oh)\nSignals surge",
            "[Drop]\n(Ahh ahh ahh)\n(Oh oh)\nSignals surge",
        ),
        (
            "Chorus",
            "[Chorus]\n(Chill synth pads, fade)\nA sung lyric",
            "[Chorus]\n(Chill synth pads, fade)\nA sung lyric",
        ),
    ],
)
def test_production_direction_parentheticals_are_bracketed_only_in_drop_and_outro(
    section: str, source: str, expected: str,
) -> None:
    assert _append_normalized_section([], source, section) == expected


def test_intro_lyrics_move_to_intro_verse() -> None:
    block = "[Instrumental Build]\n(Ahh ahh ahh)\n\nShadows dance on screens,\nData rivers flow."

    instrumental, intro_verse = split_intro_block(block)

    assert instrumental == "[Instrumental Build]\n(Ahh ahh ahh)"
    assert intro_verse == "[Intro Verse]\nShadows dance on screens,\nData rivers flow."
    assert split_intro_block("[Instrumental Build]\n(Ahh ahh ahh)") == (
        "[Instrumental Build]\n(Ahh ahh ahh)",
        "",
    )


def test_assembled_song_fixes_all_suno_friction_points() -> None:
    chorus = _append_normalized_section(
        [],
        "Signal flux pulse (信號流脈 shingō ryūme)\n"
        "Cleansed by code's reformation (由程式重塑 yóu chéngshì shùzhuàng)",
        "Chorus",
    )
    bridge = _append_normalized_section(
        [],
        "Digital fabric, stronger than before (より強い yóri tsuyoi).\n"
        "[yori tsuyoi yóri tsuyoi.]",
        "Bridge",
    )
    drop = _append_normalized_section([], "(bass drop)\nSignals surge,", "Drop")
    intro = _append_normalized_section(
        [], "(Ahh ahh ahh)\n\nShadows dance on screens,", "Instrumental Build"
    )

    assert "(" not in chorus and "信號" not in chorus and "由" not in chorus
    assert chorus == (
        "[Chorus]\nSignal flux pulse\n信号流脈\n"
        "Cleansed by code's reformation\nプログラムで再構築"
    )
    assert bridge == "[Bridge]\nDigital fabric, stronger than before.\nより強い"
    assert drop == "[Drop]\n[Heavy Bass Drop]\nSignals surge,"
    assert intro == (
        "[Instrumental Build]\n(Ahh ahh ahh)\n\n[Intro Verse]\nShadows dance on screens,"
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Pulse (信号 shingou)\n[shingou]\nNext line", "Pulse\n信号\nNext line"),
        ("Pulse (信号)\nshingou\nNext line", "Pulse\n信号\nNext line"),
        ("Pulse (信号)\n[shingou shingō]\n[Guitar Solo]", "Pulse\n信号\n[Guitar Solo]"),
        ("Pulse (信号)\n[Signals scatter]", "Pulse\n信号\n[Signals scatter]"),
    ],
)
def test_gloss_split_drops_only_phonetic_duplicates(source: str, expected: str) -> None:
    assert split_inline_glosses(source) == expected


def test_ordinary_japanese_lines_keep_their_romaji_cue() -> None:
    section = _append_normalized_section(
        [], "Pulse (信号)\nデータの海\nThe tide turns", "Verse 1"
    )

    assert section == "[Verse 1]\nPulse\n信号\nデータの海\n[deeta no umi]\nThe tide turns"


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("電子火花在空中", True),
        ("我们的梦", True),
        ("夢が終了", False),
        ("現在の存在", False),
        ("在庫を了解", False),
        ("空に在る", False),
    ],
)
def test_chinese_grammar_is_detected_only_without_japanese_markers(
    line: str, expected: bool
) -> None:
    assert has_chinese_grammar(line) is expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "電子火花在空中\n[denshi hibana zai kuuchuu]\nElectron sparks in air",
            "[Drop]\n電子火花が空に舞う\n[denshi hibana ga sora ni mau]\nElectron sparks in air",
        ),
        (
            "電子火花在空中\n[denshi hibana zai kuuchuu] [Sparks in the air]",
            "[Drop]\n電子火花が空に舞う\n[denshi hibana ga sora ni mau]\nSparks in the air",
        ),
    ],
)
def test_repaired_chinese_line_gets_a_fresh_cue(source: str, expected: str) -> None:
    assert _append_normalized_section([], source, "Drop") == expected


@pytest.mark.parametrize("placeholder", ["(Blank Line)", "(BLANK LINE)", "(line break)"])
def test_tag_instrument_cues_turns_layout_placeholders_into_blank_lines(placeholder):
    text = f"Merge, split, a dance of stars\n{placeholder}\nTheir codes sync"
    assert tag_instrument_cues(text) == "Merge, split, a dance of stars\n\nTheir codes sync"


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("📐が揺れ動く", "が揺れ動く"),
        ("霧の中、📐が浮かぶ", "霧の中、が浮かぶ"),
        ("[📐 ga yureugoku]", "[ga yureugoku]"),
        ("Bouncing bytes ✨", "Bouncing bytes"),
        ("Glitch⚡pulse", "Glitch pulse"),
        ("Hold on ✨, tonight", "Hold on, tonight"),
        ("(✨ shine ✨)", "(shine)"),
        ("❤️ Love the code", "Love the code"),
        ("👩\u200d💻 Coding all night", "Coding all night"),
        ("🇯🇵 Tokyo nights", "Tokyo nights"),
        ("1️⃣ more time", "1 more time"),
        ("⏳ Time runs out", "Time runs out"),
    ],
)
def test_strip_emoji_removes_pictographs_and_tidies_spacing(line: str, expected: str) -> None:
    assert has_emoji(line)
    assert strip_emoji(line) == expected


@pytest.mark.parametrize(
    "line",
    ["ゆっくり〜 時々ー・「光」", "Cooling to 4°C → zero", "○ signal ● noise", "データの海  (Oh oh)"],
)
def test_strip_emoji_keeps_japanese_marks_and_plain_symbols(line: str) -> None:
    assert not has_emoji(line)
    assert strip_emoji(line) == line


def test_strip_emoji_lines_drops_emoji_only_lines_and_keeps_stanza_breaks() -> None:
    text = "✨✨\nGlitching signals ⚡\n\nBouncing bytes"

    assert strip_emoji_lines(text) == "Glitching signals\n\nBouncing bytes"
    assert strip_emoji_lines("Clean line\n\n  Indented") == "Clean line\n\n  Indented"


@pytest.mark.parametrize(
    ("source", "label", "expected"),
    [
        (
            "📐が揺れ動く\n[📐 ga yureugoku]\nGlitching signals,\n✨✨\nBouncing bytes ✨",
            "Verse 1",
            "[Verse 1]\nが揺れ動く\n[ga yureugoku]\nGlitching signals,\nBouncing bytes",
        ),
        ("データの盾 🛡️\nDATA SHIELD", "Chorus", "[Chorus]\nデータの盾\n[deeta no tate]\nDATA SHIELD"),
        ("✨ Melodic synth solo ✨", "Solo", "[Solo]\n[Melodic synth solo]"),
    ],
)
def test_assembled_sections_and_romaji_cues_have_no_emoji(
    source: str, label: str, expected: str
) -> None:
    assert _append_normalized_section([], source, label) == expected
