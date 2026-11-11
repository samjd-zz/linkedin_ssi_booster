"""Navigation metadata must not be saved as learned entities or tags."""

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from services.avatar_intelligence._extraction import extract_and_append_knowledge
from services.avatar_intelligence._extraction_metadata import is_navigation_metadata


@pytest.mark.parametrize(
    "value",
    [
        "ポスト はてなブックマーク line",
        "関連記事 NIKO NIKO TAN TAN",
        "follow on instagram follow on youtube follow on line 特集",
        "menu search close menu products fully-managed auradb store",
        "『mind+』メンバー全員インタビュー pick up",
        "pick up!",
        "実存 ランキング アクセス数 シェア数",
        "追加 by CINRA編集部 このコントリビューター",
        "発表 blueprint book store もっとみる",
    ],
)
def test_navigation_metadata_is_rejected(value: str) -> None:
    assert is_navigation_metadata(value)


@pytest.mark.parametrize(
    "value",
    [
        "pick up the phone",
        "AI search products",
        "Amazon S3",
        "retrieval augmented generation",
        "音楽",
        "scale",
        "2024年",
        "MCP",
        "the researchers follow on earlier work",
    ],
)
def test_ordinary_metadata_is_not_dropped(value: str) -> None:
    assert not is_navigation_metadata(value)


def test_new_facts_filter_metadata_before_limits_and_persistence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    path = tmp_path / "knowledge.json"
    old_fact = {
        "id": "existing",
        "statement": "Existing trusted data remains untouched.",
        "source_url": "https://example.test/old",
        "source_title": "Earlier",
        "extracted_at": "2026-01-01T00:00:00Z",
        "entities": ["pick up!"],
        "tags": ["menu search close menu products fully"],
        "confidence": "medium",
        "extraction_method": "spacy_nlp",
    }
    path.write_text(json.dumps({"schemaVersion": "1.0", "facts": [old_fact]}), encoding="utf-8")
    engine = MagicMock()
    engine._ensure_model.return_value = None
    engine.extract_theme_groups.return_value = {
        "entities": ["pick up!", "OpenAI", "Amazon S3", "Python", "Java", "Kubernetes", "Extra entity"],
        "concepts": [
            "ポスト はてなブックマーク line", "MCP", "scale", "training",
            "neural networks", "retrieval", "OpenAI", "Python", "Java", "Extra concept",
        ],
    }
    classifier = MagicMock()
    classifier.is_available.return_value = False
    monkeypatch.setattr("services.spacy_nlp.get_spacy_nlp", lambda: engine)
    monkeypatch.setattr("services.model2vec_service.get_model2vec_service", lambda: classifier)
    statement = "OpenAI reported 30% faster inference with Python and Kubernetes in 2026."

    with caplog.at_level(logging.INFO):
        facts = extract_and_append_knowledge(
            statement, "https://example.test/new", "OpenAI inference", path=path,
        )

    assert len(facts) == 1
    assert facts[0].statement == statement
    assert facts[0].entities == ["OpenAI", "Amazon S3", "Python", "Java", "Kubernetes"]
    assert facts[0].tags == [
        "MCP", "scale", "training", "neural networks", "retrieval", "OpenAI", "Python", "Java",
    ]
    saved = json.loads(path.read_text(encoding="utf-8"))["facts"]
    assert saved[0]["entities"] == old_fact["entities"]
    assert saved[0]["tags"] == old_fact["tags"]
    assert saved[1]["entities"] == facts[0].entities
    assert saved[1]["tags"] == facts[0].tags
    assert "navigation" in caplog.text.lower()


def test_all_navigation_metadata_keeps_the_fact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = MagicMock()
    engine._ensure_model.return_value = None
    engine.extract_theme_groups.return_value = {
        "entities": ["pick up!"],
        "concepts": ["menu search close menu products fully-managed auradb store"],
    }
    classifier = MagicMock()
    classifier.is_available.return_value = False
    monkeypatch.setattr("services.spacy_nlp.get_spacy_nlp", lambda: engine)
    monkeypatch.setattr("services.model2vec_service.get_model2vec_service", lambda: classifier)
    path = tmp_path / "knowledge.json"
    statement = "OpenAI reported 30% faster inference with Python and Kubernetes in 2026."

    facts = extract_and_append_knowledge(statement, "https://example.test", "Test", path=path)

    assert len(facts) == 1
    assert facts[0].statement == statement
    assert facts[0].entities == []
    assert facts[0].tags == []
    saved = json.loads(path.read_text(encoding="utf-8"))["facts"][0]
    assert saved["entities"] == saved["tags"] == []


def test_regex_fallback_and_dry_run_preserve_existing_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable() -> None:
        raise RuntimeError("spaCy unavailable")

    classifier = MagicMock()
    classifier.is_available.return_value = False
    monkeypatch.setattr("services.spacy_nlp.get_spacy_nlp", unavailable)
    monkeypatch.setattr("services.model2vec_service.get_model2vec_service", lambda: classifier)
    statement = "OpenAI reported 30% faster inference with Python and Kubernetes in 2026."
    path = tmp_path / "knowledge.json"

    assert extract_and_append_knowledge(
        statement, "https://example.test", "Test", path=path, dry_run=True,
    ) == []
    assert not path.exists()
    facts = extract_and_append_knowledge(statement, "https://example.test", "Test", path=path)
    assert len(facts) == 1
    assert facts[0].extraction_method == "regex_fallback"
    assert "Python" in facts[0].entities
    assert "inference" in facts[0].tags
