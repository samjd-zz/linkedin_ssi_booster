"""Curate and console flow integration tests for FLUX art-avatar wiring in main.py."""

import os
import tempfile
from types import SimpleNamespace

import pytest

from services.flux_capacitor import RenderStatus

import main


class _MockOllamaAI:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def optimise_flux_art_prompt(self, story_text: str, **kwargs) -> str:
        self.calls.append({"story_text": story_text, **kwargs})
        return f"OPTIMIZED: {story_text}"


# ---------------------------------------------------------------------------
# _display_art_in_terminal
# ---------------------------------------------------------------------------

class TestDisplayArtInTerminal:
    def test_none_path_is_silent(self):
        # Should not raise
        main._display_art_in_terminal(None)

    def test_missing_file_is_silent(self):
        main._display_art_in_terminal("/tmp/does_not_exist_flux.png")

    def test_renders_when_term_image_available(self, monkeypatch, tmp_path):
        """If term_image.from_file succeeds, draw() is called exactly once."""
        # Write a tiny valid PNG (1×1 pixel) so is_file() passes
        import PIL.Image as _PIL
        img_path = tmp_path / "test_art.png"
        _PIL.new("RGB", (1, 1), color=(255, 0, 0)).save(str(img_path))

        drawn: list = []

        class _FakeImg:
            def draw(self):
                drawn.append(True)

        monkeypatch.setattr(
            "term_image.image.from_file",
            lambda path, **kw: _FakeImg(),
        )
        main._display_art_in_terminal(str(img_path))
        assert drawn == [True]

    def test_term_image_import_error_is_silent(self, monkeypatch, tmp_path):
        """term-image unavailable → silent skip, no exception raised."""
        import PIL.Image as _PIL
        img_path = tmp_path / "test_art2.png"
        _PIL.new("RGB", (1, 1)).save(str(img_path))

        import builtins
        real_import = builtins.__import__

        def _block_term_image(name, *args, **kwargs):
            if name == "term_image.image":
                raise ImportError("term_image not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _block_term_image)
        # Should not raise
        main._display_art_in_terminal(str(img_path))



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_flux_service(status: RenderStatus = RenderStatus.RENDERED):
    """Return a minimal mock FluxCapacitorService."""
    class _MockFluxService:
        def make_request(self, **kwargs):
            self._last_request = kwargs
            return SimpleNamespace(request_id="req-test")

        def render(self, request):
            return SimpleNamespace(
                status=status,
                image_path="/tmp/curate_img.png" if status == RenderStatus.RENDERED else None,
                metadata_path="/tmp/curate_img.json",
                story_path="/tmp/curate_story.txt",
                story_metadata_path="/tmp/curate_story.json",
                story_save_status="saved" if status == RenderStatus.RENDERED else "skipped",
                defer_reason="GPU busy" if status == RenderStatus.DEFERRED else None,
                render_error=None,
                wait_time_seconds=0.1,
            )

    return _MockFluxService()


# ---------------------------------------------------------------------------
# _render_curate_art_avatar
# ---------------------------------------------------------------------------

class TestRenderCurateArtAvatar:
    def test_skips_youtube_channel(self):
        idea = {"generated_text": "some post", "title": "T", "channel": "youtube"}
        result = main._render_curate_art_avatar(_MockOllamaAI(), idea, "youtube")
        assert result == {}

    def test_skips_all_channel(self):
        idea = {"generated_text": "some post", "title": "T", "channel": "all"}
        result = main._render_curate_art_avatar(_MockOllamaAI(), idea, "all")
        assert result == {}

    def test_skips_empty_text(self):
        idea = {"generated_text": "", "title": "T", "channel": "linkedin"}
        result = main._render_curate_art_avatar(_MockOllamaAI(), idea, "linkedin")
        assert result == {}

    def test_skips_missing_text(self):
        idea = {"title": "T", "channel": "linkedin"}
        result = main._render_curate_art_avatar(_MockOllamaAI(), idea, "linkedin")
        assert result == {}

    def test_uses_text_field_as_fallback(self, monkeypatch):
        """idea dicts from YouTube path use 'text' key instead of 'generated_text'."""
        svc = _mock_flux_service(RenderStatus.RENDERED)
        monkeypatch.setattr(main, "get_flux_service", lambda: svc)
        ai = _MockOllamaAI()
        idea = {"text": "video script body", "title": "VT", "channel": "linkedin"}
        result = main._render_curate_art_avatar(ai, idea, "linkedin")
        assert result["art_avatar_status"] == "rendered"
        assert svc._last_request["post_text"] == "OPTIMIZED: video script body"

    def test_rendered_path_returns_full_metadata(self, monkeypatch):
        svc = _mock_flux_service(RenderStatus.RENDERED)
        monkeypatch.setattr(main, "get_flux_service", lambda: svc)
        ai = _MockOllamaAI()
        idea = {"generated_text": "great post", "title": "AI trends", "channel": "linkedin"}
        result = main._render_curate_art_avatar(ai, idea, "linkedin")

        assert result["art_avatar_status"] == "rendered"
        assert result["art_avatar_image_path"] == "/tmp/curate_img.png"
        assert result["art_avatar_story_path"] == "/tmp/curate_story.txt"
        assert result["art_avatar_story_save_status"] == "saved"
        assert result["art_avatar_wait_seconds"] == pytest.approx(0.1)
        assert svc._last_request["post_text"] == "OPTIMIZED: great post"

    def test_deferred_path_returns_defer_reason(self, monkeypatch):
        svc = _mock_flux_service(RenderStatus.DEFERRED)
        monkeypatch.setattr(main, "get_flux_service", lambda: svc)
        ai = _MockOllamaAI()
        idea = {"generated_text": "deferred post", "title": "T", "channel": "x"}
        result = main._render_curate_art_avatar(ai, idea, "x")

        assert result["art_avatar_status"] == "deferred"
        assert result["art_avatar_defer_reason"] == "GPU busy"
        assert result["art_avatar_image_path"] is None

    def test_exception_returns_failed(self, monkeypatch):
        class _BoomService:
            def make_request(self, **kwargs):
                raise RuntimeError("curate-boom")

        monkeypatch.setattr(main, "get_flux_service", lambda: _BoomService())
        ai = _MockOllamaAI()
        idea = {"generated_text": "body", "title": "T", "channel": "linkedin"}
        result = main._render_curate_art_avatar(ai, idea, "linkedin")

        assert result["art_avatar_status"] == "failed"
        assert "curate-boom" in result["art_avatar_render_error"]

    def test_uses_source_mode_curate(self, monkeypatch):
        """Curate flow must pass SourceMode.CURATE."""
        from services.flux_capacitor import SourceMode
        recorded: dict = {}

        class _RecordingService:
            def make_request(self, **kwargs):
                recorded.update(kwargs)
                return SimpleNamespace(request_id="r")

            def render(self, req):
                return SimpleNamespace(
                    status=RenderStatus.TEXT_ONLY,
                    image_path=None,
                    metadata_path=None,
                    story_path=None,
                    story_metadata_path=None,
                    story_save_status="skipped",
                    defer_reason="disabled",
                    render_error=None,
                    wait_time_seconds=0.0,
                )

        ai = _MockOllamaAI()
        monkeypatch.setattr(main, "get_flux_service", lambda: _RecordingService())
        idea = {"generated_text": "post body", "title": "My Topic", "channel": "linkedin"}
        main._render_curate_art_avatar(ai, idea, "linkedin")

        assert recorded.get("source_mode") == SourceMode.CURATE
        assert recorded.get("channel") == "linkedin"
        assert recorded.get("theme") == "My Topic"
        assert recorded.get("post_text") == "OPTIMIZED: post body"


# ---------------------------------------------------------------------------
# _render_console_art_avatar
# ---------------------------------------------------------------------------

class TestRenderConsoleArtAvatar:
    def test_skips_empty_text(self):
        result = main._render_console_art_avatar(_MockOllamaAI(), "")
        assert result == {}

    def test_rendered_path_returns_full_metadata(self, monkeypatch):
        svc = _mock_flux_service(RenderStatus.RENDERED)
        monkeypatch.setattr(main, "get_flux_service", lambda: svc)
        ai = _MockOllamaAI()
        result = main._render_console_art_avatar(ai, "some reply text", "AI trends")

        assert result["art_avatar_status"] == "rendered"
        assert result["art_avatar_image_path"] == "/tmp/curate_img.png"
        assert result["art_avatar_story_path"] == "/tmp/curate_story.txt"
        assert svc._last_request["post_text"] == "OPTIMIZED: some reply text"

    def test_deferred_path_carries_reason(self, monkeypatch):
        svc = _mock_flux_service(RenderStatus.DEFERRED)
        monkeypatch.setattr(main, "get_flux_service", lambda: svc)
        result = main._render_console_art_avatar(_MockOllamaAI(), "text", None)

        assert result["art_avatar_status"] == "deferred"
        assert result["art_avatar_defer_reason"] == "GPU busy"

    def test_exception_returns_failed(self, monkeypatch):
        class _BoomService:
            def make_request(self, **kwargs):
                raise RuntimeError("console-boom")

        monkeypatch.setattr(main, "get_flux_service", lambda: _BoomService())
        result = main._render_console_art_avatar(_MockOllamaAI(), "text")

        assert result["art_avatar_status"] == "failed"
        assert "console-boom" in result["art_avatar_render_error"]

    def test_uses_source_mode_console(self, monkeypatch):
        """Console flow must pass SourceMode.CONSOLE."""
        from services.flux_capacitor import SourceMode
        recorded: dict = {}

        class _RecordingService:
            def make_request(self, **kwargs):
                recorded.update(kwargs)
                return SimpleNamespace(request_id="r")

            def render(self, req):
                return SimpleNamespace(
                    status=RenderStatus.TEXT_ONLY,
                    image_path=None,
                    metadata_path=None,
                    story_path=None,
                    story_metadata_path=None,
                    story_save_status="skipped",
                    defer_reason="disabled",
                    render_error=None,
                    wait_time_seconds=0.0,
                )

        ai = _MockOllamaAI()
        monkeypatch.setattr(main, "get_flux_service", lambda: _RecordingService())
        main._render_console_art_avatar(ai, "hello world", "topic hint")

        assert recorded.get("source_mode") == SourceMode.CONSOLE
        assert recorded.get("channel") == "linkedin"
        assert recorded.get("theme") == "topic hint"
        assert recorded.get("post_text") == "OPTIMIZED: hello world"

    def test_topic_hint_none_is_accepted(self, monkeypatch):
        svc = _mock_flux_service(RenderStatus.TEXT_ONLY)
        monkeypatch.setattr(main, "get_flux_service", lambda: svc)
        result = main._render_console_art_avatar(_MockOllamaAI(), "text without hint")
        assert "art_avatar_status" in result
