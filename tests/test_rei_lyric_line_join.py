"""Model lyric line breaks survive composition, translation, and assembly."""

import json
from unittest.mock import MagicMock

import pytest

from services.rei_toei._loaders import load_rei_domain_knowledge, load_rei_persona
from services.rei_toei._models import SongConcept
from services.rei_toei._suno_pipeline import assemble_suno_prompt, compose_lyrics


def _concept(language: str = "english") -> SongConcept:
    return SongConcept(
        song_id="line-breaks", title="Signals", theme="networks", mood="hopeful",
        bpm=142, genre_tags=["cyberpop"], narrative_arc="connections form",
        evidence_ids=[], generated_at="2026-11-14", lyric_language=language,
    )


def _draft(verse: str) -> dict[str, str]:
    return {
        "intro": "[Instrumental Build]\n(Ahh ahh ahh)\nThe city starts to glow",
        "verse_1": f"[Verse 1]\n{verse}",
        "pre_chorus": "[Pre-Chorus]\nThe gates begin to open",
        "chorus": "[Chorus]\nWE FIND THE LIGHT\nTHE FUTURE CALLS",
        "verse_2": "[Verse 2]\nNew streets await our footsteps",
        "bridge": "[Bridge]\nA bridge connects the night",
        "drop": "[Drop]\n[Heavy Bass Drop]\nOur dreams begin to rise",
        "solo": "[Solo]\n[Synth Solo]",
        "breakdown": "[Breakdown]\nThe quiet holds us close",
        "outro": "[Outro]\nWe step into the dawn",
    }


@pytest.mark.parametrize(
    "source",
    [
        "Signals intertwine,\nPatterns emerge.",
        "CHAINS BREAK,\nNEW PATHS FORM!",
        "Together we listen,\nHarmony renews.",
        "Morning lightning struck,\nRadio's voice died out.",
        "Latency ticks, buffers fill,\nPatterns shift, circuits thrill.",
        "Fixing frayed wires,\nBridging broken ties.",
        "Signals intertwine, Patterns emerge.",
        "Signals intertwine,\n\nPatterns emerge.",
    ],
)
def test_composition_and_assembly_preserve_model_line_breaks(source: str) -> None:
    concept = _concept()
    domain = load_rei_domain_knowledge()
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(_draft(source))

    lyrics = compose_lyrics(concept, load_rei_persona(), domain, ollama=ollama)
    formatted = assemble_suno_prompt(concept, lyrics, domain).lyrics

    assert lyrics.verse_1 == f"[Verse 1]\n{source}"
    assert f"[Verse 1]\n{source}" in formatted
    assert ollama._chat.call_count == 1


def test_composition_keeps_instrumental_direction_lines_separate() -> None:
    draft = _draft("The city wakes anew")
    draft["solo"] = "[Solo]\nDrums echo,\npulse intensifies."
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(draft)
    concept = _concept()
    domain = load_rei_domain_knowledge()

    lyrics = compose_lyrics(concept, load_rei_persona(), domain, ollama=ollama)
    formatted = assemble_suno_prompt(concept, lyrics, domain).lyrics

    assert "[Drums echo,]\n[pulse intensifies.]" in formatted


def test_bilingual_translation_receives_separate_model_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REI_BILINGUAL_STRATEGY", "translate")
    monkeypatch.setenv("REI_JAPANESE_LYRIC_PROBABILITY", "1")
    monkeypatch.setenv("REI_BILINGUAL_MAX_HOOK_LINES", "2")
    draft = _draft("Signals intertwine,\nPatterns emerge.\nThe city wakes anew")
    ollama = MagicMock()
    ollama._chat.side_effect = [
        json.dumps(draft),
        json.dumps({"1": "光を見つける", "2": "信号が絡まる"}, ensure_ascii=False),
    ]
    concept = _concept("bilingual")
    domain = load_rei_domain_knowledge()

    lyrics = compose_lyrics(concept, load_rei_persona(), domain, ollama=ollama)
    translation_request = ollama._chat.call_args_list[1].args[1]
    formatted = assemble_suno_prompt(concept, lyrics, domain).lyrics

    assert "2. Signals intertwine," in translation_request
    assert "Signals intertwine, Patterns emerge." not in translation_request
    assert "信号が絡まる\nSignals intertwine,\nPatterns emerge." in lyrics.verse_1
    assert "Signals intertwine,\nPatterns emerge." in formatted
    assert ollama._chat.call_count == 2
