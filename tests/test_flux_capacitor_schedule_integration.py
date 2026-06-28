"""Schedule flow integration tests for FLUX art-avatar wiring in main.py."""

from types import SimpleNamespace

from services.flux_capacitor import RenderStatus

import main


class _MockOllamaAI:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def optimise_flux_art_prompt(self, story_text: str, **kwargs) -> str:
        self.calls.append({"story_text": story_text, **kwargs})
        return f"OPTIMIZED: {story_text}"


def test_render_schedule_art_avatar_skips_youtube() -> None:
    topic = {"title": "Test Topic", "angle": "Test Angle"}
    result = main._render_schedule_art_avatar(_MockOllamaAI(), "hello", "youtube", topic)
    assert result == {}


def test_render_schedule_art_avatar_records_rendered(monkeypatch) -> None:
    recorded: dict = {}
    ai = _MockOllamaAI()

    class _MockFluxService:
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

    monkeypatch.setattr(main, "get_flux_service", lambda: _MockFluxService())

    topic = {"title": "Rust async", "angle": "queueing"}
    result = main._render_schedule_art_avatar(ai, "post body", "linkedin", topic)

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
        def make_request(self, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(main, "get_flux_service", lambda: _BoomFluxService())

    topic = {"title": "X", "angle": "Y"}
    result = main._render_schedule_art_avatar(_MockOllamaAI(), "body", "linkedin", topic)

    assert result["art_avatar_status"] == "failed"
    assert "boom" in result["art_avatar_render_error"]
