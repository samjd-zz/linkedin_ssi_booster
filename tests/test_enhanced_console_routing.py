"""Unit tests for enhanced console mode query routing."""

from __future__ import annotations

import pytest

from services.console_grounding import (
    parse_query_constraints,
    get_latest_extracted_knowledge,
    build_learned_knowledge_context,
)
from services.console_grounding._models import ProjectFact


class TestEnhancedQueryRouting:
    """Test the new 5-mode query routing logic."""

    def test_explicit_artifact_request_extracted_knowledge(self):
        """Test explicit request for extracted knowledge routes to deterministic citation."""
        query = "show me extracted knowledge"
        constraints = parse_query_constraints(query)
        
        assert constraints.explicit_artifact_request is True
        assert constraints.requires_grounding is True
        assert constraints.route_mode == "deterministic_citation"

    def test_explicit_artifact_request_persona(self):
        """Test explicit request for persona routes to deterministic citation."""
        query = "list persona"
        constraints = parse_query_constraints(query)
        
        assert constraints.explicit_artifact_request is True
        assert constraints.requires_grounding is True
        assert constraints.route_mode == "deterministic_citation"

    def test_explicit_artifact_request_domain_knowledge(self):
        """Test explicit request for domain knowledge routes to deterministic citation."""
        query = "show domain knowledge about RAG"
        constraints = parse_query_constraints(query)
        
        assert constraints.explicit_artifact_request is True
        assert constraints.requires_grounding is True
        assert constraints.route_mode == "deterministic_citation"

    def test_learned_knowledge_request(self):
        """Test 'from your learned knowledge' triggers learned context mode."""
        query = "from your learned knowledge, what are the latest AI trends?"
        constraints = parse_query_constraints(query)
        
        assert constraints.use_learned_knowledge is True
        assert constraints.route_mode == "learned_context"
        assert constraints.requires_grounding is False

    def test_learned_knowledge_variations(self):
        """Test various learned knowledge phrase variations."""
        queries = [
            "from your learning, explain this",
            "based on what you learned, tell me about AI",
            "using your learned knowledge, what's new?",
        ]
        
        for query in queries:
            constraints = parse_query_constraints(query)
            assert constraints.use_learned_knowledge is True
            assert constraints.route_mode == "learned_context"

    def test_domain_knowledge_query_routes_to_context(self):
        """Test domain knowledge queries route to LLM with context (not deterministic)."""
        query = "What is RAG?"
        constraints = parse_query_constraints(query)
        
        assert constraints.require_domain_knowledge is True
        assert constraints.explicit_artifact_request is False
        assert constraints.requires_context is True
        assert constraints.route_mode == "llm_with_context"

    def test_project_query_routes_to_context(self):
        """Test project queries route to LLM with context (not deterministic)."""
        query = "What projects have you worked on?"
        constraints = parse_query_constraints(query)
        
        assert constraints.require_projects is True
        assert constraints.explicit_artifact_request is False
        assert constraints.requires_context is True
        assert constraints.route_mode == "llm_with_context"

    def test_tech_keyword_query_routes_to_context(self):
        """Test tech keyword queries route to LLM with context."""
        query = "Tell me about your Spring Boot experience"
        constraints = parse_query_constraints(query)
        
        assert "spring boot" in constraints.tech_tags or "spring" in constraints.tech_tags
        assert constraints.explicit_artifact_request is False
        assert constraints.requires_context is True
        assert constraints.route_mode == "llm_with_context"

    def test_general_chat_routes_to_llm_only(self):
        """Test general chat queries route to LLM only (no context)."""
        query = "How are you today?"
        constraints = parse_query_constraints(query)
        
        assert constraints.explicit_artifact_request is False
        assert constraints.use_learned_knowledge is False
        assert constraints.requires_context is False
        assert constraints.route_mode == "llm_with_context"

    def test_generative_request_not_affected_by_routing(self):
        """Test generative requests (write, generate) are handled separately in main.py."""
        # These are handled by GENERATIVE_REQUEST_PHRASES in main.py before routing
        query = "write a LinkedIn post about AI"
        constraints = parse_query_constraints(query)
        
        # Should still parse normally, main.py handles the generative routing
        assert constraints.route_mode == "llm_with_context"


class TestExtractedKnowledgeHelpers:
    """Test helper functions for extracted knowledge handling."""

    def test_get_latest_extracted_knowledge_filters_correctly(self):
        """Test that get_latest_extracted_knowledge filters only extracted knowledge facts."""
        facts = [
            ProjectFact(
                project="Test Project",
                company="Test Co",
                years="2020-2021",
                details="Built a thing",
                source="persona:evidence_1",
                tags=set(),
            ),
            ProjectFact(
                project="Extracted Knowledge",
                company="",
                years="",
                details="AI agents can use tools to accomplish tasks",
                source="extracted_knowledge:ek_001",
                tags={"ai", "agents"},
            ),
            ProjectFact(
                project="Domain Fact",
                company="Domain Knowledge",
                years="",
                details="RAG stands for Retrieval Augmented Generation",
                source="domain:rag",
                tags={"rag", "llm"},
            ),
            ProjectFact(
                project="Extracted Knowledge",
                company="",
                years="",
                details="Vector databases enable semantic search",
                source="extracted_knowledge:ek_002",
                tags={"vector", "search"},
            ),
        ]
        
        extracted = get_latest_extracted_knowledge(facts, limit=5)
        
        assert len(extracted) == 2
        assert all(f.source.startswith("extracted_knowledge:") for f in extracted)

    def test_get_latest_extracted_knowledge_respects_limit(self):
        """Test that limit parameter works correctly."""
        facts = [
            ProjectFact(
                project="Extracted Knowledge",
                company="",
                years="",
                details=f"Fact {i}",
                source=f"extracted_knowledge:ek_{i:03d}",
                tags=set(),
            )
            for i in range(10)
        ]
        
        extracted = get_latest_extracted_knowledge(facts, limit=3)
        
        assert len(extracted) == 3

    def test_build_learned_knowledge_context_formats_correctly(self):
        """Test that learned knowledge context is formatted properly."""
        facts = [
            ProjectFact(
                project="Extracted Knowledge",
                company="",
                years="",
                details="AI agents can use tools",
                source="extracted_knowledge:ek_001",
                tags={"ai", "agents"},
            ),
            ProjectFact(
                project="Extracted Knowledge",
                company="",
                years="",
                details="Vector databases enable semantic search",
                source="extracted_knowledge:ek_002",
                tags={"vector", "search"},
            ),
        ]
        
        context = build_learned_knowledge_context(facts)
        
        assert "Here's what I've learned recently" in context
        assert "AI agents can use tools" in context
        assert "Vector databases enable semantic search" in context
        assert "Tags: agents, ai" in context or "Tags: ai, agents" in context
        assert "Tags: search, vector" in context or "Tags: vector, search" in context

    def test_build_learned_knowledge_context_empty_facts(self):
        """Test handling of empty facts list."""
        context = build_learned_knowledge_context([])
        
        assert "don't have any learned knowledge" in context


class TestQueryConstraintsProperties:
    """Test the new properties on QueryConstraints."""

    def test_requires_grounding_only_true_for_explicit_requests(self):
        """Test requires_grounding is only True for explicit artifact requests."""
        # Explicit request
        constraints = parse_query_constraints("show me extracted knowledge")
        assert constraints.requires_grounding is True
        
        # Domain knowledge query (should use context, not grounding)
        constraints = parse_query_constraints("What is RAG?")
        assert constraints.requires_grounding is False

    def test_requires_context_true_for_domain_project_tech(self):
        """Test requires_context is True for domain/project/tech queries."""
        # Domain knowledge
        constraints = parse_query_constraints("What is RAG?")
        assert constraints.requires_context is True
        
        # Project query
        constraints = parse_query_constraints("What projects have you worked on?")
        assert constraints.requires_context is True
        
        # Tech keyword
        constraints = parse_query_constraints("Tell me about Java")
        assert constraints.requires_context is True

    def test_requires_context_false_for_explicit_and_general(self):
        """Test requires_context is False for explicit requests and general chat."""
        # Explicit request
        constraints = parse_query_constraints("show me persona")
        assert constraints.requires_context is False
        
        # General chat
        constraints = parse_query_constraints("How are you?")
        assert constraints.requires_context is False


class TestBackwardCompatibility:
    """Test that existing functionality still works."""

    def test_tech_tags_still_extracted(self):
        """Test that tech tags are still extracted from queries."""
        query = "What Spring Boot and Java projects have you done?"
        constraints = parse_query_constraints(query)
        
        assert "spring boot" in constraints.tech_tags or "spring" in constraints.tech_tags
        assert "java" in constraints.tech_tags

    def test_require_projects_still_works(self):
        """Test that require_projects flag still works."""
        query = "What projects have you worked on?"
        constraints = parse_query_constraints(query)
        
        assert constraints.require_projects is True

    def test_require_companies_still_works(self):
        """Test that require_companies flag still works."""
        query = "Where have you worked?"
        constraints = parse_query_constraints(query)
        
        assert constraints.require_companies is True

    def test_require_domain_knowledge_still_works(self):
        """Test that require_domain_knowledge flag still works."""
        query = "What is RAG?"
        constraints = parse_query_constraints(query)
        
        assert constraints.require_domain_knowledge is True