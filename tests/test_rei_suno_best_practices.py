"""Suno best-practice knowledge is loaded and reaches Rei's lyric prompts."""

import pytest

from services.rei_toei._loaders import load_rei_domain_knowledge
from services.rei_toei._lyric_prompts import (
    MAX_SUNO_PRACTICE_RULES,
    build_lyric_prompts,
    build_suno_practice_guidance,
)
from services.rei_toei._models import ReiDomainKnowledge, ReiPersonaGraph, SongConcept

RULES = [
    "Keep bracketed cues short, so Suno does not sing them.",
    "Write Japanese in kana and kanji; Romaji goes only in a bracketed reading cue.",
]


def _domain(practices: dict | None = None) -> ReiDomainKnowledge:
    return ReiDomainKnowledge(
        schema_version="1", music_theory={}, tidal_cycles_syntax={},
        genre_production_techniques={}, bpm_and_mood={}, synth_selection_guidelines={},
        lyrical_structure={}, technical_metaphor_library={}, suno_prompt_templates={},
        production_notes={}, suno_best_practices=practices or {},
    )


def _prompts(domain: ReiDomainKnowledge, lyric_language: str, generation_language: str) -> str:
    concept = SongConcept(
        song_id="song", title="Signal", theme="light", mood="playful", bpm=142,
        genre_tags=["cyberpop"], narrative_arc="Night becomes dawn", evidence_ids=[],
        generated_at="2026-11-04", lyric_language=lyric_language,
    )
    persona = ReiPersonaGraph(
        schema_version="1", identity={"name": "Rei"}, personality_traits=[],
        musical_expertise={}, production_knowledge={"lyrical_approach": {}},
        communication_style={"tone": "digital"}, knowledge_sources={},
        creative_process={}, constraints={}, comparison_to_sam={},
    )
    _, user = build_lyric_prompts(
        concept, persona, domain, None, lyric_language=lyric_language,
        generation_language=generation_language,
        translate_mode=generation_language != lyric_language,
        japanese_target_percent=33,
    )
    return user


def test_domain_knowledge_file_has_sourced_suno_practices() -> None:
    practices = load_rei_domain_knowledge().suno_best_practices

    assert practices["target_model"] == "V6_MINI"
    assert practices["sunoapi_org_v6_mini_limits"]["lyrics_characters_max"] == 5000
    assert practices["sunoapi_org_v6_mini_limits"]["style_characters_max"] == 1000
    assert practices["prompt_rules"]
    assert all(url.startswith("https://") for url in practices["sources"].values())
    assert practices["multilingual"]["official_v6_mini_guidance"] == []


def test_prompt_rules_do_not_invite_parenthetical_word_echoes() -> None:
    rules = " ".join(load_rei_domain_knowledge().suno_best_practices["prompt_rules"]).lower()

    assert "ad-lib" not in rules
    assert "never add repeated-word echoes" in rules


def test_guidance_lists_rules_and_is_empty_without_them() -> None:
    guidance = build_suno_practice_guidance(_domain({"prompt_rules": RULES}))

    assert guidance.startswith("Suno v6-mini lyric-formatting practices:")
    assert all(f"- {rule}" in guidance for rule in RULES)
    assert build_suno_practice_guidance(_domain()) == ""
    assert build_suno_practice_guidance(_domain({"prompt_rules": ["", 3]})) == ""


def test_guidance_caps_rule_count() -> None:
    rules = [f"Rule {index}." for index in range(MAX_SUNO_PRACTICE_RULES + 3)]

    guidance = build_suno_practice_guidance(_domain({"prompt_rules": rules}))

    assert guidance.count("\n- ") == MAX_SUNO_PRACTICE_RULES


@pytest.mark.parametrize(
    ("lyric_language", "generation_language", "has_japanese_rule"),
    [
        ("bilingual", "bilingual", True),
        ("japanese", "japanese", True),
        ("bilingual", "english", False),
        ("english", "english", False),
    ],
    ids=["bilingual-generate", "japanese", "bilingual-translate", "english"],
)
def test_lyric_prompt_includes_language_appropriate_rules(
    lyric_language: str, generation_language: str, has_japanese_rule: bool,
) -> None:
    user = _prompts(_domain({"prompt_rules": RULES}), lyric_language, generation_language)

    assert "Suno v6-mini lyric-formatting practices:" in user
    assert RULES[0] in user
    assert (RULES[1] in user) is has_japanese_rule
