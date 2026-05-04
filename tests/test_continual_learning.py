"""Tests for continual learning — ExtractedFact, ExtractedKnowledgeGraph, and NLP pipeline.

Covers:
- Schema validation for extracted_knowledge.json
- Loader round-trip (load → save → reload)
- normalize_extracted_facts: stable IDs, correct field mapping
- _extracted_fact_tokens: BM25 tokenisation
- build_extracted_grounding_context: prompt formatting
- extract_and_append_knowledge: deduplication and dry_run flag
- AvatarState.extracted_knowledge integration via load_avatar_state
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from services.avatar_intelligence import (
    AvatarState,
    ExtractedEvidenceFact,
    ExtractedFact,
    ExtractedKnowledgeGraph,
    _extracted_fact_tokens,
    _load_extracted_knowledge,
    _make_extracted_evidence_id,
    _make_extracted_fact_id,
    _validate_extracted_knowledge,
    build_extracted_grounding_context,
    extract_and_append_knowledge,
    normalize_extracted_facts,
    save_extracted_knowledge,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_graph(facts: list[ExtractedFact] | None = None) -> ExtractedKnowledgeGraph:
    return ExtractedKnowledgeGraph(
        schema_version="1.0",
        facts=facts or [],
    )


def _make_fact(
    statement: str = "Transformers are state-of-the-art for NLP tasks.",
    source_url: str = "https://example.com/article",
    source_title: str = "NLP Survey 2026",
    fact_id: str | None = None,
    tags: list[str] | None = None,
    entities: list[str] | None = None,
) -> ExtractedFact:
    fid = fact_id or _make_extracted_fact_id(source_url, statement)
    return ExtractedFact(
        id=fid,
        statement=statement,
        source_url=source_url,
        source_title=source_title,
        extracted_at="2026-04-19T16:00:00+00:00",
        entities=entities or ["Transformers"],
        tags=tags or ["nlp", "transformer", "benchmark"],
        confidence="medium",
        extraction_method="spacy_nlp",
    )


def _make_avatar_state(
    extracted_knowledge: ExtractedKnowledgeGraph | None = None,
) -> AvatarState:
    return AvatarState(
        persona_graph=None,
        narrative_memory=None,
        domain_knowledge=None,
        extracted_knowledge=extracted_knowledge,
        is_loaded=False,
    )


# ---------------------------------------------------------------------------
# _validate_extracted_knowledge
# ---------------------------------------------------------------------------

def test_validate_extracted_knowledge_valid():
    data = {"schemaVersion": "1.0", "facts": []}
    assert _validate_extracted_knowledge(data) == []


def test_validate_extracted_knowledge_missing_schema_version():
    data = {"facts": []}
    errors = _validate_extracted_knowledge(data)
    assert any("schemaVersion" in e for e in errors)


def test_validate_extracted_knowledge_missing_facts():
    data = {"schemaVersion": "1.0"}
    errors = _validate_extracted_knowledge(data)
    assert any("facts" in e for e in errors)


def test_validate_extracted_knowledge_facts_not_list():
    data = {"schemaVersion": "1.0", "facts": "not-a-list"}
    errors = _validate_extracted_knowledge(data)
    assert any("facts" in e for e in errors)


# ---------------------------------------------------------------------------
# _load_extracted_knowledge
# ---------------------------------------------------------------------------

def test_load_extracted_knowledge_missing_file(tmp_path):
    path = tmp_path / "nope.json"
    graph, errors = _load_extracted_knowledge(path)
    assert graph is None
    assert any("not found" in e for e in errors)


def test_load_extracted_knowledge_malformed_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not valid json", encoding="utf-8")
    graph, errors = _load_extracted_knowledge(path)
    assert graph is None
    assert any("parse error" in e for e in errors)


def test_load_extracted_knowledge_schema_error(tmp_path):
    path = tmp_path / "bad_schema.json"
    path.write_text(json.dumps({"schemaVersion": "1.0", "facts": "not-a-list"}), encoding="utf-8")
    graph, errors = _load_extracted_knowledge(path)
    assert graph is None
    assert any("schema error" in e for e in errors)


def test_load_extracted_knowledge_empty_facts(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"schemaVersion": "1.0", "facts": []}), encoding="utf-8")
    graph, errors = _load_extracted_knowledge(path)
    assert errors == []
    assert graph is not None
    assert graph.facts == []
    assert graph.schema_version == "1.0"


def test_load_extracted_knowledge_with_facts(tmp_path):
    fact = _make_fact()
    path = tmp_path / "graph.json"
    path.write_text(
        json.dumps({
            "schemaVersion": "1.0",
            "facts": [{
                "id": fact.id,
                "statement": fact.statement,
                "source_url": fact.source_url,
                "source_title": fact.source_title,
                "extracted_at": fact.extracted_at,
                "entities": fact.entities,
                "tags": fact.tags,
                "confidence": fact.confidence,
                "extraction_method": fact.extraction_method,
            }],
        }),
        encoding="utf-8",
    )
    graph, errors = _load_extracted_knowledge(path)
    assert errors == []
    assert graph is not None
    assert len(graph.facts) == 1
    assert graph.facts[0].id == fact.id
    assert graph.facts[0].statement == fact.statement


# ---------------------------------------------------------------------------
# save_extracted_knowledge + round-trip
# ---------------------------------------------------------------------------

def test_save_and_reload_extracted_knowledge(tmp_path):
    fact = _make_fact()
    graph = _make_graph([fact])
    path = tmp_path / "out.json"

    save_extracted_knowledge(graph, path=path)
    assert path.exists()

    reloaded, errors = _load_extracted_knowledge(path)
    assert errors == []
    assert reloaded is not None
    assert len(reloaded.facts) == 1
    assert reloaded.facts[0].statement == fact.statement
    assert reloaded.facts[0].tags == fact.tags


def test_save_extracted_knowledge_creates_parent_dirs(tmp_path):
    path = tmp_path / "nested" / "dir" / "out.json"
    graph = _make_graph()
    save_extracted_knowledge(graph, path=path)
    assert path.exists()


# ---------------------------------------------------------------------------
# _make_extracted_fact_id
# ---------------------------------------------------------------------------

def test_make_extracted_fact_id_stable():
    id1 = _make_extracted_fact_id("https://example.com", "Some statement.")
    id2 = _make_extracted_fact_id("https://example.com", "Some statement.")
    assert id1 == id2


def test_make_extracted_fact_id_different_for_different_inputs():
    id1 = _make_extracted_fact_id("https://example.com", "Statement A.")
    id2 = _make_extracted_fact_id("https://example.com", "Statement B.")
    assert id1 != id2


def test_make_extracted_fact_id_has_ext_prefix():
    fid = _make_extracted_fact_id("https://example.com", "hello world")
    assert fid.startswith("ext-")


# ---------------------------------------------------------------------------
# _make_extracted_evidence_id
# ---------------------------------------------------------------------------

def test_make_extracted_evidence_id_prefix():
    eid = _make_extracted_evidence_id("fact-abc", 0)
    assert eid.startswith("X000-")


def test_make_extracted_evidence_id_stable():
    eid1 = _make_extracted_evidence_id("same-id", 5)
    eid2 = _make_extracted_evidence_id("same-id", 5)
    assert eid1 == eid2


def test_make_extracted_evidence_id_different_index():
    eid1 = _make_extracted_evidence_id("fact-x", 0)
    eid2 = _make_extracted_evidence_id("fact-x", 1)
    assert eid1 != eid2


# ---------------------------------------------------------------------------
# normalize_extracted_facts
# ---------------------------------------------------------------------------

def test_normalize_extracted_facts_empty_state():
    state = _make_avatar_state(extracted_knowledge=None)
    assert normalize_extracted_facts(state) == []


def test_normalize_extracted_facts_empty_graph():
    graph = _make_graph([])
    state = _make_avatar_state(extracted_knowledge=graph)
    assert normalize_extracted_facts(state) == []


def test_normalize_extracted_facts_single_fact():
    fact = _make_fact()
    graph = _make_graph([fact])
    state = _make_avatar_state(extracted_knowledge=graph)

    result = normalize_extracted_facts(state)
    assert len(result) == 1
    ef = result[0]
    assert isinstance(ef, ExtractedEvidenceFact)
    assert ef.statement == fact.statement
    assert ef.source_url == fact.source_url
    assert ef.source_title == fact.source_title
    assert ef.tags == fact.tags
    assert ef.entities == fact.entities
    assert ef.confidence == fact.confidence
    assert ef.source_fact_id == fact.id
    assert ef.evidence_id.startswith("X000-")


def test_normalize_extracted_facts_multiple_facts():
    facts = [
        _make_fact(statement=f"Fact {i}.", fact_id=f"id-{i}")
        for i in range(3)
    ]
    graph = _make_graph(facts)
    state = _make_avatar_state(extracted_knowledge=graph)
    result = normalize_extracted_facts(state)
    assert len(result) == 3
    # Evidence IDs should be different
    eids = [f.evidence_id for f in result]
    assert len(set(eids)) == 3


# ---------------------------------------------------------------------------
# _extracted_fact_tokens
# ---------------------------------------------------------------------------

def test_extracted_fact_tokens_returns_list():
    ef = ExtractedEvidenceFact(
        evidence_id="X000-abc",
        statement="Transformers are great for NLP.",
        source_url="https://example.com",
        source_title="AI Survey",
        tags=["nlp", "transformer"],
        entities=["OpenAI"],
        confidence="medium",
        source_fact_id="ext-abc",
    )
    tokens = _extracted_fact_tokens(ef)
    assert isinstance(tokens, list)
    assert len(tokens) > 0
    # Tags should appear multiple times (boost)
    assert tokens.count("nlp") >= 3
    assert tokens.count("transformer") >= 3


def test_extracted_fact_tokens_lowercased():
    ef = ExtractedEvidenceFact(
        evidence_id="X000-abc",
        statement="Python ML Models.",
        source_url="https://example.com",
        source_title="Tech News",
        tags=["Python", "ML"],
        entities=["Google"],
        confidence="high",
        source_fact_id="ext-abc",
    )
    tokens = _extracted_fact_tokens(ef)
    for tok in tokens:
        assert tok == tok.lower()


# ---------------------------------------------------------------------------
# build_extracted_grounding_context
# ---------------------------------------------------------------------------

def test_build_extracted_grounding_context_empty():
    assert build_extracted_grounding_context([]) == ""


def test_build_extracted_grounding_context_single():
    ef = ExtractedEvidenceFact(
        evidence_id="X000-abc",
        statement="RAG systems improve LLM accuracy.",
        source_url="https://example.com",
        source_title="AI Research",
        tags=["rag", "llm"],
        entities=["RAG"],
        confidence="medium",
        source_fact_id="ext-abc",
    )
    ctx = build_extracted_grounding_context([ef])
    assert "Recently learned context" in ctx
    assert "[X000-abc]" in ctx
    assert "RAG systems improve LLM accuracy" in ctx
    assert "rag" in ctx


def test_build_extracted_grounding_context_source_title():
    ef = ExtractedEvidenceFact(
        evidence_id="X001-xyz",
        statement="Agents are the future.",
        source_url="https://example.com",
        source_title="AI Trends 2026",
        tags=[],
        entities=[],
        confidence="low",
        source_fact_id="ext-xyz",
    )
    ctx = build_extracted_grounding_context([ef])
    assert "AI Trends 2026" in ctx


# ---------------------------------------------------------------------------
# extract_and_append_knowledge
# ---------------------------------------------------------------------------

ARTICLE = (
    "Large language models have transformed natural language processing. "
    "Recent benchmarks show that transformer-based models consistently outperform "
    "older RNN architectures on standard tasks. "
    "The adoption of vector search and RAG pipelines has accelerated significantly "
    "in enterprise AI systems."
)


def test_extract_and_append_knowledge_dry_run(tmp_path):
    path = tmp_path / "ek.json"
    path.write_text(json.dumps({"schemaVersion": "1.0", "facts": []}), encoding="utf-8")

    result = extract_and_append_knowledge(
        ARTICLE,
        source_url="https://example.com/article",
        source_title="Test Article",
        path=path,
        dry_run=True,
    )
    # dry_run returns empty list but should not modify disk
    assert result == []
    reloaded = json.loads(path.read_text())
    assert reloaded["facts"] == []


def test_extract_and_append_knowledge_writes_facts(tmp_path):
    path = tmp_path / "ek.json"
    path.write_text(json.dumps({"schemaVersion": "1.0", "facts": []}), encoding="utf-8")

    result = extract_and_append_knowledge(
        ARTICLE,
        source_url="https://example.com/article",
        source_title="Test Article",
        path=path,
        dry_run=False,
    )
    # Should have extracted at least one fact (sentences are long enough)
    assert len(result) >= 1
    for fact in result:
        assert isinstance(fact, ExtractedFact)
        assert fact.source_url == "https://example.com/article"
        assert fact.source_title == "Test Article"
        assert fact.id.startswith("ext-")

    # Verify on-disk file was updated
    reloaded = json.loads(path.read_text())
    assert len(reloaded["facts"]) == len(result)


def test_extract_and_append_knowledge_deduplication(tmp_path):
    path = tmp_path / "ek.json"
    path.write_text(json.dumps({"schemaVersion": "1.0", "facts": []}), encoding="utf-8")

    # First extraction
    first_run = extract_and_append_knowledge(
        ARTICLE,
        source_url="https://example.com/article",
        source_title="Test Article",
        path=path,
        dry_run=False,
    )
    count_after_first = len(first_run)

    # Second extraction of same article — all should be duplicates
    second_run = extract_and_append_knowledge(
        ARTICLE,
        source_url="https://example.com/article",
        source_title="Test Article",
        path=path,
        dry_run=False,
    )
    assert second_run == [] or len(second_run) == 0

    # Total on-disk count should not grow
    reloaded = json.loads(path.read_text())
    assert len(reloaded["facts"]) == count_after_first


def test_extract_and_append_knowledge_no_cap_on_facts(tmp_path):
    """All qualifying sentences are extracted — no per-article cap is enforced."""
    path = tmp_path / "ek.json"
    path.write_text(json.dumps({"schemaVersion": "1.0", "facts": []}), encoding="utf-8")

    multi_fact_article = (
        "Spring AI 1.0.6 was released on April 30, 2026 with improved model routing. "
        "IBM Granite 4.1 achieves 40% faster inference compared to its predecessor. "
        "Elastic 8.15 introduces native ONNX model hosting for semantic search pipelines. "
        "Meta deployed unified AI agents that cut infrastructure costs by 30% in Q1 2026. "
        "Broadcom donated Velero to CNCF with full Kubernetes 1.32 compatibility verified. "
        "OpenAI Codex is now available on AWS Marketplace with pay-per-token billing."
    )
    result = extract_and_append_knowledge(
        multi_fact_article,
        source_url="https://example.com/multi",
        source_title="Multi Fact Article",
        path=path,
        dry_run=False,
    )
    # All qualifying sentences should be extracted, not capped at an arbitrary limit
    assert len(result) >= 2


def test_extract_and_append_knowledge_short_sentences_skipped(tmp_path):
    path = tmp_path / "ek.json"
    path.write_text(json.dumps({"schemaVersion": "1.0", "facts": []}), encoding="utf-8")

    result = extract_and_append_knowledge(
        "Too short. Also tiny.",  # all sentences are too short
        source_url="https://example.com",
        source_title="Short",
        min_sentence_len=50,
        path=path,
        dry_run=False,
    )
    assert result == []


def test_extract_and_append_knowledge_creates_file_if_missing(tmp_path):
    path = tmp_path / "new" / "ek.json"
    # File does not exist yet
    assert not path.exists()

    result = extract_and_append_knowledge(
        ARTICLE,
        source_url="https://example.com/article",
        source_title="Test Article",
        path=path,
        dry_run=False,
    )
    assert path.exists()
    assert len(result) >= 1


def test_extract_and_append_knowledge_confidence_field(tmp_path):
    path = tmp_path / "ek.json"
    path.write_text(json.dumps({"schemaVersion": "1.0", "facts": []}), encoding="utf-8")

    result = extract_and_append_knowledge(
        ARTICLE,
        source_url="https://example.com/article",
        source_title="Test Article",
        confidence="high",
        path=path,
        dry_run=False,
    )
    for fact in result:
        assert fact.confidence == "high"


def test_extract_and_append_knowledge_category_fields_default_empty(tmp_path):
    """When Model2Vec is unavailable, primary_category and primary_ssi_component are empty strings."""
    path = tmp_path / "ek.json"
    path.write_text(json.dumps({"schemaVersion": "1.0", "facts": []}), encoding="utf-8")

    # Model2Vec is not installed in the test environment — fields should default to ""
    result = extract_and_append_knowledge(
        ARTICLE,
        source_url="https://example.com/article",
        source_title="Test Article",
        path=path,
        dry_run=False,
    )
    for fact in result:
        assert isinstance(fact.primary_category, str)
        assert isinstance(fact.primary_ssi_component, str)


def test_loader_backward_compat_missing_category_fields(tmp_path):
    """Loader must handle existing JSON facts that lack primary_category/primary_ssi_component."""
    from services.avatar_intelligence._loaders import _load_extracted_knowledge

    # Write a fact without the new fields (simulates pre-upgrade data)
    old_fact = {
        "id": "ext-abc123",
        "statement": "Python 3.12 introduced significant performance improvements.",
        "source_url": "https://example.com/python",
        "source_title": "Python 3.12 Release",
        "extracted_at": "2026-01-01T00:00:00+00:00",
        "entities": [],
        "tags": ["python"],
        "confidence": "medium",
        "extraction_method": "spacy_nlp",
        # NOTE: primary_category and primary_ssi_component intentionally absent
    }
    path = tmp_path / "ek.json"
    path.write_text(
        json.dumps({"schemaVersion": "1.0", "facts": [old_fact]}), encoding="utf-8"
    )

    graph, errors = _load_extracted_knowledge(path)
    assert not errors
    assert graph is not None
    assert len(graph.facts) == 1
    fact = graph.facts[0]
    assert fact.primary_category == ""
    assert fact.primary_ssi_component == ""


# ---------------------------------------------------------------------------
# AvatarState integration
# ---------------------------------------------------------------------------

def test_avatar_state_holds_extracted_knowledge():
    fact = _make_fact()
    graph = _make_graph([fact])
    state = _make_avatar_state(extracted_knowledge=graph)
    assert state.extracted_knowledge is not None
    assert len(state.extracted_knowledge.facts) == 1


def test_normalize_extracted_facts_ids_are_unique_across_reloads(tmp_path):
    """IDs should be deterministic across two normalize_extracted_facts calls."""
    fact = _make_fact(fact_id="stable-id")
    graph = _make_graph([fact])
    state = _make_avatar_state(extracted_knowledge=graph)

    result1 = normalize_extracted_facts(state)
    result2 = normalize_extracted_facts(state)
    assert result1[0].evidence_id == result2[0].evidence_id


# ---------------------------------------------------------------------------
# Sentence-filter regression tests (noise filtering)
# ---------------------------------------------------------------------------
# Each test passes a single-sentence article through extract_and_append_knowledge
# with dry_run=False and asserts whether it is filtered (returns []) or passes
# (returns a fact).  This keeps filter regressions visible and prevents
# accidental removal of a guard later.

def _run_sentence(sentence: str, tmp_path) -> list:
    """Helper: run one sentence through the extraction pipeline."""
    path = tmp_path / "ek.json"
    path.write_text(json.dumps({"schemaVersion": "1.0", "facts": []}), encoding="utf-8")
    return extract_and_append_knowledge(
        sentence,
        source_url="https://example.com/test",
        source_title="Test Source",
        path=path,
        dry_run=False,
    )


# --- sentences that MUST be filtered ---

@pytest.mark.parametrize("sentence", [
    # adversative conjunction + pronoun/demonstrative opener (context-dependent)
    "However, this also means the build process is now significantly slower on CI.",
    "Yet, that migration path requires careful planning across all dependent services.",
    "Nevertheless, these trade-offs must be evaluated before adopting this approach.",
    "But it was designed to handle exactly this kind of workload at enterprise scale.",
    # conditional tutorial/advisory fragment
    "When you are developing components that render thousands of DOM elements, performance tuning matters.",
    "While you are building microservices, it is important to consider service mesh options carefully.",
    "Whenever you need to handle large payloads, chunked streaming is the recommended approach.",
    # anthropomorphism / never-thinks-about background prose
    "A modern web UI is built around a scrolling viewport and other overlays that the user never thinks about, but that a printer happily reproduces on A4.",
    # first-person author narration
    "I couldn't believe how quickly the latency dropped after switching to the new runtime.",
    "As I reviewed the benchmarks, the results were surprisingly consistent across all runs.",
    # newsletter/podcast preamble
    "Welcome to this week's edition of the AI Engineering digest.",
    "For this episode we invited three platform engineers to discuss observability patterns.",
    # boilerplate article opener
    "In this post, we will explore how to deploy a Kubernetes cluster on AWS EKS.",
    "This article covers the basics of setting up a RAG pipeline from scratch.",
    # CTA boilerplate
    "Learn more about our enterprise plan and how it can accelerate your team.",
    "Get started with the free tier today and explore all available integrations.",
    # passive advisory
    "Users are encouraged to migrate to the new SDK before the deprecation deadline.",
    "Developers should update their dependencies to avoid breaking changes in Q3.",
    # marketing superlative tagline
    "Our most advanced model yet, designed for enterprise-grade reliability.",
    "The world's fastest vector database, now available on all major clouds.",
    # RSS "appeared first on" boilerplate
    "The post How to Use LangChain with Redis appeared first on The New Stack.",
    # "X, Y, Z, and more." list fragment
    "Support for streaming, caching, retries, and more.",
    # rhetorical question openers
    "Have you ever wondered why your RAG pipeline returns stale results?",
    "Did you know that most enterprise AI projects fail in the first six months?",
    "Are you struggling to keep up with the pace of LLM releases?",
    # dangling-pronoun opener (no antecedent)
    "It was designed to handle exactly this kind of workload at enterprise scale.",
    "They were introduced to reduce cold-start latency across all regions.",
    "This was the key insight that changed how the team approached the problem.",
    # heading+pronoun concatenation (section title glued to next sentence)
    "Velero It operates as a Kubernetes-native backup and migration tool for clusters.",
    "Redis They support a wide range of data structures including sorted sets.",
    # dangling-pronoun quantity reference (requires prior context)
    "V4-Flash drops these numbers even further with additional quantization passes.",
    "The benchmark shows these results across all three evaluated hardware configurations.",
    # generic-dismissal advisory
    "Optimizing CSS is rarely something you need to worry about in typical web apps.",
    "Database indexing is rarely a concern for projects with fewer than 10,000 rows.",
    # "Read more" truncated RSS fragment
    "The new Bedrock AgentCore SDK provides a unified interface for all major LLM providers... Read more.",
    # event marketing announcement
    "Join us at the conference for Java developers in Toronto this September.",
    "Our summit for AI practitioners will cover every major framework and toolchain.",
    # double-dash section header concatenation (ToC blob)
    "Model architecture overview -- Efficient Video Sampling -- Temporal compression -- Benchmark results -- Deployment guide -- Fine-tuning details.",
    # generic marketing CTA
    "Now is the time to explore your options and plan ahead for the next major release.",
    "Take advantage of the latest features before your competitors do.",
    # event marketing opener
    "This year, we're launching three new product lines aimed at enterprise customers.",
    "Next quarter, we are planning a major overhaul of the developer experience.",
    # section header blob
    "Version-Specific Highlights for the Spring Boot 3.4 release cycle.",
    "TL;DR: This is a summary of all the breaking changes introduced in v2.",
    "What's New in the latest Elasticsearch release for vector search users.",
    # podcast preamble "In this installment/episode, I..."
    "In this episode, I chat with the Kubernetes project maintainer about future roadmap plans.",
    "In our discussion, I interview the lead architect about the new distributed tracing API.",
    # pure URL sentence
    "https://github.com/example/repo/releases/tag/v2.3.1",
    # truncated sentence ending with ellipsis
    "The new architecture introduces several important changes to how agents communicate...",
    # sentence dangling on bare preposition at end
    "These patterns trace all the way back to the foundational techniques of",
    # "we show / walk through / introduce" preamble
    "We walk you through the process of setting up a local Kubernetes cluster for development.",
    "We introduce a new abstraction layer that simplifies cross-cloud deployments.",
    # HuggingFace/GitHub navigation blob
    "Log In Sign Up Back to Articles Models Datasets Spaces Upvote 42 for this model checkpoint.",
    # pipe-delimited navigation links
    "Home | Source on GitHub | Reference documentation | Changelog | Contributing guide",
    # "In our recent livestream/webinar" opener
    "In our recent livestream, we covered the new Spring AI 2.0 release with live demos.",
    "In my recent webinar, I walked through the full agentic workflow from prompt to tool call.",
    # anecdotal scene-setter
    "Imagine if your entire data pipeline could self-heal without any human intervention.",
    "Picture this: a world where every microservice automatically scales to zero on idle.",
    "Somewhere out there, a team is still running Java 8 in production without a migration plan.",
    # vague rhetorical survey opener
    "Here's what we learned from the 2026 State of AI Infrastructure survey results.",
    "Here's how you can avoid the most common mistakes when building RAG pipelines.",
    # "You'll learn" educational preamble
    "You'll learn how to configure the new authentication middleware in three easy steps.",
    "You will discover why most teams underestimate the complexity of distributed tracing.",
    # "On behalf of / Did you see / Have you seen" openers
    "Did you see the announcement about the new Anthropic model released yesterday?",
    "Have you seen the benchmarks comparing Llama 3 with GPT-4o on coding tasks?",
    # "We'll focus / dive / cover" preambles
    "We'll dive into the architecture decisions that drove the Spring Boot 3 redesign.",
    "We will cover the three most impactful changes in the Kubernetes 1.33 release.",
    # award/recognition self-promotion
    "We're honored to be named a leader in the 2026 Gartner Magic Quadrant for AI platforms.",
    "We are thrilled to announce that our platform won the InfoQ eMag award for best tooling.",
    # camelCase mangled heading+body concatenation
    "Why the Future of Macro-Risk is Agentic and InterconnectedThe phone rang at 3am.",
    "Observability Patterns for Distributed SystemsWe have been running this approach.",
    # table/architecture blob (digit-heavy repeated tokens)
    "Dense 8B Dense 30B Dense Embedding size 2560 4096 4096 Number layers 40 40 64 heads 32 32 64.",
    # release-list blob (3+ version numbers with at least one repeat)
    "Spring Modulith 2.1.0 2.0.5 2.1.0 and 1.4.10 released with important bug fixes.",
    # generic filler (no metric)
    "Many companies are now investing heavily in AI infrastructure and platform tooling.",
    "Several organizations have adopted Kubernetes as their primary container orchestration layer.",
    # bare product availability announcement (no metric or "enabling")
    "Vaadin 25.1 is now available and makes for a strong upgrade for existing applications.",
    "The new Redis 8.0 release is now available with no breaking changes.",
    # email consent form scraped from InfoQ / similar sidebars
    "View an example Enter your e-mail address Select your country Select a country I consent to InfoQ.com handling my data.",
    "Enter your e-mail address Select your country to receive our weekly newsletter.",
    # author byline / changelog entry starting with punctuation
    ", Bharathan Balaji , and Daniel Suarez on 30 APR 2026 in Advanced (300) , Amazon Nova , Amazon SageMaker AI , Technical How-to Permalink Comments Share Large language models.",
    "; fixed a critical bug where the scheduler would skip posts published on Sunday.",
    # sentence truncated mid-word (scraper cut off page content)
    "AWS is betting that the next competitive frontier in AI-assisted development is code-generati",
    "XDR and endpoint security Secure your endpoints, clouds, and containers with AI-driven insights AI for security Automate your triage, investiga",    # 1-2 char trailing fragment (scraper cut mid-word: "...and re", "...triage, i")
    "XDR and endpoint security Secure your endpoints, clouds, and containers with AI-driven insights AI for security Automate your triage, investigation, and re",
    "XDR and endpoint security Secure your endpoints, clouds, and containers with AI-driven insights AI for security Automate your triage, i",    # Elastic product-feature-list sidebar blob
    "Context engineering Get the most relevant context to agents so that they deliver accurate and trusted outcomes Vector database Efficiently create, store, and search vector embeddings Search powered applications The speed, scale, and flexibility to power modern application experience Logs Collect, search, explore, and act on large volumes Threat protection Detect, investigate, and remediate cyber threats at scale.",
    # future-tense preamble teaser (no extractable fact)
    "It will also cover Monarch's major improvements since October, including native Kubernetes support.",
    "It will demonstrate how to wire up the new AgentCore SDK with an existing Spring Boot service.",
    # newsletter-link opener ("This latest one looks at...")
    "This latest one looks at using A2A to enable yet another kind of agent-to-agent communication with Spring AI.",
    # newsletter promo banner (InfoQ Software Architects' Newsletter)
    "InfoQ BT InfoQ Software Architects' Newsletter A monthly overview of things you need to know as an architect or aspiring architect.",
    "Sign up for the Software Architects' Newsletter and get things you need to know as an architect every month.",
    # bullet-list run-on (2+ "Be <Capital>" imperatives glued into one sentence)
    "Be generic to cover a variety of use cases Be specific so that a new user can apply it Be automated and scalable.",
    # code classname blob (CamelCase identifier ≥25 chars)
    "Upgraded Spring Boot to 3.5.14 Renamed JdbcChatMemoryRepositorySchemaInitializerPostgresqlTests to follow the integration test naming convention.",
    # section-heading comparison question ("Why X compared to Y?")
    "Why RFT with LLM-as-a-judge compared to generic RFT?",
    "Why serverless compared to container-based deployments for latency-sensitive workloads?",
    # "This section covers" boilerplate opener
    "This section covers the key steps involved in designing and deploying LLM-as-a-judge reward functions.",
    "This section discusses the architecture decisions behind the new distributed cache layer.",
])
def test_noisy_sentences_are_filtered(sentence, tmp_path):
    """Sentences identified as noise must produce zero extracted facts."""
    result = _run_sentence(sentence, tmp_path)
    assert result == [], f"Expected sentence to be filtered, but it passed:\n  {sentence!r}"


# --- sentences that MUST pass (good domain facts) ---

@pytest.mark.parametrize("sentence", [
    # the three facts currently in extracted_knowledge.json that should remain
    "Agentic AI systems are rapidly expanding beyond the digital world and into the physical, where AI agents perceive, reason, and act in real environments.",
    "Broadcom has announced the contribution of Velero, its Kubernetes-native backup and migration project, to the Cloud Native Computing Foundation as a Sandbox project.",
    "OpenAI GPT models, Codex, and Managed Agents are now available on AWS, enabling enterprises to build secure AI in their AWS environments.",
    # concrete metrics and named entities
    "The solution improved extraction accuracy from 79.7% to 90.8% and reduced processing time from 20 hours to under 5 seconds.",
    "Kubernetes is becoming the de facto operating system for AI.",
    "The spring-ai-openai module now uses the official openai-java SDK across all OpenAI models.",
    # availability announcement WITH enabling keyword (should pass)
    "Elastic 8.16 is now available on AWS Marketplace, enabling one-click deployment with BYOK encryption.",
    # generic filler WITH a concrete metric (should pass the generic-filler guard)
    "Many companies reported a 40% reduction in infrastructure costs after migrating to Kubernetes.",
    # camelCase inside a product name + 4-digit year (should pass the camelCase guard)
    "Spring Boot 3.4 was released in November 2025 with support for CDS and virtual threads.",
    # adversative opener that is not a conjunction — starts with a named subject
    "Meta has unveiled a new AI-driven capacity efficiency platform using unified AI agents.",
    # adversative conjunction + named subject (self-contained fact, must NOT be filtered)
    "However, IBM Bob has now reached 80,000 developers with 45% productivity gains.",
    "Nevertheless, Spring Boot 3.4 delivers a 30% reduction in AOT compilation time.",
    # version numbers that are all unique (should pass the version-blob guard)
    "Spring Boot 3.2, 3.3, and 3.4 each introduced distinct improvements to the AOT compiler.",
])
def test_good_sentences_pass_filters(sentence, tmp_path):
    """Sentences with concrete domain facts must survive the filter gauntlet."""
    result = _run_sentence(sentence, tmp_path)
    assert len(result) >= 1, f"Expected sentence to be extracted, but it was filtered:\n  {sentence!r}"


def test_cross_url_dedup_same_statement_not_stored_twice(tmp_path):
    """The same statement fetched from two different URLs must only be stored once."""
    good = "Kubernetes is becoming the de facto operating system for AI workloads."
    target = tmp_path / "ek.json"
    facts1 = extract_and_append_knowledge(
        article_text=good,
        source_url="https://site-a.example.com/article",
        source_title="Article A",
        path=target,
    )
    assert len(facts1) == 1, "First call should extract exactly 1 fact"
    facts2 = extract_and_append_knowledge(
        article_text=good,
        source_url="https://site-b.example.com/other-article",
        source_title="Article B",
        path=target,
    )
    assert facts2 == [], "Second call with same text from different URL should return 0 new facts"
