"""Tests for the shared search tokenizer and batched similarity helpers.

These back the BM25 call sites in ``console_grounding``, ``hybrid_retriever``
and ``avatar_intelligence``, so the regex fallback path matters as much as the
spaCy path: English models are frequently absent outside Docker.
"""

from unittest.mock import MagicMock, patch

import pytest

from services.spacy_nlp import (
    SpacyNLP,
    regex_tokens,
    tokenize_for_search,
    tokenize_many_for_search,
)

_PATCH_ENGINE = "services.spacy_nlp.get_spacy_nlp"


def _fake_doc(tokens: list[tuple[str, str]]) -> list[MagicMock]:
    """Build a doc-like iterable of (text, lemma) pairs."""
    docs = []
    for text, lemma in tokens:
        tok = MagicMock()
        tok.text = text
        tok.lemma_ = lemma
        tok.is_space = False
        tok.is_punct = False
        tok.is_stop = False
        docs.append(tok)
    return docs


class TestRegexTokens:
    def test_lowercases_and_drops_single_characters(self) -> None:
        assert regex_tokens("Built RAG a X pipeline") == [
            "built",
            "rag",
            "pipeline",
        ]

    def test_keeps_technical_punctuation(self) -> None:
        # No stopword filtering here — that only happens on the spaCy path.
        assert regex_tokens("C++ and F# on .NET") == [
            "c++",
            "and",
            "f#",
            "on",
            ".net",
        ]

    def test_returns_almost_nothing_for_japanese(self) -> None:
        # This is precisely why it is a fallback only.
        assert regex_tokens("新宿でライブを観る") == []

    def test_empty_string(self) -> None:
        assert regex_tokens("") == []


class TestTokenizeManyForSearch:
    def test_empty_input_returns_empty_list(self) -> None:
        assert tokenize_many_for_search([]) == []

    def test_falls_back_to_regex_when_model_missing(self) -> None:
        engine = MagicMock()
        engine.get_model_for_text.return_value = None
        with patch(_PATCH_ENGINE, return_value=engine):
            assert tokenize_many_for_search(["Built a RAG pipeline"]) == [
                ["built", "rag", "pipeline"]
            ]

    def test_uses_lemmas_when_model_available(self) -> None:
        nlp = MagicMock()
        nlp.pipe_names = ["tok2vec", "morphologizer", "parser", "ner"]
        nlp.pipe.return_value = iter(
            [_fake_doc([("観る", "観る"), ("ライブ", "ライブ")])]
        )
        engine = MagicMock()
        engine.get_model_for_text.return_value = nlp

        with patch(_PATCH_ENGINE, return_value=engine):
            assert tokenize_many_for_search(["ライブを観る"]) == [["観る", "ライブ"]]

        # parser/ner contribute nothing to tokenization and are disabled.
        assert nlp.pipe.call_args.kwargs["disable"] == ["parser", "ner"]

    def test_only_disables_components_present_in_pipeline(self) -> None:
        nlp = MagicMock()
        nlp.pipe_names = ["tok2vec", "ner"]
        nlp.pipe.return_value = iter([_fake_doc([("built", "build")])])
        engine = MagicMock()
        engine.get_model_for_text.return_value = nlp

        with patch(_PATCH_ENGINE, return_value=engine):
            tokenize_many_for_search(["built"])

        assert nlp.pipe.call_args.kwargs["disable"] == ["ner"]

    def test_routes_mixed_language_corpus_per_language(self) -> None:
        engine = MagicMock()
        engine.get_model_for_text.return_value = None
        with patch(_PATCH_ENGINE, return_value=engine):
            tokenize_many_for_search(["Built a pipeline", "新宿でライブ", "more text"])

        langs = {
            call.kwargs["lang"] for call in engine.get_model_for_text.call_args_list
        }
        assert langs == {"en", "ja"}
        # One model lookup per language, not one per document.
        assert engine.get_model_for_text.call_count == 2

    def test_preserves_input_order_across_language_groups(self) -> None:
        engine = MagicMock()
        engine.get_model_for_text.return_value = None
        with patch(_PATCH_ENGINE, return_value=engine):
            result = tokenize_many_for_search(["alpha beta", "新宿", "gamma delta"])

        assert result[0] == ["alpha", "beta"]
        assert result[1] == []
        assert result[2] == ["gamma", "delta"]

    def test_falls_back_when_pipe_yields_no_doc(self) -> None:
        nlp = MagicMock()
        nlp.pipe_names = []
        nlp.pipe.return_value = iter([])
        engine = MagicMock()
        engine.get_model_for_text.return_value = nlp

        with patch(_PATCH_ENGINE, return_value=engine):
            assert tokenize_many_for_search(["Built a pipeline"]) == [
                ["built", "pipeline"]
            ]

    def test_falls_back_when_pipe_raises(self) -> None:
        nlp = MagicMock()
        nlp.pipe_names = []
        nlp.pipe.side_effect = RuntimeError("model exploded")
        engine = MagicMock()
        engine.get_model_for_text.return_value = nlp

        with patch(_PATCH_ENGINE, return_value=engine):
            assert tokenize_many_for_search(["Built a pipeline"]) == [
                ["built", "pipeline"]
            ]

    def test_falls_back_when_lemmas_are_all_filtered(self) -> None:
        nlp = MagicMock()
        nlp.pipe_names = []
        nlp.pipe.return_value = iter([[]])
        engine = MagicMock()
        engine.get_model_for_text.return_value = nlp

        with patch(_PATCH_ENGINE, return_value=engine):
            assert tokenize_many_for_search(["Built a pipeline"]) == [
                ["built", "pipeline"]
            ]

    def test_explicit_lang_skips_detection(self) -> None:
        engine = MagicMock()
        engine.get_model_for_text.return_value = None
        with patch(_PATCH_ENGINE, return_value=engine):
            tokenize_many_for_search(["新宿でライブ"], lang="en")

        assert engine.get_model_for_text.call_args.kwargs["lang"] == "en"


class TestTokenizeForSearch:
    def test_single_text_wrapper(self) -> None:
        engine = MagicMock()
        engine.get_model_for_text.return_value = None
        with patch(_PATCH_ENGINE, return_value=engine):
            assert tokenize_for_search("Built a RAG pipeline") == [
                "built",
                "rag",
                "pipeline",
            ]

    def test_empty_string_returns_empty_list(self) -> None:
        engine = MagicMock()
        engine.get_model_for_text.return_value = None
        with patch(_PATCH_ENGINE, return_value=engine):
            assert tokenize_for_search("") == []


class TestComputeSimilarityBatch:
    """The base text must be parsed once and candidates piped in one batch."""

    def _engine_with_model(self, nlp: MagicMock) -> SpacyNLP:
        engine = SpacyNLP.__new__(SpacyNLP)
        engine._nlp_models = {}  # type: ignore[attr-defined]
        engine.get_model_for_text = MagicMock(return_value=nlp)  # type: ignore[method-assign]
        return engine

    def test_empty_candidates_returns_empty_list(self) -> None:
        engine = self._engine_with_model(MagicMock())
        assert engine.compute_similarity_batch("anything", []) == []

    def test_returns_one_score_per_candidate(self) -> None:
        base = MagicMock()
        base.similarity.side_effect = [0.9, 0.1]
        nlp = MagicMock()
        nlp.return_value = base
        nlp.pipe.return_value = iter([MagicMock(), MagicMock()])

        engine = self._engine_with_model(nlp)
        assert engine.compute_similarity_batch("base", ["a", "b"]) == [0.9, 0.1]

        # Base text parsed exactly once, candidates batched through pipe.
        assert nlp.call_count == 1
        assert nlp.pipe.call_count == 1

    def test_returns_zeros_when_model_unavailable(self) -> None:
        engine = SpacyNLP.__new__(SpacyNLP)
        engine._nlp_models = {}  # type: ignore[attr-defined]
        engine.get_model_for_text = MagicMock(return_value=None)  # type: ignore[method-assign]

        assert engine.compute_similarity_batch("base", ["a", "b"]) == [0.0, 0.0]


class TestBuildBm25Index:
    def test_returns_none_for_empty_corpus(self) -> None:
        from services.console_grounding._gate_helpers import build_bm25_index

        assert build_bm25_index("", []) is None

    def test_prebuilt_index_matches_on_demand_score(self) -> None:
        from services.console_grounding._gate_helpers import (
            _score_sentence_bm25,
            build_bm25_index,
        )
        from services.console_grounding._models import ProjectFact

        def _fact(project: str, details: str) -> ProjectFact:
            return ProjectFact(
                project=project,
                company="Acme",
                years="2024",
                details=details,
                source="test",
                tags=set(),
            )

        # BM25 needs more than one document for IDF to be meaningful.
        facts = [
            _fact("RAG Pipeline", "Built a retrieval pipeline with BM25"),
            _fact("Voice Avatar", "Neural text to speech on a local GPU"),
        ]
        sentence = "We built a retrieval pipeline."

        with_index = _score_sentence_bm25(
            sentence, "", facts, index=build_bm25_index("", facts)
        )
        without_index = _score_sentence_bm25(sentence, "", facts)

        assert with_index == pytest.approx(without_index)
        assert with_index > 0.0
