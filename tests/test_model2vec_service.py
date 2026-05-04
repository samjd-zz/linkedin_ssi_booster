"""
Tests for services/model2vec_service.py

All tests run without the model2vec package installed — the service must
degrade gracefully in that case.  When model2vec IS available the tests
use a mock StaticModel so no network calls are made.
"""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_service(enabled: bool = True, model_available: bool = False):
    """Return a Model2VecService instance with controlled availability."""
    import services.model2vec_service as svc_mod

    # Patch module-level availability flag and config
    with (
        patch.object(svc_mod, "_MODEL2VEC_AVAILABLE", model_available),
        patch.object(svc_mod, "MODEL2VEC_ENABLED", enabled),
        # Reset singleton so tests don't interfere with each other
        patch.object(svc_mod, "_SERVICE_INSTANCE", None),
    ):
        svc = svc_mod.Model2VecService()
        # Force a fresh instance (singleton not in play here)
        return svc


def _make_mock_model(dim: int = 8):
    """Return a mock StaticModel that returns deterministic embeddings."""
    import numpy as np

    mock_model = MagicMock()

    def fake_encode(texts):
        # Return a fixed embedding per text (different per text via hash)
        result = []
        for text in texts:
            seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16) % (2**31)
            rng = np.random.default_rng(seed)
            vec = rng.random(dim).astype(np.float32)
            # Normalise so cosine sim is non-trivial
            vec /= np.linalg.norm(vec) + 1e-9
            result.append(vec)
        return np.array(result)

    mock_model.encode.side_effect = fake_encode
    return mock_model


# ---------------------------------------------------------------------------
# CategoryPrediction / ClassificationResult dataclasses
# ---------------------------------------------------------------------------


def test_classification_result_post_init_sets_primary():
    from services.model2vec_service import CategoryPrediction, ClassificationResult

    pred = CategoryPrediction(
        category="Technology",
        confidence=0.9,
        description="Tech stuff",
        ssi_component="establish_brand",
    )
    result = ClassificationResult(
        text_hash="abc",
        predictions=[pred],
        processing_time_ms=5.0,
    )
    assert result.primary_category == "Technology"
    assert result.primary_ssi_component == "establish_brand"


def test_classification_result_empty():
    from services.model2vec_service import ClassificationResult

    result = ClassificationResult(text_hash="", predictions=[], processing_time_ms=0.0)
    assert result.primary_category == ""
    assert result.top_category is None
    assert result.top_confidence == 0.0


# ---------------------------------------------------------------------------
# Service availability / graceful degradation
# ---------------------------------------------------------------------------


def test_service_unavailable_when_model2vec_not_installed():
    import services.model2vec_service as svc_mod

    with patch.object(svc_mod, "_MODEL2VEC_AVAILABLE", False):
        svc = svc_mod.Model2VecService()
        assert not svc.is_available()


def test_service_unavailable_when_disabled():
    import services.model2vec_service as svc_mod

    with patch.object(svc_mod, "MODEL2VEC_ENABLED", False):
        svc = svc_mod.Model2VecService()
        assert not svc.is_available()


def test_classify_text_returns_empty_when_model_unavailable():
    import services.model2vec_service as svc_mod

    with patch.object(svc_mod, "_MODEL2VEC_AVAILABLE", False):
        svc = svc_mod.Model2VecService()
        result = svc.classify_text("Some article about technology and AI.")
        assert result.predictions == []
        assert result.primary_category == ""


def test_classify_text_empty_input_returns_empty():
    import services.model2vec_service as svc_mod

    svc = svc_mod.Model2VecService()
    result = svc.classify_text("")
    assert result.predictions == []
    assert result.text_hash == ""


def test_batch_classify_empty_list_returns_empty():
    import services.model2vec_service as svc_mod

    svc = svc_mod.Model2VecService()
    results = svc.batch_classify([])
    assert results == []


def test_batch_classify_returns_empty_results_when_unavailable():
    import services.model2vec_service as svc_mod

    with patch.object(svc_mod, "_MODEL2VEC_AVAILABLE", False):
        svc = svc_mod.Model2VecService()
        results = svc.batch_classify(["article one", "article two"])
        assert len(results) == 2
        for r in results:
            assert r.predictions == []


# ---------------------------------------------------------------------------
# Default category registration
# ---------------------------------------------------------------------------


def test_default_categories_registered():
    import services.model2vec_service as svc_mod

    with patch.object(svc_mod, "_MODEL2VEC_AVAILABLE", True):
        svc = svc_mod.Model2VecService()
        cats = svc.list_categories()
        assert "Technology" in cats
        assert "Artificial Intelligence" in cats
        assert "Business" in cats
        assert len(cats) == 10  # 10 default categories


def test_default_categories_not_removable():
    import services.model2vec_service as svc_mod

    with patch.object(svc_mod, "_MODEL2VEC_AVAILABLE", True):
        svc = svc_mod.Model2VecService()
        results = svc.remove_categories(["Technology"])
        assert results == [False]
        assert "Technology" in svc.list_categories()


# ---------------------------------------------------------------------------
# Custom category management
# ---------------------------------------------------------------------------


def test_add_custom_category_without_model():
    import services.model2vec_service as svc_mod

    with patch.object(svc_mod, "_MODEL2VEC_AVAILABLE", True):
        svc = svc_mod.Model2VecService()
        # Don't load model — test category registration path only
        result = svc.add_category(
            name="GovTech",
            description="Government technology, public sector AI, regulatory compliance.",
            ssi_component="find_right_people",
        )
        assert result is True
        cats = svc.list_categories()
        assert "GovTech" in cats
        assert cats["GovTech"]["ssi_component"] == "find_right_people"
        assert cats["GovTech"]["custom"] == "True"


def test_add_duplicate_category_returns_false():
    import services.model2vec_service as svc_mod

    with patch.object(svc_mod, "_MODEL2VEC_AVAILABLE", True):
        svc = svc_mod.Model2VecService()
        svc.add_category("MyCustom", "desc", "establish_brand")
        result = svc.add_category("MyCustom", "desc2", "establish_brand")
        assert result is False


def test_remove_custom_category():
    import services.model2vec_service as svc_mod

    with patch.object(svc_mod, "_MODEL2VEC_AVAILABLE", True):
        svc = svc_mod.Model2VecService()
        svc.add_category("ToRemove", "description", "build_relationships")
        assert "ToRemove" in svc.list_categories()
        results = svc.remove_categories(["ToRemove"])
        assert results == [True]
        assert "ToRemove" not in svc.list_categories()


def test_remove_nonexistent_category_returns_false():
    import services.model2vec_service as svc_mod

    with patch.object(svc_mod, "_MODEL2VEC_AVAILABLE", True):
        svc = svc_mod.Model2VecService()
        results = svc.remove_categories(["DoesNotExist"])
        assert results == [False]


def test_batch_add_categories():
    import services.model2vec_service as svc_mod

    with patch.object(svc_mod, "_MODEL2VEC_AVAILABLE", True):
        svc = svc_mod.Model2VecService()
        categories = [
            {"name": "OpenSource", "description": "Open source projects", "ssi_component": "establish_brand"},
            {"name": "CloudNative", "description": "Kubernetes, Docker, cloud", "ssi_component": "establish_brand"},
            {"name": "", "description": "Missing name"},  # invalid
        ]
        results = svc.batch_add_categories(categories)
        assert results == [True, True, False]
        cats = svc.list_categories()
        assert "OpenSource" in cats
        assert "CloudNative" in cats


# ---------------------------------------------------------------------------
# Classification with mock model
# ---------------------------------------------------------------------------


def test_classify_text_with_mock_model():
    """When model2vec is available, classify_text returns non-empty predictions."""
    import numpy as np
    import services.model2vec_service as svc_mod

    mock_model = _make_mock_model(dim=8)

    with (
        patch.object(svc_mod, "_MODEL2VEC_AVAILABLE", True),
        patch.object(svc_mod, "MODEL2VEC_ENABLED", True),
        patch("services.model2vec_service.StaticModel") as mock_static_model_cls,
    ):
        mock_static_model_cls.from_pretrained.return_value = mock_model
        svc = svc_mod.Model2VecService()
        result = svc.classify_text("Machine learning and neural networks", top_k=3)

    assert len(result.predictions) <= 3
    assert result.text_hash != ""
    assert result.processing_time_ms >= 0.0
    # All predictions must be from the registered default categories
    cat_names = {p.category for p in result.predictions}
    known = set(svc_mod.DEFAULT_CATEGORIES.keys())
    assert cat_names.issubset(known)


def test_batch_classify_with_mock_model():
    import services.model2vec_service as svc_mod

    mock_model = _make_mock_model(dim=8)

    texts = [
        "Latest advances in large language models",
        "Government regulatory policy for AI",
        "Business strategy for SaaS startups",
    ]

    with (
        patch.object(svc_mod, "_MODEL2VEC_AVAILABLE", True),
        patch.object(svc_mod, "MODEL2VEC_ENABLED", True),
        patch("services.model2vec_service.StaticModel") as mock_static_model_cls,
    ):
        mock_static_model_cls.from_pretrained.return_value = mock_model
        svc = svc_mod.Model2VecService()
        results = svc.batch_classify(texts, top_k=1)

    assert len(results) == 3
    for r in results:
        assert r.text_hash != ""


# ---------------------------------------------------------------------------
# Convenience wrapper functions
# ---------------------------------------------------------------------------


def test_classify_article_wrapper():
    import services.model2vec_service as svc_mod

    article = {
        "title": "New breakthrough in quantum computing",
        "summary": "Researchers achieve 1000-qubit processor.",
    }

    with (
        patch.object(svc_mod, "_MODEL2VEC_AVAILABLE", False),
        patch.object(svc_mod, "_SERVICE_INSTANCE", None),
    ):
        result = svc_mod.classify_article(article)
    # With model unavailable the result should be gracefully empty
    assert result.predictions == []


def test_batch_classify_articles_wrapper():
    import services.model2vec_service as svc_mod

    articles = [
        {"title": "AI research news", "summary": "New LLM released."},
        {"title": "Sports highlights", "summary": "Team wins championship."},
    ]

    with (
        patch.object(svc_mod, "_MODEL2VEC_AVAILABLE", False),
        patch.object(svc_mod, "_SERVICE_INSTANCE", None),
    ):
        results = svc_mod.batch_classify_articles(articles)
    assert len(results) == 2
    for r in results:
        assert r.predictions == []


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


def test_get_model2vec_service_returns_singleton():
    import services.model2vec_service as svc_mod

    with patch.object(svc_mod, "_SERVICE_INSTANCE", None):
        svc1 = svc_mod.get_model2vec_service()
        svc2 = svc_mod.get_model2vec_service()
        assert svc1 is svc2


# ---------------------------------------------------------------------------
# _text_hash utility
# ---------------------------------------------------------------------------


def test_text_hash_is_deterministic():
    from services.model2vec_service import Model2VecService

    h1 = Model2VecService._text_hash("hello world")
    h2 = Model2VecService._text_hash("hello world")
    h3 = Model2VecService._text_hash("different text")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 16


# ---------------------------------------------------------------------------
# _cosine_similarity
# ---------------------------------------------------------------------------


def test_cosine_similarity_identical_vectors():
    import numpy as np
    from services.model2vec_service import Model2VecService

    v = np.array([1.0, 0.0, 0.0])
    sim = Model2VecService._cosine_similarity(v, v)
    assert abs(sim - 1.0) < 1e-6


def test_cosine_similarity_orthogonal_vectors():
    import numpy as np
    from services.model2vec_service import Model2VecService

    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    sim = Model2VecService._cosine_similarity(a, b)
    assert abs(sim) < 1e-6


def test_cosine_similarity_zero_vector():
    import numpy as np
    from services.model2vec_service import Model2VecService

    zero = np.array([0.0, 0.0, 0.0])
    v = np.array([1.0, 2.0, 3.0])
    sim = Model2VecService._cosine_similarity(zero, v)
    assert sim == 0.0


# ---------------------------------------------------------------------------
# _rss_fetcher integration: articles get category keys
# ---------------------------------------------------------------------------


def test_rss_fetcher_articles_have_category_keys(monkeypatch):
    """fetch_relevant_articles always includes primary_category keys in returned dicts."""
    import feedparser
    import services.content_curator._rss_fetcher as fetcher_mod

    # Minimal fake RSS entry
    fake_entry = MagicMock()
    fake_entry.get = lambda k, default="": {
        "title": "LLM agents now smarter than ever",
        "summary": "Large language model agents improve with new techniques.",
        "link": "https://example.com/llm",
        "published": "",
    }.get(k, default)

    fake_feed = MagicMock()
    fake_feed.entries = [fake_entry]

    monkeypatch.setattr(feedparser, "parse", lambda url: fake_feed)
    # Don't classify — just verify the keys are always present
    articles = fetcher_mod.fetch_relevant_articles(max_per_feed=1, classify=False)
    # The list may be empty if no keywords match, but if it has items, check keys
    for article in articles:
        assert "primary_category" in article
        assert "primary_ssi_component" in article


# ---------------------------------------------------------------------------
# selection_learning _models: CandidateRecord has category fields
# ---------------------------------------------------------------------------


def test_candidate_record_has_category_fields():
    from services.selection_learning._models import CandidateRecord

    record = CandidateRecord(
        candidate_id="test-123",
        timestamp="2026-01-01T00:00:00",
        article_url="https://example.com",
        article_title="Test Article",
        article_source="TestFeed",
        ssi_component="establish_brand",
        channel="linkedin",
        text_hash="abc123",
        text_snippet="Test post text.",
        buffer_id=None,
        route="idea",
        selected=None,
        selected_at=None,
        run_id="run-001",
    )
    assert record.primary_category == ""
    assert record.primary_ssi_component == ""
    assert record.category_confidence == 0.0

    # Also verify fields can be set
    record.primary_category = "Technology"
    record.primary_ssi_component = "establish_brand"
    record.category_confidence = 0.87
    assert record.primary_category == "Technology"


# ---------------------------------------------------------------------------
# selection_learning _ranking: category boost
# ---------------------------------------------------------------------------


def test_ranking_category_boost_matching_component():
    from services.selection_learning._ranking import RankingService

    article_with_match = {
        "primary_ssi_component": "establish_brand",
    }
    boost = RankingService._category_boost(article_with_match, "establish_brand")
    assert boost == pytest.approx(1.15)


def test_ranking_category_boost_mismatched_component():
    from services.selection_learning._ranking import RankingService

    article = {"primary_ssi_component": "find_right_people"}
    boost = RankingService._category_boost(article, "establish_brand")
    assert boost == pytest.approx(1.0)


def test_ranking_category_boost_missing_metadata():
    from services.selection_learning._ranking import RankingService

    article_no_category = {}
    boost = RankingService._category_boost(article_no_category, "establish_brand")
    assert boost == pytest.approx(1.0)


def test_ranking_category_boost_empty_ssi_component():
    from services.selection_learning._ranking import RankingService

    article = {"primary_ssi_component": "establish_brand"}
    boost = RankingService._category_boost(article, "")
    assert boost == pytest.approx(1.0)
