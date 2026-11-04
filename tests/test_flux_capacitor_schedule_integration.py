"""Schedule flow integration tests for FLUX art-avatar wiring in main.py."""

from types import SimpleNamespace

from services.flux_capacitor import RenderStatus
from services.ollama_service import OllamaService

import cli._flux_render as flux_render


class _MockOllamaAI(OllamaService):
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def optimise_flux_art_prompt(
        self,
        story_text: str,
        *,
        title: str = "",
        angle: str = "",
        theme: str = "",
        knowledge_context: str = "",
        channel: str = "linkedin",
        source_mode: str = "schedule",
        max_tokens: int = 260,
    ) -> str:
        self.calls.append({
            "story_text": story_text, "title": title, "angle": angle, "theme": theme,
            "knowledge_context": knowledge_context, "channel": channel,
            "source_mode": source_mode, "max_tokens": max_tokens,
        })
        return f"OPTIMIZED: {story_text}"


def test_render_schedule_art_avatar_skips_youtube() -> None:
    topic = {"title": "Test Topic", "angle": "Test Angle"}
    result = flux_render._render_schedule_art_avatar(_MockOllamaAI(), "hello", "youtube", topic)
    assert result == {}


def test_render_schedule_art_avatar_records_rendered(monkeypatch) -> None:
    recorded: dict = {}
    ai = _MockOllamaAI()

    class _MockFluxService:
        config = SimpleNamespace(enabled=True, minimal_mode=False)

        def make_request(self, **kwargs):
            recorded["request"] = kwargs
            return SimpleNamespace(request_id="req-1")

        def render(self, request):
            return SimpleNamespace(
                status=RenderStatus.RENDERED,
                image_path="/tmp/img.png",
                metadata_path="/tmp/img.json",
                story_path="/tmp/story.txt",
                story_metadata_path="/tmp/story.json",
                story_save_status="saved",
                defer_reason=None,
                render_error=None,
                wait_time_seconds=0.0,
            )

    monkeypatch.setattr(flux_render, "get_flux_service", lambda: _MockFluxService())

    topic = {"title": "Rust async", "angle": "queueing"}
    result = flux_render._render_schedule_art_avatar(ai, "post body", "linkedin", topic)

    assert recorded["request"]["post_text"] == "OPTIMIZED: post body"
    assert recorded["request"]["channel"] == "linkedin"
    assert recorded["request"]["theme"] == "Rust async"
    assert recorded["request"]["knowledge_context"] == "queueing"
    assert ai.calls[0]["source_mode"] == "schedule"
    assert result["art_avatar_status"] == "rendered"
    assert result["art_avatar_image_path"] == "/tmp/img.png"
    assert result["art_avatar_story_save_status"] == "saved"


def test_render_schedule_art_avatar_returns_failed_on_exception(monkeypatch) -> None:
    class _BoomFluxService:
        config = SimpleNamespace(enabled=True, minimal_mode=False)

        def make_request(self, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(flux_render, "get_flux_service", lambda: _BoomFluxService())

    topic = {"title": "X", "angle": "Y"}
    result = flux_render._render_schedule_art_avatar(_MockOllamaAI(), "body", "linkedin", topic)

    assert result["art_avatar_status"] == "failed"
    assert "boom" in result["art_avatar_render_error"]
