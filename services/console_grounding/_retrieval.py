"""Query constraint parsing, fact retrieval, and grounded-reply builders."""

from __future__ import annotations

import os

from services.console_grounding._config import (
    DOMAIN_KNOWLEDGE_PHRASES,
    EXPLICIT_ARTIFACT_PHRASES,
    LEARNED_KNOWLEDGE_PHRASES,
    SEARCH_LEARNED_KNOWLEDGE_PHRASES,
    get_console_grounding_keywords,
    get_console_grounding_tag_expansions_from_graph,
)
from services.console_grounding._models import ProjectFact, QueryConstraints


def parse_query_constraints(
    query: str,
    tech_keywords: set[str] | None = None,
    tag_expansions: dict[str, set[str]] | None = None,
) -> QueryConstraints:
    """Parse query to determine routing mode and constraints.
    
    New routing logic:
    - Explicit artifact phrases (e.g., "show me extracted knowledge") → deterministic citation
    - "From your learned knowledge" → search extracted knowledge for relevant facts
    - Domain/project/tech queries → use artifacts as LLM context (default)
    - Everything else → LLM only
    """
    q = query.lower()
    
    # Check for explicit artifact requests (deterministic citation mode)
    explicit_artifact_request = any(phrase in q for phrase in EXPLICIT_ARTIFACT_PHRASES)
    
    # Check for "learned knowledge" requests
    use_learned_knowledge = any(phrase in q for phrase in LEARNED_KNOWLEDGE_PHRASES)
    
    # Check for "search learned knowledge" requests (explicit search command)
    search_learned_knowledge = any(phrase in q for phrase in SEARCH_LEARNED_KNOWLEDGE_PHRASES)
    
    # If user asks about learned knowledge with a specific topic, always search
    # Only use "latest 5" if they ask something generic like "what have you learned?"
    if use_learned_knowledge and not search_learned_knowledge:
        # Check if query has specific topic keywords (not just the learned knowledge phrase)
        # If it does, treat it as a search request
        topic_indicators = ["explain", "about", "regarding", "on", "for", "with", "using"]
        has_specific_topic = any(indicator in q for indicator in topic_indicators)
        if has_specific_topic:
            search_learned_knowledge = True
    
    # Determine route mode
    if explicit_artifact_request:
        route_mode = "deterministic_citation"
    elif use_learned_knowledge:
        route_mode = "learned_context_search" if search_learned_knowledge else "learned_context"
    else:
        route_mode = "llm_with_context"
    
    require_projects = any(w in q for w in ["project", "projects", "worked on", "built", "resume"])
    require_companies = any(w in q for w in ["company", "companies", "where", "worked at", "employer"])
    require_domain_knowledge = any(phrase in q for phrase in DOMAIN_KNOWLEDGE_PHRASES)

    active_keywords = tech_keywords if tech_keywords is not None else get_console_grounding_keywords()
    tags: set[str] = set()
    for kw in active_keywords:
        if kw in q:
            tags.add(kw)

    expansions = tag_expansions if tag_expansions is not None else get_console_grounding_tag_expansions_from_graph()
    for base_tag, related in expansions.items():
        if base_tag in tags:
            tags.update(related)

    return QueryConstraints(
        require_projects=require_projects,
        require_companies=require_companies,
        require_domain_knowledge=require_domain_knowledge,
        tech_tags=tags,
        explicit_artifact_request=explicit_artifact_request,
        use_learned_knowledge=use_learned_knowledge,
        search_learned_knowledge=search_learned_knowledge,
        route_mode=route_mode,
    )


def retrieve_relevant_facts(
    facts: list[ProjectFact],
    constraints: QueryConstraints,
    limit: int = 8,
) -> list[ProjectFact]:
    if not facts:
        return []

    _is_domain = lambda f: f.source.startswith("domain:") or f.company == "Domain Knowledge"

    scored: list[tuple[int, ProjectFact]] = []
    for fact in facts:
        score = 0
        if constraints.tech_tags:
            score += len(fact.tags.intersection(constraints.tech_tags)) * 5
        if constraints.require_projects and not _is_domain(fact):
            score += 1
        if constraints.require_companies and fact.company and not _is_domain(fact):
            score += 2
        if constraints.require_domain_knowledge and _is_domain(fact):
            score += 4
        if (
            (constraints.require_projects or constraints.require_companies)
            and not constraints.require_domain_knowledge
            and _is_domain(fact)
        ):
            score -= 2
        score += min(len(fact.details) // 120, 3)
        scored.append((score, fact))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [f for s, f in scored if s > 0][:limit]
    return top if top else [f for _, f in scored[:limit]]


def build_deterministic_grounded_reply(
    query: str,
    facts: list[ProjectFact],
    constraints: QueryConstraints,
) -> str:
    """Build a deterministic cited response for fact-heavy console queries."""
    if not facts:
        if constraints.require_domain_knowledge:
            return (
                "I don't have confirmed domain knowledge records for that topic. "
                "Try asking about a specific technology (e.g. RAG, BM25, microservices, LLM)."
            )
        return (
            "I don't have confirmed project/company records for that request in the loaded profile context. "
            "Try asking with a specific technology or company keyword."
        )

    # Categorize facts by source type
    _is_domain = lambda f: f.source.startswith("domain:") or f.company == "Domain Knowledge"
    _is_extracted = lambda f: f.source.startswith("extracted_knowledge:")
    _is_persona = lambda f: f.source.startswith("persona:") and not _is_domain(f) and not _is_extracted(f)

    # Check if user explicitly requested a specific artifact file
    query_lower = query.lower()
    requested_extracted = "extracted_knowledge" in query_lower
    requested_persona = "persona_graph" in query_lower
    requested_domain = "domain_knowledge" in query_lower
    requested_narrative = "narrative_memory" in query_lower

    extracted_facts = [f for f in facts if _is_extracted(f)]
    domain_facts = [f for f in facts if _is_domain(f)]
    persona_facts = [f for f in facts if _is_persona(f)]

    lines: list[str] = []

    # If user explicitly requested extracted_knowledge, show ONLY that
    if requested_extracted:
        if not extracted_facts:
            return "I don't have any extracted knowledge available yet. Use --curate --learn to extract knowledge from articles."
        lines.append("Here's what I've learned from articles and content I've processed:")
        for i, f in enumerate(extracted_facts, 1):
            lines.append(f"{i}. {f.details}")
            if f.tags:
                lines.append(f"   Tags: {', '.join(sorted(f.tags))}")
            lines.append(f"   [source: {f.source}]")
        return "\n".join(lines)

    # If user explicitly requested persona_graph, show ONLY that
    if requested_persona:
        if not persona_facts:
            return "I don't have any persona facts loaded from persona_graph.json."
        lines.append("Here are the projects I can confirm from persona_graph.json:")
        for f in persona_facts:
            lines.append(f"- Project: {f.project}")
            if f.company:
                lines.append(f"  Company: {f.company}")
            lines.append(f"  Years: {f.years}")
            lines.append(f"  Details: {f.details}")
            lines.append(f"  [source: {f.source}]")
        return "\n".join(lines)

    # If user explicitly requested domain_knowledge, show ONLY that
    if requested_domain:
        if not domain_facts:
            return "I don't have any domain knowledge loaded from domain_knowledge packs."
        lines.append("Here is what I know from domain_knowledge packs:")
        for f in domain_facts:
            lines.append(f"- Topic: {f.project}")
            lines.append(f"  Fact: {f.details}")
            lines.append(f"  Tags: {', '.join(sorted(f.tags)) if f.tags else 'n/a'}")
            lines.append(f"  [source: {f.source}]")
        return "\n".join(lines)

    # If user explicitly requested narrative_memory, show message (not yet implemented)
    if requested_narrative:
        return "Narrative memory is not yet implemented. This will store episodic memories and experiences."

    # Otherwise, show all relevant facts (mixed mode for general queries)
    if persona_facts:
        lines.append("Here are the projects I can confirm from loaded profile context:")
        for f in persona_facts:
            lines.append(f"- Project: {f.project}")
            if constraints.require_companies or f.company:
                lines.append(f"  Company: {f.company}")
            lines.append(f"  Years: {f.years}")
            lines.append(f"  Why relevant: {f.details}")
            lines.append(f"  [source: {f.source}]")

    if domain_facts:
        if persona_facts:
            lines.append("")
        lines.append("Here is what I know from domain knowledge:")
        for f in domain_facts:
            lines.append(f"- Topic: {f.project}")
            lines.append(f"  Fact: {f.details}")
            lines.append(f"  Tags: {', '.join(sorted(f.tags)) if f.tags else 'n/a'}")
            lines.append(f"  [source: {f.source}]")

    if extracted_facts:
        if persona_facts or domain_facts:
            lines.append("")
        lines.append("Here's what I've learned from articles:")
        for i, f in enumerate(extracted_facts, 1):
            lines.append(f"{i}. {f.details}")
            if f.tags:
                lines.append(f"   Tags: {', '.join(sorted(f.tags))}")

    if constraints.tech_tags:
        lines.append(f"\nFilter applied: {', '.join(sorted(constraints.tech_tags))}")
    return "\n".join(lines)


def build_grounding_facts_block(facts: list[ProjectFact], limit: int | None = None) -> str:
    """Build a compact deterministic facts block for generation prompts.

    *limit* defaults to EVIDENCE_PROJECT_COUNT + EVIDENCE_DOMAIN_COUNT from .env
    (falling back to 5) so the display cap always matches the retrieval split.
    """
    if limit is None:
        try:
            limit = int(os.getenv("EVIDENCE_PROJECT_COUNT", "3")) + int(
                os.getenv("EVIDENCE_DOMAIN_COUNT", "2")
            )
        except Exception:
            limit = 5
    if not facts:
        return ""

    lines = [
        "Your background — weave these in naturally when they genuinely connect to the topic:"
    ]
    for fact in facts[:limit]:
        lines.append(
            f"- Project: {fact.project} | Company: {fact.company} | Years: {fact.years} | Detail: {fact.details}"
        )
    return "\n".join(lines)


def build_katzilla_citation_reply(query: str, external_facts: list[object]) -> str:
    """Build a deterministic citation-first reply for Katzilla evidence."""
    if not external_facts:
        return (
            "No Katzilla evidence was returned for that query. "
            "Try a more specific request like 'congress AI bill', 'fda recall', or 'usgs earthquake'."
        )

    lines: list[str] = [
        f"Katzilla evidence for: {query}",
        "",
    ]
    for idx, fact in enumerate(external_facts, 1):
        statement = str(getattr(fact, "statement", "")).strip()
        source_name = str(getattr(fact, "source_name", "")).strip()
        source_url = str(getattr(fact, "source_url", "")).strip()
        retrieved_at = str(getattr(fact, "retrieved_at", "")).strip()
        license_name = str(getattr(fact, "license", "")).strip()
        update_frequency = str(getattr(fact, "update_frequency", "")).strip()
        evidence_id = str(getattr(fact, "evidence_id", "")).strip()
        lines.append(f"{idx}. {statement}")
        lines.append(f"   [id: {evidence_id}]")
        if source_name:
            lines.append(f"   source: {source_name}")
        if source_url:
            lines.append(f"   url: {source_url}")
        if retrieved_at:
            lines.append(f"   retrieved_at: {retrieved_at}")
        if license_name:
            lines.append(f"   license: {license_name}")
        if update_frequency:
            lines.append(f"   update_frequency: {update_frequency}")

    return "\n".join(lines)


def get_latest_extracted_knowledge(all_facts: list[ProjectFact], limit: int = 5) -> list[ProjectFact]:
    """Get the latest N extracted knowledge facts for 'learned knowledge' queries.
    
    Filters for extracted_knowledge source and returns the most recent ones.
    """
    extracted = [f for f in all_facts if f.source.startswith("extracted_knowledge:")]
    # Return latest N (they're already in order from the loader)
    return extracted[:limit]


def search_learned_knowledge(
    query: str,
    all_facts: list[ProjectFact],
    limit: int = 5,
) -> list[ProjectFact]:
    """Search extracted knowledge facts by keyword overlap with query.
    
    Scores each extracted knowledge fact based on:
    - Number of query words found in fact details (case-insensitive)
    - Tag overlap with query keywords
    
    Returns top N facts sorted by relevance score.
    """
    extracted = [f for f in all_facts if f.source.startswith("extracted_knowledge:")]
    if not extracted:
        return []
    
    # Tokenize query into keywords (filter out common stop words)
    stop_words = {"a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by", "from", "your", "my", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "should", "could", "may", "might", "must", "can", "about", "what", "which", "who", "when", "where", "why", "how", "this", "that", "these", "those", "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them"}
    query_lower = query.lower()
    query_words = [w for w in query_lower.split() if w not in stop_words and len(w) > 2]
    
    if not query_words:
        # Fallback to latest if no meaningful keywords
        return extracted[:limit]
    
    scored: list[tuple[int, ProjectFact]] = []
    for fact in extracted:
        score = 0
        fact_lower = fact.details.lower()
        
        # Score by keyword overlap in details
        for word in query_words:
            if word in fact_lower:
                score += 3
        
        # Score by tag overlap
        fact_tags_lower = {tag.lower() for tag in fact.tags}
        for word in query_words:
            if word in fact_tags_lower:
                score += 5
        
        scored.append((score, fact))
    
    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    
    # Return top N with score > 0, or fallback to latest if no matches
    top = [f for s, f in scored if s > 0][:limit]
    return top if top else extracted[:limit]


def build_learned_knowledge_context(facts: list[ProjectFact]) -> str:
    """Build a context block from learned knowledge for LLM prompts.
    
    Used when user says "from your learned knowledge" or similar phrases.
    """
    if not facts:
        return "I don't have any learned knowledge available yet."
    
    lines = [
        "Here's what I've learned recently from articles and content I've processed:"
    ]
    for i, fact in enumerate(facts, 1):
        lines.append(f"{i}. {fact.details}")
        if fact.tags:
            lines.append(f"   Tags: {', '.join(sorted(fact.tags))}")
    
    return "\n".join(lines)
