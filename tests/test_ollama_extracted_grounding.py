from services.avatar_intelligence import ExtractedEvidenceFact
from services.ollama_service import OllamaService


class DummyOllamaService(OllamaService):
    def __init__(self) -> None:
        self.last_user_prompt = ""
        self.last_system_prompt = ""

    def _chat(self, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        return "This is a grounded response."


def test_summarise_for_curation_includes_extracted_grounding(monkeypatch):
    svc = DummyOllamaService()

    monkeypatch.setattr(
        "services.ollama_service.truth_gate",
        lambda text, article_text, grounding_facts, interactive=False, channel="linkedin": text,
    )

    extracted = [
        ExtractedEvidenceFact(
            evidence_id="X001-aaaaaa",
            statement="Anthropic launched Claude Managed Agents in public beta.",
            source_url="https://example.com/article",
            source_title="Anthropic wants to be the AWS of agentic AI",
            tags=["anthropic", "agents"],
            entities=["claude managed agents"],
            confidence="medium",
            source_fact_id="ext-abc",
        )
    ]

    article_text = (
        "Anthropic announced new managed agents capabilities and updated memory behavior "
        "for long-running workflows in enterprise environments. "
        "This release adds controls for orchestration and context persistence."
    )

    _ = svc.summarise_for_curation(
        article_text=article_text,
        source_url="https://example.com/article",
        extracted_facts=extracted,
    )

    assert "Recently learned context" in svc.last_user_prompt
    assert "Claude Managed Agents" in svc.last_user_prompt


def test_optimize_flux_art_prompt_defaults_to_ultra_realistic_image():
    svc = DummyOllamaService()

    prompt = svc.optimise_flux_art_prompt(
        "A founder presents a new AI workflow on stage.",
        title="AI summit",
        angle="product launch",
        theme="founder story",
        knowledge_context="conference keynote",
        channel="linkedin",
        source_mode="schedule",
    )

    assert prompt == "This is a grounded response."
    assert "FLUX image generation" in svc.last_system_prompt
    assert "ultra realistic image of the input story" in svc.last_system_prompt.lower()
    assert "A founder presents a new AI workflow on stage" in svc.last_user_prompt
