"""Curator article helpers: prefetch targeting and knowledge-learning logs."""

import logging
from unittest.mock import Mock

import pytest

from services.content_curator import ContentCurator


def make_curator() -> ContentCurator:
    curator = ContentCurator.__new__(ContentCurator)
    curator._spacy_nlp = None
    curator._extracted_facts = []
    curator._topic_signal = {}
    return curator


def article(summary: str, link: str = "https://example.test/a", title: str = "Agents") -> dict:
    return {"title": title, "summary": summary, "link": link, "source": "Test"}


def test_prefetch_targets_only_short_summaries_with_links() -> None:
    curator = make_curator()
    curator._fetch_article_text_with_summary = Mock(side_effect=lambda url: "" if url.endswith("empty") else f"text:{url}")
    articles = [
        article("short", "https://example.test/short"),
        article("long " * 200, "https://example.test/long"),
        article("no link", ""),
        article("short", "https://example.test/empty"),
    ]
    assert curator._prefetch_article_texts(articles) == {
        "https://example.test/short": "text:https://example.test/short",
    }
    fetched = sorted(call.args[0] for call in curator._fetch_article_text_with_summary.call_args_list)
    assert fetched == ["https://example.test/empty", "https://example.test/short"]


def test_prefetch_tolerates_invalid_worker_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURATOR_LEARN_FETCH_WORKERS", "many")
    curator = make_curator()
    curator._fetch_article_text_with_summary = Mock(return_value="full text")
    assert curator._prefetch_article_texts([article("short")]) == {"https://example.test/a": "full text"}


@pytest.mark.parametrize(
    ("learn_only", "facts", "expected"),
    [
        (True, ["fact"], "🧠 ✨ +1 fact(s) from 'Agents' (🗂️ pool=1)"),
        (False, ["fact"], "🧠 Knowledge extraction: ✨ +1 fact(s) from 'Agents' (🗂️ pool=1)"),
        (True, [], "🧠 0 new facts from 'Agents' (🗂️ pool=0)"),
        (False, [], "🧠 Knowledge extraction: ➕ 0 new facts from 'Agents' (🗂️ pool=0)"),
    ],
)
def test_learn_from_article_uses_prefetched_text_and_mode_log(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    learn_only: bool,
    facts: list,
    expected: str,
) -> None:
    extract = Mock(return_value=facts)
    monkeypatch.setattr("services.avatar_intelligence.extract_and_append_knowledge", extract)
    monkeypatch.setattr("services.avatar_intelligence.load_avatar_state", lambda: None)
    monkeypatch.setattr("services.avatar_intelligence.normalize_extracted_facts", lambda state: ["fact"])
    curator = make_curator()
    with caplog.at_level(logging.INFO, logger="services.content_curator._articles"):
        curator._learn_from_article(
            article("short"), {"https://example.test/a": "prefetched body"}, learn_only=learn_only,
        )
    assert extract.call_args.kwargs["article_text"] == "prefetched body"
    assert expected in caplog.messages
    assert curator._extracted_facts == (["fact"] if facts else [])


def test_learn_from_article_swallows_extraction_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "services.avatar_intelligence.extract_and_append_knowledge",
        Mock(side_effect=RuntimeError("spaCy down")),
    )
    curator = make_curator()
    curator._learn_from_article(article("short"), {}, learn_only=True)
    assert curator._extracted_facts == []
