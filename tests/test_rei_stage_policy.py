"""Domain-driven mandatory sections, instrumental cues, and intro primers."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from services.rei_toei import _loaders
from services.rei_toei._lyric_prompts import build_lyric_prompts
from services.rei_toei._models import Lyrics, ReiDomainKnowledge, SongConcept
from services.rei_toei._song_structure import missing_required_sections, missing_sections_feedback
from services.rei_toei._solo_options import build_solo_style_guidance
from services.rei_toei._stage_policy import StagePolicy, load_stage_policy
from services.rei_toei._suno_blocks import _normalize_freeform_suno_reply
from services.rei_toei._suno_pipeline import assemble_suno_prompt, compose_lyrics
from services.rei_toei._suno_quality import ensure_suno_quality


@pytest.fixture
def domain() -> ReiDomainKnowledge:
    return copy.deepcopy(_loaders.load_rei_domain_knowledge())


@pytest.fixture
def concept() -> SongConcept:
    return SongConcept(
        song_id="policy", title="Candle", theme="a room after a storm", mood="quiet",
        bpm=100, genre_tags=["cyberpop"], narrative_arc="Darkness gives way to warmth",
        evidence_ids=[], generated_at="2026-11-05", lyric_language="english",
    )


def _select(domain: ReiDomainKnowledge, name: str) -> StagePolicy:
    domain.lyrical_structure["stage_cues"]["active_profile"] = name
    return load_stage_policy(domain.lyrical_structure)


def _draft() -> dict[str, str]:
    return {
        "verse_1": "[Verse 1]\nRain taps against the window\nA candle waits",
        "chorus": "[Chorus]\nHOLD THE DOOR FOR MORNING\nWE WILL FIND OUR WAY",
        "verse_2": "[Verse 2]\nThe puddles catch the sunlight\nShe opens every curtain",
        "outro": "[Outro]\nThe house is warm again",
    }


def _compose_profile_draft(domain: ReiDomainKnowledge, concept: SongConcept) -> Lyrics:
    draft = dict(
        _draft(), intro="[Atmospheric Pads]\nThe room waits",
        bridge="The window opens to the sky", drop="The air begins to dance",
        solo="[Distorted Synth Solo]", breakdown="[Ambient Interlude]",
    )
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(draft)
    return compose_lyrics(concept, _loaders.load_rei_persona(), domain, ollama=ollama)


@pytest.mark.parametrize("name", ["cyberpop", "cyberpunk", "acoustic", "rock", "hip_hop", "ambient"])
def test_shipped_profiles_validate(domain: ReiDomainKnowledge, name: str) -> None:
    policy = _select(domain, name)
    assert policy.name == name
    assert any(rule.required and rule.content == "sung" for rule in policy.sections)


def test_explicit_acoustic_profile_does_not_require_electronic_sections(domain: ReiDomainKnowledge) -> None:
    policy = _select(domain, "acoustic")
    assert missing_required_sections(_draft(), policy) == []
    assert policy.intro_primer is None and policy.intro_verse_label is None


def test_cyberpunk_assembly_uses_dark_production_cues(
    domain: ReiDomainKnowledge, concept: SongConcept,
) -> None:
    _select(domain, "cyberpunk")
    lyrics = _compose_profile_draft(domain, concept)
    result = assemble_suno_prompt(concept, lyrics, domain)
    for cue in ("Dark Synth Pulse", "Distorted Bass Drop", "Distorted Synth Solo", "Fade Out"):
        assert result.lyrics.count(f"[{cue}]") == 1
    assert "[Heavy Bass Drop]" not in result.lyrics
    assert result.metadata["stage_cue_profile"] == "cyberpunk"


def test_custom_required_section_changes_gate_and_feedback(domain: ReiDomainKnowledge) -> None:
    settings = domain.lyrical_structure["stage_cues"]["profiles"]["acoustic"]
    settings["sections"]["bridge"]["required"] = True
    settings["sections"]["bridge"]["label"] = "Middle Eight"
    policy = _select(domain, "acoustic")
    assert missing_required_sections(_draft(), policy) == ["bridge"]
    assert "[Middle Eight]" in missing_sections_feedback(["bridge"], policy)


def test_instrumental_and_sung_requirements_are_distinct(domain: ReiDomainKnowledge) -> None:
    policy = _select(domain, "ambient")
    draft = {
        "intro": "[Intro]\n[Atmospheric Pads]", "verse_1": "A breath of daylight",
        "breakdown": "[Interlude]\n[Ambient Interlude]", "outro": "[Outro]\n[Fade Out]",
    }
    assert missing_required_sections(draft, policy) == []
    draft["verse_1"] = "[Verse 1]\n[Atmospheric Pads]"
    assert missing_required_sections(draft, policy) == ["verse_1"]


@pytest.mark.parametrize("name", ["acoustic", "hip_hop", "ambient"])
def test_assembly_never_adds_disabled_drop_or_primer(
    domain: ReiDomainKnowledge, concept: SongConcept, name: str,
) -> None:
    policy = _select(domain, name)
    lyrics = _compose_profile_draft(domain, concept)
    result = assemble_suno_prompt(concept, lyrics, domain)
    assert "[Heavy Bass Drop]" not in result.lyrics
    assert "[Instrumental Build]" not in result.lyrics
    assert "(Ahh ahh ahh)" not in result.lyrics
    assert "[Intro Verse]" not in result.lyrics
    assert result.metadata["stage_cue_profile"] == name
    assert result.metadata["has_drop"] is False
    assert missing_required_sections(vars(lyrics), policy) == []


def test_configured_cues_and_primer_are_inserted_exactly_once(
    domain: ReiDomainKnowledge, concept: SongConcept,
) -> None:
    settings = domain.lyrical_structure["stage_cues"]["profiles"]["cyberpop"]
    settings["intro_primer"] = "(Yeah yeah)"
    settings["intro_verse_label"] = "Opening Verse"
    settings["sections"]["drop"]["label"] = "Dance Break"
    settings["sections"]["drop"]["cues"] = ["Drum Break"]
    policy = load_stage_policy(domain.lyrical_structure)
    lyrics = Lyrics(
        verse_1="The room wakes", chorus="WE OPEN EVERY DOOR",
        verse_2="She lets the daylight in", bridge="The clouds unravel", evidence_ids=[],
        intro="(Ahh ahh ahh)\nThe floorboards shimmer",
        drop="[Dance Break]\n[Drum Break] We step outside\n[Drum Break]",
    )
    result = assemble_suno_prompt(concept, lyrics, domain)
    assert result.lyrics.startswith("[Instrumental Build]\n(Yeah yeah)")
    assert "[Opening Verse]\nThe floorboards shimmer" in result.lyrics
    assert "[Dance Break]\n[Drum Break]\nWe step outside" in result.lyrics
    assert result.lyrics.count("[Drum Break]") == 1
    assert "(Ahh ahh ahh)" not in result.lyrics
    assert "[Heavy Bass Drop]" not in result.lyrics
    assert ensure_suno_quality(result.lyrics, policy) == result.lyrics


def test_configured_cue_is_not_rewritten_as_japanese_pronunciation(
    domain: ReiDomainKnowledge, concept: SongConcept,
) -> None:
    settings = domain.lyrical_structure["stage_cues"]["profiles"]["cyberpop"]
    settings["sections"]["drop"]["cues"] = ["Soft Drum Entrance"]
    concept.lyric_language = "bilingual"
    lyrics = Lyrics(
        verse_1="Morning comes", chorus="The light returns",
        verse_2="A window opens", bridge="The night recedes", evidence_ids=[],
        intro="Light the candle", drop="光の海\n[Soft Drum Entrance]",
    )
    result = assemble_suno_prompt(concept, lyrics, domain)
    assert "[Soft Drum Entrance]\n光の海\n[hikari no umi]" in result.lyrics


def test_custom_header_freeform_normalization_is_idempotent(domain: ReiDomainKnowledge) -> None:
    policy = _select(domain, "hip_hop")
    source = "Title: Candle\n[Verse 1]\nThe room wakes\n[Hook]\nFind the daylight\nStyle Tags: hip hop"
    result = _normalize_freeform_suno_reply(source, policy)
    assert "[Hook]\nFind the daylight" in result
    assert "[Chorus]" not in result
    assert result.startswith("Title: Candle\n") and result.endswith("Style Tags: hip hop")
    assert _normalize_freeform_suno_reply(result, policy) == result


def test_freeform_hook_without_verses_keeps_custom_heading(domain: ReiDomainKnowledge) -> None:
    policy = _select(domain, "hip_hop")
    result = _normalize_freeform_suno_reply("[Hook]\nFind the daylight", policy)
    assert result == "[Hook]\nFind the daylight"


def test_primer_inside_intro_verse_is_not_duplicated() -> None:
    result = ensure_suno_quality(
        "[Intro Verse]\n(Ahh ahh ahh)\nThe room wakes\n[Verse 1]\nWindows open"
    )
    assert result.count("(Ahh ahh ahh)") == 1
    assert ensure_suno_quality(result) == result


def test_explicit_null_policy_is_invalid() -> None:
    with pytest.raises(ValueError, match="stage_cues"):
        load_stage_policy({"stage_cues": None})


def test_solo_palette_uses_selected_heading_and_respects_disabled_solos(domain: ReiDomainKnowledge) -> None:
    settings = domain.lyrical_structure["stage_cues"]["profiles"]["rock"]
    settings["sections"]["solo"]["label"] = "Instrumental Feature"
    _select(domain, "rock")
    guidance = build_solo_style_guidance(domain.lyrical_structure)
    assert "beneath [Instrumental Feature]" in guidance and "beneath [Solo]" not in guidance
    _select(domain, "hip_hop")
    assert build_solo_style_guidance(domain.lyrical_structure) == ""


def test_prompt_tracks_active_profile_not_song_genre(
    domain: ReiDomainKnowledge, concept: SongConcept,
) -> None:
    _select(domain, "acoustic")
    system, user = build_lyric_prompts(
        concept, _loaders.load_rei_persona(), domain, None,
        lyric_language="english", generation_language="english",
        translate_mode=False, japanese_target_percent=0,
    )
    assert "Stage-cue profile: acoustic" in user
    assert "bridge (optional)" in user and "outro (required)" in user
    assert "[Heavy Bass Drop]" not in system + user
    assert '"drop":' not in user
    assert "No mandatory intro vocalization primer." in user


def test_composition_accepts_missing_disabled_and_optional_sections(
    domain: ReiDomainKnowledge, concept: SongConcept,
) -> None:
    _select(domain, "acoustic")
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps(_draft())
    lyrics = compose_lyrics(concept, _loaders.load_rei_persona(), domain, ollama=ollama)
    assert ollama._chat.call_count == 1
    assert lyrics.bridge == "" and not lyrics.drop and not lyrics.solo
    assert "Rain taps" in lyrics.verse_1


def test_retry_feedback_uses_selected_cues_without_framing_fallback(
    domain: ReiDomainKnowledge, concept: SongConcept,
) -> None:
    _select(domain, "ambient")
    ollama = MagicMock()
    ollama._chat.return_value = json.dumps({"verse_1": _draft()["verse_1"]})
    with pytest.raises(RuntimeError, match="Missing required fields"):
        compose_lyrics(concept, _loaders.load_rei_persona(), domain, ollama=ollama)
    assert ollama._chat.call_count == 5
    assert "[Ambient Interlude]" in ollama._chat.call_args_list[1].args[1]


@pytest.mark.parametrize("name", ["acoustic", "rock", "hip_hop", "ambient"])
def test_malformed_model_output_fails_in_every_profile(
    domain: ReiDomainKnowledge, concept: SongConcept, name: str,
) -> None:
    _select(domain, name)
    ollama = MagicMock()
    ollama._chat.return_value = "not valid json"
    with pytest.raises(RuntimeError, match="after 5 attempts"):
        compose_lyrics(concept, _loaders.load_rei_persona(), domain, ollama=ollama)
    assert ollama._chat.call_count == 5


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("label", "[Verse 1]"), ("label", ""), ("label", "Chorus"),
        ("required", "yes"), ("content", "maybe"), ("content", []),
        ("cues", "Guitar Solo"), ("cues", ["[Guitar Solo]"]),
        ("cues", ["Echo", "echo"]), ("cues", ["Chorus"]),
    ],
)
def test_invalid_section_settings_fail_fast(
    domain: ReiDomainKnowledge, key: str, value: Any,
) -> None:
    domain.lyrical_structure["stage_cues"]["profiles"]["cyberpop"]["sections"]["verse_1"][key] = value
    with pytest.raises(ValueError):
        load_stage_policy(domain.lyrical_structure)


@pytest.mark.parametrize(
    "change",
    [
        {"active_profile": "missing"}, {"profiles": []}, {"profiles": {}},
        {"profiles": {"broken": {"sections": {"verse_3": {}}}}},
        {"profiles": {"broken": {"sections": {}}}},
    ],
)
def test_invalid_policy_settings_fail_fast(domain: ReiDomainKnowledge, change: dict[str, Any]) -> None:
    domain.lyrical_structure["stage_cues"].update(change)
    with pytest.raises(ValueError):
        load_stage_policy(domain.lyrical_structure)


def test_invalid_intro_primer_is_rejected_by_loader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = json.loads(Path("data/avatar/rei_toei_domain_knowledge.json").read_text())
    data["lyrical_structure"]["stage_cues"]["profiles"]["cyberpop"]["intro_primer"] = "[Ahh]"
    path = tmp_path / "knowledge.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(_loaders, "ReiToeiConfig", lambda: SimpleNamespace(domain_knowledge_path=path))
    with pytest.raises(ValueError, match="intro_primer"):
        _loaders.load_rei_domain_knowledge()
