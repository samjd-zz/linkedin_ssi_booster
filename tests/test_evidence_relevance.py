"""Article grounding must not fill evidence quotas with unrelated knowledge."""

import re
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from services.avatar_intelligence import DomainEvidenceFact, EvidenceFact, ExtractedEvidenceFact
from services.console_grounding import ProjectFact
from services.content_curator import ContentCurator
from services.content_curator._evidence_paths import extracted_fact_to_evidence_path
from services.evidence_relevance import rank_relevant_evidence
from services.ollama_service import OllamaService


def extracted(statement: str, identifier: str = "ext-123456789abc") -> ExtractedEvidenceFact:
    return ExtractedEvidenceFact(
        evidence_id=f"X-{identifier}", statement=statement,
        source_url="https://example.test/article", source_title="Source",
        tags=[], entities=[], confidence="medium", source_fact_id=identifier,
    )


@pytest.fixture(autouse=True)
def tokenizer(monkeypatch: pytest.MonkeyPatch) -> Mock:
    # Exercise the no-language-model path without loading or downloading models.
    tokenize = Mock(side_effect=lambda texts: [
        re.findall(r"[a-z0-9]+", text.lower()) for text in texts
    ])
    monkeypatch.setattr("services.evidence_relevance.tokenize_many_for_search", tokenize)
    return tokenize


@pytest.mark.parametrize(
    "query,statement,expected",
    [
        ("Replit autonomous agents", "Replit deploys autonomous agents.", True),
        ("Replit autonomous agents", "LOVE SUPREME JAZZ FESTIVAL 2026.", False),
        ("Replit autonomous agents", "Java agents support reactive streams.", False),
        ("The company and the world", "The music and the festival", False),
        ("2026 1937", "Festival 2026 and 1937", False),
        ("", "Replit autonomous agents", False),
        ("Replit", "Replit deploys software", True),
        ("東京の音楽フェスティバル", "東京で音楽フェスティバルを開催する。", True),
        ("東京の音楽フェスティバル", "大阪で医療システムを運用する。", False),
    ],
)
def test_content_eligibility(query: str, statement: str, expected: bool) -> None:
    fact = extracted(statement)
    assert rank_relevant_evidence(query, [fact]) == ([fact] if expected else [])


def test_metadata_cannot_make_unrelated_statement_eligible() -> None:
    fact = extracted("Jazz musicians perform on stage.")
    fact.source_title = "Replit autonomous agents"
    fact.tags = ["Replit", "autonomous", "agents"]
    fact.entities = ["Replit", "autonomous agents"]
    assert rank_relevant_evidence("Replit autonomous agents", [fact]) == []


def test_matching_uses_lemmas_in_one_batch(tokenizer: Mock) -> None:
    tokenizer.side_effect = None
    tokenizer.return_value = [["agent", "deploy"], ["agent", "deploy"]]
    fact = extracted("An agent deployed.")
    assert rank_relevant_evidence("Agents deploying", [fact]) == [fact]
    tokenizer.assert_called_once_with(["Agents deploying", "An agent deployed."])


def test_capitalized_product_names_match_raw_words_despite_different_lemmas(
    tokenizer: Mock,
) -> None:
    tokenizer.side_effect = None
    tokenizer.return_value = [
        ["anthropic", "manage", "agent"], ["anthropic", "managed", "agents"],
    ]
    fact = extracted("Anthropic launched Managed Agents.")
    assert rank_relevant_evidence("Anthropic announced managed agents", [fact]) == [fact]


def test_raw_and_lemma_variants_do_not_count_as_two_shared_topics(tokenizer: Mock) -> None:
    tokenizer.side_effect = None
    tokenizer.return_value = [
        ["replit", "autonomous", "agent"], ["java", "agent", "stream"],
    ]
    assert rank_relevant_evidence(
        "Replit autonomous agents", [extracted("Java agents support streams")],
    ) == []


def test_ranking_prefers_focused_fact_and_preserves_ties() -> None:
    broad = extracted("Replit autonomous agents music food fashion", "broad")
    focused = extracted("Replit autonomous agents", "focused")
    tied = extracted("Replit autonomous agents", "tied")
    assert rank_relevant_evidence("Replit autonomous agents", [broad, focused, tied]) == [
        focused, tied, broad,
    ]


def test_empty_pool_does_not_tokenize(tokenizer: Mock) -> None:
    assert rank_relevant_evidence("Replit autonomous agents", []) == []
    tokenizer.assert_not_called()


def make_curator() -> ContentCurator:
    curator = ContentCurator.__new__(ContentCurator)
    curator._avatar_facts = []
    curator._domain_facts = []
    curator._extracted_facts = []
    curator._hybrid_retriever = None
    return curator


@pytest.mark.parametrize("hybrid", [False, True])
def test_curator_filters_before_ranking_and_honors_type_quotas(
    monkeypatch: pytest.MonkeyPatch, hybrid: bool,
) -> None:
    monkeypatch.setattr("services.content_curator.curator.KATZILLA_ENABLED", False)
    for key in ("EVIDENCE_PROJECT_COUNT", "EVIDENCE_DOMAIN_COUNT", "EXTRACTED_EVIDENCE_COUNT"):
        monkeypatch.setenv(key, "1")
    curator = make_curator()
    persona = EvidenceFact("E1", "Replit tools", "Acme", "2026", "Autonomous agents", [], "p1")
    domain = DomainEvidenceFact("D1", "Agents", "Replit autonomous agents", [], "high", "d1")
    good = extracted("Replit autonomous agents")
    bad = extracted("De La Soul headlines LOVE SUPREME JAZZ FESTIVAL.", "bad")
    curator._avatar_facts = [persona]
    curator._domain_facts = [domain]
    curator._extracted_facts = [bad, good]
    if hybrid:
        curator._hybrid_retriever = Mock()
        curator._hybrid_retriever.find_facts.side_effect = lambda q, facts, limit: facts
    grounding, hits, external = curator._grounding_facts_for_article(
        "Replit autonomous agents", "", "establish_brand",
    )
    assert {fact.source for fact in grounding} == {"avatar:p1", "domain:d1"}
    assert hits == [good]
    assert external == []
    if hybrid:
        _, candidates = curator._hybrid_retriever.find_facts.call_args.args
        assert bad not in candidates
        assert len(candidates) == 3
        assert curator._hybrid_retriever.find_facts.call_args.kwargs["limit"] == 3


@pytest.mark.parametrize("hybrid", [False, True])
def test_no_match_does_not_fill_quota_or_match_ssi_label(
    monkeypatch: pytest.MonkeyPatch, hybrid: bool,
) -> None:
    monkeypatch.setattr("services.content_curator.curator.KATZILLA_ENABLED", False)
    curator = make_curator()
    curator._extracted_facts = [extracted("build_relationships music festival")]
    if hybrid:
        curator._hybrid_retriever = Mock()
        curator._hybrid_retriever.find_facts.return_value = []
    assert curator._grounding_facts_for_article(
        "Replit autonomous agents", "", "build_relationships",
    ) == ([], [], [])


@pytest.mark.parametrize("relevant", [False, True])
def test_prompt_never_restores_unrelated_extracted_facts(
    monkeypatch: pytest.MonkeyPatch, relevant: bool,
) -> None:
    service = OllamaService.__new__(OllamaService)
    service._chat = Mock(return_value="A grounded response.")
    monkeypatch.setattr(
        "services.ollama_service.truth_gate_result",
        lambda text, *args, **kwargs: (text, None),
    )
    fact = extracted("Replit autonomous agents" if relevant else "Japanese jazz festival")
    text = "Replit deploys autonomous agents. " * 5
    assert service.summarise_for_curation(
        text, "https://example.test/replit", channel="x", extracted_facts=[fact],
    )
    prompt = service._chat.call_args.args[1]
    assert (fact.statement in prompt) is relevant


def test_explain_uses_selected_sources_not_independent_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    curator = make_curator()
    selected = DomainEvidenceFact("D1", "Agents", "Replit autonomous agents", [], "high", "d1")
    other = DomainEvidenceFact("D2", "Java", "Java lambda functions", [], "high", "d2")
    curator._domain_facts = [other, selected]
    build = Mock()
    monkeypatch.setattr("services.avatar_intelligence.build_explain_output", build)
    monkeypatch.setattr("services.avatar_intelligence.format_explain_output", lambda result: "")
    monkeypatch.setattr(
        "services.console_grounding.truth_gate_result",
        lambda *args: ("text", SimpleNamespace(dot_per_sentence_scores=[], spacy_sim_scores=[])),
    )
    curator._print_avatar_explain(
        "text", {"title": "Replit", "summary": "Agents"},
        [ProjectFact("Agents", "Domain Knowledge", "general", selected.statement, "domain:d1", set())],
        "linkedin", "establish_brand",
    )
    assert build.call_args.kwargs["evidence_facts"] == [selected]


def test_newly_learned_facts_available_before_shared_channel_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    curator = make_curator()
    curator._classify = False
    curator._spacy_nlp = None
    curator._topic_signal = {}
    curator._load_published_titles = Mock(return_value=set())
    curator._process_single_channel = Mock(return_value=[])
    article = {
        "title": "Replit autonomous agents", "summary": "Replit autonomous agents. " * 40,
        "link": "https://example.test/replit", "source": "Test",
    }
    new_fact = extracted("Replit autonomous agents")
    monkeypatch.setattr("services.content_curator.curator.fetch_relevant_articles", lambda **kw: [article])
    monkeypatch.setattr("services.content_curator.curator.KATZILLA_ENABLED", False)
    monkeypatch.setattr("services.selection_learning.compute_acceptance_priors", lambda: {})
    monkeypatch.setattr("services.selection_learning.rank_articles", lambda articles, *a, **kw: articles)
    monkeypatch.setattr("services.avatar_intelligence.extract_and_append_knowledge", lambda **kw: [new_fact])
    monkeypatch.setattr("services.avatar_intelligence.load_avatar_state", lambda: None)
    monkeypatch.setattr("services.avatar_intelligence.normalize_extracted_facts", lambda state: [new_fact])
    assert curator.curate_and_create_ideas(channel="linkedin,facebook,x", request_delay=0) == []
    assert curator._process_single_channel.call_count == 3
    for call in curator._process_single_channel.call_args_list:
        assert call.kwargs["extracted_facts"] == [new_fact]


def test_evidence_path_preserves_full_source_id() -> None:
    fact = extracted("Replit autonomous agents")
    assert extracted_fact_to_evidence_path(fact, fact.statement).source == (
        f"extracted_knowledge:{fact.source_fact_id}"
    )
