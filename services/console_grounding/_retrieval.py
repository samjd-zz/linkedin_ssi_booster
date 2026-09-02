"""Query constraint parsing, fact retrieval, and grounded-reply builders."""

from __future__ import annotations

import os
import re

from services.console_grounding._config import (
    DOMAIN_KNOWLEDGE_PHRASES,
    EXPLICIT_ARTIFACT_PHRASES,
    IMAGE_REQUEST_VERBS,
    JAPANESE_ART_SUBJECTS,
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

    # Special deterministic intent: list/extract all kanji characters from
    # domain knowledge (supports natural phrasing, not only file names).
    character_list_request = (
        ("character" in q or "characters" in q or "kanji" in q)
        and ("list" in q or "show" in q or "all" in q)
        and ("domain knowledge" in q or "domain_knowledge" in q)
    )

    term_list_request = (
        ("term" in q or "terms" in q or "concept" in q or "concepts" in q)
        and ("list" in q or "show" in q or "all" in q)
        and ("domain knowledge" in q or "domain_knowledge" in q)
        and ("meaning" in q or "meanings" in q)
    )
    explicit_artifact_request = explicit_artifact_request or character_list_request
    explicit_artifact_request = explicit_artifact_request or term_list_request
    
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

    # Check for image generation / artwork requests
    has_image_request = any(phrase in q for phrase in IMAGE_REQUEST_VERBS)
    has_japanese_subject = any(subject in q for subject in JAPANESE_ART_SUBJECTS)
    is_japanese_art_request = has_image_request and (
        has_japanese_subject
        or any(k in q for k in ["japanese", "kanji", "hiragana", "katakana", "romaji", "anime", "manga"])
    )

    art_subject_hint = ""
    if has_image_request:
        match = re.search(r'["\']([^"\']+)["\']', query)
        if match:
            art_subject_hint = match.group(1).strip()
        else:
            for prep in [
                "illustration of",
                "picture of",
                "image of",
                "art of",
                "depicting",
                "showing",
                "draw a",
                "draw an",
                "draw",
                "render",
                "paint",
                "visualize",
            ]:
                if prep in q:
                    idx = q.find(prep) + len(prep)
                    art_subject_hint = query[idx:].strip(" .!?,;")
                    break
            if not art_subject_hint:
                art_subject_hint = query.strip()

    return QueryConstraints(
        require_projects=require_projects,
        require_companies=require_companies,
        require_domain_knowledge=require_domain_knowledge,
        tech_tags=tags,
        explicit_artifact_request=explicit_artifact_request,
        list_domain_characters=character_list_request,
        list_domain_terms=term_list_request,
        use_learned_knowledge=use_learned_knowledge,
        search_learned_knowledge=search_learned_knowledge,
        has_image_request=has_image_request,
        is_japanese_art_request=is_japanese_art_request,
        art_subject_hint=art_subject_hint,
        route_mode=route_mode,
    )


def retrieve_relevant_facts(
    facts: list[ProjectFact],
    constraints: QueryConstraints,
    query: str = "",
    limit: int = 8,
) -> list[ProjectFact]:
    if not facts:
        return []

    _is_domain = lambda f: f.source.startswith("domain:") or f.company == "Domain Knowledge"
    query_tokens = set(re.findall(r"\w+", query.lower()))

    scored: list[tuple[int, ProjectFact]] = []
    for fact in facts:
        score = 0
        fact_text = f"{fact.project} {fact.company} {fact.years} {fact.details}".lower()
        fact_tokens = set(re.findall(r"\w+", fact_text))
        # Reward direct lexical overlap so new domain packs are discoverable
        # even when their tags are not pre-configured in .env keyword lists.
        if query_tokens:
            score += len(query_tokens.intersection(fact_tokens)) * 3
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
    requested_domain = "domain_knowledge" in query_lower or "domain knowledge" in query_lower
    requested_narrative = "narrative_memory" in query_lower

    extracted_facts = [f for f in facts if _is_extracted(f)]
    domain_facts = [f for f in facts if _is_domain(f)]
    persona_facts = [f for f in facts if _is_persona(f)]

    lines: list[str] = []

    list_term_request = constraints.list_domain_terms

    list_character_request = (
        requested_domain
        and ("character" in query_lower or "characters" in query_lower or "kanji" in query_lower)
        and ("list" in query_lower or "show" in query_lower or "all" in query_lower)
    )

    if list_character_request:
        if not domain_facts:
            return "I don't have any domain knowledge facts loaded to extract characters from."
        include_meanings = "meaning" in query_lower or "meanings" in query_lower
        chars = _extract_cjk_characters_from_domain_facts(domain_facts)
        if not chars:
            # Fallback: reload full domain-knowledge fact pool in case caller
            # passed a ranked subset that omitted kanji-bearing facts.
            try:
                from services.avatar_intelligence import (
                    domain_facts_to_project_facts,
                    load_avatar_state,
                    normalize_domain_facts,
                )

                full_state = load_avatar_state()
                full_domain_facts = domain_facts_to_project_facts(
                    normalize_domain_facts(full_state)
                )
                domain_facts = full_domain_facts
                chars = _extract_cjk_characters_from_domain_facts(full_domain_facts)
            except Exception:
                chars = []
        if not chars:
            return "I found domain knowledge facts, but no CJK characters were detected in them."

        if include_meanings:
            meanings = _extract_cjk_character_meanings_from_domain_facts(domain_facts)
            lines.append(f"I found {len(chars)} characters with extracted meanings from loaded domain knowledge:")
            for ch in chars:
                meaning = meanings.get(ch, "meaning not explicitly stated")
                lines.append(f"{ch}: {meaning}")
            return "\n".join(lines)

        # Keep output readable while returning the full list deterministically.
        chunk_size = 40
        lines.append(f"I found {len(chars)} characters in loaded domain knowledge:")
        for i in range(0, len(chars), chunk_size):
            lines.append("".join(chars[i : i + chunk_size]))
        return "\n".join(lines)

    if list_term_request:
        if not domain_facts:
            return "I don't have any domain knowledge facts loaded to extract terms from."
        term_meanings = _extract_domain_terms_with_meanings(domain_facts)
        if not term_meanings:
            return "I found domain knowledge facts, but no clear term-meaning pairs were detected."

        lines.append(
            f"I found {len(term_meanings)} domain terms with extracted meanings from loaded domain knowledge:"
        )
        for term, meaning in term_meanings:
            lines.append(f"{term}: {meaning}")
        return "\n".join(lines)

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


def _extract_cjk_characters_from_domain_facts(domain_facts: list[ProjectFact]) -> list[str]:
    """Extract unique CJK Unified Ideographs from domain fact text/tags.

    Preserves first-seen order so output is deterministic and stable.
    """
    seen: set[str] = set()
    ordered: list[str] = []

    def _push(text: str) -> None:
        for ch in text:
            if "\u4e00" <= ch <= "\u9fff" and ch not in seen:
                seen.add(ch)
                ordered.append(ch)

    for fact in domain_facts:
        _push(fact.project)
        _push(fact.details)
        for tag in fact.tags:
            _push(tag)

    return ordered


def _extract_cjk_character_meanings_from_domain_facts(
    domain_facts: list[ProjectFact],
) -> dict[str, str]:
    """Extract per-character meanings from domain facts.

    Heuristics (first match wins in corpus order):
    - "<char> ... meaning <text>;" pattern in the statement.
    - English tags (non-CJK) when available.
    """
    mapping: dict[str, str] = {}
    meaning_re = re.compile(
        r"([\u4e00-\u9fff])[^\n]{0,80}?\bmeaning\s+([^.;\n]+)",
        re.IGNORECASE,
    )

    for fact in domain_facts:
        statement = fact.details or ""
        match = meaning_re.search(statement)
        if match:
            ch = match.group(1)
            meaning = match.group(2).strip().strip('"\'')
            if ch and meaning and ch not in mapping:
                mapping[ch] = meaning

        # Tag fallback for characters that have no explicit "meaning ..." clause.
        # We treat the first non-CJK tag as a concise gloss.
        for tag in sorted(fact.tags):
            cjk_chars = [c for c in tag if "\u4e00" <= c <= "\u9fff"]
            if not cjk_chars:
                continue
            gloss_candidates = [
                t.strip()
                for t in sorted(fact.tags)
                if t.strip() and not any("\u4e00" <= x <= "\u9fff" for x in t)
            ]
            if not gloss_candidates:
                continue
            gloss = gloss_candidates[0]
            for ch in cjk_chars:
                mapping.setdefault(ch, gloss)

    return mapping


def _extract_domain_terms_with_meanings(
    domain_facts: list[ProjectFact],
) -> list[tuple[str, str]]:
    """Extract generic term -> meaning pairs from domain facts.

    Heuristics:
    - Primary: leading noun phrase before definition verbs ("is", "are", "refers to", "means").
    - Fallback: first non-CJK tag as term when statement still contains a definition cue.
    """
    # Capture concise leading term and definition tail.
    # Example: "Python is a high-level ..." -> (Python, a high-level ...)
    primary_re = re.compile(
        r"^\s*([A-Za-z0-9][A-Za-z0-9_+.#\-/()\s]{1,80}?)\s+"
        r"(is|are|refers to|means)\s+(.+?)\.?\s*$",
        re.IGNORECASE,
    )

    seen: set[str] = set()
    pairs: list[tuple[str, str]] = []

    for fact in domain_facts:
        statement = (fact.details or "").strip()
        if not statement:
            continue

        m = primary_re.match(statement)
        if m:
            term = " ".join(m.group(1).split())
            meaning = " ".join(m.group(3).split())
            term_key = term.lower()
            if term_key not in seen and len(term) <= 80 and len(meaning) >= 8:
                seen.add(term_key)
                pairs.append((term, meaning))
            continue

        # Fallback: try first ASCII tag when statement appears definitional.
        if not re.search(r"\b(is|are|refers to|means)\b", statement, re.IGNORECASE):
            continue
        ascii_tags = [
            t.strip()
            for t in sorted(fact.tags)
            if t.strip() and not any("\u4e00" <= ch <= "\u9fff" for ch in t)
        ]
        if not ascii_tags:
            continue
        term = ascii_tags[0]
        term_key = term.lower()
        if term_key in seen:
            continue
        seen.add(term_key)
        pairs.append((term, statement))

    return pairs


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
