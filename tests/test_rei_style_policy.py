"""Selected styles govern concept generation, draft checks and final Suno output."""

import copy
import json
from unittest.mock import MagicMock
from typing import Any

import pytest

from services.rei_toei._loaders import load_rei_domain_knowledge, load_rei_persona
from services.rei_toei._lyric_checks import chorus_line_deficit
from services.rei_toei._lyric_prompts import build_lyric_prompts
from services.rei_toei._models import Lyrics, ReiDomainKnowledge, SongConcept, Theme
from services.rei_toei._song_tidy import tidy_song_sections
from services.rei_toei._stage_policy import load_stage_policy
from services.rei_toei._style_policy import parse_style_policy
from services.rei_toei._suno_blocks import _normalize_freeform_suno_reply
from services.rei_toei._suno_concept import generate_song_concept
from services.rei_toei._suno_pipeline import assemble_suno_prompt, compose_lyrics
from services.rei_toei._suno_quality import ensure_suno_quality, normalize_profile_cues

PROFILES = [
    "cyberpop", "cyberpunk", "acoustic", "rock", "psytrance", "progressive_psytrance",
    "jungle_dnb", "psychedelic_rock", "progressive_rock", "hip_hop", "ambient",
]


@pytest.fixture
def domain() -> ReiDomainKnowledge:
    result = copy.deepcopy(load_rei_domain_knowledge())
    result.lyrical_structure["stage_cues"]["active_profile"] = "psychedelic_rock"
    return result


@pytest.fixture
def concept() -> SongConcept:
    return SongConcept(
        song_id="style", title="Red Wax Traces", theme="a mysterious room", mood="dreamlike",
        bpm=140, genre_tags=["industrial techno", "cyberpop", "glitch synthesis"],
        narrative_arc="A secret is revealed", evidence_ids=[], generated_at="2026-11-07",
        lyric_language="english",
    )


def _draft() -> dict[str, str]:
    return {
        "intro": "[Psychedelic Guitar Intro ;]",
        "verse_1": "A red mark stains the window\nYour shadow waits behind the door",
        "chorus": "Follow the fading light\nTell me what the silence means",
        "verse_2": "The garden opens after rain\nWe carry every secret home",
        "bridge": "I leave the broken key behind\nThe room becomes a memory",
        "solo": "[Epic Guitar Solo]",
        "breakdown": "[Psychedelic Breakdown ;]",
        "outro": "The morning finds us on the shore",
    }


def _lyrics(draft: dict[str, str]) -> Lyrics:
    return Lyrics(evidence_ids=[], **draft)


@pytest.mark.parametrize("name", PROFILES)
def test_every_shipped_style_controls_output(
    domain: ReiDomainKnowledge, concept: SongConcept, name: str,
) -> None:
    domain.lyrical_structure["stage_cues"]["active_profile"] = name
    policy = load_stage_policy(domain.lyrical_structure)
    prompt = assemble_suno_prompt(concept, _lyrics(_draft()), domain)

    assert prompt.metadata["template_used"] == policy.style.template
    assert prompt.metadata["stage_cue_profile"] == name
    assert prompt.metadata["genre_tags"] == list(policy.style.genre_tags)
    assert concept.genre_tags == list(policy.style.genre_tags)
    if name != "cyberpop":
        assert "cyberpop" not in prompt.suno_prompt.lower()
        if name != "cyberpunk":
            assert "warehouse kick" not in prompt.suno_prompt.lower()
        assert "vocaloid" not in prompt.metadata["vocal_delivery"]
        assert "bitcrushed synths" not in prompt.metadata["suno_description_prompt"]


@pytest.mark.parametrize("name", PROFILES)
def test_concept_overrides_conflicting_environment_and_model_tags(
    domain: ReiDomainKnowledge, monkeypatch: pytest.MonkeyPatch, name: str,
) -> None:
    domain.lyrical_structure["stage_cues"]["active_profile"] = name
    style = load_stage_policy(domain.lyrical_structure).style
    monkeypatch.setenv("REI_TOEI_DEFAULT_GENRE", "industrial techno, cyberpop")
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps({
        "title": "Red Wax Traces", "mood": "dreamlike", "bpm": 300,
        "genre_tags": ["cyberpop"], "narrative_arc": "A secret unfolds.",
    })
    theme = Theme(id="room", name="a mysterious room", technical_concepts=["mystery"],
                  evidence_ids=[], frequency=1, recency_score=1)

    generated = generate_song_concept(theme, load_rei_persona(), domain, ollama=ollama)

    assert generated.genre_tags == list(style.genre_tags)
    assert style.bpm_range is not None
    assert generated.bpm == style.bpm_range[1]
    system, user = ollama._chat.call_args.args[:2]
    assert style.arrangement in system
    assert ", ".join(style.genre_tags) in user
    if name != "cyberpop":
        assert "cyberpop industrial techno" not in user
        assert "Think cyberpop" not in user


def test_dense_rock_lyrics_can_exceed_initial_range_without_electronic_delivery(
    domain: ReiDomainKnowledge, concept: SongConcept,
) -> None:
    draft = _draft()
    long_line = "Every single syllable is carried through this enormous overflowing story of the distant horizon"
    for field in ("verse_1", "verse_2", "chorus", "bridge", "outro"):
        draft[field] = long_line
    result = assemble_suno_prompt(concept, _lyrics(draft), domain)

    assert result.metadata["bpm"] > 140
    assert result.metadata["concept_bpm"] == 140
    assert result.metadata["vocal_delivery"] == "flowing expressive rock phrasing"
    assert "vocaloid" not in result.suno_prompt
    assert "club propulsion" not in result.suno_prompt
    assert "Every single syllable" in result.lyrics


def test_required_cues_and_aliases_are_canonical_and_idempotent(
    domain: ReiDomainKnowledge, concept: SongConcept,
) -> None:
    draft = _draft()
    draft["intro"] += "\n[Psychedelic Guitar Intro]\n[Organ Swell]"
    draft["solo"] += "\n[Psychedelic Guitar Solo]"
    draft["breakdown"] += "\n[Psychedelic Breakdown]"
    policy = load_stage_policy(domain.lyrical_structure)
    tidy_song_sections(draft, policy)
    result = assemble_suno_prompt(concept, _lyrics(draft), domain).lyrics

    for cue in ("Psychedelic Guitar Intro", "Psychedelic Guitar Solo", "Psychedelic Breakdown"):
        assert result.count(f"[{cue}]") == 1
    assert "[Epic Guitar Solo]" not in result
    assert "[Organ Swell]" in result
    assert " ;]" not in result
    assert ensure_suno_quality(result, policy) == result


@pytest.mark.parametrize("solo", ["[Epic Guitar Solo]", "(Epic Guitar Solo)"])
def test_freeform_uses_same_cue_cleanup_and_keeps_real_lyrics(
    domain: ReiDomainKnowledge, solo: str,
) -> None:
    policy = load_stage_policy(domain.lyrical_structure)
    raw = f"[Verse 1]\nThe garden opens\n[Solo]\n{solo}\n[Psychedelic Guitar Solo ;]"
    formatted = _normalize_freeform_suno_reply(raw, policy)
    assert formatted.count("[Psychedelic Guitar Solo]") == 1
    assert "Epic Guitar Solo" not in formatted
    assert "The garden opens" in formatted
    assert _normalize_freeform_suno_reply(formatted, policy) == formatted


def test_cue_cleanup_preserves_unknown_directions_and_pronunciation(domain: ReiDomainKnowledge) -> None:
    policy = load_stage_policy(domain.lyrical_structure)
    text = "[hoshi no hikari]\n[Hammond Organ]\n[Psychedelic Guitar Intro ;]"
    result = normalize_profile_cues(text, "intro", policy)
    assert result == "[hoshi no hikari]\n[Hammond Organ]\n[Psychedelic Guitar Intro]"


def test_style_quality_drives_prompt_retry_and_preserves_english_casing(
    domain: ReiDomainKnowledge, concept: SongConcept,
) -> None:
    profile = domain.lyrical_structure["stage_cues"]["profiles"]["psychedelic_rock"]
    profile["style"]["quality"]["min_chorus_lines"] = 3
    first = _draft()
    second = {**first, "chorus": first["chorus"] + "\nWe follow what the dawn reveals"}
    ollama = MagicMock()
    ollama._chat.side_effect = [json.dumps(first), json.dumps(second)]
    lyrics = compose_lyrics(concept, load_rei_persona(), domain, ollama=ollama)

    assert ollama._chat.call_count == 2
    assert "at least 3" in ollama._chat.call_args_list[1].args[1]
    assert "Follow the fading light" in assemble_suno_prompt(concept, lyrics, domain).lyrics
    assert "THE CHORUS MUST BE ENTIRELY UPPERCASE" not in ollama._chat.call_args_list[0].args[0]
    assert "Epic Guitar Solo" not in ollama._chat.call_args_list[0].args[1]


def test_profile_can_allow_bridge_reprises_without_tidy_removing_them(
    domain: ReiDomainKnowledge, concept: SongConcept,
) -> None:
    profile = domain.lyrical_structure["stage_cues"]["profiles"]["psychedelic_rock"]
    profile["style"]["quality"].update(max_borrowed_lines=2, remove_bridge_echoes=False)
    draft = _draft()
    draft["bridge"] = draft["chorus"] + "\nThe garden door swings open"
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(draft)

    lyrics = compose_lyrics(concept, load_rei_persona(), domain, ollama=ollama)

    assert ollama._chat.call_count == 1
    assert draft["chorus"] in lyrics.bridge
    profile["style"]["quality"]["remove_bridge_echoes"] = True
    tidy_song_sections(draft, load_stage_policy(domain.lyrical_structure))
    assert "Follow the fading light" not in draft["bridge"]
    assert "The garden door swings open" in draft["bridge"]


def test_bridge_warning_uses_style_target(
    domain: ReiDomainKnowledge, concept: SongConcept, caplog: pytest.LogCaptureFixture,
) -> None:
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(_draft())
    compose_lyrics(concept, load_rei_persona(), domain, ollama=ollama)
    assert "Bridge has fewer" not in caplog.text


@pytest.mark.parametrize("minimum", [1, 2, 4])
def test_chorus_gate_uses_configured_threshold(domain: ReiDomainKnowledge, minimum: int) -> None:
    profile = domain.lyrical_structure["stage_cues"]["profiles"]["psychedelic_rock"]
    profile["style"]["quality"]["min_chorus_lines"] = minimum
    policy = load_stage_policy(domain.lyrical_structure)
    assert chorus_line_deficit("One sung line", policy) == (None if minimum == 1 else 1)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("genre_tags", []), ("genre_tags", "rock"), ("template", ""),
        ("bpm", {"min": 140, "max": 80, "default": 110}),
        ("bpm", {"min": True, "max": 140, "default": 110}),
        ("quality", {"min_chorus_lines": 0}), ("quality", {"min_bridge_lines": -1}),
        ("quality", {"verse_repeat_threshold": float("nan")}),
        ("quality", {"uppercase_chorus": "false"}),
        ("density", {"base_bpm": 200, "max_bpm": 100}),
        ("density", {"unknown": 123}), ("cue_aliases", []),
        ("cue_aliases", {"Epic Guitar Solo": "Unknown Cue"}),
    ],
)
def test_invalid_style_settings_fail_fast(domain: ReiDomainKnowledge, key: str, value: Any) -> None:
    raw = domain.lyrical_structure["stage_cues"]["profiles"]["psychedelic_rock"]["style"]
    raw[key] = value
    with pytest.raises(ValueError, match="style"):
        load_stage_policy(domain.lyrical_structure)


def test_missing_template_fails_before_model_request(domain: ReiDomainKnowledge) -> None:
    domain.suno_prompt_templates.pop("psychedelic_rock_template")
    ollama = MagicMock()
    theme = Theme(id="t", name="room", technical_concepts=[], evidence_ids=[],
                  frequency=1, recency_score=1)
    with pytest.raises(ValueError, match="template"):
        generate_song_concept(theme, load_rei_persona(), domain, ollama=ollama)
    ollama._chat.assert_not_called()


@pytest.mark.parametrize("template", ["", "{unknown}", "{"])
def test_invalid_template_fails_before_model_request(
    domain: ReiDomainKnowledge, template: str,
) -> None:
    domain.suno_prompt_templates["psychedelic_rock_template"] = template
    ollama = MagicMock()
    theme = Theme(id="t", name="room", technical_concepts=[], evidence_ids=[],
                  frequency=1, recency_score=1)
    with pytest.raises(ValueError, match="template"):
        generate_song_concept(theme, load_rei_persona(), domain, ollama=ollama)
    ollama._chat.assert_not_called()


def test_legacy_profile_keeps_independent_genre_and_default_quality(
    domain: ReiDomainKnowledge, concept: SongConcept,
) -> None:
    raw = domain.lyrical_structure["stage_cues"]["profiles"]["psychedelic_rock"]
    raw.pop("style")
    policy = load_stage_policy(domain.lyrical_structure)
    original_tags = list(concept.genre_tags)
    result = assemble_suno_prompt(concept, _lyrics(_draft()), domain)
    assert result.metadata["template_used"] == "cyberpunk_electro_template"
    assert concept.genre_tags == original_tags
    assert policy.style.min_bridge_lines == 4
    assert parse_style_policy(None, "style").genre_tags == ()


@pytest.mark.parametrize("profile", ["cyberpop", "psychedelic_rock"])
def test_lyric_prompt_requests_newline_separated_lines_and_full_chorus(
    domain: ReiDomainKnowledge, concept: SongConcept, profile: str,
) -> None:
    domain.lyrical_structure["stage_cues"]["active_profile"] = profile
    system_prompt, user_prompt = build_lyric_prompts(
        concept, load_rei_persona(), domain, None,
        lyric_language="english", generation_language="english",
        translate_mode=False, japanese_target_percent=0,
    )
    assert "] ; sung lines" not in user_prompt
    assert "Start with [Chorus]. Write sung lines, one per line." in user_prompt
    assert "header, then" not in user_prompt
    assert "Never join lines with ';'" in user_prompt
    assert "4-8 sung lines built on" in user_prompt
    assert "At least 2 lines must be distinct" in user_prompt
    assert "never repeat it back-to-back" in user_prompt
    assert "Character Cap" not in user_prompt
    assert "Vary line lengths naturally" in system_prompt
    assert "Let verses and the bridge carry complete thoughts in fuller lines" in system_prompt
    assert "within about two syllables" not in system_prompt
    assert "verses and the bridge may carry fuller thoughts" in user_prompt.lower()


def test_copied_character_limit_is_schema_leakage() -> None:
    from services.rei_toei._suno_json import _has_prompt_schema_leakage

    assert _has_prompt_schema_leakage({"chorus": "[Chorus]\nRISE UP\nMax 400 characters."})
    assert _has_prompt_schema_leakage({
        "chorus": "[Chorus] header, then sung lines, one per line. Write every Chorus lyric in uppercase.\nRISE UP"
    })
    assert not _has_prompt_schema_leakage({"chorus": "[Chorus]\nRISE UP\nWE MAX OUT THE NIGHT"})
    assert _has_prompt_schema_leakage({"intro": "[Instrumental Build]\nheader\n(Ahh ahh ahh)"})
    assert _has_prompt_schema_leakage({"solo": "[Solo]\n[header]\n[Modulated Bass Solo]"})
    assert _has_prompt_schema_leakage({"intro": "[Instrumental Build] header"})
    assert not _has_prompt_schema_leakage({"verse_1": "Read the header of my heart"})


@pytest.mark.parametrize(
    ("chorus", "deficit"),
    [
        ("[Chorus]\nDATA CONVERGENCE\nDATA CONVERGENCE", 1),
        ("[Chorus]\nDATA CONVERGENCE\ndata convergence!", 1),
        ("[Chorus]\nDATA CONVERGENCE\nWE BECOME THE LIGHT\nDATA CONVERGENCE", None),
    ],
)
def test_chorus_gate_counts_distinct_lines(domain: ReiDomainKnowledge, chorus: str, deficit: int | None) -> None:
    domain.lyrical_structure["stage_cues"]["active_profile"] = "cyberpop"
    assert chorus_line_deficit(chorus, load_stage_policy(domain.lyrical_structure)) == deficit
