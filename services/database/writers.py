"""
Database writers for dual-write migration strategy.

During Phase 3 migration, data is written to both the database AND the filesystem
to ensure backward compatibility. Once migration is complete, file writes can be removed.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from services.database.repositories import (
    PersonaGraphRepository,
    ProjectRepository,
    CompanyRepository,
    SkillRepository,
    ClaimRepository,
    DomainRepository,
    DomainFactRepository,
    DomainRelationshipRepository,
    ExtractedFactRepository,
    NarrativeMemoryRepository,
)

logger = logging.getLogger(__name__)


# ============================================================================
# PERSONA GRAPH WRITERS
# ============================================================================


def write_persona_graph_to_db(
    session: Session,
    persona_data: Dict[str, Any],
) -> int:
    """
    Write persona graph to database.
    
    Args:
        session: Database session
        persona_data: Persona graph dictionary (from JSON file format)
        
    Returns:
        ID of created PersonaGraph record
    """
    # Create main persona graph record
    persona = PersonaGraphRepository.create(
        session=session,
        graph_data=persona_data,
    )
    session.flush()  # Flush to ensure persona.id is populated
    
    # Extract projects, companies, skills, claims and write to normalized tables
    persona_id_int: int = persona.id  # type: ignore
    
    # First create companies and build a mapping of JSON IDs to database IDs
    company_id_map: Dict[str, str] = {}
    for company_data in persona_data.get("companies", []):
        company = CompanyRepository.create(
            session=session,
            persona_id=persona_id_int,
            name=company_data.get("name", ""),
            role=None,
            skills=[],
            aliases=company_data.get("aliases", []),
        )
        json_company_id: str = company_data.get("id", "")
        db_company_id_val: str = company.id  # type: ignore
        if json_company_id and db_company_id_val:
            company_id_map[json_company_id] = db_company_id_val
    
    # Now create projects with the mapped company_id
    project_id_map: Dict[str, str] = {}
    for project_data in persona_data.get("projects", []):
        json_company_id = project_data.get("companyId")
        db_company_id: str | None = company_id_map.get(json_company_id) if json_company_id else None
        
        project = ProjectRepository.create(
            session=session,
            persona_id=persona_id_int,
            name=project_data.get("name", ""),
            company_id=db_company_id,
            description=project_data.get("details", ""),
            url=project_data.get("url"),
            skills=project_data.get("skills", []),
            years=project_data.get("years"),
        )
        json_project_id: str = project_data.get("id", "")
        db_project_id_val: str = project.id  # type: ignore
        if json_project_id and db_project_id_val:
            project_id_map[json_project_id] = db_project_id_val
    
    for skill_data in persona_data.get("skills", []):
        SkillRepository.create(
            session=session,
            persona_id=persona_id_int,
            name=skill_data.get("name", ""),
            aliases=skill_data.get("aliases", []),
        )
    
    for claim_data in persona_data.get("claims", []):
        # Map JSON project IDs to database project IDs
        json_project_ids = claim_data.get("projectIds", [])
        db_project_ids = [project_id_map[pid] for pid in json_project_ids if pid in project_id_map]
        
        ClaimRepository.create(
            session=session,
            persona_id=persona_id_int,
            claim_text=claim_data.get("text", ""),
            tags=[],
            project_ids=db_project_ids,
            links=claim_data.get("links", []),
        )
    
    session.commit()
    logger.info(f"Wrote persona graph to database (ID: {persona_id_int})")
    return persona_id_int


def write_persona_graph_dual(
    session: Session,
    persona_data: Dict[str, Any],
    file_path: Path,
) -> int:
    """
    Write persona graph to BOTH database and file (dual-write).
    
    Args:
        session: Database session
        persona_data: Persona graph dictionary
        file_path: Path to JSON file
        
    Returns:
        ID of created PersonaGraph record
    """
    # Write to database
    persona_id = write_persona_graph_to_db(session, persona_data)
    
    # Write to file (for backward compatibility)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(persona_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(f"Wrote persona graph to file: {file_path}")
    
    return persona_id


# ============================================================================
# DOMAIN KNOWLEDGE WRITERS
# ============================================================================


def write_domain_knowledge_to_db(
    session: Session,
    domain_data: Dict[str, Any],
) -> Dict[str, str]:
    """
    Write domain knowledge to database.
    
    Args:
        session: Database session
        domain_data: Domain knowledge dictionary (from JSON file format)
        
    Returns:
        Dictionary mapping domain names to their database IDs (strings)
    """
    domain_ids: Dict[str, str] = {}
    
    # Create domains
    for domain_entry in domain_data.get("domains", []):
        domain = DomainRepository.create(
            session=session,
            name=domain_entry.get("name", ""),
            description=domain_entry.get("description", ""),
        )
        session.flush()  # Flush to ensure domain.id is populated
        
        # Map the JSON domain ID (e.g., "ai-ml") to the database ID
        json_domain_id: str = domain_entry.get("id", "")
        domain_name_str: str = domain.name  # type: ignore
        domain_id_str: str = domain.id  # type: ignore
        domain_ids[json_domain_id] = domain_id_str
        logger.debug(f"Created domain: {domain_name_str} (ID: {domain_id_str}, JSON ID: {json_domain_id})")
    
    # Create facts (linked to domains) and build a mapping of JSON fact IDs to database IDs
    fact_id_map: Dict[str, str] = {}
    for fact_entry in domain_data.get("facts", []):
        domain_name = fact_entry.get("domainId", "")
        domain_id = domain_ids.get(domain_name)
        
        if domain_id is None:
            logger.warning(f"Fact references unknown domain: {domain_name}, skipping")
            continue
        
        fact = DomainFactRepository.create(
            session=session,
            domain_id=domain_id,
            fact_text=fact_entry.get("statement", ""),
            tags=fact_entry.get("tags", []),
            metadata={
                "confidence": fact_entry.get("confidence", "medium"),
                "scope": fact_entry.get("scope", "general"),
                "original_id": fact_entry.get("id", ""),
            },
        )
        json_fact_id: str = fact_entry.get("id", "")
        db_fact_id: str = fact.id  # type: ignore
        if json_fact_id and db_fact_id:
            fact_id_map[json_fact_id] = db_fact_id
    
    # Create relationships using the fact ID mapping
    for rel_entry in domain_data.get("relationships", []):
        from_fact_json_id = rel_entry.get("fromFactId", "")
        to_fact_json_id = rel_entry.get("toFactId", "")
        
        from_fact_db_id = fact_id_map.get(from_fact_json_id)
        to_fact_db_id = fact_id_map.get(to_fact_json_id)
        
        if from_fact_db_id and to_fact_db_id:
            DomainRelationshipRepository.create(
                session=session,
                from_fact_id=from_fact_db_id,
                to_fact_id=to_fact_db_id,
                relation_type=rel_entry.get("relationType", ""),
                description=rel_entry.get("description", ""),
            )
        else:
            logger.warning(f"Skipping relationship: fact IDs not found (from: {from_fact_json_id}, to: {to_fact_json_id})")
    
    session.commit()
    logger.info(f"Wrote domain knowledge to database ({len(domain_ids)} domains)")
    return domain_ids


def write_domain_knowledge_dual(
    session: Session,
    domain_data: Dict[str, Any],
    file_path: Path,
) -> Dict[str, str]:
    """
    Write domain knowledge to BOTH database and file (dual-write).
    
    Args:
        session: Database session
        domain_data: Domain knowledge dictionary
        file_path: Path to JSON file
        
    Returns:
        Dictionary mapping domain names to their database IDs (strings)
    """
    # Write to database
    domain_ids = write_domain_knowledge_to_db(session, domain_data)
    
    # Write to file (for backward compatibility)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(domain_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(f"Wrote domain knowledge to file: {file_path}")
    
    return domain_ids


# ============================================================================
# EXTRACTED KNOWLEDGE WRITERS
# ============================================================================


def write_extracted_knowledge_to_db(
    session: Session,
    extracted_data: Dict[str, Any],
) -> int:
    """
    Write extracted knowledge facts to database.
    
    Args:
        session: Database session
        extracted_data: Extracted knowledge dictionary (from JSON file format)
        
    Returns:
        Number of facts written
    """
    from sqlalchemy.exc import IntegrityError
    
    facts_written = 0
    facts_skipped = 0
    
    for fact_entry in extracted_data.get("facts", []):
        try:
            ExtractedFactRepository.create(
                session=session,
                fact_text=fact_entry.get("statement", ""),
                source_url=fact_entry.get("source_url", ""),
                source_title=fact_entry.get("source_title", ""),
                entities=fact_entry.get("entities", []),
                themes=fact_entry.get("tags", []),
                primary_category=fact_entry.get("primary_category", ""),
                primary_ssi_component=fact_entry.get("primary_ssi_component", ""),
                sentiment={
                    "confidence": fact_entry.get("confidence", "medium"),
                    "extraction_method": fact_entry.get("extraction_method", "spacy_nlp"),
                },
            )
            facts_written += 1
        except IntegrityError as e:
            session.rollback()
            logger.debug(f"Skipping duplicate fact: {fact_entry.get('statement', '')[:50]}...")
            facts_skipped += 1
    
    session.commit()
    logger.info(f"Wrote {facts_written} extracted facts to database ({facts_skipped} duplicates skipped)")
    return facts_written


def write_extracted_knowledge_dual(
    session: Session,
    extracted_data: Dict[str, Any],
    file_path: Path,
) -> int:
    """
    Write extracted knowledge to BOTH database and file (dual-write).
    
    Args:
        session: Database session
        extracted_data: Extracted knowledge dictionary
        file_path: Path to JSON file
        
    Returns:
        Number of facts written
    """
    # Write to database
    facts_written = write_extracted_knowledge_to_db(session, extracted_data)
    
    # Write to file (for backward compatibility)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(extracted_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(f"Wrote extracted knowledge to file: {file_path}")
    
    return facts_written


# ============================================================================
# NARRATIVE MEMORY WRITERS
# ============================================================================


def write_narrative_memory_to_db(
    session: Session,
    narrative_data: Dict[str, Any],
) -> int:
    """
    Write narrative memory entries to database.
    
    Args:
        session: Database session
        narrative_data: Narrative memory dictionary (from JSON file format)
        
    Returns:
        Number of narrative entries written
    """
    entries_written = 0
    
    # Create a single narrative memory entry with all data
    themes = narrative_data.get("recentThemes", [])
    claims = narrative_data.get("recentClaims", [])
    arcs = narrative_data.get("openNarrativeArcs", [])
    
    if themes or claims or arcs:
        NarrativeMemoryRepository.create(
            session=session,
            themes=themes,
            claims=claims,
            narrative_arcs=arcs,
        )
        entries_written = 1
    
    session.commit()
    logger.info(f"Wrote {entries_written} narrative entries to database")
    return entries_written


def write_narrative_memory_dual(
    session: Session,
    narrative_data: Dict[str, Any],
    file_path: Path,
) -> int:
    """
    Write narrative memory to BOTH database and file (dual-write).
    
    Args:
        session: Database session
        narrative_data: Narrative memory dictionary
        file_path: Path to JSON file
        
    Returns:
        Number of narrative entries written
    """
    # Write to database
    entries_written = write_narrative_memory_to_db(session, narrative_data)
    
    # Write to file (for backward compatibility)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(narrative_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(f"Wrote narrative memory to file: {file_path}")
    
    return entries_written