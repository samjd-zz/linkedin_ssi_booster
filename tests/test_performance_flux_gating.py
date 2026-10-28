"""Image-prompt generation must not run in text-only flows."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import main
from services.flux_capacitor import SourceMode


@pytest.mark.parametrize("source_mode", list(SourceMode))
@pytest.mark.parametrize("enabled,minimal_mode", [(False, False), (False, True), (True, True)])
def test_text_only_preserves_story_without_llm(
    monkeypatch: pytest.MonkeyPatch,
    source_mode: SourceMode,
    enabled: bool,
    minimal_mode: bool,
) -> None:
    service = SimpleNamespace(config=SimpleNamespace(enabled=enabled, minimal_mode=minimal_mode))
    monkeypatch.setattr(main, "get_flux_service", lambda: service)
    ai = Mock()
    result = main._optimize_flux_story_for_render(
        ai, "  Original story.  ", source_mode=source_mode, channel="linkedin",
    )
    assert result == "Original story."
    ai.optimise_flux_art_prompt.assert_not_called()


def test_enabled_render_optimizes_once(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SimpleNamespace(config=SimpleNamespace(enabled=True, minimal_mode=False))
    monkeypatch.setattr(main, "get_flux_service", lambda: service)
    ai = Mock()
    ai.optimise_flux_art_prompt.return_value = "Visual story"
    assert main._optimize_flux_story_for_render(
        ai, "Original story", source_mode=SourceMode.CURATE, channel="x",
    ) == "Visual story"
    ai.optimise_flux_art_prompt.assert_called_once()
