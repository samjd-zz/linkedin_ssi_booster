"""User feedback persistence and application helpers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.selection_learning._constants import CANDIDATES_LOG_PATH
from services.selection_learning._storage import JsonlStore

logger = logging.getLogger(__name__)


class FeedbackService:
    """Manage explicit user feedback labels for candidates."""

    @staticmethod
    def record_user_feedback(
        candidate_id: str,
        feedback_type: str,
        feedback_value: Any,
        *,
        path: Path | None = None,
    ) -> bool:
        """Record feedback (rating/override/upvote/downvote) for a candidate."""
        target = path or CANDIDATES_LOG_PATH
        records = JsonlStore.read(target)
        found = False

        for rec in records:
            if rec.get("candidate_id") == candidate_id:
                if "user_feedback" not in rec:
                    rec["user_feedback"] = {}
                rec["user_feedback"][feedback_type] = feedback_value
                rec["user_feedback"]["last_updated"] = datetime.now(timezone.utc).isoformat()
                found = True
                break

        if found:
            JsonlStore.rewrite(target, records)
            logger.info(
                "selection_learning: recorded %s feedback for candidate %s: %s",
                feedback_type,
                candidate_id,
                feedback_value,
            )
        else:
            logger.warning(
                "selection_learning: candidate_id %s not found — feedback not recorded",
                candidate_id,
            )

        return found

    @staticmethod
    def apply_user_feedback_to_selection(
        *,
        path: Path | None = None,
        upvote_as_selected: bool = True,
        downvote_as_rejected: bool = False,
    ) -> int:
        """Apply user feedback values to selected/selected_at labels."""
        target = path or CANDIDATES_LOG_PATH
        records = JsonlStore.read(target)
        updated = 0

        for rec in records:
            feedback = rec.get("user_feedback", {})
            if not feedback or rec.get("selected") is not None:
                continue

            applied = False
            if upvote_as_selected and feedback.get("upvote") is True:
                rec["selected"] = True
                rec["selected_at"] = datetime.now(timezone.utc).isoformat()
                applied = True
            elif downvote_as_rejected and feedback.get("downvote") is True:
                rec["selected"] = False
                rec["selected_at"] = datetime.now(timezone.utc).isoformat()
                applied = True

            if "override" in feedback:
                rec["selected"] = feedback["override"]
                rec["selected_at"] = datetime.now(timezone.utc).isoformat()

            if applied or "override" in feedback:
                updated += 1

        if updated > 0:
            JsonlStore.rewrite(target, records)
            logger.info("selection_learning: applied user feedback to %d candidates", updated)

        return updated
