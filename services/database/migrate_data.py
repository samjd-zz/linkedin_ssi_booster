"""
Data migration script to import existing JSON files into PostgreSQL.

This script reads avatar data from JSON files and writes them to the database
using the dual-write pattern. Run this once after database setup to migrate
existing data.

Usage:
    python -m services.database.migrate_data
    python -m services.database.migrate_data --dry-run
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from services.avatar_intelligence._loaders import (
    load_avatar_state,
)
from services.avatar_intelligence._paths import (
    PERSONA_GRAPH_PATH,
    NARRATIVE_MEMORY_PATH,
    DOMAIN_KNOWLEDGE_PATH,
    EXTRACTED_KNOWLEDGE_PATH,
)
from services.database.session import check_database_connection, init_db, get_session
from services.database.writers import (
    write_persona_graph_dual,
    write_narrative_memory_dual,
    write_domain_knowledge_dual,
    write_extracted_knowledge_dual,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def migrate_persona_graph(dry_run: bool = False) -> bool:
    """Migrate persona_graph.json to database."""
    logger.info("Migrating persona_graph...")
    
    if not PERSONA_GRAPH_PATH.exists():
        logger.warning(f"Persona graph not found at {PERSONA_GRAPH_PATH}")
        return False
    
    try:
        data = json.loads(PERSONA_GRAPH_PATH.read_text(encoding="utf-8"))
        logger.info(f"Loaded persona graph with {len(data.get('projects', []))} projects")
        
        if dry_run:
            logger.info("[DRY RUN] Would write persona graph to database")
            return True
        
        with get_session() as session:
            write_persona_graph_dual(session, data, PERSONA_GRAPH_PATH)
        logger.info("✓ Persona graph migrated successfully")
        return True
    except Exception as exc:
        logger.error(f"Failed to migrate persona graph: {exc}")
        return False


def migrate_narrative_memory(dry_run: bool = False) -> bool:
    """Migrate narrative_memory.json to database."""
    logger.info("Migrating narrative_memory...")
    
    if not NARRATIVE_MEMORY_PATH.exists():
        logger.warning(f"Narrative memory not found at {NARRATIVE_MEMORY_PATH}")
        return False
    
    try:
        data = json.loads(NARRATIVE_MEMORY_PATH.read_text(encoding="utf-8"))
        logger.info(f"Loaded narrative memory with {len(data.get('recentThemes', []))} themes")
        
        if dry_run:
            logger.info("[DRY RUN] Would write narrative memory to database")
            return True
        
        with get_session() as session:
            write_narrative_memory_dual(session, data, NARRATIVE_MEMORY_PATH)
        logger.info("✓ Narrative memory migrated successfully")
        return True
    except Exception as exc:
        logger.error(f"Failed to migrate narrative memory: {exc}")
        return False


def migrate_domain_knowledge(dry_run: bool = False) -> bool:
    """Migrate domain_knowledge.json (and siblings) to database."""
    logger.info("Migrating domain_knowledge...")
    
    # Find all domain_knowledge*.json files
    domain_files = list(DOMAIN_KNOWLEDGE_PATH.parent.glob("domain_knowledge*.json"))
    
    if not domain_files:
        logger.warning("No domain knowledge files found")
        return False
    
    success_count = 0
    for dk_path in sorted(domain_files):
        try:
            data = json.loads(dk_path.read_text(encoding="utf-8"))
            logger.info(f"Loaded {dk_path.name} with {len(data.get('facts', []))} facts")
            
            if dry_run:
                logger.info(f"[DRY RUN] Would write {dk_path.name} to database")
                success_count += 1
                continue
            
            with get_session() as session:
                write_domain_knowledge_dual(session, data, dk_path)
            logger.info(f"✓ {dk_path.name} migrated successfully")
            success_count += 1
        except Exception as exc:
            logger.error(f"Failed to migrate {dk_path.name}: {exc}")
    
    logger.info(f"Domain knowledge migration: {success_count}/{len(domain_files)} files migrated")
    return success_count > 0


def migrate_extracted_knowledge(dry_run: bool = False) -> bool:
    """Migrate extracted_knowledge.json to database."""
    logger.info("Migrating extracted_knowledge...")
    
    if not EXTRACTED_KNOWLEDGE_PATH.exists():
        logger.warning(f"Extracted knowledge not found at {EXTRACTED_KNOWLEDGE_PATH}")
        return False
    
    try:
        data = json.loads(EXTRACTED_KNOWLEDGE_PATH.read_text(encoding="utf-8"))
        fact_count = len(data.get('facts', []))
        logger.info(f"Loaded extracted knowledge with {fact_count} facts")
        
        if dry_run:
            logger.info("[DRY RUN] Would write extracted knowledge to database")
            return True
        
        with get_session() as session:
            write_extracted_knowledge_dual(session, data, EXTRACTED_KNOWLEDGE_PATH)
        logger.info("✓ Extracted knowledge migrated successfully")
        return True
    except Exception as exc:
        logger.error(f"Failed to migrate extracted knowledge: {exc}")
        return False


def main():
    """Run the data migration."""
    parser = argparse.ArgumentParser(
        description="Migrate avatar data from JSON files to PostgreSQL"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without actually writing to the database"
    )
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("PostgreSQL Data Migration")
    logger.info("=" * 70)
    
    if args.dry_run:
        logger.info("DRY RUN MODE: No data will be written to the database")
    
    # Check database connectivity
    logger.info("Checking database connection...")
    if not check_database_connection():
        logger.error("Database connection failed. Please check DATABASE_URL in .env")
        sys.exit(1)
    
    logger.info("✓ Database connection successful")
    
    # Initialize database tables
    if not args.dry_run:
        logger.info("Initializing database tables...")
        init_db()
        logger.info("✓ Database tables initialized")
    
    # Migrate each data type
    results = []
    results.append(("Persona Graph", migrate_persona_graph(args.dry_run)))
    results.append(("Narrative Memory", migrate_narrative_memory(args.dry_run)))
    results.append(("Domain Knowledge", migrate_domain_knowledge(args.dry_run)))
    results.append(("Extracted Knowledge", migrate_extracted_knowledge(args.dry_run)))
    
    # Summary
    logger.info("=" * 70)
    logger.info("Migration Summary")
    logger.info("=" * 70)
    
    for name, success in results:
        status = "✓" if success else "✗"
        logger.info(f"{status} {name}")
    
    success_count = sum(1 for _, success in results if success)
    total_count = len(results)
    
    logger.info(f"\nMigrated {success_count}/{total_count} data types successfully")
    
    if success_count < total_count:
        logger.warning("Some migrations failed - see errors above")
        sys.exit(1)
    
    if args.dry_run:
        logger.info("\nDRY RUN COMPLETE - no data was written")
    else:
        logger.info("\nMIGRATION COMPLETE")
        logger.info("\nNext steps:")
        logger.info("1. Set DATABASE_ENABLED=true in .env to enable dual-read")
        logger.info("2. Test dual-read by running: python main.py --console")
        logger.info("3. Verify data integrity with unit tests")


if __name__ == "__main__":
    main()