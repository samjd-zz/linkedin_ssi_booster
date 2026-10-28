"""Operation-count regressions for large truth-gate evidence pools."""

from unittest.mock import Mock, patch

import pytest

from services._nlp_corpus_cache import CorpusCache
from services.console_grounding import ProjectFact, _build_evidence_paths_for_sentence
from services.spacy_nlp import SpacyNLP, tokenize_many_for_search


def test_cache_invalidates_for_model_or_content_and_bounds_entries() -> None:
    cache: CorpusCache[str] = CorpusCache(max_entries=2)
    build = Mock(return_value=["doc"])
    assert cache.get_or_build("en", ["fact"], build) == ["doc"]
    assert cache.get_or_build("en", ["fact"], build) == ["doc"]
    assert build.call_count == 1
    cache.get_or_build("ja", ["fact"], build)
    cache.get_or_build("en", ["changed"], build)
    cache.get_or_build("en", ["fact"], build)
    assert build.call_count == 4
    assert len(cache._entries) == 2


def test_incomplete_or_oversized_corpora_are_not_cached() -> None:
    cache: CorpusCache[str] = CorpusCache(max_texts=1)
    build = Mock(return_value=["doc"])
    for _ in range(2):
        cache.get_or_build("en", ["a", "b"], build)
    build.return_value = ["a", "b"]
    for _ in range(2):
        cache.get_or_build("en", ["a", "b"], build)
    assert build.call_count == 4


def test_failed_build_is_retried() -> None:
    cache: CorpusCache[str] = CorpusCache()
    build = Mock(side_effect=[RuntimeError("parse failed"), ["doc"]])
    with pytest.raises(RuntimeError, match="parse failed"):
        cache.get_or_build("en", ["fact"], build)
    assert cache.get_or_build("en", ["fact"], build) == ["doc"]


def test_617_similarity_facts_are_parsed_once_across_sentences() -> None:
    base = Mock(has_vector=True)
    base.similarity.return_value = 0.8
    doc = Mock(has_vector=True)
    nlp = Mock(return_value=base)
    nlp.pipe.side_effect = lambda texts: [doc for _ in texts]
    engine = SpacyNLP()
    facts = [f"Fact {idx}" for idx in range(617)]
    with patch.object(engine, "get_model_for_text", return_value=nlp):
        for sentence in ("First claim", "Second claim", "Third claim"):
            assert engine.compute_similarity_batch(sentence, facts) == [0.8] * 617
        assert nlp.pipe.call_count == 1
        assert nlp.call_count == 3
        changed = facts[:-1] + ["Updated fact"]
        engine.compute_similarity_batch("Another claim", changed)
        assert nlp.pipe.call_count == 2


def test_similarity_corpus_is_not_shared_between_models() -> None:
    base = Mock(has_vector=True)
    base.similarity.return_value = 0.5
    models = [Mock(return_value=base), Mock(return_value=base)]
    for model in models:
        model.pipe.side_effect = lambda texts: [Mock(has_vector=True) for _ in texts]
    engine = SpacyNLP()
    with patch.object(engine, "get_model_for_text", side_effect=models):
        engine.compute_similarity_batch("claim", ["fact"])
        engine.compute_similarity_batch("claim", ["fact"])
    assert [model.pipe.call_count for model in models] == [1, 1]


def test_evidence_tokens_are_batched_and_reused_without_changing_overlap() -> None:
    engine = SpacyNLP()
    nlp = Mock()
    nlp.pipe_names = []

    def pipe(texts: list[str], **kwargs: object) -> list[list[Mock]]:
        return [
            [Mock(text=word, lemma_=word, is_space=False, is_punct=False, is_stop=False)
             for word in text.lower().split()]
            for text in texts
        ]

    nlp.pipe.side_effect = pipe
    facts = [
        ProjectFact(project="RAG", company="", years="", details=f"search {idx}",
                    source="domain:test", tags=set())
        for idx in range(617)
    ]
    with patch("services.spacy_nlp.get_spacy_nlp", return_value=engine), \
            patch.object(engine, "get_model_for_text", return_value=nlp):
        first = _build_evidence_paths_for_sentence("RAG search", facts)
        second = _build_evidence_paths_for_sentence("RAG search extra", facts)
        assert len(first) == len(second) == 617
        assert first[0].overlap == pytest.approx(2 / 3)
        assert second[0].overlap == pytest.approx(2 / 4)
        large_batches = [
            call.args[0] for call in nlp.pipe.call_args_list if len(call.args[0]) == 617
        ]
        assert len(large_batches) == 1
        tokens = tokenize_many_for_search(["new corpus"])
        tokens[0].append("caller mutation")
        assert tokenize_many_for_search(["new corpus"]) == [["new", "corpus"]]
        _build_evidence_paths_for_sentence("RAG search", facts)
        assert len([
            call for call in nlp.pipe.call_args_list if len(call.args[0]) == 617
        ]) == 1
        facts[0].details = "updated 0"
        updated = _build_evidence_paths_for_sentence("RAG search", facts)
        assert updated[0].overlap == pytest.approx(1 / 4)
        assert len([
            call for call in nlp.pipe.call_args_list if len(call.args[0]) == 617
        ]) == 2
