"""Tests for CURATOR_RSS_FEEDS_EXTRA / CURATOR_KEYWORDS_EXTRA append semantics."""

import importlib
import json

import pytest


def _reload_config(monkeypatch, env: dict[str, str]):
    for key in (
        "CURATOR_RSS_FEEDS",
        "CURATOR_RSS_FEEDS_EXTRA",
        "CURATOR_KEYWORDS",
        "CURATOR_KEYWORDS_EXTRA",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    import services.content_curator._config as config

    return importlib.reload(config)


@pytest.fixture(autouse=True)
def _restore_config():
    yield
    import services.content_curator._config as config

    importlib.reload(config)


def test_extra_feeds_append_to_defaults(monkeypatch):
    extra = [{"name": "Real Sound 音楽", "url": "https://realsound.jp/music/feed"}]
    config = _reload_config(
        monkeypatch, {"CURATOR_RSS_FEEDS_EXTRA": json.dumps(extra, ensure_ascii=False)}
    )

    assert len(config.RSS_FEEDS) == len(config._DEFAULT_RSS_FEEDS) + 1
    assert config.RSS_FEEDS[-1]["url"] == "https://realsound.jp/music/feed"


def test_extra_feeds_append_to_explicit_override(monkeypatch):
    base = [{"name": "Base", "url": "https://base.example/feed"}]
    extra = [{"name": "Extra", "url": "https://extra.example/feed"}]
    config = _reload_config(
        monkeypatch,
        {
            "CURATOR_RSS_FEEDS": json.dumps(base),
            "CURATOR_RSS_FEEDS_EXTRA": json.dumps(extra),
        },
    )

    assert [f["url"] for f in config.RSS_FEEDS] == [
        "https://base.example/feed",
        "https://extra.example/feed",
    ]


def test_extra_feeds_dedupe_by_url(monkeypatch):
    base = [{"name": "Base", "url": "https://base.example/feed"}]
    config = _reload_config(
        monkeypatch,
        {
            "CURATOR_RSS_FEEDS": json.dumps(base),
            "CURATOR_RSS_FEEDS_EXTRA": json.dumps(base),
        },
    )

    assert len(config.RSS_FEEDS) == 1


def test_extra_keywords_append_and_dedupe(monkeypatch):
    config = _reload_config(
        monkeypatch,
        {
            "CURATOR_KEYWORDS": "RAG,LLM",
            "CURATOR_KEYWORDS_EXTRA": "新宿, rag ,ライブハウス",
        },
    )

    assert config.KEYWORDS == ["RAG", "LLM", "新宿", "ライブハウス"]


def test_defaults_are_not_mutated_across_reloads(monkeypatch):
    _reload_config(
        monkeypatch,
        {"CURATOR_RSS_FEEDS_EXTRA": json.dumps([{"name": "X", "url": "https://x.example/feed"}])},
    )
    config = _reload_config(monkeypatch, {})

    assert all(f["url"] != "https://x.example/feed" for f in config.RSS_FEEDS)
