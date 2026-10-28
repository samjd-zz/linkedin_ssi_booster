"""Operation-count regressions for console retrieval and large embeddings."""

import asyncio
import logging
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest

import main
import services.avatar_intelligence as avatar
import services.rei_toei.service as rei_service
from services.hybrid_retriever import HybridRetriever
from services.model2vec_service import Model2VecService
from services.console_grounding import _rei_console as rei


def test_large_embedding_batches_preserve_scores_and_reuse_corpus() -> None:
    service = Model2VecService()
    model = Mock()
    model.encode.side_effect = lambda texts: np.array([[1.0, 0.0] for _ in texts])
    service._model = model
    texts = [f"Fact {idx}" for idx in range(617)]
    with patch.object(service, "_load_model", return_value=True):
        assert service.batch_semantic_similarity("Query", texts) == [1.0] * 617
        assert service.batch_semantic_similarity("Different query", texts) == [1.0] * 617
        assert [len(call.args[0]) for call in model.encode.call_args_list] == [1, 617, 1]
        assert len(service._embedding_cache) <= 512
        changed = texts[:-1] + ["Updated fact"]
        assert service.batch_semantic_similarity("Query", changed) == [1.0] * 617
        assert model.encode.call_count == 4


def test_embeddings_preserve_order_duplicates_and_model_changes() -> None:
    service = Model2VecService()
    model = Mock()
    model.encode.side_effect = lambda texts: [[len(text)] for text in texts]
    service._model = model
    assert service._encode_cached(["bb", "a", "bb"]) == [[2], [1], [2]]
    model.encode.assert_called_once_with(["bb", "a"])
    replacement = Mock()
    replacement.encode.side_effect = lambda texts: [[-len(text)] for text in texts]
    service._model = replacement
    assert service._encode_cached(["bb", "a", "bb"]) == [[-2], [-1], [-2]]
    replacement.encode.assert_called_once_with(["bb", "a"])


def test_incomplete_embedding_batch_is_not_cached() -> None:
    service = Model2VecService()
    service._model = Mock()
    service._model.encode.return_value = [[1]]
    with pytest.raises(ValueError, match="incomplete embedding batch"):
        service._encode_cached(["one", "two"])
    service._model.encode.return_value = [[1], [2]]
    assert service._encode_cached(["one", "two"]) == [[1], [2]]
    assert service._model.encode.call_count == 2


def test_hybrid_batches_tokenization_and_refreshes_same_id_edits() -> None:
    fact = SimpleNamespace(
        evidence_id="D001", domain="Retrieval", statement="Original fact", tags=[],
    )
    index = Mock()
    index.get_scores.return_value = np.array([1.0])
    retriever = HybridRetriever()
    with patch("services.hybrid_retriever._BM25_AVAILABLE", True), \
            patch("services.hybrid_retriever._BM25Okapi", return_value=index) as build, \
            patch("services.spacy_nlp.tokenize_for_search", return_value=["query"]), \
            patch("services.spacy_nlp.tokenize_many_for_search", return_value=[["fact"]]) as tokenize:
        retriever._bm25_scores("query", [fact])
        retriever._bm25_scores("another query", [fact])
        assert tokenize.call_count == build.call_count == 1
        fact.statement = "Updated fact"
        retriever._bm25_scores("query", [fact])
        assert tokenize.call_count == build.call_count == 2
        assert "Updated fact" in tokenize.call_args.args[0][0]


@pytest.mark.parametrize("query_tokens", [["query"], []])
def test_hybrid_fallback_uses_at_most_one_tokenizer_batch(query_tokens: list[str]) -> None:
    facts = [SimpleNamespace(statement="query fact"), SimpleNamespace(statement="another fact")]
    with patch("services.hybrid_retriever._BM25_AVAILABLE", False), \
            patch("services.spacy_nlp.tokenize_for_search", return_value=query_tokens), \
            patch("services.spacy_nlp.tokenize_many_for_search", return_value=[["query"], ["another"]]) as tokenize:
        assert HybridRetriever()._bm25_scores("query", facts) == (
            [1.0, 0.0] if query_tokens else [0.0, 0.0]
        )
        assert tokenize.call_count == (1 if query_tokens else 0)


def test_rei_conversation_does_not_load_pattern_library(monkeypatch: pytest.MonkeyPatch) -> None:
    service = rei_service.ReiToeiService()
    persona = Mock()
    domain = Mock()
    patterns = Mock(side_effect=AssertionError("unused"))
    monkeypatch.setattr(rei_service, "load_rei_persona", persona)
    monkeypatch.setattr(rei_service, "load_rei_domain_knowledge", domain)
    monkeypatch.setattr(rei_service, "load_strudel_patterns", patterns)
    monkeypatch.setattr(rei, "get_rei_service", lambda: service)
    conversation = AsyncMock(return_value=("Hello", []))
    monkeypatch.setattr(rei, "_handle_conversation", conversation)
    assert asyncio.run(rei.handle_rei_console("Hello there", Mock(), []))[0] == "Hello"
    assert asyncio.run(rei.handle_rei_console("Hello again", Mock(), []))[0] == "Hello"
    persona.assert_called_once()
    domain.assert_called_once()
    patterns.assert_not_called()
    service.reload(eager=False)
    assert persona.call_count == domain.call_count == 1
    assert asyncio.run(rei.handle_rei_console("Reloaded", Mock(), []))[0] == "Hello"
    assert persona.call_count == domain.call_count == 2
    patterns.assert_not_called()


def test_rei_song_uses_active_console_client(monkeypatch: pytest.MonkeyPatch) -> None:
    ai = Mock()
    monkeypatch.setattr(rei, "_lav_rei_console", Mock())
    monkeypatch.setattr(rei, "_normalize_extracted_rei", Mock(return_value=[Mock()]))
    monkeypatch.setattr(rei, "extract_themes", Mock(return_value=[Mock()]))
    monkeypatch.setattr(rei, "load_recent_rei_titles", Mock(return_value=[]))
    concept = SimpleNamespace(title="Song", theme="Async", mood="Playful", bpm=142, genre_tags=[])
    generate = Mock(return_value=concept)
    compose = Mock()
    monkeypatch.setattr(rei, "generate_song_concept", generate)
    monkeypatch.setattr(rei, "compose_lyrics", compose)
    monkeypatch.setattr(rei, "assemble_suno_prompt", Mock(return_value=SimpleNamespace(
        lyrics="Lyrics", suno_prompt="Tags",
    )))
    reply, _ = asyncio.run(rei._handle_suno_request("song about async", ai, Mock(), Mock(), []))
    assert "Style tags:" in reply
    assert generate.call_args.kwargs["ollama"] is ai
    assert compose.call_args.kwargs["ollama"] is ai


def test_rei_pattern_uses_active_console_client(monkeypatch: pytest.MonkeyPatch) -> None:
    ai = Mock()
    service = Mock()
    monkeypatch.setattr(rei, "get_rei_service", lambda: service)
    monkeypatch.setattr(rei, "_lav_rei_console", Mock())
    monkeypatch.setattr(rei, "_normalize_extracted_rei", Mock(return_value=[Mock()]))
    monkeypatch.setattr(rei, "extract_themes", Mock(return_value=[Mock()]))
    monkeypatch.setattr(rei, "load_recent_rei_titles", Mock(return_value=[]))
    monkeypatch.setattr(rei, "choose_diverse_theme", Mock(return_value=SimpleNamespace(name="Async")))
    template = Mock()
    monkeypatch.setattr(rei, "map_concept_to_pattern", Mock(return_value=template))
    generate = Mock(return_value=SimpleNamespace(strudel_code="note('c3')"))
    monkeypatch.setattr(rei, "generate_strudel_code", generate)
    monkeypatch.setattr(rei, "validate_strudel_syntax", Mock(return_value=SimpleNamespace(valid=True)))
    reply, history = asyncio.run(rei.handle_rei_console("Generate a Strudel pattern", ai, []))
    assert "note('c3')" in reply
    assert history[-1]["_rei_pending_pattern"] == "note('c3')"
    assert generate.call_args.kwargs["ollama"] is ai
    assert rei.map_concept_to_pattern.call_args.args[1] is service.pattern_library


@pytest.fixture
def console(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Keep interactive tests isolated from files, hardware, and external APIs."""
    import services.console_grounding as grounding
    import services.hybrid_retriever as hybrid
    import services.knowledge_graph as graph

    facts = [
        avatar.DomainEvidenceFact(
            evidence_id=f"D{i}", domain="Retrieval", statement=f"Grounded fact {i}",
            tags=[], confidence="high", source_fact_id=f"fact{i}",
        )
        for i in range(2)
    ]
    state = SimpleNamespace(domain_knowledge=None)
    load = Mock(return_value=state)
    monkeypatch.setattr(avatar, "load_avatar_state", load)
    monkeypatch.setattr(avatar, "normalize_evidence_facts", Mock(return_value=[]))
    monkeypatch.setattr(avatar, "normalize_domain_facts", Mock(return_value=facts))
    monkeypatch.setattr(avatar, "normalize_extracted_facts", Mock(return_value=[]))
    kg_factory = Mock(side_effect=lambda: Mock(_persona_id="Sam"))
    retriever = Mock()
    retriever.find_facts.side_effect = lambda query, candidates, limit: candidates
    retrievers = Mock(return_value=retriever)
    monkeypatch.setattr(graph, "KnowledgeGraphManager", kg_factory)
    monkeypatch.setattr(hybrid, "HybridRetriever", retrievers)
    cleanup = Mock()
    monkeypatch.setattr(main, "_run_post_generation_cleanup", cleanup)
    monkeypatch.setattr(main, "speak_text", Mock())
    monkeypatch.setattr(main, "_auto_render_art_if_requested", Mock())
    monkeypatch.setattr(main, "_render_console_art_avatar", Mock())
    gate = Mock(return_value=("", SimpleNamespace(truth_gradient=0.8, fact_sim_scores={})))
    monkeypatch.setattr(grounding, "truth_gate_result", gate)
    external = Mock(return_value=[])
    monkeypatch.setattr(avatar, "retrieve_evidence", external)
    rei_cache = Mock()
    monkeypatch.setattr("services.rei_toei_service.get_rei_service", lambda: rei_cache)
    ai = Mock()
    ai.chat_as_persona.return_value = "A grounded reply."
    # Restore the hook even if an assertion fails during the mocked interaction.
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    return SimpleNamespace(
        ai=ai, load=load, state=state, kg_factory=kg_factory, retrievers=retrievers,
        facts=facts, gate=gate, external=external, cleanup=cleanup, rei_cache=rei_cache,
    )


def test_console_loads_one_snapshot_and_rebuilds_graph_on_reload(
    console: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = iter(["Explain retrieval", "/reload", "Explain retrieval again", "/exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    main.run_console(console.ai)
    assert console.load.call_count == 2
    assert console.kg_factory.call_count == console.retrievers.call_count == 2
    for call in console.retrievers.call_args_list:
        call.kwargs["kg"].bootstrap_from_avatar_state.assert_called_once_with(console.state)
    console.rei_cache.reload.assert_called_once_with(eager=False)
    console.external.assert_not_called()
    console.gate.assert_not_called()
    console.cleanup.assert_called_once_with(console.ai, source_mode="console")
    assert console.ai.chat_as_persona.call_count == 2


@pytest.mark.parametrize("fact_count", [0, 1, 2])
def test_console_preserves_sparse_pool_external_fallback(
    console: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, fact_count: int,
) -> None:
    del console.facts[fact_count:]
    inputs = iter(["Explain retrieval", "/exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    main.run_console(console.ai)
    assert console.external.call_count == (1 if fact_count == 1 else 0)


def test_console_verifies_once_without_duplicate_truth_bar(
    console: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = iter(["Explain retrieval", "/exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    main.run_console(console.ai, verify=True)
    console.gate.assert_called_once()
    assert capsys.readouterr().out.count("DoT 0.80") == 1


def test_console_tag_relationships_reuse_snapshot_and_refresh_on_reload(
    console: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def state(related: str) -> SimpleNamespace:
        return SimpleNamespace(domain_knowledge=SimpleNamespace(
            facts=[SimpleNamespace(id="base", tags=["rag"]), SimpleNamespace(id="next", tags=[related])],
            relationships=[SimpleNamespace(from_fact_id="base", to_fact_id="next")],
        ))

    console.load.side_effect = [state("old"), state("new")]
    parse = Mock(wraps=main.parse_query_constraints)
    monkeypatch.setattr(main, "parse_query_constraints", parse)
    inputs = iter(["Explain rag", "/reload", "Explain rag", "/exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    main.run_console(console.ai)
    assert console.load.call_count == 2
    assert [call.kwargs["tag_expansions"] for call in parse.call_args_list] == [
        {"rag": {"old"}}, {"rag": {"new"}},
    ]


def test_rei_console_bounds_history_and_preserves_persona_switching(
    console: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_lengths: list[int] = []

    async def handle(
        text: str, ai: Mock, history: list[dict[str, str]], max_tokens: int,
    ) -> tuple[str, list[dict[str, str]]]:
        seen_lengths.append(len(history))
        return "Rei reply", history + [
            {"role": "user", "content": text}, {"role": "assistant", "content": "Rei reply"},
        ]

    handler = AsyncMock(side_effect=handle)
    monkeypatch.setattr(rei, "handle_rei_console", handler)
    inputs = iter(["/rei Hello", *(["Hello again"] * 30), "/sam", "Explain retrieval", "/exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    main.run_console(console.ai)
    assert handler.await_count == 31
    assert max(seen_lengths) == 48
    console.ai.chat_as_persona.assert_called_once()


def test_voice_timing_retains_synchronous_completion(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    from services import piper_service

    service = Mock()
    service.speak.return_value = True
    monkeypatch.setattr(piper_service, "get_piper_service", lambda: service)
    with caplog.at_level(logging.INFO):
        assert piper_service.speak_text("A reply") is True
    service.speak.assert_called_once_with("A reply")
    assert "Stage end stage=console.voice" in caplog.text


@pytest.mark.parametrize("avatar_name", ["sam", "rei"])
@pytest.mark.parametrize("fail", [False, True])
def test_console_llm_timings_preserve_replies_and_errors(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    avatar_name: str, fail: bool,
) -> None:
    from ollama import ChatResponse
    from services.ollama_service import OllamaService

    client = Mock()
    monkeypatch.setattr("services.ollama_service.ollama.Client", Mock(return_value=client))
    ai = OllamaService(model="test-model")
    client.chat.return_value = ChatResponse(
        message={"role": "assistant", "content": "A reply"},
        load_duration=1_000_000_000, eval_duration=2_000_000_000,
    )
    if fail:
        client.chat.side_effect = ConnectionError("unavailable")

    def chat() -> str:
        if avatar_name == "sam":
            return ai.chat_as_persona([{"role": "user", "content": "Hello"}])
        return rei._rei_chat(ai, [], "Rei identity", "Hello")

    with caplog.at_level(logging.INFO):
        if fail:
            with pytest.raises(RuntimeError):
                chat()
        else:
            assert chat() == "A reply"
    client.chat.assert_called_once()
    assert f"Stage end stage=console.{avatar_name}.chat" in caplog.text
    assert f"status={'error' if fail else 'ok'}" in caplog.text
    if not fail:
        assert "load_s=1.0" in caplog.text
        assert "generation_s=2.0" in caplog.text


def test_disabled_reports_skip_reporting_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins
    from services.shared import print_validation_reports

    original_import = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object) -> object:
        if name in {"services.console_grounding", "services.avatar_intelligence"}:
            raise AssertionError("Disabled reporting must not import validation services")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    print_validation_reports("Reply", "", [], [], [], [], [], [])
