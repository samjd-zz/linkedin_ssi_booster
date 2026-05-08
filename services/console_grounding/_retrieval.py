"""Query constraint parsing, fact retrieval, and grounded-reply builders."""

from __future__ import annotations

import os

from services.console_grounding._config import (
    DOMAIN_KNOWLEDGE_PHRASES,
    EXPLICIT_ARTIFACT_PHRASES,
    LEARNED_KNOWLEDGE_PHRASES,
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
    - "From your learned knowledge" → use latest 5 extracted knowledge as context
    - Domain/project/tech queries → use artifacts as LLM context (default)
    - Everything else → LLM only
    """
    q = query.lower()
    
    # Check for explicit artifact requests (deterministic citation mode)
    explicit_artifact_request = any(phrase in q for phrase in EXPLICIT_ARTIFACT_PHRASES)
    
    # Check for "learned knowledge" requests
    use_learned_knowledge = any(phrase in q for phrase in LEARNED_KNOWLEDGE_PHRASES)
    
    # Determine route mode
    if explicit_artifact_request:
        route_mode = "deterministic_citation"
    elif use_learned_knowledge:
        route_mode = "learned_context"
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

    _is_domain = lambda f: f.source.startswith("domain:") or f.company == "Domain Knowledge"

    domain_facts = [f for f in facts if _is_domain(f)]
    project_facts = [f for f in facts if not _is_domain(f)]

    lines: list[str] = []

    if project_facts:
        lines.append("Here are the projects I can confirm from loaded profile context:")
        for f in project_facts:
            lines.append(f"- Project: {f.project}")
            if constraints.require_companies or f.company:
                lines.append(f"  Company: {f.company}")
            lines.append(f"  Years: {f.years}")
            lines.append(f"  Why relevant: {f.details}")
            lines.append(f"  [source: {f.source}]")

    if domain_facts:
        if project_facts:
            lines.append("")
        lines.append("Here is what I know from domain knowledge:")
        for f in domain_facts:
            lines.append(f"- Topic: {f.project}")
            lines.append(f"  Fact: {f.details}")
            lines.append(f"  Tags: {', '.join(sorted(f.tags)) if f.tags else 'n/a'}")
            lines.append(f"  [source: {f.source}]")

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


def get_latest_extracted_knowledge(all_facts: list[ProjectFact], limit: int = 5) -> list[ProjectFact]:
    """Get the latest N extracted knowledge facts for 'learned knowledge' queries.
    
    Filters for extracted_knowledge source and returns the most recent ones.
    """
    extracted = [f for f in all_facts if f.source.startswith("extracted_knowledge:")]
    # Return latest N (they're already in order from the loader)
    return extracted[:limit]


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
