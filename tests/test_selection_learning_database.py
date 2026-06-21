"""Tests for selection_learning database integration."""

import pytest
from datetime import datetime, timezone
from sqlalchemy import select

from services.database.models import (
    CandidateRecord as CandidateRecordModel,
    PublishedRecord as PublishedRecordModel,
)
from services.database.repositories import (
    CandidateRecordRepository,
    PublishedRecordRepository,
)


class TestCandidateRecordRepository:
    """Test CandidateRecordRepository methods."""

    def test_create_candidate_record(self, db_session):
        """Test creating a candidate record in the database."""
        timestamp = datetime.now(timezone.utc)
        
        candidate = CandidateRecordRepository.create(
            session=db_session,
            candidate_id="test-candidate-123",
            timestamp=timestamp,
            article_url="https://example.com/article",
            article_title="Test Article",
            article_source="example.com",
            ssi_component="establish_brand",
            channel="linkedin",
            text_hash="abc123def456",
            text_snippet="This is a test snippet...",
            buffer_id="buffer-123",
            route="draft",
            run_id="run-001",
            themes=["AI", "Python"],
            sentiment={"polarity": 0.8, "subjectivity": 0.6},
        )
        
        db_session.commit()
        
        # Verify record was created
        assert candidate.candidate_id == "test-candidate-123"
        assert candidate.ssi_component == "establish_brand"
        assert candidate.channel == "linkedin"
        assert candidate.buffer_id == "buffer-123"
        assert candidate.themes == ["AI", "Python"]
        assert candidate.sentiment.get("polarity") == 0.8

    def test_update_selected_candidate(self, db_session):
        """Test updating selected status on a candidate record."""
        timestamp = datetime.now(timezone.utc)
        
        # Create candidate
        candidate = CandidateRecordRepository.create(
            session=db_session,
            candidate_id="test-candidate-456",
            timestamp=timestamp,
            article_url="https://example.com/article2",
            article_title="Test Article 2",
            article_source="example.com",
            ssi_component="find_right_people",
            channel="linkedin",
            text_hash="xyz789",
            text_snippet="Another snippet...",
            buffer_id=None,
            route="review",
            run_id="run-002",
        )
        
        db_session.commit()
        
        # Update selected status
        selected_at = datetime.now(timezone.utc)
        CandidateRecordRepository.update_selected(
            session=db_session,
            candidate_id="test-candidate-456",
            selected=True,
            selected_at=selected_at,
        )
        
        db_session.commit()
        
        # Verify update
        stmt = select(CandidateRecordModel).where(
            CandidateRecordModel.candidate_id == "test-candidate-456"
        )
        updated = db_session.execute(stmt).scalar_one()
        assert updated.selected is True
        assert updated.selected_at is not None

    def test_list_unpublished_candidates(self, db_session):
        """Test listing unpublished candidates."""
        timestamp = datetime.now(timezone.utc)
        
        # Create multiple candidates
        for i in range(3):
            CandidateRecordRepository.create(
                session=db_session,
                candidate_id=f"unpub-candidate-{i}",
                timestamp=timestamp,
                article_url=f"https://example.com/article{i}",
                article_title=f"Test Article {i}",
                article_source="example.com",
                ssi_component="establish_brand",
                channel="linkedin",
                text_hash=f"hash{i}",
                text_snippet=f"Snippet {i}...",
                buffer_id=None,
                route="draft",
                run_id="run-003",
            )
        
        db_session.commit()
        
        # List unpublished (should get at least the 3 we created)
        unpublished = CandidateRecordRepository.list_unpublished(
            session=db_session,
            limit=10,
        )
        
        assert len(unpublished) >= 3
        unpub_ids = [c.candidate_id for c in unpublished]
        assert "unpub-candidate-0" in unpub_ids
        assert "unpub-candidate-1" in unpub_ids
        assert "unpub-candidate-2" in unpub_ids


class TestPublishedRecordRepository:
    """Test PublishedRecordRepository methods."""

    def test_create_published_record(self, db_session):
        """Test creating a published record in the database."""
        timestamp = datetime.now(timezone.utc)
        
        published = PublishedRecordRepository.create(
            session=db_session,
            buffer_id="buffer-pub-123",
            channel="linkedin",
            text_snippet="Published post snippet...",
            published_at=timestamp,
            fetched_at=timestamp,
            candidate_id="test-candidate-123",
        )
        
        db_session.commit()
        
        # Verify record was created
        assert published.buffer_id == "buffer-pub-123"
        assert published.channel == "linkedin"
        assert published.candidate_id == "test-candidate-123"
        assert published.published_at is not None

    def test_list_recent_published(self, db_session):
        """Test listing recent published records."""
        timestamp = datetime.now(timezone.utc)
        
        # Create multiple published records
        for i in range(3):
            PublishedRecordRepository.create(
                session=db_session,
                buffer_id=f"buffer-pub-{i}",
                channel="linkedin",
                text_snippet=f"Published snippet {i}...",
                published_at=timestamp,
                fetched_at=timestamp,
                candidate_id=f"candidate-{i}",
            )
        
        db_session.commit()
        
        # List recent
        recent = PublishedRecordRepository.list_recent(
            session=db_session,
            limit=10,
        )
        
        assert len(recent) >= 3
