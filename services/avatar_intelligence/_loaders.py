"""Schema validators, file loaders, and load_avatar_state."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import services.avatar_intelligence._paths as _paths
from services.avatar_intelligence._models import (
    AvatarState,
    ClaimNode,
    CompanyNode,
    DomainFact,
    DomainKnowledge,
    DomainNode,
    DomainRelationship,
    ExtractedFact,
    ExtractedKnowledgeGraph,
    NarrativeMemory,
    PersonaGraph,
    PersonNode,
    ProjectNode,
    SkillNode,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Database integration flag
# ---------------------------------------------------------------------------

def _is_database_enabled() -> bool:
    """Check if database integration is enabled via environment variable."""
    return os.getenv("DATABASE_ENABLED", "false").lower() == "true"


# ---------------------------------------------------------------------------
# Schema validation helpers
# ---------------------------------------------------------------------------


def _validate_persona_graph(data: dict[str, Any]) -> list[str]:
    """Return a list of validation errors; empty list means valid."""
    errors: list[str] = []
    if not isinstance(data.get("schemaVersion"), str):
        errors.append("missing or invalid 'schemaVersion'")
    if not isinstance(data.get("person"), dict):
        errors.append("missing or invalid 'person'")
    for key in ("projects", "companies", "skills", "claims"):
        if not isinstance(data.get(key), list):
            errors.append(f"missing or invalid '{key}' (must be a list)")
    return errors


def _validate_narrative_memory(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("recentThemes", "recentClaims", "openNarrativeArcs"):
        if not isinstance(data.get(key), list):
            errors.append(f"missing or invalid '{key}' (must be a list)")
    return errors


def _validate_extracted_knowledge(data: dict[str, Any]) -> list[str]:
    """Return a list of validation errors for extracted_knowledge.json; empty list means valid."""
    errors: list[str] = []
    if not isinstance(data.get("schemaVersion"), str):
        errors.append("missing or invalid 'schemaVersion'")
    if not isinstance(data.get("facts"), list):
        errors.append("missing or invalid 'facts' (must be a list)")
    return errors


def _validate_domain_knowledge(data: dict[str, Any]) -> list[str]:
    """Return a list of validation errors; empty list means valid."""
    errors: list[str] = []
    if not isinstance(data.get("schemaVersion"), str):
        errors.append("missing or invalid 'schemaVersion'")
    for key in ("domains", "facts", "relationships"):
        if not isinstance(data.get(key), list):
            errors.append(f"missing or invalid '{key}' (must be a list)")
    return errors


# ---------------------------------------------------------------------------
# Database loaders (dual-read: try DB first, fallback to file)
# ---------------------------------------------------------------------------


def _load_persona_graph_from_db() -> tuple[PersonaGraph | None, list[str]]:
    """Load persona graph from database.
    
    Returns (None, [error]) if database is unavailable or no data exists.
    """
    try:
        from services.database.session import get_session
        from services.database.repositories import (
            PersonaGraphRepository,
            ProjectRepository,
            CompanyRepository,
            SkillRepository,
            ClaimRepository,
        )
        
        with next(get_session()) as session:
            # Get the latest persona graph
            persona_db = PersonaGraphRepository.get_latest(session)
            if not persona_db:
                return None, ["No persona graph found in database"]
            
            # Extract graph data from JSONB
            graph_data = persona_db.graph_data
            if not graph_data:
                return None, ["Persona graph data is empty"]
            
            # Parse the graph data into models
            errors = _validate_persona_graph(graph_data)
            if errors:
                return None, [f"persona_graph schema error: {e}" for e in errors]
            
            raw_person = graph_data.get("person", {})
            person = PersonNode(
                name=raw_person.get("name", ""),
                title=raw_person.get("title", ""),
                location=raw_person.get("location", ""),
                links=raw_person.get("links", []),
            )
            
            projects = [
                ProjectNode(
                    id=p.get("id", ""),
                    name=p.get("name", ""),
                    company_id=p.get("companyId", ""),
                    years=p.get("years", ""),
                    details=p.get("details", ""),
                    skills=p.get("skills", []),
                    aliases=p.get("aliases", []),
                )
                for p in graph_data.get("projects", [])
            ]
            
            companies = [
                CompanyNode(
                    id=c.get("id", ""),
                    name=c.get("name", ""),
                    aliases=c.get("aliases", []),
                )
                for c in graph_data.get("companies", [])
            ]
            
            skills = [
                SkillNode(
                    id=s.get("id", ""),
                    name=s.get("name", ""),
                    aliases=s.get("aliases", []),
                    scope=s.get("scope", "domain"),
                )
                for s in graph_data.get("skills", [])
            ]
            
            claims = [
                ClaimNode(
                    id=cl.get("id", ""),
                    text=cl.get("text", ""),
                    project_ids=cl.get("projectIds", []),
                    confidence_hint=cl.get("confidenceHint", "medium"),
                )
                for cl in graph_data.get("claims", [])
            ]
            
            graph = PersonaGraph(
                schema_version=graph_data["schemaVersion"],
                person=person,
                projects=projects,
                companies=companies,
                skills=skills,
                claims=claims,
            )
            return graph, []
    except Exception as exc:
        return None, [f"Database load error: {exc}"]


# ---------------------------------------------------------------------------
# File loaders
# ---------------------------------------------------------------------------


def _load_persona_graph(path: Path) -> tuple[PersonaGraph | None, list[str]]:
    """Load persona graph from file or database (dual-read pattern).
    
    If DATABASE_ENABLED=true, tries database first, then falls back to file.
    Otherwise, loads directly from file.
    """
    # Dual-read: try database first if enabled
    if _is_database_enabled():
        graph, db_errors = _load_persona_graph_from_db()
        if graph is not None:
            logger.debug("Loaded persona graph from database")
            return graph, []
        else:
            logger.debug("Database load failed, falling back to file: %s", db_errors[0] if db_errors else "unknown error")
    
    # Fallback to file loading
    if not path.exists():
        return None, [f"persona_graph not found at {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"persona_graph JSON parse error: {exc}"]

    errors = _validate_persona_graph(data)
    if errors:
        return None, [f"persona_graph schema error: {e}" for e in errors]

    raw_person = data.get("person", {})
    person = PersonNode(
        name=raw_person.get("name", ""),
        title=raw_person.get("title", ""),
        location=raw_person.get("location", ""),
        links=raw_person.get("links", []),
    )

    projects = [
        ProjectNode(
            id=p.get("id", ""),
            name=p.get("name", ""),
            company_id=p.get("companyId", ""),
            years=p.get("years", ""),
            details=p.get("details", ""),
            skills=p.get("skills", []),
            aliases=p.get("aliases", []),
        )
        for p in data.get("projects", [])
    ]

    companies = [
        CompanyNode(
            id=c.get("id", ""),
            name=c.get("name", ""),
            aliases=c.get("aliases", []),
        )
        for c in data.get("companies", [])
    ]

    skills = [
        SkillNode(
            id=s.get("id", ""),
            name=s.get("name", ""),
            aliases=s.get("aliases", []),
            scope=s.get("scope", "domain"),
        )
        for s in data.get("skills", [])
    ]

    claims = [
        ClaimNode(
            id=cl.get("id", ""),
            text=cl.get("text", ""),
            project_ids=cl.get("projectIds", []),
            confidence_hint=cl.get("confidenceHint", "medium"),
        )
        for cl in data.get("claims", [])
    ]

    graph = PersonaGraph(
        schema_version=data["schemaVersion"],
        person=person,
        projects=projects,
        companies=companies,
        skills=skills,
        claims=claims,
    )
    return graph, []


def _load_narrative_memory(path: Path) -> tuple[NarrativeMemory | None, list[str]]:
    if not path.exists():
        return None, [f"narrative_memory not found at {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"narrative_memory JSON parse error: {exc}"]

    errors = _validate_narrative_memory(data)
    if errors:
        return None, [f"narrative_memory schema error: {e}" for e in errors]

    memory = NarrativeMemory(
        recent_themes=data.get("recentThemes", []),
        recent_claims=data.get("recentClaims", []),
        open_narrative_arcs=data.get("openNarrativeArcs", []),
        last_updated=data.get("lastUpdated"),
    )
    return memory, []


def _load_extracted_knowledge(path: Path) -> tuple["ExtractedKnowledgeGraph | None", list[str]]:
    """Load NLP-extracted knowledge graph from disk.

    Returns (None, [error]) when the file is missing or malformed.
    An empty facts list is valid — the graph is just empty.
    """
    if not path.exists():
        return None, [f"extracted_knowledge not found at {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"extracted_knowledge JSON parse error: {exc}"]

    errors = _validate_extracted_knowledge(data)
    if errors:
        return None, [f"extracted_knowledge schema error: {e}" for e in errors]

    facts = [
        ExtractedFact(
            id=f.get("id", ""),
            statement=f.get("statement", ""),
            source_url=f.get("source_url", ""),
            source_title=f.get("source_title", ""),
            extracted_at=f.get("extracted_at", ""),
            entities=f.get("entities", []),
            tags=f.get("tags", []),
            confidence=f.get("confidence", "medium"),
            extraction_method=f.get("extraction_method", "spacy_nlp"),
            primary_category=f.get("primary_category", ""),
            primary_ssi_component=f.get("primary_ssi_component", ""),
        )
        for f in data.get("facts", [])
    ]

    graph = ExtractedKnowledgeGraph(
        schema_version=data["schemaVersion"],
        facts=facts,
    )
    return graph, []


def _load_domain_knowledge(path: Path) -> tuple[DomainKnowledge | None, list[str]]:
    """Load domain knowledge graph from disk."""
    if not path.exists():
        return None, [f"domain_knowledge not found at {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"domain_knowledge JSON parse error: {exc}"]

    errors = _validate_domain_knowledge(data)
    if errors:
        return None, [f"domain_knowledge schema error: {e}" for e in errors]

    domains = [
        DomainNode(
            id=d.get("id", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
        )
        for d in data.get("domains", [])
    ]

    facts = [
        DomainFact(
            id=f.get("id", ""),
            domain_id=f.get("domainId", ""),
            statement=f.get("statement", ""),
            tags=f.get("tags", []),
            confidence=f.get("confidence", "medium"),
            scope=f.get("scope", "general"),
        )
        for f in data.get("facts", [])
    ]

    relationships = [
        DomainRelationship(
            id=r.get("id", ""),
            from_fact_id=r.get("fromFactId", ""),
            to_fact_id=r.get("toFactId", ""),
            relation_type=r.get("relationType", ""),
            description=r.get("description", ""),
        )
        for r in data.get("relationships", [])
    ]

    knowledge = DomainKnowledge(
        schema_version=data["schemaVersion"],
        domains=domains,
        facts=facts,
        relationships=relationships,
    )
    return knowledge, []


# ---------------------------------------------------------------------------
# Avatar state loader
# ---------------------------------------------------------------------------


def load_avatar_state(
    persona_graph_path: Path | None = None,
    narrative_memory_path: Path | None = None,
    domain_knowledge_path: Path | None = None,
    extracted_knowledge_path: Path | None = None,
) -> AvatarState:
    """Load persona graph, narrative memory, and domain knowledge from disk.

    Returns a fully-populated AvatarState with is_loaded=True when all
    required files parse successfully. Domain knowledge is optional; if missing,
    the system continues without it. On any error, logs a warning, sets
    is_loaded=False, and records the errors in load_errors.
    """
    all_errors: list[str] = []

    graph, graph_errors = _load_persona_graph(
        persona_graph_path or _paths.PERSONA_GRAPH_PATH
    )
    all_errors.extend(graph_errors)

    memory, memory_errors = _load_narrative_memory(
        narrative_memory_path or _paths.NARRATIVE_MEMORY_PATH
    )
    all_errors.extend(memory_errors)

    # Domain knowledge is optional - log as info if missing, not an error
    _dk_path = domain_knowledge_path or _paths.DOMAIN_KNOWLEDGE_PATH
    knowledge, knowledge_errors = _load_domain_knowledge(_dk_path)
    if knowledge_errors and "not found" not in knowledge_errors[0]:
        all_errors.extend(knowledge_errors)
    elif knowledge_errors:
        logger.info("Domain knowledge not found (optional): %s", knowledge_errors[0])

    # Auto-discover and merge domain_knowledge_*.json siblings in the same dir
    # (e.g. domain_knowledge_java.json, domain_knowledge_python.json).
    for extra_path in sorted(_dk_path.parent.glob("domain_knowledge_*.json")):
        extra_dk, extra_errors = _load_domain_knowledge(extra_path)
        if extra_errors:
            if "not found" not in extra_errors[0]:
                logger.warning(
                    "Extra domain knowledge load error (%s): %s",
                    extra_path.name,
                    extra_errors[0],
                )
            continue
        if extra_dk is None:
            continue
        if knowledge is None:
            knowledge = extra_dk
        else:
            knowledge = DomainKnowledge(
                schema_version=knowledge.schema_version,
                domains=knowledge.domains + extra_dk.domains,
                facts=knowledge.facts + extra_dk.facts,
                relationships=knowledge.relationships + extra_dk.relationships,
            )
        logger.debug(
            "Merged domain knowledge from %s (%d facts)",
            extra_path.name,
            len(extra_dk.facts),
        )

    # Extracted knowledge is optional — log as info if missing, not an error
    extracted, extracted_errors = _load_extracted_knowledge(
        extracted_knowledge_path or _paths.EXTRACTED_KNOWLEDGE_PATH
    )
    if extracted_errors and "not found" not in extracted_errors[0]:
        all_errors.extend(extracted_errors)
    elif extracted_errors:
        logger.info("Extracted knowledge not found (optional): %s", extracted_errors[0])

    if all_errors:
        for err in all_errors:
            logger.warning("Avatar state load: %s", err)

    is_loaded = graph is not None and memory is not None
    return AvatarState(
        persona_graph=graph,
        narrative_memory=memory,
        domain_knowledge=knowledge,
        extracted_knowledge=extracted,
        is_loaded=is_loaded,
        load_errors=all_errors,
    )
