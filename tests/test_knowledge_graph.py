"""Unit tests for KnowledgeGraphManager and HybridRetriever.

Tests cover:
- Node and edge CRUD operations
- Graph proximity and claim support scoring
- Hybrid BM25 + graph reranking
- Serialization round-trip
- Bootstrap from AvatarState
- Graceful fallback when KG is absent
"""
from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import guards — skip all tests if networkx is not installed
# ---------------------------------------------------------------------------

try:
    import networkx as nx  # noqa: F401
    _NX_AVAILABLE = True
except ImportError:
    _NX_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _NX_AVAILABLE,
    reason="networkx not installed — skipping knowledge graph tests",
)

from services.knowledge_graph import (  # noqa: E402
    EDGE_HAS_SKILL,
    EDGE_SUPPORTS,
    EDGE_WORKED_ON,
    NODE_CLAIM,
    NODE_FACT,
    NODE_PERSON,
    NODE_PROJECT,
    NODE_SKILL,
    KnowledgeGraphManager,
)
from services.hybrid_retriever import HybridRetriever  # noqa: E402


# ---------------------------------------------------------------------------
# Minimal stub data classes (mirror avatar_intelligence dataclasses)
# ---------------------------------------------------------------------------


@dataclass
class _PersonNode:
    name: str = "Test Person"
    title: str = "Engineer"
    location: str = "Remote"
    links: list[str] = field(default_factory=list)


@dataclass
class _ProjectNode:
    id: str = "proj-1"
    name: str = "Test Project"
    company_id: str = "co-1"
    years: str = "2020-2024"
    details: str = "Built a Python RAG pipeline with BM25 and vector search."
    skills: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)


@dataclass
class _CompanyNode:
    id: str = "co-1"
    name: str = "Acme Corp"
    aliases: list[str] = field(default_factory=list)


@dataclass
class _SkillNode:
    id: str = "skill-python"
    name: str = "Python"
    aliases: list[str] = field(default_factory=list)
    scope: str = "domain"


@dataclass
class _ClaimNode:
    id: str = "claim-1"
    text: str = "Reduced API latency by 40% using async Python."
    project_ids: list[str] = field(default_factory=list)
    confidence_hint: str = "high"


@dataclass
class _PersonaGraph:
    schema_version: str = "1.0"
    person: _PersonNode = field(default_factory=_PersonNode)
    projects: list[_ProjectNode] = field(default_factory=list)
    companies: list[_CompanyNode] = field(default_factory=list)
    skills: list[_SkillNode] = field(default_factory=list)
    claims: list[_ClaimNode] = field(default_factory=list)


@dataclass
class _AvatarState:
    persona_graph: Optional[_PersonaGraph] = None
    narrative_memory: None = None
    domain_knowledge: None = None
    extracted_knowledge: None = None
    is_loaded: bool = True
    load_errors: list[str] = field(default_factory=list)


@dataclass
class _EvidenceFact:
    evidence_id: str
    project: str
    company: str
    years: str
    details: str
    skills: list[str]
    source_project_id: str


@dataclass
class _DomainEvidenceFact:
    evidence_id: str
    domain: str
    statement: str
    tags: list[str]
    confidence: str
    source_fact_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_simple_kg() -> KnowledgeGraphManager:
    """Return a KG with person → project → skill."""
    kg = KnowledgeGraphManager()
    kg.add_node("person:Alice", NODE_PERSON, label="Alice")
    kg._persona_id = "person:Alice"
    kg.add_node("skill:python", NODE_SKILL, label="Python")
    kg.add_node("project:rag", NODE_PROJECT, label="RAG Pipeline",
                metadata={"details": "BM25 retrieval system", "confidence": "high"})
    kg.add_node("fact:f1", NODE_FACT, label="Python is fast",
                metadata={"tags": ["python", "performance"]})
    kg.link_entities("person:Alice", "skill:python", EDGE_HAS_SKILL)
    kg.link_entities("person:Alice", "project:rag", EDGE_WORKED_ON)
    kg.link_entities("project:rag", "fact:f1", "DescribedBy")
    return kg


def _make_state_with_projects() -> _AvatarState:
    skill = _SkillNode(id="python", name="Python", aliases=["py"])
    project = _ProjectNode(
        id="rag-proj",
        name="RAG Pipeline",
        company_id="co-1",
        years="2023",
        details="Built BM25 and vector retrieval.",
        skills=["python"],
    )
    company = _CompanyNode(id="co-1", name="Acme Corp")
    claim = _ClaimNode(
        id="c1",
        text="Shipped RAG system with 95% accuracy.",
        project_ids=["rag-proj"],
        confidence_hint="high",
    )
    pg = _PersonaGraph(
        person=_PersonNode(name="Alice"),
        projects=[project],
        companies=[company],
        skills=[skill],
        claims=[claim],
    )
    return _AvatarState(persona_graph=pg, is_loaded=True)


# ---------------------------------------------------------------------------
# KnowledgeGraphManager — node/edge operations
# ---------------------------------------------------------------------------


class TestKGNodeOperations:
    def test_add_node_creates_node(self) -> None:
        kg = KnowledgeGraphManager()
        nid = kg.add_node("n1", NODE_PERSON, label="Alice")
        assert nid == "n1"
        assert kg.node_count == 1

    def test_add_node_idempotent_updates(self) -> None:
        kg = KnowledgeGraphManager()
        kg.add_node("n1", NODE_PERSON, label="Alice")
        kg.add_node("n1", NODE_PERSON, label="Alice Updated")
        assert kg.node_count == 1
        nodes = kg.query()
        assert nodes[0]["label"] == "Alice Updated"

    def test_link_entities_creates_edge(self) -> None:
        kg = KnowledgeGraphManager()
        kg.add_node("n1", NODE_PERSON, label="Alice")
        kg.add_node("n2", NODE_SKILL, label="Python")
        kg.link_entities("n1", "n2", EDGE_HAS_SKILL)
        assert kg.edge_count == 1

    def test_link_entities_missing_node_raises(self) -> None:
        kg = KnowledgeGraphManager()
        kg.add_node("n1", NODE_PERSON, label="Alice")
        with pytest.raises(ValueError, match="not in graph"):
            kg.link_entities("n1", "nonexistent", EDGE_HAS_SKILL)

    def test_add_fact_basic(self) -> None:
        kg = KnowledgeGraphManager()
        nid = kg.add_fact({"id": "f1", "type": NODE_FACT, "text": "Python is fast",
                           "confidence": "high", "source": "test"})
        assert nid == "f1"
        nodes = kg.query(node_type=NODE_FACT)
        assert len(nodes) == 1
        assert nodes[0]["label"] == "Python is fast"

    def test_add_fact_missing_id_raises(self) -> None:
        kg = KnowledgeGraphManager()
        with pytest.raises(ValueError, match="non-empty 'id'"):
            kg.add_fact({"type": NODE_FACT, "text": "something"})

    def test_query_filters_by_type(self) -> None:
        kg = _make_simple_kg()
        persons = kg.query(node_type=NODE_PERSON)
        assert len(persons) == 1
        assert persons[0]["label"] == "Alice"

    def test_query_all_returns_all(self) -> None:
        kg = _make_simple_kg()
        all_nodes = kg.query()
        assert len(all_nodes) == 4  # person + skill + project + fact


# ---------------------------------------------------------------------------
# KnowledgeGraphManager — proximity and support scoring
# ---------------------------------------------------------------------------


class TestKGScoring:
    def test_graph_proximity_direct_neighbour(self) -> None:
        kg = _make_simple_kg()
        prox = kg.graph_proximity("person:Alice", "skill:python")
        # distance=1 → 1/(1+1)=0.5
        assert prox == pytest.approx(0.5)

    def test_graph_proximity_two_hops(self) -> None:
        kg = _make_simple_kg()
        prox = kg.graph_proximity("person:Alice", "fact:f1")
        # path: Alice→project→fact, distance=2 → 1/3 ≈ 0.333
        assert prox == pytest.approx(1.0 / 3.0, abs=1e-3)

    def test_graph_proximity_no_path(self) -> None:
        kg = KnowledgeGraphManager()
        kg.add_node("n1", NODE_PERSON, label="A")
        kg.add_node("n2", NODE_FACT, label="B")
        prox = kg.graph_proximity("n1", "n2")
        assert prox == 0.0

    def test_graph_proximity_missing_node(self) -> None:
        kg = _make_simple_kg()
        assert kg.graph_proximity("person:Alice", "nonexistent") == 0.0

    def test_claim_support_connected(self) -> None:
        kg = _make_simple_kg()
        # fact:f1 has one incoming edge (from project:rag)
        support = kg.claim_support("fact:f1")
        assert support > 0.0
        assert support <= 1.0

    def test_claim_support_isolated(self) -> None:
        kg = KnowledgeGraphManager()
        kg.add_node("isolated", NODE_FACT, label="Alone")
        assert kg.claim_support("isolated") == 0.0

    def test_claim_support_missing_node(self) -> None:
        kg = _make_simple_kg()
        assert kg.claim_support("nonexistent") == 0.0


# ---------------------------------------------------------------------------
# KnowledgeGraphManager — find_facts
# ---------------------------------------------------------------------------


class TestKGFindFacts:
    def test_find_facts_returns_fact_types(self) -> None:
        kg = _make_simple_kg()
        results = kg.find_facts("python performance", persona_id="person:Alice")
        assert any(r["id"] == "fact:f1" for r in results)

    def test_find_facts_limit_respected(self) -> None:
        kg = KnowledgeGraphManager()
        kg.add_node("person:A", NODE_PERSON, label="A")
        kg._persona_id = "person:A"
        for i in range(10):
            fid = f"fact:{i}"
            kg.add_node(fid, NODE_FACT, label=f"fact about python {i}",
                        metadata={"tags": ["python"]})
        results = kg.find_facts("python", limit=3)
        assert len(results) <= 3

    def test_find_facts_empty_graph(self) -> None:
        kg = KnowledgeGraphManager()
        assert kg.find_facts("python") == []


# ---------------------------------------------------------------------------
# KnowledgeGraphManager — explain_fact_usage
# ---------------------------------------------------------------------------


class TestKGExplain:
    def test_explain_returns_paths(self) -> None:
        kg = _make_simple_kg()
        paths = kg.explain_fact_usage("fact:f1")
        assert len(paths) >= 1
        # All paths start from persona
        assert all(p[0] == "person:Alice" for p in paths)

    def test_explain_no_persona(self) -> None:
        kg = KnowledgeGraphManager()
        kg.add_node("fact:x", NODE_FACT, label="X")
        assert kg.explain_fact_usage("fact:x") == []

    def test_explain_missing_fact(self) -> None:
        kg = _make_simple_kg()
        assert kg.explain_fact_usage("fact:nonexistent") == []


# ---------------------------------------------------------------------------
# KnowledgeGraphManager — bootstrap_from_avatar_state
# ---------------------------------------------------------------------------


class TestKGBootstrap:
    def test_bootstrap_creates_person_node(self) -> None:
        kg = KnowledgeGraphManager()
        state = _make_state_with_projects()
        kg.bootstrap_from_avatar_state(state)
        persons = kg.query(node_type=NODE_PERSON)
        assert len(persons) == 1
        assert persons[0]["label"] == "Alice"

    def test_bootstrap_creates_project_nodes(self) -> None:
        kg = KnowledgeGraphManager()
        state = _make_state_with_projects()
        kg.bootstrap_from_avatar_state(state)
        projects = kg.query(node_type=NODE_PROJECT)
        assert len(projects) == 1
        assert projects[0]["label"] == "RAG Pipeline"

    def test_bootstrap_creates_skill_nodes(self) -> None:
        kg = KnowledgeGraphManager()
        state = _make_state_with_projects()
        kg.bootstrap_from_avatar_state(state)
        skills = kg.query(node_type=NODE_SKILL)
        assert len(skills) == 1

    def test_bootstrap_creates_claim_nodes(self) -> None:
        kg = KnowledgeGraphManager()
        state = _make_state_with_projects()
        kg.bootstrap_from_avatar_state(state)
        claims = kg.query(node_type=NODE_CLAIM)
        assert len(claims) == 1

    def test_bootstrap_persona_id_set(self) -> None:
        kg = KnowledgeGraphManager()
        state = _make_state_with_projects()
        kg.bootstrap_from_avatar_state(state)
        assert kg._persona_id == "person:Alice"

    def test_bootstrap_not_loaded_skips(self) -> None:
        kg = KnowledgeGraphManager()
        state = _AvatarState(is_loaded=False, persona_graph=None)
        kg.bootstrap_from_avatar_state(state)
        assert kg.node_count == 0

    def test_bootstrap_idempotent(self) -> None:
        kg = KnowledgeGraphManager()
        state = _make_state_with_projects()
        kg.bootstrap_from_avatar_state(state)
        count_1 = kg.node_count
        kg.bootstrap_from_avatar_state(state)
        count_2 = kg.node_count
        assert count_1 == count_2  # no duplicates

    def test_bootstrap_summary(self) -> None:
        kg = KnowledgeGraphManager()
        state = _make_state_with_projects()
        kg.bootstrap_from_avatar_state(state)
        s = kg.summary()
        assert s["nodes"] > 0
        assert s["edges"] > 0
        assert "Person" in s["node_types"]


# ---------------------------------------------------------------------------
# KnowledgeGraphManager — serialization round-trip
# ---------------------------------------------------------------------------


class TestKGSerialization:
    def test_serialize_and_load(self) -> None:
        kg = _make_simple_kg()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)
        try:
            kg.serialize_graph(path)
            kg2 = KnowledgeGraphManager()
            kg2.load_graph(path)
            assert kg2.node_count == kg.node_count
            assert kg2._persona_id == kg._persona_id
        finally:
            path.unlink(missing_ok=True)

    def test_load_missing_file_raises(self) -> None:
        kg = KnowledgeGraphManager()
        with pytest.raises(FileNotFoundError):
            kg.load_graph("/tmp/definitely_does_not_exist_kg.json")


# ---------------------------------------------------------------------------
# HybridRetriever — without KG (pure BM25)
# ---------------------------------------------------------------------------


class TestHybridRetrieverNullKG:
    def _facts(self) -> list[_EvidenceFact]:
        return [
            _EvidenceFact(
                evidence_id="E001",
                project="RAG Pipeline",
                company="Acme",
                years="2023",
                details="BM25 retrieval system with Python",
                skills=["Python", "BM25"],
                source_project_id="rag-proj",
            ),
            _EvidenceFact(
                evidence_id="E002",
                project="Java API",
                company="Beta Corp",
                years="2021",
                details="Spring Boot microservice with Kafka",
                skills=["Java", "Kafka"],
                source_project_id="java-api",
            ),
        ]

    def test_find_facts_returns_correct_length(self) -> None:
        hr = HybridRetriever(kg=None)
        results = hr.find_facts("python bm25", self._facts(), limit=1)
        assert len(results) == 1

    def test_find_facts_ranks_relevant_first(self) -> None:
        hr = HybridRetriever(kg=None)
        results = hr.find_facts("python bm25", self._facts(), limit=2)
        assert results[0].evidence_id == "E001"

    def test_find_facts_empty_candidates(self) -> None:
        hr = HybridRetriever(kg=None)
        assert hr.find_facts("query", [], limit=5) == []

    def test_score_breakdown_structure(self) -> None:
        hr = HybridRetriever(kg=None)
        breakdown = hr.score_breakdown("python", self._facts())
        assert len(breakdown) == 2
        for row in breakdown:
            assert "bm25" in row
            assert "semantic" in row
            assert "graph_proximity" in row
            assert "claim_support" in row
            assert "hybrid" in row

    def test_explain_fact_usage_no_kg(self) -> None:
        hr = HybridRetriever(kg=None)
        result = hr.explain_fact_usage(self._facts()[0])
        assert result == []


# ---------------------------------------------------------------------------
# HybridRetriever — with KG
# ---------------------------------------------------------------------------


class TestHybridRetrieverWithKG:
    def _make_hr(self) -> tuple[HybridRetriever, list[_EvidenceFact]]:
        kg = KnowledgeGraphManager()
        kg.add_node("person:Alice", NODE_PERSON, label="Alice")
        kg._persona_id = "person:Alice"
        kg.add_node("project:rag-proj", NODE_PROJECT, label="RAG Pipeline",
                    metadata={"details": "BM25 retrieval system", "confidence": "high"})
        kg.link_entities("person:Alice", "project:rag-proj", EDGE_WORKED_ON)
        kg.add_node("project:java-api", NODE_PROJECT, label="Java API",
                    metadata={"details": "Spring Boot"})
        # No link from persona to java-api — should have lower proximity

        hr = HybridRetriever(kg=kg, persona_id="person:Alice")
        facts = [
            _EvidenceFact(
                evidence_id="E001",
                project="RAG Pipeline",
                company="Acme",
                years="2023",
                details="BM25 retrieval system with Python",
                skills=["Python", "BM25"],
                source_project_id="rag-proj",
            ),
            _EvidenceFact(
                evidence_id="E002",
                project="Java API",
                company="Beta",
                years="2021",
                details="Spring Boot microservice",
                skills=["Java"],
                source_project_id="java-api",
            ),
        ]
        return hr, facts

    def test_graph_proximity_boosts_connected_fact(self) -> None:
        hr, facts = self._make_hr()
        breakdown = hr.score_breakdown("project details", facts)
        # E001 should have higher graph_proximity than E002 (E001 connected to persona)
        prox_e001 = next(b for b in breakdown if b["fact_id"] == "E001")["graph_proximity"]
        prox_e002 = next(b for b in breakdown if b["fact_id"] == "E002")["graph_proximity"]
        assert prox_e001 > prox_e002

    def test_hybrid_score_weights_sum_to_one(self) -> None:
        hr = HybridRetriever(kg=None,
                             bm25_weight=0.6, semantic_weight=0.15,
                             graph_weight=0.15, claim_weight=0.1)
        assert abs(hr._w_bm25 + hr._w_semantic + hr._w_graph + hr._w_claim - 1.0) < 1e-9

    def test_explain_fact_usage_with_kg(self) -> None:
        hr, facts = self._make_hr()
        paths = hr.explain_fact_usage(facts[0])
        # Should return at least one path from persona to project
        assert isinstance(paths, list)

    def test_find_facts_respects_limit(self) -> None:
        hr, facts = self._make_hr()
        results = hr.find_facts("python bm25", facts, limit=1)
        assert len(results) == 1
