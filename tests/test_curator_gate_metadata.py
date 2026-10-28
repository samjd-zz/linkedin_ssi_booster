"""Curation reuses the original gate assessment, including removal penalties."""

from unittest.mock import Mock, patch

import pytest

from services.console_grounding import TruthGateMeta
from services.content_curator import ContentCurator
from services.ollama_service import OllamaService


@pytest.fixture
def curator(monkeypatch: pytest.MonkeyPatch) -> ContentCurator:
    monkeypatch.setattr("services.shared.AVATAR_LEARNING_ENABLED", False)
    instance = ContentCurator.__new__(ContentCurator)
    instance.ai = OllamaService.__new__(OllamaService)
    instance._narrative_memory = None
    instance.confidence_policy = "balanced"
    instance.github_context = ""
    return instance


def test_generation_retains_meta_and_resets_it_on_skipped_input(curator: ContentCurator) -> None:
    ai = curator.ai
    meta = TruthGateMeta(removed_count=1, total_sentences=2, reason_codes=["unsupported_numeric"])
    with patch.object(ai, "_chat", return_value="Valid sentence. Invalid sentence."), \
            patch("services.ollama_service.truth_gate_result", return_value=("Valid sentence.", meta)) as gate:
        result = ai.summarise_for_curation("Article evidence. " * 10, "https://example.com", channel="facebook")
        assert ai.last_truth_gate_meta is meta
        assert ai.last_truth_gate_text == result
        gate.assert_called_once()
        assert ai.summarise_for_curation("too short", "") is None
        assert ai.last_truth_gate_meta is None
        assert ai.last_truth_gate_text == ""


@pytest.mark.parametrize("channel", ["linkedin", "facebook", "x", "all"])
def test_confidence_reuses_original_removal_penalties(curator: ContentCurator, channel: str) -> None:
    text = "Grounded response."
    curator.ai.last_truth_gate_meta = TruthGateMeta(
        removed_count=8, total_sentences=9, reason_codes=["fabricated_detail"],
    )
    curator.ai.last_truth_gate_text = text
    with patch("services.content_curator.curator.truth_gate_result") as gate:
        route, _ = curator._score_and_route(text, "Article", [], channel, "ref", "post")
    gate.assert_not_called()
    assert route != "post"


def test_mismatching_metadata_runs_gate_with_correct_channel(curator: ContentCurator) -> None:
    curator.ai.last_truth_gate_meta = TruthGateMeta(0, 1)
    curator.ai.last_truth_gate_text = "Previous post."
    with patch(
        "services.content_curator.curator.truth_gate_result",
        return_value=("Current post.", TruthGateMeta(0, 1)),
    ) as gate:
        curator._score_and_route("Current post.", "Article", [], "x", "ref", "post")
    gate.assert_called_once_with("Current post.", "Article", [], channel="x", article_ref="ref")


@pytest.mark.parametrize("channel", ["linkedin", "facebook", "x"])
def test_channel_formatting_keeps_generation_meta(
    curator: ContentCurator, channel: str,
) -> None:
    meta = TruthGateMeta(1, 3, reason_codes=["unsupported_numeric"])
    text = "A grounded response that fits the short channel budget."
    article = {
        "title": "Article", "summary": "Article evidence. " * 10,
        "source": "Test", "link": "https://example.com",
    }
    with patch.object(curator.ai, "_chat", return_value="Raw draft."), \
            patch("services.ollama_service.truth_gate_result", return_value=(text, meta)) as first_gate, \
            patch("services.content_curator.curator.truth_gate_result") as second_gate, \
            patch.object(curator, "_score_and_route", wraps=curator._score_and_route) as score:
        result = curator._process_single_channel(
            article, "establish_brand", [], [], [], channel, "post", True,
            False, False, False, "candidate", [], Mock(),
        )
    assert score.call_args.kwargs["gate_meta"] is meta
    first_gate.assert_called_once()
    second_gate.assert_not_called()
    assert result[0]["generated_text"] != text
