"""Unit tests for enhanced console mode query routing."""

from __future__ import annotations

import pytest

from services.console_grounding import (
    build_deterministic_grounded_reply,
    build_kanji_teaching_context,
    parse_query_constraints,
    get_latest_extracted_knowledge,
    build_learned_knowledge_context,
    retrieve_relevant_facts,
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
        """Test various learned knowledge phrase variations.
        
        Note: These queries now trigger search mode because they contain
        topic indicators like 'explain', 'about', etc.
        """
        queries = [
            "from your learning, explain this",
            "based on what you learned, tell me about AI",
            "using your learned knowledge, what's new?",
        ]
        
        for query in queries:
            constraints = parse_query_constraints(query)
            assert constraints.use_learned_knowledge is True
            # These now trigger search because they have topic indicators
            assert constraints.route_mode == "learned_context_search"
            assert constraints.search_learned_knowledge is True

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

    def test_list_domain_knowledge_characters_routes_deterministic(self):
        """Natural language character-list requests should bypass LLM."""
        query = "list me all the characters from your domain knowledge"
        constraints = parse_query_constraints(query)

        assert constraints.explicit_artifact_request is True
        assert constraints.list_domain_characters is True
        assert constraints.route_mode == "deterministic_citation"

    def test_list_domain_terms_with_meanings_routes_deterministic(self):
        query = "list all domain knowledge terms with meanings"
        constraints = parse_query_constraints(query)

        assert constraints.explicit_artifact_request is True
        assert constraints.list_domain_terms is True
        assert constraints.route_mode == "deterministic_citation"


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


def test_kanji_teaching_context_combines_domain_fact_and_hepburn_reading():
    facts = [
        ProjectFact(
            project="Kanji Core",
            company="Domain Knowledge",
            years="general",
            details="一 is a core high-frequency kanji meaning one; teach via words.",
            source="domain:k200-001",
            tags={"一", "one", "core kanji"},
        )
    ]

    context = build_kanji_teaching_context(facts)

    assert "Kanji teaching aids from loaded domain knowledge" in context
    assert "一 | Hepburn: ichi" in context
    assert "Domain meaning: is a core high-frequency kanji meaning one" in context


class TestBackwardCompatibility:
    """Test that existing functionality still works."""

    def test_kanji_teaching_request_is_detected(self):
        constraints = parse_query_constraints("Sam, teach me kanji from your domain knowledge")

        assert constraints.is_kanji_teaching_request is True

    def test_plain_kanji_question_is_not_teaching_request(self):
        constraints = parse_query_constraints("What is kanji?")

        assert constraints.is_kanji_teaching_request is False

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


class TestFactRetrievalScoring:
    """Regression tests for query-aware ranking in console retrieval."""

    def test_query_overlap_boosts_domain_fact(self):
        constraints = parse_query_constraints("kanji")
        facts = [
            ProjectFact(
                project="Spring APIs",
                company="Acme",
                years="2021",
                details="Built microservices with Java and Spring Boot",
                source="avatar:proj-1",
                tags={"java", "spring"},
            ),
            ProjectFact(
                project="Japanese Writing System",
                company="Domain Knowledge",
                years="general",
                details="Kanji are used with hiragana and katakana in mixed script.",
                source="domain:kanji-writing-system-mixed-script",
                tags={"kanji", "hiragana", "katakana"},
            ),
        ]

        ranked = retrieve_relevant_facts(facts, constraints, query="kanji", limit=1)
        assert ranked
        assert ranked[0].source.startswith("domain:")


class TestDomainCharacterListing:
    """Deterministic listing for domain knowledge character extraction."""

    def test_build_reply_lists_detected_cjk_characters(self):
        facts = [
            ProjectFact(
                project="Kanji Core",
                company="Domain Knowledge",
                years="general",
                details="Characters include 一二三 and 界 in examples.",
                source="domain:k200",
                tags={"一", "二", "三", "界"},
            )
        ]
        constraints = parse_query_constraints("list me all the characters from your domain knowledge")
        reply = build_deterministic_grounded_reply(
            "list me all the characters from your domain knowledge",
            facts,
            constraints,
        )

        assert "I found" in reply
        for ch in ("一", "二", "三", "界"):
            assert ch in reply

    def test_build_reply_lists_characters_with_meanings(self):
        facts = [
            ProjectFact(
                project="Kanji Core",
                company="Domain Knowledge",
                years="general",
                details="一 is a core high-frequency kanji meaning one; teach via words.",
                source="domain:k200-001",
                tags={"一", "one", "core kanji"},
            ),
            ProjectFact(
                project="Kanji Core",
                company="Domain Knowledge",
                years="general",
                details="二 is a core high-frequency kanji meaning two; teach via words.",
                source="domain:k200-002",
                tags={"二", "two", "core kanji"},
            ),
        ]
        constraints = parse_query_constraints(
            "list me all the characters from your domain knowledge with their meaning"
        )
        reply = build_deterministic_grounded_reply(
            "list me all the characters from your domain knowledge with their meaning",
            facts,
            constraints,
        )

        assert "with extracted meanings" in reply
        assert "一: one" in reply
        assert "二: two" in reply

    def test_build_reply_lists_generic_domain_terms_with_meanings(self):
        facts = [
            ProjectFact(
                project="Python",
                company="Domain Knowledge",
                years="general",
                details="Python is a high-level interpreted programming language.",
                source="domain:python-core",
                tags={"python", "language"},
            ),
            ProjectFact(
                project="FastAPI",
                company="Domain Knowledge",
                years="general",
                details="FastAPI is a modern high-performance Python web framework for APIs.",
                source="domain:python-fastapi",
                tags={"fastapi", "api"},
            ),
        ]
        constraints = parse_query_constraints("list all domain knowledge terms with meanings")
        reply = build_deterministic_grounded_reply(
            "list all domain knowledge terms with meanings",
            facts,
            constraints,
        )

        assert "domain terms with extracted meanings" in reply
        assert "Python: a high-level interpreted programming language" in reply
        assert "FastAPI: a modern high-performance Python web framework for APIs" in reply

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


class TestJapaneseArtImageIntent:
    """Test suite for Japanese art and character image request detection."""

    def test_japanese_art_image_request_detection(self):
        queries = [
            ("Draw a shrine maiden near a torii gate", "shrine maiden near a torii gate"),
            ("Render a samurai warrior in ukiyo-e style", "samurai warrior in ukiyo-e style"),
            ("Generate an image of 'Sakura'", "Sakura"),
            ("Paint an illustration of a geisha with cherry blossoms", "geisha with cherry blossoms"),
            ("Show me a picture of kanji 夢 in golden calligraphy", "kanji 夢 in golden calligraphy"),
        ]
        for query, expected_hint in queries:
            constraints = parse_query_constraints(query)
            assert constraints.has_image_request is True
            assert constraints.is_japanese_art_request is True
            assert expected_hint in constraints.art_subject_hint

    def test_generic_image_request_detection(self):
        query = "Generate an image of a cloud architecture diagram"
        constraints = parse_query_constraints(query)
        assert constraints.has_image_request is True
        assert constraints.is_japanese_art_request is False
        assert "cloud architecture" in constraints.art_subject_hint

