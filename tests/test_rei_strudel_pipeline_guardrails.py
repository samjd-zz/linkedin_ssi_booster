import asyncio

import pytest

from services.rei_toei._models import (
    ReiDomainKnowledge,
    ReiPersonaGraph,
    StrudelPattern,
    StrudelPatternTemplate,
    Theme,
)
from services.rei_toei._strudel_pipeline import (
    execute_strudel_pattern,
    generate_strudel_code,
    validate_strudel_syntax,
)


def _sample_theme() -> Theme:
    return Theme(
        id="theme_1",
        name="Async Systems",
        technical_concepts=["async", "queues", "events"],
        evidence_ids=["ev1"],
        frequency=1,
        recency_score=1.0,
        suggested_bpm=128,
        suggested_mood="driving",
    )


def _sample_template() -> StrudelPatternTemplate:
    return StrudelPatternTemplate(
        template_id="tmpl_1",
        name="Pulse",
        description="Simple pulse pattern",
        suitable_for_concepts=["async", "events"],
        code_template="s('bd sd').fast(2)",
        parameters={"speed": 2},
        example="s('bd sd').fast(2)",
        bpm_range=[120, 140],
        intensity="medium",
        synth_types=["drum"],
    )


def _sample_persona() -> ReiPersonaGraph:
    return ReiPersonaGraph(
        schema_version="1.0",
        identity={"name": "Rei"},
        personality_traits=["focused"],
        musical_expertise={"production_techniques": ["compression"]},
        production_knowledge={"production_techniques": ["sidechain"]},
        communication_style={},
        knowledge_sources={},
        creative_process={},
        constraints={},
        comparison_to_sam={},
    )


def _sample_domain() -> ReiDomainKnowledge:
    return ReiDomainKnowledge(
        schema_version="1.0",
        music_theory={},
        tidal_cycles_syntax={
            "core_functions": ["s", "stack", "note"],
            "transformations": ["fast", "slow", "every"],
        },
        genre_production_techniques={},
        bpm_and_mood={},
        synth_selection_guidelines={},
        lyrical_structure={},
        technical_metaphor_library={},
        suno_prompt_templates={},
        production_notes={},
    )


def test_validate_strudel_syntax_rejects_known_runtime_invalid_construct() -> None:
    result = validate_strudel_syntax('note("c2 e2").wrap("128")')
    assert result.valid is False
    assert any("Runtime-invalid construct" in err for err in result.errors)
    assert 1 in result.line_numbers


def test_generate_strudel_code_replaces_runtime_invalid_output_with_safe_fallback() -> None:
    class _FakeOllama:
        def _chat(self, system_prompt: str, user_prompt: str, max_tokens: int = 512) -> str:
            return 'note("c2 e2").wrap("128")'

    pattern = generate_strudel_code(
        theme=_sample_theme(),
        template=_sample_template(),
        persona=_sample_persona(),
        domain_knowledge=_sample_domain(),
        ollama=_FakeOllama(),
    )

    assert pattern.strudel_code == "sound('bd*2,hh*3').gain(1).fast(1)"


@pytest.mark.asyncio
async def test_execute_strudel_pattern_uses_safe_fallback_for_runtime_invalid_construct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pattern = StrudelPattern(
        pattern_id="p1",
        title="invalid",
        theme="demo",
        strudel_code='note("c2 e2").wrap("128")',
        bpm=128,
        duration_bars=8,
        synths=["drum"],
        evidence_ids=["ev1"],
        generated_at="now",
    )

    seen_codes: list[str] = []

    def _fake_send_to_strudel_mcp(code: str) -> bool:
        seen_codes.append(code)
        return True

    monkeypatch.setenv("STRUDEL_WS_URL", "off")
    monkeypatch.setattr("agents.strudel_mcp_agent.send_to_strudel_mcp", _fake_send_to_strudel_mcp)

    result = await execute_strudel_pattern(pattern)

    assert result.success is True
    assert seen_codes == ["sound('bd*2,hh*3').gain(1).fast(1)"]
    assert "safe fallback" in result.message.lower()
