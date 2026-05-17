"""
Database session management and initialization.

Provides connection pooling, session factory, and database initialization
for the LinkedIn SSI Booster PostgreSQL backend.
"""

import logging
import os
from typing import Generator

from sqlalchemy import create_engine, event, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import Pool

from services.database.models import Base

logger = logging.getLogger(__name__)

# Global engine and session factory
_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def _get_database_url() -> str:
    """
    Get DATABASE_URL from environment.
    
    Returns:
        Database connection URL
        
    Raises:
        ValueError: If DATABASE_URL is not set
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError(
            "DATABASE_URL environment variable is required. "
            "Example: postgresql://user:pass@localhost:5432/dbname"
        )
    return url


def _configure_engine_listeners(engine: Engine) -> None:
    """
    Configure SQLAlchemy engine event listeners for logging and optimization.
    
    Args:
        engine: SQLAlchemy engine instance
    """
    @event.listens_for(engine, "connect")
    def receive_connect(dbapi_conn, connection_record):
        """Log new database connections."""
        logger.debug("New database connection established")
    
    @event.listens_for(Pool, "checkout")
    def receive_checkout(dbapi_conn, connection_record, connection_proxy):
        """Log connection pool checkouts."""
        logger.debug("Connection checked out from pool")


def get_engine() -> Engine:
    """
    Get or create the SQLAlchemy engine (singleton).
    
    Configuration:
    - Connection pooling: 5-20 connections
    - Pool recycle: 3600s (1 hour)
    - Echo SQL: disabled in production
    
    Returns:
        Configured SQLAlchemy engine
    """
    global _engine
    
    if _engine is None:
        database_url = _get_database_url()
        
        # Engine configuration
        # - pool_size=5: Minimum connections in pool
        # - max_overflow=15: Additional connections beyond pool_size
        # - pool_recycle=3600: Recycle connections after 1 hour
        # - pool_pre_ping=True: Verify connections before using
        _engine = create_engine(
            database_url,
            pool_size=5,
            max_overflow=15,
            pool_recycle=3600,
            pool_pre_ping=True,
            echo=False,  # Set to True for SQL query logging during development
        )
        
        _configure_engine_listeners(_engine)
        logger.info("Database engine initialized with connection pooling")
    
    return _engine


def get_session_factory() -> sessionmaker:
    """
    Get or create the session factory (singleton).
    
    Returns:
        SQLAlchemy sessionmaker bound to the engine
    """
    global _SessionLocal
    
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )
        logger.info("Database session factory created")
    
    return _SessionLocal


def get_session() -> Generator[Session, None, None]:
    """
    Dependency injection pattern for database sessions.
    
    Usage:
        ```python
        with get_session() as session:
            # Use session for queries
            results = session.query(PersonaGraph).all()
            session.commit()
        ```
    
    Or with FastAPI/dependency injection:
        ```python
        def my_function(session: Session = Depends(get_session)):
            return session.query(Model).all()
        ```
    
    Yields:
        Database session (auto-closes on exit)
    """
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
    except Exception as e:
        logger.error(f"Database session error: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """
    Initialize the database by creating all tables.
    
    NOTE: This uses SQLAlchemy's metadata to create tables.
    For production, use Alembic migrations instead:
        `alembic revision --autogenerate -m "Initial migration"`
        `alembic upgrade head`
    
    This function is useful for:
    - Development/testing environments
    - Initial setup before Alembic is configured
    - Ensuring tables exist before running the app
    
    Raises:
        Exception: If table creation fails
    """
    try:
        engine = get_engine()
        
        # Create all tables defined in Base metadata
        # (imported from services/database/models.py)
        Base.metadata.create_all(bind=engine)
        
        logger.info("Database tables created/verified successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def check_database_connection() -> bool:
    """
    Verify database connectivity.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
        logger.info("Database connection verified")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def close_database_connections() -> None:
    """
    Close all database connections and dispose of the engine.
    
    Call this during application shutdown to cleanly close all
    connection pool resources.
    """
    global _engine, _SessionLocal
    
    if _engine is not None:
        _engine.dispose()
        logger.info("Database engine disposed, all connections closed")
        _engine = None
        _SessionLocal = None
