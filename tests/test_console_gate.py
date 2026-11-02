"""Tests for rebuilding a console reply after truth-gate removals."""

import pytest

from services.console_grounding import remove_gated_sentences


@pytest.mark.parametrize(
    ("text", "removed", "expected"),
    [
        ("A. B. C.", ["B."], "A. C."),
        ("Keep this.", [], "Keep this."),
        ("Only one.", ["Only one."], ""),
        (
            "Certainly! Here are phrases:\n\nGreeting:\n   - こんにちは — Hello!\n   - Thanks.\n\nEnjoy.",
            ["Certainly!", "Greeting:\n   - こんにちは — Hello!"],
            "Here are phrases:\n\n   - Thanks.\n\nEnjoy.",
        ),
    ],
)
def test_remove_gated_sentences_keeps_layout(text: str, removed: list[str], expected: str) -> None:
    assert remove_gated_sentences(text, removed) == expected


@pytest.mark.parametrize(("log_removals", "loud"), [(True, True), (False, False)])
def test_truth_gate_removal_logging_can_be_quiet(
    caplog: pytest.LogCaptureFixture, log_removals: bool, loud: bool,
) -> None:
    import logging
    from unittest.mock import patch

    from services.console_grounding import ProjectFact, truth_gate_result

    fact = ProjectFact(project="Spring AI", company="Acme", years="2022", details="Built RAG", source="test", tags=set())

    with (
        patch("services.console_grounding._truth_gate.get_domain_facts_from_avatar_state", return_value=[]),
        patch("services.console_grounding._truth_gate._score_sentence_bm25", return_value=0.0),
        caplog.at_level(logging.INFO, logger="services.console_grounding._truth_gate"),
    ):
        _, meta = truth_gate_result(
            "Certainly! Hello there.", "", [fact], channel="console", log_removals=log_removals,
        )
    assert meta.removed_sentences
    info_lines = [r for r in caplog.records if r.levelno >= logging.INFO and "Truth gate" in r.getMessage()]
    assert bool(info_lines) is loud
