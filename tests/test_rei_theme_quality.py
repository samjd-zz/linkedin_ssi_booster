"""Tests for Rei theme-candidate quality rules (generic words vs named concepts)."""

from typing import List

import pytest

from services.avatar_intelligence._models import ExtractedEvidenceFact
from services.rei_toei._suno_themes import extract_themes
from services.rei_toei._theme_quality import (
    display_theme_name,
    has_named_evidence,
    normalize_theme_candidate,
)


def _fact(index: int, statement: str, tags: List[str], entities: List[str] | None = None) -> ExtractedEvidenceFact:
    return ExtractedEvidenceFact(
        evidence_id=f"ev_quality_{index:03d}",
        statement=statement,
        source_url=f"https://example.com/quality/{index}",
        source_title="Theme Quality Source",
        entities=entities or [],
        tags=tags,
        confidence="high",
        source_fact_id=f"fact_quality_{index:03d}",
    )


@pytest.mark.parametrize(
    "raw",
    [
        "feat.",
        "u.s.",
        "1990年代",
        "第1弾",
        "1990s",
        "label",
        "OPEN",
        "release date",
        "best practices",
        "the-art",
        "graphrag solutions industries financial",
        "supply chain partners aws databricks",
        "〈gap〉を象徴するアメリカンベーシック",
        "u2、björk",
        "10月28日（水",
    ],
)
def test_normalize_theme_candidate_rejects_metadata_and_fragments(raw: str) -> None:
    assert normalize_theme_candidate(raw) == ""


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("The Agent", "agent"),
        ("an agent", "agent"),
        ("〈GAP（ギャップ", "gap"),
        ("『Fuji Rock Festival", "fuji rock festival"),
        ("＜NIGHT HIKE＞", "night hike"),
        ("Spring Boot", "spring boot"),
    ],
)
def test_normalize_theme_candidate_collapses_wrappers_and_determiners(raw: str, expected: str) -> None:
    assert normalize_theme_candidate(raw) == expected


@pytest.mark.parametrize(
    ("concept", "statements", "entities", "expected"),
    [
        ("scale", ["Teams scale models quickly.", "Agents work at scale."], set(), False),
        ("access", ["Access Control.", "Developers get access to tools."], set(), False),
        ("training", ["Model Training Guide covers training loops and training data."], set(), False),
        ("java", ["Teams migrate legacy Java services.", "Modern Java runs fast."], set(), True),
        ("lstm", ["The LSTM baseline is strong."], set(), True),
        ("nerf", ["NeRF renders novel views."], set(), True),
        ("tokyo", ["公演はTOKYOで開催された。"], set(), True),
        ("tokio", ["Tokio is an async runtime."], {"tokio"}, True),
        ("changes", ["Changes are coming."], set(), False),
        ("rust", ["For example, generic fact."], set(), False),
        ("scale", ["Teams deploy Java services."], set(), False),
        ("scale", ["Teams deploy Java services."], {"scale"}, False),
        ("scale", ["Teams use Timescale for metrics."], set(), False),
        ("scale", [], set(), False),
        ("agent quality loop", ["Teams deploy Java services."], set(), False),
        ("フジロック", ["別のイベントが開催された。"], {"フジロック"}, False),
        ("生成ai", ["別のイベントが開催された。"], set(), False),
        ("agent quality loop", ["improves the agent quality loop."], set(), True),
        ("それぞれ", ["それぞれの楽曲"], {"それぞれ"}, False),
        ("アーティスト", ["アーティストが出演"], set(), False),
        ("フジロック", ["フジロックに出演"], {"フジロック"}, True),
        ("生成ai", ["生成AIを使った音楽イベント"], set(), True),
    ],
)
def test_has_named_evidence_separates_common_words_from_names(
    concept: str, statements: List[str], entities: set[str], expected: bool
) -> None:
    assert has_named_evidence(concept, iter(statements), entities) is expected


@pytest.mark.parametrize(
    ("concept", "statements", "expected"),
    [
        ("openai", ["OpenAI shipped Codex.", "Docs live at openai.com.", "OpenAI agents."], "OpenAI"),
        ("nerf", ["NeRF renders views."], "NeRF"),
        ("spring boot", ["Migrating to Spring  Boot today."], "Spring Boot"),
        ("agent quality loop", ["improves the agent quality loop."], "Agent Quality Loop"),
    ],
)
def test_display_theme_name_prefers_source_casing(
    concept: str, statements: List[str], expected: str
) -> None:
    assert display_theme_name(concept, statements) == expected


def test_extract_themes_drops_common_words_like_scale_and_keeps_named_concepts() -> None:
    """Regression: lowercase common nouns ("scale") were picked as song themes."""
    facts = [
        _fact(1, "Teams scale Java services with LSTM forecasting.", ["scale", "java", "lstm"]),
        _fact(2, "Modern Java systems scale through training pipelines.", ["scale", "java", "training"]),
        _fact(3, "The LSTM training job had to scale across GPUs.", ["scale", "lstm", "training"]),
        _fact(4, "フジロックに出演するアーティストを発表。", ["アーティスト", "それぞれ"], ["フジロック"]),
        _fact(5, "1990年代のフジロックとアーティスト。", ["アーティスト"], ["フジロック", "1990年代"]),
    ]

    themes = extract_themes(facts, limit=20)
    names = {theme.name for theme in themes}

    assert {"Java", "LSTM", "フジロック"} <= names
    assert not {"scale", "training", "アーティスト", "それぞれ", "1990年代"} & {
        name.casefold() for name in names
    }


def test_extract_themes_drops_frequent_scale_tags_without_statement_support() -> None:
    facts = [
        _fact(index, "Teams deploy Java services.", ["scale"], ["Scale"])
        for index in range(3)
    ]
    facts.append(_fact(3, "Teams deploy Java services.", ["java"]))

    themes = extract_themes(facts, limit=50)

    assert [theme.name for theme in themes] == ["Java"]
    assert themes[0].evidence_ids == ["ev_quality_003"]
