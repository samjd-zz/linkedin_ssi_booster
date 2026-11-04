"""Rei stage cues must not become sung lyrics or translated hooks."""

import pytest

from services.rei_toei._hook_translation import select_hook_lines
from services.rei_toei._lyric_prompts import build_lyric_prompts
from services.rei_toei._models import Lyrics, ReiDomainKnowledge, ReiPersonaGraph, SongConcept
from services.rei_toei._song_tidy import tidy_song_sections
from services.rei_toei._suno_cleanup import tag_instrument_cues
from services.rei_toei._suno_pipeline import (
    _append_normalized_section,
    _normalize_freeform_suno_reply,
    assemble_suno_prompt,
)
from services.rei_toei._suno_quality import ensure_suno_quality


DROP_EXAMPLE = (
    "[Drop]\n[Heavy Bass Drop]\n"
    "重低音ドロップ\n[juu teion doroppu]\nHeavy Bass Drop\n"
    "ベースラインが降下し、エネルギーが点き上がる\n"
    "[beesurain ga kouka shi, enerugii ga tsuki agaru]\n"
    "Bassline descends, energy ignites\n"
    "Quantum Nodes, Binary Dance\nFutures collide, in this electronic state"
)


@pytest.mark.parametrize(
    "cue",
    [
        "Heavy Bass Drop",
        "heavy   bass drop!",
        "Bass Drop",
        "**Heavy Bass Drop**",
        "Heavy Bass Drop (Heavy Bass Drop)",
    ],
)
def test_tidy_removes_bare_drop_cues_before_hook_selection(cue: str) -> None:
    payload = {
        "drop": f"[Drop]\n[Heavy Bass Drop]\n{cue}\nBassline descends, energy ignites",
        "verse_1": "A signal rises",
    }

    tidy_song_sections(payload)

    assert payload["drop"] == (
        "[Drop]\n[Heavy Bass Drop]\nBassline descends, energy ignites"
    )
    hooks = select_hook_lines(payload, 0.9, 40)
    assert {hook.text for hook in hooks} == {
        "A signal rises", "Bassline descends, energy ignites",
    }


@pytest.mark.parametrize(
    ("japanese", "reading"),
    [
        ("重低音ドロップ", "[juu teion doroppu]"),
        ("重低音ドロップ", "juu teion doroppu"),
        ("重低音のドロップ", "[juu teion no doroppu]"),
        ("ベースドロップ", "[beesu doroppu]"),
    ],
)
def test_tidy_removes_translated_drop_cue_and_its_reading(
    japanese: str, reading: str,
) -> None:
    payload = {
        "drop": f"[Drop]\n[Heavy Bass Drop]\n{japanese}\n{reading}\n"
                "Heavy Bass Drop\nBassline descends",
    }

    tidy_song_sections(payload)

    assert payload["drop"] == "[Drop]\n[Heavy Bass Drop]\nBassline descends"


def test_tidy_preserves_lyrics_metadata_and_instrumental_solo() -> None:
    payload = {
        "title": "Heavy Bass Drop",
        "drop": (
            "[Drop]\n[Heavy Bass Drop]\nHeavy bass drops like thunder\n"
            "The bass drop shakes the floor\n重低音ドロップが響く\n"
            "ベースドロップ、響き、崩壊する\n(Oh oh)"
        ),
        "solo": "Heavy Bass Drop",
    }

    tidy_song_sections(payload)

    assert payload["title"] == "Heavy Bass Drop"
    assert payload["solo"] == "[Solo]\n[Heavy Bass Drop]"
    assert payload["drop"] == (
        "[Drop]\n[Heavy Bass Drop]\nHeavy bass drops like thunder\n"
        "The bass drop shakes the floor\n重低音ドロップが響く\n"
        "ベースドロップ、響き、崩壊する\n(Oh oh)"
    )


def test_suno_section_removes_the_reported_sung_copies() -> None:
    section = _append_normalized_section([], DROP_EXAMPLE, "Drop")

    assert section.startswith("[Drop]\n[Heavy Bass Drop]\n")
    assert section.count("[Heavy Bass Drop]") == 1
    assert "重低音ドロップ" not in section
    assert "[juu teion doroppu]" not in section
    assert "\nHeavy Bass Drop\n" not in section
    assert "ベースラインが降下し、エネルギーが点き上がる" in section
    assert "Bassline descends, energy ignites" in section
    assert "Quantum Nodes, Binary Dance" in section
    assert _append_normalized_section([], section, "Drop") == section


def test_inline_japanese_cue_is_removed_without_losing_other_stage_tags() -> None:
    source = (
        "[Heavy Bass Drop]\n"
        "重低音ドロップ [juu teion doroppu] [Guitar Solo]\n"
        "Heavy Bass Drop\nBassline descends"
    )

    section = _append_normalized_section([], source, "Drop")

    assert section == (
        "[Drop]\n[Heavy Bass Drop]\n[Guitar Solo]\nBassline descends"
    )


def test_stage_marker_after_removed_japanese_line_is_preserved() -> None:
    source = "重低音ドロップ\n[Heavy Bass Drop]\nBassline descends"

    assert _append_normalized_section([], source, "Drop") == (
        "[Drop]\n[Heavy Bass Drop]\nBassline descends"
    )


@pytest.mark.parametrize(
    "following",
    ["[Ambient drums] [Synth sweep]", "[Synth loop] [Bass echoes]", "Bassline descends"],
)
def test_removing_japanese_cue_preserves_unrelated_following_content(following: str) -> None:
    payload = {
        "drop": f"[Heavy Bass Drop]\n重低音ドロップ\n{following}\nA new dawn",
    }

    tidy_song_sections(payload)

    assert payload["drop"] == f"[Heavy Bass Drop]\n{following}\nA new dawn"
    assert following in _append_normalized_section([], payload["drop"], "Drop")


def test_combined_bass_and_chaos_cues_do_not_leave_sung_words() -> None:
    payload = {"drop": "[Heavy Bass Drop]\nHeavy Bass Drop (chaos)\nBassline descends"}

    tidy_song_sections(payload)

    assert payload["drop"] == "[Heavy Bass Drop]\n[Chaos]\nBassline descends"
    assert _append_normalized_section([], payload["drop"], "Drop") == (
        "[Drop]\n[Heavy Bass Drop]\n[Chaos]\nBassline descends"
    )
    assert _append_normalized_section(
        [], "[Heavy Bass Drop]\nHeavy Bass Drop (chaos)\nBassline descends", "Drop"
    ) == "[Drop]\n[Heavy Bass Drop]\n[Chaos]\nBassline descends"


@pytest.mark.parametrize(
    "source",
    [
        "then '(chaos)',",
        "then '(chaos)' on its own line as a Suno energy-shift cue, then",
    ],
)
def test_prompt_leakage_around_chaos_is_removed_after_tidy(source: str) -> None:
    payload = {"drop": f"{source}\nBassline descends"}

    tidy_song_sections(payload)

    assert _append_normalized_section([], payload["drop"], "Drop") == (
        "[Drop]\n[Chaos]\nBassline descends"
    )


@pytest.mark.parametrize(
    "source",
    ["(Heavy Bass Drop)", "重低音ドロップ\n[juu teion doroppu] (Heavy Bass Drop)"],
)
def test_quality_repair_brackets_parenthesized_heavy_bass_drop(source: str) -> None:
    song = f"[Intro Verse]\nA signal rises\n[Chorus]\nWe shine\n[Drop]\n{source}\nBassline descends"

    formatted = ensure_suno_quality(song)

    assert "[Drop]\n[Heavy Bass Drop]\nBassline descends" in formatted
    assert formatted.count("[Heavy Bass Drop]") == 1
    assert "(Heavy Bass Drop)" not in formatted


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("(chaos)", "[Chaos]"),
        ("( CHAOS )", "[Chaos]"),
        ("(chaos!)", "[Chaos]"),
        ("（chaos）", "[Chaos]"),
        ("（ CHAOS！ ）", "[Chaos]"),
        ("chaos", "[Chaos]"),
        ("CHAOS!", "[Chaos]"),
        ("[chaos]", "[Chaos]"),
        ("[(chaos)]", "[Chaos]"),
        ("Chaos (chaos)", "[Chaos]"),
        ("Chaos [Chaos]", "[Chaos]"),
        ("Signals surge (chaos)", "Signals surge [Chaos]"),
        ("Let chaos rise", "Let chaos rise"),
        ("(pure chaos)", "(pure chaos)"),
        ("(Oh oh)", "(Oh oh)"),
    ],
)
def test_chaos_stage_cues_are_bracketed_without_rewriting_sung_lyrics(
    source: str, expected: str,
) -> None:
    assert tag_instrument_cues(source) == expected


def test_tidy_brackets_chaos_before_hook_selection() -> None:
    payload = {
        "drop": "[Drop]\n[Heavy Bass Drop]\n(chaos)\nCHAOS\nSignals erupt",
    }

    tidy_song_sections(payload)

    assert payload["drop"] == "[Drop]\n[Heavy Bass Drop]\n[Chaos]\n[Chaos]\nSignals erupt"
    assert [hook.text for hook in select_hook_lines(payload, 0.9, 40)] == ["Signals erupt"]


def test_freeform_and_quality_repairs_keep_cues_out_of_sung_output() -> None:
    song = (
        "[Intro Verse]\nA signal rises\n[Verse 1]\nA new day begins\n"
        "[Chorus]\nWe light the night\n" + DROP_EXAMPLE + "\n(chaos)"
    )

    for formatted in (_normalize_freeform_suno_reply(song), ensure_suno_quality(song)):
        assert formatted.count("[Heavy Bass Drop]") == 1
        assert "重低音ドロップ" not in formatted
        assert "[juu teion doroppu]" not in formatted
        assert "\nHeavy Bass Drop\n" not in formatted
        assert "\n[Chaos]" in formatted
        assert "(chaos)" not in formatted
        assert "Bassline descends, energy ignites" in formatted


@pytest.mark.parametrize(
    ("lyric_language", "generation_language", "translate_mode"),
    [
        ("english", "english", False),
        ("japanese", "japanese", False),
        ("bilingual", "bilingual", False),
        ("bilingual", "english", True),
    ],
)
def test_lyric_prompts_request_bracketed_unsung_stage_cues(
    lyric_language: str, generation_language: str, translate_mode: bool,
) -> None:
    concept = SongConcept(
        song_id="song", title="Signal", theme="light", mood="playful", bpm=142,
        genre_tags=["cyberpop"], narrative_arc="Night becomes dawn", evidence_ids=[],
        generated_at="2026-11-03", lyric_language=lyric_language,
    )
    persona = ReiPersonaGraph(
        schema_version="1", identity={"name": "Rei"}, personality_traits=[],
        musical_expertise={}, production_knowledge={"lyrical_approach": {}},
        communication_style={"tone": "digital"}, knowledge_sources={},
        creative_process={}, constraints={}, comparison_to_sam={},
    )
    domain = ReiDomainKnowledge(
        schema_version="1", music_theory={}, tidal_cycles_syntax={},
        genre_production_techniques={}, bpm_and_mood={}, synth_selection_guidelines={},
        lyrical_structure={}, technical_metaphor_library={}, suno_prompt_templates={},
        production_notes={},
    )

    system, user = build_lyric_prompts(
        concept, persona, domain, None, lyric_language=lyric_language,
        generation_language=generation_language, translate_mode=translate_mode,
        japanese_target_percent=33,
    )

    assert "[Chaos]" in system
    assert "'(chaos)'" not in system
    assert "[Heavy Bass Drop]" in system and "[Heavy Bass Drop]" in user
    assert "never sing or translate" in user.lower()


def test_structured_song_preserves_drop_and_real_lyrics() -> None:
    concept = SongConcept(
        song_id="song", title="Signal", theme="light", mood="playful", bpm=142,
        genre_tags=["cyberpop"], narrative_arc="Night becomes dawn", evidence_ids=[],
        generated_at="2026-11-03", lyric_language="bilingual",
    )
    domain = ReiDomainKnowledge(
        schema_version="1", music_theory={}, tidal_cycles_syntax={},
        genre_production_techniques={}, bpm_and_mood={}, synth_selection_guidelines={},
        lyrical_structure={}, technical_metaphor_library={}, suno_prompt_templates={},
        production_notes={},
    )
    lyrics = Lyrics(
        verse_1="A new day begins", chorus="We light the night",
        verse_2="A signal returns", bridge="The darkness fades", evidence_ids=[],
        drop=DROP_EXAMPLE + "\n(chaos)",
    )

    result = assemble_suno_prompt(concept, lyrics, domain)

    assert result.lyrics.count("[Heavy Bass Drop]") == 1
    assert "[Drop]\n[Heavy Bass Drop]\n" in result.lyrics
    assert "重低音ドロップ" not in result.lyrics
    assert "[juu teion doroppu]" not in result.lyrics
    assert "\nHeavy Bass Drop\n" not in result.lyrics
    assert "Bassline descends, energy ignites" in result.lyrics
    assert "[Chaos]" in result.lyrics
    assert result.metadata["has_drop"] is True


# --- Intro vocalization / echoed label cleanup ------------------------------

from services.rei_toei._song_tidy import tidy_song_sections as _tidy_sections  # noqa: E402
from services.rei_toei._suno_blocks import _append_normalized_section as _append_section  # noqa: E402
from services.rei_toei._suno_cleanup import tidy_vocalization_cues  # noqa: E402

_REPORTED_INTRO = (
    "[Instrumental Build]\n(Ahh ahh ahh)\n[Intro Verse]\n"
    "[Ahh ahh ahh] (Instrumental Build)\nCode flows in the night, agents ignite"
)


@pytest.mark.parametrize("raw", [
    _REPORTED_INTRO,
    "[Instrumental Build]\n(Ahh ahh ahh) (Instrumental Build)\nCode flows in the night, agents ignite",
    "(Ahh ahh ahh)\nAhh ahh ahh (Instrumental Build)\nCode flows in the night, agents ignite",
    "[Ahh ahh ahh]\nInstrumental Build\nCode flows in the night, agents ignite",
])
def test_intro_keeps_single_parenthesized_vocalization(raw: str) -> None:
    block = _append_section([], raw, "Instrumental Build")
    assert block == (
        "[Instrumental Build]\n(Ahh ahh ahh)\n\n"
        "[Intro Verse]\nCode flows in the night, agents ignite"
    )


def test_song_tidy_cleans_intro_field() -> None:
    payload = {"intro": _REPORTED_INTRO}
    _tidy_sections(payload)
    assert "[Ahh ahh ahh]" not in payload["intro"]
    assert "(Instrumental Build)" not in payload["intro"]
    assert payload["intro"].count("(Ahh ahh ahh)") == 1


def test_bracketed_vocalization_in_verse_becomes_parenthesized() -> None:
    assert tidy_vocalization_cues("[Ooh ooh]\nSignals rise") == "(Ooh ooh)\nSignals rise"


def test_instrumental_build_parenthetical_directions_become_bracketed() -> None:
    block = _append_section(
        [],
        "[Instrumental Build]\n(Ahh ahh ahh)\n"
        "(Start with glitchy synth tones)\n[Intro Verse]\nCode flows in the night",
        "Instrumental Build",
    )

    assert block == (
        "[Instrumental Build]\n(Ahh ahh ahh)\n"
        "[Start with glitchy synth tones]\n\n"
        "[Intro Verse]\nCode flows in the night"
    )


def test_non_vocal_brackets_are_untouched() -> None:
    text = "[Heavy Bass Drop]\n[Synth sweep]\nSignals rise"
    assert tidy_vocalization_cues(text) == text
    assert tidy_vocalization_cues(text, intro=True) == text


# --- Bracketed English meanings after Romaji cues ---------------------------

from services.rei_toei._suno_cleanup import unbracket_romaji_glosses  # noqa: E402
from services.rei_toei._suno_fallback import build_fallback_lyrics  # noqa: E402


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "赤いスレッドが闇をほどく。\n[Akai sureddo ga yami o hodoku] [Red threads unravel the dark]\nNext line",
            "赤いスレッドが闇をほどく。\n[akai sureddo ga yami o hodoku]\nRed threads unravel the dark\nNext line",
        ),
        (
            "システムを再起動する。\n[shisutemu o saikidou suru] [Restart the system]\nRestart the system.",
            "システムを再起動する。\n[shisutemu o saikidou suru]\nRestart the system.",
        ),
        (
            "データが流れる\n[Deeta ga nagareru] [Data flows]",
            "データが流れる\n[deeta ga nagareru]\nData flows",
        ),
        (
            "SQLで探査\n[SQL de tansa] [Exploring with SQL]",
            "SQLで探査\n[SQL de tansa]\nExploring with SQL",
        ),
    ],
    ids=["moves-meaning", "skips-duplicate", "short-meaning", "keeps-acronym"],
)
def test_bracketed_english_meaning_becomes_sung(source: str, expected: str) -> None:
    assert unbracket_romaji_glosses(source) == expected


@pytest.mark.parametrize(
    "source",
    [
        "赤いスレッドが闇をほどく。\n[akai sureddo ga yami o hodoku] [Synth sweep]",
        "赤いスレッドが闇をほどく。\n[akai sureddo ga yami o hodoku] [Heavy Bass Drop]",
        "[Ambient drums] [Synth sweep]\nSignals rise",
    ],
)
def test_stage_cues_after_romaji_stay_bracketed(source: str) -> None:
    assert unbracket_romaji_glosses(source) == source


def test_fallback_song_sings_every_english_meaning() -> None:
    concept = SongConcept(
        song_id="s", title="Java Loop", theme="Java", mood="playful", bpm=142,
        genre_tags=["cyberpop"], narrative_arc="arc", evidence_ids=[],
        generated_at="2026-11-04", lyric_language="bilingual",
    )
    lyrics = build_fallback_lyrics(concept, "bilingual")
    blocks = [
        _append_section([], getattr(lyrics, field), label)
        for field, label in [("verse_1", "Verse 1"), ("verse_2", "Verse 2"), ("bridge", "Bridge")]
    ]
    rendered = "\n".join(blocks)

    assert "] [" not in rendered
    for meaning in ("Red threads unravel the dark", "Cross the boundary, rewrite the state", "Restart the system"):
        assert f"\n{meaning}" in rendered
