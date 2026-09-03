"""
Unit tests for spaCy NLP Engine.

Tests cover theme extraction, similarity computation, sentiment analysis,
error handling, and fallback behavior when spaCy is unavailable.
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch, MagicMock

from services.spacy_nlp import SpacyNLP, get_spacy_nlp, _is_spacy_available, _load_model


class TestSpacyNLP:
    """Test suite for SpacyNLP class."""
    
    def test_extract_themes_with_spacy(self):
        """Test theme extraction when spaCy is available."""
        # Mock spaCy doc with entities and noun chunks
        mock_ent1 = Mock()
        mock_ent1.text = "OpenAI"
        mock_ent1.label_ = "ORG"
        
        mock_ent2 = Mock()
        mock_ent2.text = "GPT-4"
        mock_ent2.label_ = "PRODUCT"
        
        mock_chunk1 = Mock()
        mock_chunk1.text = "machine learning"
        
        mock_chunk2 = Mock()
        mock_chunk2.text = "AI"  # Too short, should be filtered
        
        mock_doc = Mock()
        mock_doc.ents = [mock_ent1, mock_ent2]
        mock_doc.noun_chunks = [mock_chunk1, mock_chunk2]
        
        mock_nlp = Mock(return_value=mock_doc)
        
        nlp_engine = SpacyNLP()
        nlp_engine._nlp = mock_nlp
        
        result = nlp_engine.extract_themes("OpenAI released GPT-4 for machine learning.")
        
        # Should extract entities and meaningful noun chunks
        assert "openai" in result
        assert "gpt-4" in result
        assert "machine learning" in result
        # Short chunk should be filtered out
        assert "ai" not in result or len(result) == 3  # may be included if >5 chars
    
    def test_extract_themes_without_spacy(self):
        """Test theme extraction fallback when spaCy unavailable."""
        nlp_engine = SpacyNLP()
        nlp_engine._nlp = None
        
        with patch("services.spacy_nlp._load_model", return_value=None):
            result = nlp_engine.extract_themes("Some text")
        
        # Should return empty list as fallback
        assert result == []
    
    def test_extract_themes_exception_handling(self):
        """Test theme extraction handles exceptions gracefully."""
        mock_nlp = Mock(side_effect=Exception("spaCy error"))
        
        nlp_engine = SpacyNLP()
        nlp_engine._nlp = mock_nlp
        
        result = nlp_engine.extract_themes("Some text")
        
        # Should return empty list on error
        assert result == []
    
    def test_compute_similarity_with_vectors(self):
        """Test similarity computation when vectors are available."""
        mock_doc1 = Mock()
        mock_doc1.has_vector = True
        mock_doc1.similarity = Mock(return_value=0.85)
        
        mock_doc2 = Mock()
        mock_doc2.has_vector = True
        
        mock_nlp = Mock(side_effect=[mock_doc1, mock_doc2])
        
        nlp_engine = SpacyNLP()
        nlp_engine._nlp = mock_nlp
        
        result = nlp_engine.compute_similarity("text1", "text2")
        
        assert result == 0.85
        mock_doc1.similarity.assert_called_once_with(mock_doc2)
    
    def test_compute_similarity_without_vectors(self):
        """Test similarity computation fallback when vectors unavailable."""
        mock_doc1 = Mock()
        mock_doc1.has_vector = False
        
        mock_doc2 = Mock()
        mock_doc2.has_vector = False
        
        mock_nlp = Mock(side_effect=[mock_doc1, mock_doc2])
        
        nlp_engine = SpacyNLP()
        nlp_engine._nlp = mock_nlp
        
        result = nlp_engine.compute_similarity("text1", "text2")
        
        # Should return 0.0 as fallback
        assert result == 0.0
    
    def test_compute_similarity_clamping(self):
        """Test similarity scores are clamped to [0.0, 1.0] range."""
        mock_doc1 = Mock()
        mock_doc1.has_vector = True
        mock_doc1.similarity = Mock(return_value=1.5)  # Out of range
        
        mock_doc2 = Mock()
        mock_doc2.has_vector = True
        
        mock_nlp = Mock(side_effect=[mock_doc1, mock_doc2])
        
        nlp_engine = SpacyNLP()
        nlp_engine._nlp = mock_nlp
        
        result = nlp_engine.compute_similarity("text1", "text2")
        
        # Should be clamped to 1.0
        assert result == 1.0
    
    def test_analyze_sentiment_positive(self):
        """Test sentiment analysis for positive text."""
        # Create mock tokens with positive words
        mock_token1 = Mock()
        mock_token1.text = "great"
        
        mock_token2 = Mock()
        mock_token2.text = "excellent"
        
        # Create mock sentences
        mock_sent = Mock()
        mock_sent.__iter__ = Mock(return_value=iter([mock_token1, mock_token2]))
        
        mock_doc = Mock()
        mock_doc.__iter__ = Mock(return_value=iter([mock_token1, mock_token2]))
        mock_doc.sents = [mock_sent]
        
        mock_nlp = Mock(return_value=mock_doc)
        
        nlp_engine = SpacyNLP()
        nlp_engine._nlp = mock_nlp
        
        result = nlp_engine.analyze_sentiment("This is great and excellent!")
        
        assert result["polarity"] == "positive"
        assert result["confidence"] > 0.5
        assert "enthusiastic" in result["tone"]
    
    def test_analyze_sentiment_negative(self):
        """Test sentiment analysis for negative text."""
        mock_token1 = Mock()
        mock_token1.text = "bad"
        mock_token2 = Mock()
        mock_token2.text = "terrible"
        # Both doc and sent should yield the tokens
        mock_sent = Mock()
        mock_sent.__iter__ = Mock(return_value=iter([mock_token1, mock_token2]))
        mock_doc = Mock()
        mock_doc.__iter__ = Mock(return_value=iter([mock_token1, mock_token2]))
        mock_doc.sents = [mock_sent]
        mock_nlp = Mock(return_value=mock_doc)
        nlp_engine = SpacyNLP()
        nlp_engine._nlp = mock_nlp
        result = nlp_engine.analyze_sentiment("This is bad and terrible.")
        assert result["polarity"] == "negative"
        assert result["confidence"] > 0.5
    
    def test_analyze_sentiment_neutral(self):
        """Test sentiment analysis for neutral text."""
        mock_token1 = Mock()
        mock_token1.text = "the"
        
        mock_token2 = Mock()
        mock_token2.text = "data"
        
        mock_sent = Mock()
        mock_sent.__iter__ = Mock(return_value=iter([mock_token1, mock_token2]))
        
        mock_doc = Mock()
        mock_doc.__iter__ = Mock(return_value=iter([mock_token1, mock_token2]))
        mock_doc.sents = [mock_sent]
        
        mock_nlp = Mock(return_value=mock_doc)
        
        nlp_engine = SpacyNLP()
        nlp_engine._nlp = mock_nlp
        
        result = nlp_engine.analyze_sentiment("The data is here.")
        
        assert result["polarity"] == "neutral"
        assert "neutral" in result["tone"]
    
    def test_analyze_sentiment_without_spacy(self):
        """Test sentiment analysis fallback when spaCy unavailable."""
        nlp_engine = SpacyNLP()
        nlp_engine._nlp = None
        
        with patch("services.spacy_nlp._load_model", return_value=None):
            result = nlp_engine.analyze_sentiment("Some text")
        
        # Should return neutral sentiment as fallback
        assert result["polarity"] == "neutral"
        assert result["confidence"] == 0.0
        assert result["tone"] == []
    
    def test_lazy_model_loading(self):
        """Test that model is loaded lazily on first use."""
        with patch("services.spacy_nlp._load_model") as mock_load:
            mock_load.return_value = Mock()
            
            nlp_engine = SpacyNLP()
            
            # Model not loaded yet
            assert nlp_engine._nlp is None
            
            # First use triggers loading
            nlp_engine._ensure_model()
            
            assert mock_load.called
            assert nlp_engine._nlp is not None


class TestModuleFunctions:
    """Test module-level functions."""
    
    def test_is_spacy_available_true(self):
        """Test spaCy availability check when installed."""
        with patch("services.spacy_nlp._SPACY_AVAILABLE", None):
            with patch("builtins.__import__", return_value=Mock()):
                result = _is_spacy_available()
                assert result is True
    
    def test_is_spacy_available_false(self):
        """Test spaCy availability check when not installed."""
        with patch("services.spacy_nlp._SPACY_AVAILABLE", None):
            with patch("builtins.__import__", side_effect=ImportError()):
                result = _is_spacy_available()
                assert result is False
    
    def test_load_model_success(self):
        """Test successful model loading."""
        with patch("services.spacy_nlp._SPACY_NLP_MODEL", None):
            with patch("services.spacy_nlp._is_spacy_available", return_value=True):
                mock_spacy = Mock()
                mock_model = Mock()
                mock_spacy.load = Mock(return_value=mock_model)
                
                with patch.dict("sys.modules", {"spacy": mock_spacy}):
                    result = _load_model("en_core_web_sm")
                
                assert result is not None
                mock_spacy.load.assert_called_once_with("en_core_web_sm")
    
    def test_load_model_not_found(self):
        """Test model loading when model not found."""
        with patch("services.spacy_nlp._SPACY_NLP_MODEL", None):
            with patch("services.spacy_nlp._is_spacy_available", return_value=True):
                mock_spacy = Mock()
                mock_spacy.load = Mock(side_effect=OSError("Model not found"))
                
                with patch.dict("sys.modules", {"spacy": mock_spacy}):
                    result = _load_model("en_core_web_sm")
                
                assert result is None
    
    def test_get_spacy_nlp_singleton(self):
        """Test singleton pattern for get_spacy_nlp."""
        with patch("services.spacy_nlp._default_instance", None):
            instance1 = get_spacy_nlp()
            instance2 = get_spacy_nlp()
            
            assert instance1 is instance2


class TestFactSuggestion:
    """Test fact suggestion for truth gate integration."""
    
    def test_suggest_matching_facts_with_spacy(self):
        """Test fact suggestion when spaCy is available."""
        # Mock spaCy doc with similarity
        mock_sent_doc = Mock()
        mock_sent_doc.has_vector = True
        mock_sent_doc.similarity = Mock(side_effect=[0.85, 0.60, 0.40])
        
        mock_fact_doc1 = Mock()
        mock_fact_doc1.has_vector = True
        
        mock_fact_doc2 = Mock()
        mock_fact_doc2.has_vector = True
        
        mock_fact_doc3 = Mock()
        mock_fact_doc3.has_vector = True
        
        mock_nlp = Mock(side_effect=[mock_sent_doc, mock_fact_doc1, mock_fact_doc2, mock_fact_doc3])
        
        nlp_engine = SpacyNLP()
        nlp_engine._nlp = mock_nlp
        
        dropped_sentence = "I worked with Spring Boot and Neo4j at Acme Corp in 2020"
        available_facts = [
            "Project A | Built microservices with Spring Boot and PostgreSQL",
            "Project B | Implemented graph database with Neo4j",
            "Project C | Developed React frontend with TypeScript",
        ]
        
        result = nlp_engine.suggest_matching_facts(
            dropped_sentence=dropped_sentence,
            available_facts=available_facts,
            top_n=3,
        )
        
        # Should return 3 suggestions sorted by similarity
        assert len(result) == 3
        assert result[0]["similarity"] == 0.85
        assert result[1]["similarity"] == 0.60
        assert result[2]["similarity"] == 0.40
        assert "suggestion" in result[0]
        assert "fact" in result[0]
    
    def test_suggest_matching_facts_without_spacy(self):
        """Test fact suggestion fallback when spaCy unavailable."""
        nlp_engine = SpacyNLP()
        nlp_engine._nlp = None
        
        with patch("services.spacy_nlp._load_model", return_value=None):
            result = nlp_engine.suggest_matching_facts(
                dropped_sentence="test sentence",
                available_facts=["fact 1", "fact 2"],
            )
        
        # Should return empty list as fallback
        assert result == []
    
    def test_suggest_matching_facts_no_vectors(self):
        """Test fact suggestion when vectors unavailable."""
        mock_doc = Mock()
        mock_doc.has_vector = False
        
        mock_nlp = Mock(return_value=mock_doc)
        
        nlp_engine = SpacyNLP()
        nlp_engine._nlp = mock_nlp
        
        result = nlp_engine.suggest_matching_facts(
            dropped_sentence="test",
            available_facts=["fact"],
        )
        
        # Should return empty list
        assert result == []


class TestArticleSummarization:
    """Test article summarization functionality."""
    
    def test_summarize_article_with_spacy(self):
        """Test article summarization when spaCy is available."""
        # Create mock sentences
        mock_sent1 = Mock()
        mock_sent1.text = "OpenAI released GPT-4."
        mock_sent1.start = 0
        mock_sent1.ents = [Mock()]
        mock_sent1.__iter__ = Mock(return_value=iter([Mock()] * 10))
        
        mock_sent2 = Mock()
        mock_sent2.text = "The model shows significant improvements."
        mock_sent2.start = 1
        mock_sent2.ents = [Mock(), Mock()]
        mock_sent2.__iter__ = Mock(return_value=iter([Mock()] * 15))
        
        mock_sent3 = Mock()
        mock_sent3.text = "This is a minor detail."
        mock_sent3.start = 2
        mock_sent3.ents = []
        mock_sent3.__iter__ = Mock(return_value=iter([Mock()] * 8))
        
        mock_doc = Mock()
        mock_doc.sents = [mock_sent1, mock_sent2, mock_sent3]
        
        mock_nlp = Mock(return_value=mock_doc)
        
        nlp_engine = SpacyNLP()
        nlp_engine._nlp = mock_nlp
        
        article_text = "OpenAI released GPT-4. The model shows significant improvements. This is a minor detail."
        
        result = nlp_engine.summarize_article(
            article_text=article_text,
            max_sentences=2,
            focus_entities=True,
        )
        
        # Should return a summary with the most important sentences
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_summarize_article_without_spacy(self):
        """Test article summarization fallback when spaCy unavailable."""
        nlp_engine = SpacyNLP()
        nlp_engine._nlp = None
        
        article_text = "Sentence one. Sentence two. Sentence three. Sentence four."
        
        with patch("services.spacy_nlp._load_model", return_value=None):
            result = nlp_engine.summarize_article(
                article_text=article_text,
                max_sentences=2,
            )
        
        # Should return first 2 sentences as fallback
        assert "Sentence one" in result
        assert "Sentence two" in result


class TestSelectionLearningIntegration:
    """Test spaCy integration with selection_learning module."""
    
    def test_log_candidate_with_nlp(self):
        """Test that log_candidate extracts themes and sentiment."""
        from services.selection_learning import log_candidate, make_candidate_id
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "candidates.jsonl"
            
            # Mock the spaCy NLP engine
            with patch("services.selection_learning.get_spacy_nlp") as mock_get_nlp:
                mock_nlp = Mock()
                mock_nlp.extract_themes = Mock(return_value=["ai", "machine learning"])
                mock_nlp.analyze_sentiment = Mock(return_value={
                    "polarity": "positive",
                    "confidence": 0.8,
                    "tone": ["professional"]
                })
                mock_get_nlp.return_value = mock_nlp
                
                result = log_candidate(
                    candidate_id=make_candidate_id(),
                    article_url="https://example.com/article",
                    article_title="AI News",
                    article_source="Tech Blog",
                    ssi_component="establish_brand",
                    channel="linkedin",
                    post_text="Exciting advances in AI and machine learning!",
                    buffer_id=None,
                    route="post",
                    run_id="test-run",
                    path=test_path,
                    enable_nlp=True,
                )
                
                assert result.themes == ["ai", "machine learning"]
                assert result.sentiment["polarity"] == "positive"
                mock_nlp.extract_themes.assert_called_once()
                mock_nlp.analyze_sentiment.assert_called_once()
    
    def test_log_candidate_without_nlp(self):
        """Test that log_candidate works with NLP disabled."""
        from services.selection_learning import log_candidate, make_candidate_id
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "candidates.jsonl"
            
            result = log_candidate(
                candidate_id=make_candidate_id(),
                article_url="https://example.com/article",
                article_title="AI News",
                article_source="Tech Blog",
                ssi_component="establish_brand",
                channel="linkedin",
                post_text="Test post",
                buffer_id=None,
                route="post",
                run_id="test-run",
                path=test_path,
                enable_nlp=False,
            )
            
            assert result.themes == []
            assert result.sentiment == {}
    
    def test_find_similar_candidates(self):
        """Test similarity-based repetition detection."""
        from services.selection_learning import find_similar_candidates
        
        candidates = [
            {"candidate_id": "1", "text_snippet": "AI is transforming the world"},
            {"candidate_id": "2", "text_snippet": "Machine learning advances"},
            {"candidate_id": "3", "text_snippet": "Completely different topic"},
        ]
        
        with patch("services.selection_learning.get_spacy_nlp") as mock_get_nlp:
            mock_nlp = Mock()
            # High similarity for first two, low for third
            mock_nlp.compute_similarity = Mock(side_effect=[0.85, 0.12])
            mock_get_nlp.return_value = mock_nlp
            
            result = find_similar_candidates(
                "AI is changing everything",
                candidates=candidates,
                similarity_threshold=0.75,
            )
            
            # Should only return the first candidate (high similarity)
            assert len(result) == 1
            assert result[0]["candidate_id"] == "1"
            assert result[0]["similarity_score"] == 0.85


class TestMultiLanguageSpacyNLP:
    """Test suite for multi-language spaCy support."""

    def test_detect_language(self):
        from services.spacy_nlp import detect_language

        assert detect_language("Hello world") == "en"
        assert detect_language("こんにちは世界") == "ja"
        assert detect_language("Python 3.12 と spaCy NLP") == "ja"
        assert detect_language("Software engineering best practices") == "en"

    def test_multi_language_init(self):
        nlp_engine = SpacyNLP(
            model_name="en_core_web_md",
            model_names="en_core_web_md,ja_core_news_md",
        )
        assert nlp_engine.model_name == "en_core_web_md"
        assert "en_core_web_md" in nlp_engine.model_names
        assert "ja_core_news_md" in nlp_engine.model_names

    def test_get_model_for_text_auto_routing(self):
        mock_en_nlp = Mock()
        mock_ja_nlp = Mock()

        nlp_engine = SpacyNLP(
            model_name="en_core_web_md",
            model_names=["en_core_web_md", "ja_core_news_md"],
        )

        def mock_load_by_name(name):
            if name.startswith("ja"):
                return mock_ja_nlp
            return mock_en_nlp

        with patch.object(nlp_engine, "_ensure_model_by_name", side_effect=mock_load_by_name):
            en_model = nlp_engine.get_model_for_text("Building AI pipelines with Python")
            ja_model = nlp_engine.get_model_for_text("AIパイプラインと信号処理の構築")

            assert en_model is mock_en_nlp
            assert ja_model is mock_ja_nlp

    def test_japanese_fallback_only_tries_default_medium_model(self):
        """Unconfigured Japanese routing must not probe optional sm/lg models."""
        mock_ja_nlp = Mock()
        nlp_engine = SpacyNLP(model_name="en_core_web_md")

        with patch.object(
            nlp_engine,
            "_ensure_model_by_name",
            return_value=mock_ja_nlp,
        ) as mock_load:
            result = nlp_engine.get_model_for_text("AIパイプラインと信号処理の構築")

        assert result is mock_ja_nlp
        mock_load.assert_called_once_with("ja_core_news_md")

    def test_japanese_sentiment_analysis(self):
        mock_token1 = Mock()
        mock_token1.text = "素晴らしい"
        mock_token2 = Mock()
        mock_token2.text = "成功"

        mock_sent = Mock()
        mock_sent.__iter__ = Mock(return_value=iter([mock_token1, mock_token2]))

        mock_doc = Mock()
        mock_doc.__iter__ = Mock(return_value=iter([mock_token1, mock_token2]))
        mock_doc.sents = [mock_sent]

        mock_nlp = Mock(return_value=mock_doc)

        nlp_engine = SpacyNLP(model_name="ja_core_news_md")
        nlp_engine._nlp = mock_nlp

        result = nlp_engine.analyze_sentiment("このシステムは素晴らしい成功です！", lang="ja")

        assert result["polarity"] == "positive"
        assert result["confidence"] > 0.5
        assert "enthusiastic" in result["tone"]

    def test_get_spacy_nlp_loads_spacy_models_env(self):
        with patch.dict(
            "os.environ",
            {
                "SPACY_MODEL": "en_core_web_md",
                "SPACY_MODELS": "en_core_web_md,ja_core_news_md",
            },
        ):
            with patch("services.spacy_nlp._default_instance", None):
                instance = get_spacy_nlp()
                assert instance.model_name == "en_core_web_md"
                assert "ja_core_news_md" in instance.model_names

