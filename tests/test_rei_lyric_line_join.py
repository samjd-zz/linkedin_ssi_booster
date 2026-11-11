"""Short comma-separated lyric fragments are joined before translation."""

import json
from unittest.mock import MagicMock

import pytest

from services.rei_toei._loaders import load_rei_domain_knowledge, load_rei_persona
from services.rei_toei._models import SongConcept
from services.rei_toei._song_tidy import join_short_comma_lines
from services.rei_toei._stage_policy import load_stage_policy
from services.rei_toei._suno_json import _normalize_lyric_payload, _parse_llm_json_payload
from services.rei_toei._suno_pipeline import assemble_suno_prompt, compose_lyrics
from services.rei_toei._suno_sections import _normalize_suno_section


@pytest.mark.parametrize(
    ("source", "expected", "count"),
    [
        ("Signals intertwine,\nPatterns emerge.", "Signals intertwine, Patterns emerge.", 1),
        ("Glitch pulses,\nsilence breaks forth.", "Glitch pulses, silence breaks forth.", 1),
        ("CHAINS BREAK,\nNEW PATHS FORM!", "CHAINS BREAK, NEW PATHS FORM!", 1),
        ("Signals intertwine, Patterns emerge.", "Signals intertwine, Patterns emerge.", 0),
        ("Signals intertwine,\n\nPatterns emerge.", "Signals intertwine,\n\nPatterns emerge.", 0),
        ("Signals intertwine,\n[Silence]\nPatterns emerge.", "Signals intertwine,\n[Silence]\nPatterns emerge.", 0),
        ("Signals intertwine,\n(Ahh ahh)\nPatterns emerge.", "Signals intertwine,\n(Ahh ahh)\nPatterns emerge.", 0),
        ("These five words make this long,\nPatterns emerge.", "These five words make this long,\nPatterns emerge.", 0),
        ("Signals intertwine,\nThese five words make this long.", "Signals intertwine,\nThese five words make this long.", 0),
        ("Signals intertwine,\nSignals intertwine!", "Signals intertwine,\nSignals intertwine!", 0),
        ("信号が流れ、\n夜明けが来る", "信号が流れ、\n夜明けが来る", 0),
        ("Signals intertwine,\n夜明けが来る", "Signals intertwine,\n夜明けが来る", 0),
        ("Signals intertwine,\nPatterns emerge,\nEchoes return.", "Signals intertwine,\nPatterns emerge,\nEchoes return.", 0),
        ("Signals intertwine.\nPatterns emerge.", "Signals intertwine.\nPatterns emerge.", 0),
    ],
)
def test_short_line_join_preserves_boundaries(source: str, expected: str, count: int) -> None:
    payload = {"verse_1": source}
    policy = load_stage_policy()
    assert join_short_comma_lines(payload, policy) == count
    assert payload["verse_1"] == expected
    assert join_short_comma_lines(payload, policy) == 0
    assert payload["verse_1"] == expected


def test_instrumental_fields_are_not_joined() -> None:
    payload = {"solo": "[Solo]\nDrums echo,\npulse intensifies."}
    assert join_short_comma_lines(payload, load_stage_policy()) == 0
    assert payload["solo"] == "[Solo]\nDrums echo,\npulse intensifies."


def test_parser_and_assembly_do_not_split_comma_inside_a_line() -> None:
    payload = _normalize_lyric_payload(_parse_llm_json_payload(
        json.dumps({"verse_1": "Signals intertwine, Patterns emerge."})
    ))
    assert join_short_comma_lines(payload, load_stage_policy()) == 0
    assert payload["verse_1"] == "Signals intertwine, Patterns emerge."
    assert _normalize_suno_section(payload["verse_1"], "Verse 1") == (
        "[Verse 1]\nSignals intertwine, Patterns emerge."
    )


def test_composition_translates_joined_line_as_one_unit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REI_BILINGUAL_STRATEGY", "translate")
    monkeypatch.setenv("REI_JAPANESE_LYRIC_PROBABILITY", "0.15")
    concept = SongConcept(
        song_id="join", title="Signals", theme="networks", mood="hopeful", bpm=142,
        genre_tags=["cyberpop"], narrative_arc="connections form", evidence_ids=[],
        generated_at="2026-11-10", lyric_language="bilingual",
    )
    draft = {
        "intro": "[Instrumental Build]\n(Ahh ahh ahh)\nThe city starts to glow",
        "verse_1": "[Verse 1]\nSignals intertwine,\nPatterns emerge.\nThe city wakes anew",
        "pre_chorus": "[Pre-Chorus]\nThe gates begin to open",
        "chorus": "[Chorus]\nWE FIND THE LIGHT\nTHE FUTURE CALLS",
        "verse_2": "[Verse 2]\nNew streets await our footsteps",
        "bridge": "[Bridge]\nA bridge connects the night",
        "drop": "[Drop]\n[Heavy Bass Drop]\nOur dreams begin to rise",
        "solo": "[Solo]\n[Synth Solo]",
        "breakdown": "[Breakdown]\nThe quiet holds us close",
        "outro": "[Outro]\nWe step into the dawn",
    }
    ollama = MagicMock()
    ollama._chat.side_effect = [
        json.dumps(draft),
        json.dumps({"translations": ["光を見つける", "信号が絡まり模様が現れる"]}, ensure_ascii=False),
    ]
    domain = load_rei_domain_knowledge()
    lyrics = compose_lyrics(concept, load_rei_persona(), domain, ollama=ollama)
    translation_request = ollama._chat.call_args_list[1].args[1]
    assert "Signals intertwine, Patterns emerge." in translation_request
    assert "Signals intertwine,\nPatterns emerge." not in lyrics.verse_1
    assert "信号が絡まり模様が現れる\nSignals intertwine, Patterns emerge." in lyrics.verse_1
    formatted = assemble_suno_prompt(concept, lyrics, domain).lyrics
    assert "Signals intertwine, Patterns emerge." in formatted
