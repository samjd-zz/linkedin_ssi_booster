"""Tests for learned knowledge search routing and retrieval."""

import pytest

from services.console_grounding import (
    parse_query_constraints,
    search_learned_knowledge,
)
from services.console_grounding._models import ProjectFact


class TestLearnedKnowledgeRouting:
    """Test that learned knowledge queries are routed correctly."""

    def test_learned_knowledge_with_specific_topic_triggers_search(self):
        """When user asks 'based on what you learned, explain X', should trigger search."""
        query = "based on what you learned, explain the system is run on google kubernetes"
        constraints = parse_query_constraints(query)
        
        assert constraints.use_learned_knowledge is True
        assert constraints.search_learned_knowledge is True
        assert constraints.route_mode == "learned_context_search"

    def test_learned_knowledge_with_explain_triggers_search(self):
        """Queries with 'explain' should trigger search."""
        query = "from your learned knowledge, explain RAG"
        constraints = parse_query_constraints(query)
        
        assert constraints.use_learned_knowledge is True
        assert constraints.search_learned_knowledge is True
        assert constraints.route_mode == "learned_context_search"

    def test_learned_knowledge_with_about_triggers_search(self):
        """Queries with 'about' should trigger search."""
        query = "from your learning, tell me about vector search"
        constraints = parse_query_constraints(query)
        
        assert constraints.use_learned_knowledge is True
        assert constraints.search_learned_knowledge is True
        assert constraints.route_mode == "learned_context_search"

    def test_learned_knowledge_with_using_triggers_search(self):
        """Queries with 'using' should trigger search."""
        query = "using your learned knowledge, what are the AI trends?"
        constraints = parse_query_constraints(query)
        
        assert constraints.use_learned_knowledge is True
        assert constraints.search_learned_knowledge is True
        assert constraints.route_mode == "learned_context_search"

    def test_generic_learned_knowledge_query_no_search(self):
        """Generic queries like 'what have you learned?' should NOT trigger search."""
        query = "what have you learned recently?"
        constraints = parse_query_constraints(query)
        
        # This should NOT match learned knowledge phrases at all
        assert constraints.use_learned_knowledge is False
        assert constraints.search_learned_knowledge is False
        assert constraints.route_mode == "llm_with_context"

    def test_explicit_search_command(self):
        """Explicit 'search your learned knowledge' should trigger search."""
        query = "search your learned knowledge for kubernetes"
        constraints = parse_query_constraints(query)
        
        assert constraints.use_learned_knowledge is False  # Not a learned knowledge phrase
        assert constraints.search_learned_knowledge is True
        assert constraints.route_mode == "llm_with_context"

    def test_explicit_artifact_request_not_learned_knowledge(self):
        """Explicit artifact requests should not be treated as learned knowledge queries."""
        query = "show me extracted_knowledge"
        constraints = parse_query_constraints(query)
        
        assert constraints.explicit_artifact_request is True
        assert constraints.use_learned_knowledge is False
        assert constraints.search_learned_knowledge is False
        assert constraints.route_mode == "deterministic_citation"

    def test_regular_query_not_learned_knowledge(self):
        """Regular queries should not trigger learned knowledge routing."""
        query = "what is RAG?"
        constraints = parse_query_constraints(query)
        
        assert constraints.use_learned_knowledge is False
        assert constraints.search_learned_knowledge is False
        assert constraints.route_mode == "llm_with_context"


class TestSearchLearnedKnowledge:
    """Test the search_learned_knowledge function."""

    def test_search_finds_relevant_facts_by_keyword(self):
        """Search should find facts with matching keywords in details."""
        facts = [
            ProjectFact(
                project="Article 1",
                company="",
                years="",
                details="Kubernetes is a container orchestration platform for managing containerized applications.",
                source="extracted_knowledge:ext-001",
                tags={"kubernetes", "containers", "orchestration"},
            ),
            ProjectFact(
                project="Article 2",
                company="",
                years="",
                details="RAG (Retrieval Augmented Generation) combines retrieval with LLM generation.",
                source="extracted_knowledge:ext-002",
                tags={"rag", "llm", "retrieval"},
            ),
            ProjectFact(
                project="Article 3",
                company="",
                years="",
                details="Vector databases store embeddings for semantic search.",
                source="extracted_knowledge:ext-003",
                tags={"vector", "embeddings", "search"},
            ),
        ]
        
        query = "explain kubernetes orchestration"
        results = search_learned_knowledge(query, facts, limit=5)
        
        # Should return kubernetes fact first
        assert len(results) > 0
        assert "kubernetes" in results[0].details.lower()

    def test_search_finds_relevant_facts_by_tag(self):
        """Search should prioritize facts with matching tags."""
        facts = [
            ProjectFact(
                project="Article 1",
                company="",
                years="",
                details="This article discusses various topics in AI.",
                source="extracted_knowledge:ext-001",
                tags={"kubernetes", "containers"},
            ),
            ProjectFact(
                project="Article 2",
                company="",
                years="",
                details="This article covers machine learning concepts.",
                source="extracted_knowledge:ext-002",
                tags={"rag", "llm"},
            ),
        ]
        
        query = "kubernetes"
        results = search_learned_knowledge(query, facts, limit=5)
        
        # Should return kubernetes-tagged fact first (tag match scores higher)
        assert len(results) > 0
        assert "kubernetes" in results[0].tags

    def test_search_returns_empty_when_no_extracted_facts(self):
        """Search should return empty list when no extracted knowledge exists."""
        facts = [
            ProjectFact(
                project="Project X",
                company="Company Y",
                years="2020-2021",
                details="Built a system",
                source="persona:proj-001",
                tags=set(),
            ),
        ]
        
        query = "kubernetes"
        results = search_learned_knowledge(query, facts, limit=5)
        
        assert len(results) == 0

    def test_search_fallback_to_latest_when_no_matches(self):
        """When no keywords match, should return latest facts."""
        facts = [
            ProjectFact(
                project="Article 1",
                company="",
                years="",
                details="Topic A discussion",
                source="extracted_knowledge:ext-001",
                tags={"topic-a"},
            ),
            ProjectFact(
                project="Article 2",
                company="",
                years="",
                details="Topic B discussion",
                source="extracted_knowledge:ext-002",
                tags={"topic-b"},
            ),
        ]
        
        query = "completely unrelated query xyz"
        results = search_learned_knowledge(query, facts, limit=5)
        
        # Should return facts even though no matches (fallback to latest)
        assert len(results) == 2

    def test_search_respects_limit(self):
        """Search should respect the limit parameter."""
        facts = [
            ProjectFact(
                project=f"Article {i}",
                company="",
                years="",
                details=f"Kubernetes topic {i}",
                source=f"extracted_knowledge:ext-{i:03d}",
                tags={"kubernetes"},
            )
            for i in range(10)
        ]
        
        query = "kubernetes"
        results = search_learned_knowledge(query, facts, limit=3)
        
        assert len(results) == 3
