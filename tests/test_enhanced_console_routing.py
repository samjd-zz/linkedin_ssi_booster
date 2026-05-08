"""Unit tests for enhanced console mode query routing."""

from __future__ import annotations

import pytest

from services.console_grounding import (
    parse_query_constraints,
    get_latest_extracted_knowledge,
    build_learned_knowledge_context,
)
from services.console_grounding._models import ProjectFact


class TestSimplifiedQueryRouting:
    """Test the new 3-mode query routing logic."""

    def test_explicit_file_name_persona_graph(self):
        """Test explicit file name 'persona_graph' routes to deterministic citation."""
        query = "persona_graph"
        constraints = parse_query_constraints(query)
        
        assert constraints.explicit_artifact_request is True
        assert constraints.route_mode == "deterministic_citation"

    def test_explicit_file_name_extracted_knowledge(self):
        """Test explicit file name 'extracted_knowledge' routes to deterministic citation."""
        query = "extracted_knowledge"
        constraints = parse_query_constraints(query)
        
        assert constraints.explicit_artifact_request is True
        assert constraints.route_mode == "deterministic_citation"

    def test_explicit_file_name_domain_knowledge(self):
        """Test explicit file name 'domain_knowledge' routes to deterministic citation."""
        query = "domain_knowledge"
        constraints = parse_query_constraints(query)
        
        assert constraints.explicit_artifact_request is True
        assert constraints.route_mode == "deterministic_citation"

    def test_explicit_file_name_narrative_memory(self):
        """Test explicit file name 'narrative_memory' routes to deterministic citation."""
        query = "narrative_memory"
        constraints = parse_query_constraints(query)
        
        assert constraints.explicit_artifact_request is True
        assert constraints.route_mode == "deterministic_citation"

    def test_file_name_in_sentence(self):
        """Test file name mentioned in a sentence still triggers deterministic routing."""
        query = "Show me the persona_graph file"
        constraints = parse_query_constraints(query)
        
        assert constraints.explicit_artifact_request is True
        assert constraints.route_mode == "deterministic_citation"

    def test_learned_knowledge_request(self):
        """Test 'from your learned knowledge' triggers learned context mode."""
        query = "from your learned knowledge, what are the latest AI trends?"
        constraints = parse_query_constraints(query)
        
        assert constraints.use_learned_knowledge is True
        assert constraints.route_mode == "learned_context"
        assert constraints.explicit_artifact_request is False

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

    def test_domain_knowledge_query_routes_to_llm_context(self):
        """Test domain knowledge queries route to LLM with context (not deterministic)."""
        query = "What is RAG?"
        constraints = parse_query_constraints(query)
        
        assert constraints.require_domain_knowledge is True
        assert constraints.explicit_artifact_request is False
        assert constraints.use_learned_knowledge is False
        assert constraints.route_mode == "llm_with_context"

    def test_project_query_routes_to_llm_context(self):
        """Test project queries route to LLM with context (not deterministic)."""
        query = "What projects have you worked on?"
        constraints = parse_query_constraints(query)
        
        assert constraints.require_projects is True
        assert constraints.explicit_artifact_request is False
        assert constraints.use_learned_knowledge is False
        assert constraints.route_mode == "llm_with_context"

    def test_tech_keyword_query_routes_to_llm_context(self):
        """Test tech keyword queries route to LLM with context."""
        query = "Tell me about your Spring Boot experience"
        constraints = parse_query_constraints(query)
        
        assert "spring boot" in constraints.tech_tags or "spring" in constraints.tech_tags
        assert constraints.explicit_artifact_request is False
        assert constraints.use_learned_knowledge is False
        assert constraints.route_mode == "llm_with_context"

    def test_general_chat_routes_to_llm_context(self):
        """Test general chat queries route to LLM with context (default)."""
        query = "How are you today?"
        constraints = parse_query_constraints(query)
        
        assert constraints.explicit_artifact_request is False
        assert constraints.use_learned_knowledge is False
        assert constraints.route_mode == "llm_with_context"

    def test_generative_request_routes_to_llm_context(self):
        """Test generative requests route to LLM with context (default)."""
        query = "write a LinkedIn post about AI"
        constraints = parse_query_constraints(query)
        
        # Should route to default LLM with context
        assert constraints.explicit_artifact_request is False
        assert constraints.use_learned_knowledge is False
        assert constraints.route_mode == "llm_with_context"

    def test_show_me_extracted_knowledge_not_file_name(self):
        """Test 'show me extracted knowledge' does NOT trigger deterministic routing."""
        query = "show me extracted knowledge"
        constraints = parse_query_constraints(query)
        
        # This should NOT match because we only match exact file names
        assert constraints.explicit_artifact_request is False
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
