"""
spaCy NLP Engine — theme extraction, semantic similarity, and sentiment analysis.

This module provides advanced NLP capabilities for the LinkedIn SSI Booster:
- Multi-language support (English, Japanese, etc.) with automatic model selection
- Theme/claim extraction using NER and noun chunking
- Semantic similarity using spaCy word vectors
- Sentiment/tone analysis for content moderation
- Fact suggestion for truth gate
- Contextual article summarization

The design ensures:
- Lazy model loading (on first use)
- Multi-model routing (English + Japanese + others)
- Graceful fallbacks if spaCy unavailable
- Mockable interface for testing
- Minimal performance overhead (<1s per post)
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

# Global cache for spaCy models to avoid reloading
_SPACY_NLP_MODELS: dict[str, Any] = {}
_SPACY_NLP_MODEL: Any = None  # Alias for primary model (backward compatibility)
_SPACY_AVAILABLE: bool | None = None

_JAPANESE_CHAR_RE = re.compile(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]")


def detect_language(text: str) -> str:
    """Basic character-set language detection.

    Returns 'ja' if Japanese characters (Hiragana, Katakana, Kanji) are present,
    else 'en'.
    """
    if _JAPANESE_CHAR_RE.search(text):
        return "ja"
    return "en"


def _is_spacy_available() -> bool:
    """Check if spaCy is available and can be imported."""
    global _SPACY_AVAILABLE
    if _SPACY_AVAILABLE is not None:
        return _SPACY_AVAILABLE

    try:
        import spacy  # noqa: F401

        _SPACY_AVAILABLE = True
        return True
    except Exception as exc:
        logger.warning("spacy_nlp: spaCy not available — NLP features disabled (%s)", exc)
        _SPACY_AVAILABLE = False
        return False


def _load_model(model_name: str = "en_core_web_sm") -> Any:
    """Load a spaCy model, caching it globally. Returns None if unavailable."""
    global _SPACY_NLP_MODELS, _SPACY_NLP_MODEL

    # If _SPACY_NLP_MODEL is explicitly patched to None in test suite, clear model cache
    if _SPACY_NLP_MODEL is None and _SPACY_NLP_MODELS:
        _SPACY_NLP_MODELS.clear()

    if model_name in _SPACY_NLP_MODELS:
        return _SPACY_NLP_MODELS[model_name]

    if not _is_spacy_available():
        return None

    try:
        import spacy

        nlp = spacy.load(model_name)
        _SPACY_NLP_MODELS[model_name] = nlp
        _SPACY_NLP_MODEL = nlp
        logger.info("spacy_nlp: loaded model '%s'", model_name)
        return nlp
    except OSError:
        logger.warning(
            "spacy_nlp: model '%s' not found — run 'python -m spacy download %s'",
            model_name,
            model_name,
        )
        return None
    except Exception as exc:
        logger.warning("spacy_nlp: failed to load model '%s': %s", model_name, exc)
        return None


class SpacyNLP:
    """spaCy NLP Engine for theme extraction, similarity, and sentiment analysis.

    Supports multi-language spaCy pipelines (e.g. English, Japanese) with auto-routing
    based on character set detection or explicit language tags.

    All methods gracefully degrade if spaCy is unavailable, returning
    fallback values (empty lists, 0.0 similarity, neutral sentiment).
    """

    def __init__(
        self,
        model_name: str = "en_core_web_sm",
        model_names: list[str] | str | None = None,
    ):
        """Initialize the NLP engine with specified spaCy models.

        Args:
            model_name: Primary spaCy model to use (default: en_core_web_sm)
            model_names: List or comma-separated string of additional/all models to support
                         (e.g., ["en_core_web_md", "ja_core_news_md"])
        """
        self.model_name = model_name
        self.model_names: list[str] = []

        if isinstance(model_names, str):
            self.model_names = [m.strip() for m in model_names.split(",") if m.strip()]
        elif isinstance(model_names, list):
            self.model_names = [
                m.strip() for m in model_names if isinstance(m, str) and m.strip()
            ]

        if self.model_name not in self.model_names:
            self.model_names.insert(0, self.model_name)

        self._nlp = None  # Cache for primary model (test compatibility)
        self._nlp_models: dict[str, Any] = {}

    def _ensure_model(self) -> Any:
        """Lazy load the primary spaCy model on first use."""
        if self._nlp is None:
            self._nlp = self._ensure_model_by_name(self.model_name)
        return self._nlp

    def _ensure_model_by_name(self, model_name: str) -> Any:
        """Lazy load a specific spaCy model by name."""
        if model_name in self._nlp_models:
            return self._nlp_models[model_name]

        if model_name == self.model_name and self._nlp is not None:
            self._nlp_models[model_name] = self._nlp
            return self._nlp

        nlp_inst = _load_model(model_name)
        if nlp_inst is not None:
            self._nlp_models[model_name] = nlp_inst
            if model_name == self.model_name:
                self._nlp = nlp_inst
        return nlp_inst

    def get_model_for_text(self, text: str = "", lang: str | None = None) -> Any:
        """Select and lazy-load appropriate spaCy model based on text or explicit language code.

        Args:
            text: Text to analyze (used for auto-detecting language if lang not provided)
            lang: Explicit language code ('ja', 'japanese', 'en', 'english') or model name

        Returns:
            Loaded spaCy NLP model, or None if unavailable.
        """
        target_lang = None
        if lang:
            lang_str = lang.lower().strip()
            if lang_str in {
                "ja",
                "japanese",
                "ja_core_news_md",
                "ja_core_news_sm",
                "ja_core_news_lg",
            }:
                target_lang = "ja"
            elif lang_str in {
                "en",
                "english",
                "en_core_web_md",
                "en_core_web_sm",
                "en_core_web_lg",
            }:
                target_lang = "en"
            elif "_" in lang_str:
                target_lang = lang_str.split("_")[0]
        elif text:
            target_lang = detect_language(text)

        if target_lang:
            for m_name in self.model_names:
                if m_name.startswith(f"{target_lang}_"):
                    nlp_inst = self._ensure_model_by_name(m_name)
                    if nlp_inst is not None:
                        return nlp_inst

            # If target is Japanese and not yet in model_names, attempt standard ja models
            if target_lang == "ja":
                for ja_candidate in (
                    "ja_core_news_md",
                    "ja_core_news_sm",
                    "ja_core_news_lg",
                ):
                    nlp_inst = self._ensure_model_by_name(ja_candidate)
                    if nlp_inst is not None:
                        if ja_candidate not in self.model_names:
                            self.model_names.append(ja_candidate)
                        return nlp_inst

        return self._ensure_model()

    def extract_themes(self, text: str, lang: str | None = None) -> list[str]:
        """Extract themes/topics from text using NER and noun chunks.

        Combines:
        - Named entities (PERSON, ORG, GPE, PRODUCT, etc.)
        - Noun chunks (meaningful noun phrases)

        Returns a deduplicated list of themes, normalized to lowercase.
        Falls back to empty list if spaCy unavailable.

        Args:
            text: Input text to analyze
            lang: Optional language code ('ja', 'en') or model override

        Returns:
            List of extracted theme strings
        """
        nlp = self.get_model_for_text(text, lang=lang)
        if nlp is None:
            logger.debug("spacy_nlp: extract_themes fallback (spaCy unavailable)")
            return []

        try:
            doc = nlp(text)
            themes: set[str] = set()

            # Extract named entities
            for ent in doc.ents:
                if ent.label_ in {
                    "PERSON",
                    "ORG",
                    "GPE",
                    "PRODUCT",
                    "EVENT",
                    "WORK_OF_ART",
                    "LAW",
                    "LANGUAGE",
                    "NORP",
                    "FAC",
                    "LOC",
                    "DATE",
                    "TIME",
                }:
                    themes.add(ent.text.lower().strip())

            # Safely extract noun chunks (some language models like Japanese may not implement noun_chunks)
            try:
                if hasattr(doc, "noun_chunks"):
                    for chunk in doc.noun_chunks:
                        chunk_text = chunk.text.lower().strip()
                        if (
                            len(chunk_text.split()) >= 2
                            or len(chunk_text) >= 5
                            or detect_language(chunk_text) == "ja"
                        ):
                            themes.add(chunk_text)
            except (NotImplementedError, AttributeError, Exception):
                pass

            return sorted(themes)

        except Exception as exc:
            logger.warning("spacy_nlp: extract_themes failed: %s", exc)
            return []

    def compute_similarity(
        self, text1: str, text2: str, lang: str | None = None
    ) -> float:
        """Compute semantic similarity between two texts using spaCy vectors.

        Returns cosine similarity (0.0–1.0) based on document vectors.
        Falls back to 0.0 if spaCy unavailable or vectors not present.

        Args:
            text1: First text
            text2: Second text
            lang: Optional language code ('ja', 'en') or model override

        Returns:
            Similarity score (0.0 = dissimilar, 1.0 = identical)
        """
        nlp = self.get_model_for_text(text1 + " " + text2, lang=lang)
        if nlp is None:
            logger.debug("spacy_nlp: compute_similarity fallback (spaCy unavailable)")
            return 0.0

        try:
            doc1 = nlp(text1)
            doc2 = nlp(text2)

            # Check if vectors are available
            if not doc1.has_vector or not doc2.has_vector:
                logger.debug("spacy_nlp: compute_similarity fallback (no vectors)")
                return 0.0

            similarity = doc1.similarity(doc2)
            return max(0.0, min(1.0, float(similarity)))

        except Exception as exc:
            logger.warning("spacy_nlp: compute_similarity failed: %s", exc)
            return 0.0

    def analyze_sentiment(
        self, text: str, lang: str | None = None
    ) -> dict[str, Any]:
        """Analyze sentiment and tone of text.

        Args:
            text: Input text to analyze
            lang: Optional language code ('ja', 'en') or model override

        Returns:
            Dict with keys: polarity, confidence, tone
        """
        nlp = self.get_model_for_text(text, lang=lang)
        if nlp is None:
            logger.debug("spacy_nlp: analyze_sentiment fallback (spaCy unavailable)")
            return {"polarity": "neutral", "confidence": 0.0, "tone": []}

        try:
            doc = nlp(text)

            positive_words = {
                "great",
                "excellent",
                "amazing",
                "wonderful",
                "fantastic",
                "love",
                "best",
                "perfect",
                "awesome",
                "brilliant",
                "excited",
                "happy",
                "delighted",
                "thrilled",
                "proud",
                "素晴らしい",
                "最高",
                "成功",
                "完璧",
                "感動",
                "期待",
                "輝く",
            }
            negative_words = {
                "bad",
                "terrible",
                "awful",
                "horrible",
                "worst",
                "hate",
                "disappointed",
                "frustrated",
                "angry",
                "sad",
                "poor",
                "weak",
                "failed",
                "broken",
                "wrong",
                "失敗",
                "最悪",
                "エラー",
                "問題",
                "遅延",
                "障壁",
                "欠陥",
            }

            tokens = list(doc)
            pos_count = sum(
                1 for token in tokens if token.text.lower() in positive_words
            )
            neg_count = sum(
                1 for token in tokens if token.text.lower() in negative_words
            )

            if pos_count > neg_count:
                polarity = "positive"
                confidence = min(0.9, 0.5 + (pos_count - neg_count) * 0.1)
            elif neg_count > pos_count:
                polarity = "negative"
                confidence = min(0.9, 0.5 + (neg_count - pos_count) * 0.1)
            else:
                polarity = "neutral"
                confidence = 0.6

            tone: list[str] = []

            sents = list(doc.sents) if hasattr(doc, "sents") else [doc]
            avg_sent_len = sum(len(list(sent)) for sent in sents) / max(
                1, len(sents)
            )
            if avg_sent_len > 15:
                tone.append("professional")

            if "!" in text or "！" in text:
                tone.append("enthusiastic")

            if "?" in text or "？" in text:
                tone.append("inquisitive")

            if not tone:
                tone.append("neutral")

            return {
                "polarity": polarity,
                "confidence": confidence,
                "tone": tone,
            }

        except Exception as exc:
            logger.warning("spacy_nlp: analyze_sentiment failed: %s", exc)
            return {"polarity": "neutral", "confidence": 0.0, "tone": []}

    def suggest_matching_facts(
        self,
        dropped_sentence: str,
        available_facts: list[str],
        top_n: int = 3,
        lang: str | None = None,
    ) -> list[dict[str, Any]]:
        """Suggest the closest matching facts for a dropped sentence."""
        nlp = self.get_model_for_text(dropped_sentence, lang=lang)
        if nlp is None or not available_facts:
            logger.debug(
                "spacy_nlp: suggest_matching_facts fallback (spaCy unavailable or no facts)"
            )
            return []

        try:
            sent_doc = nlp(dropped_sentence)
            if not sent_doc.has_vector:
                logger.debug("spacy_nlp: suggest_matching_facts fallback (no vectors)")
                return []

            suggestions: list[tuple[float, str]] = []

            for fact in available_facts:
                fact_doc = nlp(fact)
                if not fact_doc.has_vector:
                    continue

                similarity = sent_doc.similarity(fact_doc)
                suggestions.append((similarity, fact))

            suggestions.sort(key=lambda x: x[0], reverse=True)
            top_suggestions = suggestions[:top_n]

            results: list[dict[str, Any]] = []
            for sim, fact in top_suggestions:
                suggestion_text = self._generate_rephrase_suggestion(
                    dropped_sentence, fact, sim
                )
                results.append({
                    "fact": fact,
                    "similarity": round(sim, 3),
                    "suggestion": suggestion_text,
                })

            return results

        except Exception as exc:
            logger.warning("spacy_nlp: suggest_matching_facts failed: %s", exc)
            return []

    def _generate_rephrase_suggestion(
        self,
        sentence: str,
        fact: str,
        similarity: float,
    ) -> str:
        """Generate a rephrase suggestion based on similarity score."""
        if similarity > 0.75:
            return "High match — consider incorporating key terms from this fact"
        elif similarity > 0.5:
            return "Moderate match — rephrase to align more closely with this evidence"
        else:
            return "Low match — this fact may not support the claim; consider different evidence"

    def summarize_article(
        self,
        article_text: str,
        max_sentences: int = 3,
        focus_entities: bool = True,
        lang: str | None = None,
    ) -> str:
        """Generate a concise, context-aware summary of an article."""
        nlp = self.get_model_for_text(article_text, lang=lang)
        if nlp is None:
            logger.debug("spacy_nlp: summarize_article fallback (spaCy unavailable)")
            sentences = [
                s.strip() for s in re.split(r"[。\n.]+", article_text) if s.strip()
            ][:max_sentences]
            return ". ".join(sentences) + "."

        try:
            doc = nlp(article_text)

            sentence_scores: list[tuple[float, Any]] = []

            for sent in doc.sents:
                score = 0.0

                if focus_entities:
                    entity_count = len([ent for ent in sent.ents])
                    score += entity_count * 2.0

                position_score = 1.0 / (1.0 + len(sentence_scores))
                score += position_score

                length = len(list(sent))
                if 10 <= length <= 25:
                    score += 1.0
                elif length > 5:
                    score += 0.5

                text_lower = sent.text.lower()
                if any(
                    marker in text_lower
                    for marker in [
                        "new",
                        "announce",
                        "launch",
                        "release",
                        "breakthrough",
                        "significant",
                        "important",
                        "key",
                        "major",
                        "発表",
                        "新",
                        "開発",
                        "公開",
                        "導入",
                    ]
                ):
                    score += 1.5

                sentence_scores.append((score, sent))

            sentence_scores.sort(key=lambda x: x[0], reverse=True)
            top_sentences = sentence_scores[:max_sentences]

            top_sentences.sort(key=lambda x: x[1].start)

            summary = " ".join(sent.text.strip() for _, sent in top_sentences)
            return summary

        except Exception as exc:
            logger.warning("spacy_nlp: summarize_article failed: %s", exc)
            sentences = [
                s.strip() for s in re.split(r"[。\n.]+", article_text) if s.strip()
            ][:max_sentences]
            return ". ".join(sentences) + "."


_default_instance: SpacyNLP | None = None


def get_spacy_nlp() -> SpacyNLP:
    """Return the default singleton SpacyNLP instance.

    The primary model is selected via the ``SPACY_MODEL`` env var
    (default: ``en_core_web_md``). Additional language packs/models
    can be configured via ``SPACY_MODELS`` or ``SPACY_LANGUAGE_PACKS``
    (e.g., ``en_core_web_md,ja_core_news_md``).
    """
    global _default_instance
    if _default_instance is None:
        primary = os.getenv("SPACY_MODEL", "en_core_web_md")
        models_env = os.getenv("SPACY_MODELS") or os.getenv("SPACY_LANGUAGE_PACKS")
        _default_instance = SpacyNLP(model_name=primary, model_names=models_env)
    return _default_instance

