"""
FLUX Capacitor Artifact Storage

Local-first artifact persistence for rendered images and generated story text.
Implements the system-wide generated-content persistence contract:
  - every generated story has a durable local artifact
  - metadata sidecars link story text, image path, run/request IDs, channel,
    and source references
  - save failures propagate as explicit status strings (never silent)
  - all paths live under GENERATED_CONTENT_DIR (shared.get_generated_content_dir)

Naming pattern:  <prefix>_<YYYYMMDD_HHMMSS>_<8-char hash>_<request_id[:8]>.<ext>

When DATABASE_ENABLED=true the local-artifact state is also mirrored as a
secondary index row in generated_content_records.  Local files remain canonical.

Author: Shawn Jackson Dyck
Version: alpha-v0.0.3.5
"""

import hashlib
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.shared import get_generated_content_dir
from services.flux_capacitor._config import FluxCapacitorConfig

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Path helpers
# --------------------------------------------------------------------------- #


def _flux_dir(config: FluxCapacitorConfig) -> Path:
    """Return the image artifact directory, creating it if needed."""
    return get_generated_content_dir(config.flux_subdir, create=True)


def _stories_dir(config: FluxCapacitorConfig) -> Path:
    """Return the story text artifact directory, creating it if needed."""
    return get_generated_content_dir(config.stories_subdir, create=True)


def _make_slug(text: str, length: int = 8) -> str:
    """Return a short deterministic hash slug for *text*."""
    return hashlib.sha256(text.encode()).hexdigest()[:length]


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def build_image_path(
    request_id: str,
    channel: Optional[str],
    config: FluxCapacitorConfig,
) -> Path:
    """Return the deterministic output path for an image artifact."""
    ts = _timestamp()
    slug = _make_slug(request_id)
    channel_tag = (channel or "generic").replace("/", "-")[:12]
    filename = f"flux_{channel_tag}_{ts}_{slug}_{request_id[:8]}.png"
    return _flux_dir(config) / filename


def build_story_path(
    request_id: str,
    channel: Optional[str],
    config: FluxCapacitorConfig,
) -> Path:
    """Return the deterministic output path for a story text artifact."""
    ts = _timestamp()
    slug = _make_slug(request_id)
    channel_tag = (channel or "generic").replace("/", "-")[:12]
    filename = f"story_{channel_tag}_{ts}_{slug}_{request_id[:8]}.txt"
    return _stories_dir(config) / filename


def build_metadata_path(base_path: Path) -> Path:
    """Return the sidecar metadata path next to *base_path*."""
    return base_path.with_suffix(".json")


# --------------------------------------------------------------------------- #
# Story persistence
# --------------------------------------------------------------------------- #


def save_story_artifact(
    story_text: str,
    request_id: str,
    source_mode: str,
    channel: Optional[str],
    source_url: Optional[str],
    source_title: Optional[str],
    image_path: Optional[str],
    config: FluxCapacitorConfig,
) -> tuple[Optional[str], Optional[str], str]:
    """Persist a generated story text artifact with its metadata sidecar.

    Returns (story_path_str, metadata_path_str, save_status).
    save_status is "saved" on success, "failed" on error.
    The caller must treat a "failed" status as an explicit signal — never silently ignored.
    """
    if not story_text or not story_text.strip():
        return None, None, "skipped"

    story_path = build_story_path(request_id, channel, config)
    meta_path = build_metadata_path(story_path)

    metadata: Dict[str, Any] = {
        "request_id": request_id,
        "source_mode": source_mode,
        "channel": channel,
        "source_url": source_url,
        "source_title": source_title,
        "image_path": image_path,
        "story_path": str(story_path),
        "saved_at": datetime.now(UTC).isoformat(),
    }

    try:
        story_path.write_text(story_text, encoding="utf-8")
        meta_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(
            "Story artifact saved: %s (request_id=%s)", story_path.name, request_id
        )
        return str(story_path), str(meta_path), "saved"
    except OSError as exc:
        logger.error(
            "Story artifact save FAILED for request_id=%s: %s", request_id, exc
        )
        return None, None, "failed"


# --------------------------------------------------------------------------- #
# Image metadata sidecar
# --------------------------------------------------------------------------- #


def save_image_metadata(
    image_path: Path,
    request_id: str,
    prompt_text: str,
    style_preset: str,
    wait_time_seconds: float,
    render_duration_seconds: float,
    evidence_ids: list[str],
    story_path: Optional[str],
    config: FluxCapacitorConfig,
) -> Optional[str]:
    """Write a JSON sidecar next to the rendered image.

    Returns the metadata path string on success, None on failure.
    """
    meta_path = build_metadata_path(image_path)
    metadata: Dict[str, Any] = {
        "request_id": request_id,
        "prompt_summary": prompt_text[:300],
        "style_preset": style_preset,
        "queue_wait_seconds": wait_time_seconds,
        "render_duration_seconds": render_duration_seconds,
        "evidence_ids": evidence_ids,
        "story_path": story_path,
        "saved_at": datetime.now(UTC).isoformat(),
        "image_path": str(image_path),
    }
    try:
        meta_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.debug("Image metadata sidecar saved: %s", meta_path.name)
        return str(meta_path)
    except OSError as exc:
        logger.error(
            "Image metadata sidecar save FAILED for %s: %s", image_path.name, exc
        )
        return None


# --------------------------------------------------------------------------- #
# Optional DB dual-write
# --------------------------------------------------------------------------- #


def save_to_db(
    *,
    request_id: str,
    run_id: str,
    source_mode: str,
    render_status: str,
    generated_at: datetime,
    candidate_id: Optional[str] = None,
    channel: Optional[str] = None,
    ssi_component: Optional[str] = None,
    source_url: Optional[str] = None,
    source_title: Optional[str] = None,
    story_path: Optional[str] = None,
    story_metadata_path: Optional[str] = None,
    image_path: Optional[str] = None,
    image_metadata_path: Optional[str] = None,
    save_status: str = "saved",
    style_preset: Optional[str] = None,
    prompt_text: Optional[str] = None,
    evidence_ids: Optional[List[str]] = None,
    queue_wait_seconds: float = 0.0,
    render_duration_seconds: float = 0.0,
) -> bool:
    """Mirror the artifact metadata to the DB if DATABASE_ENABLED=true.

    This is an optional secondary index — the local files are canonical.
    Returns True if the row was persisted, False on skip or error.
    """
    if os.getenv("DATABASE_ENABLED", "false").lower() != "true":
        return False

    try:
        from services.database.session import get_session  # type: ignore[import]
        from services.database.repositories import GeneratedContentRecordRepository

        with get_session() as session:
            GeneratedContentRecordRepository.upsert(
                session=session,
                request_id=request_id,
                run_id=run_id,
                source_mode=source_mode,
                render_status=render_status,
                generated_at=generated_at,
                candidate_id=candidate_id,
                channel=channel,
                ssi_component=ssi_component,
                source_url=source_url,
                source_title=source_title,
                story_path=story_path,
                story_metadata_path=story_metadata_path,
                image_path=image_path,
                image_metadata_path=image_metadata_path,
                save_status=save_status,
                style_preset=style_preset,
                prompt_text=prompt_text,
                evidence_ids=evidence_ids or [],
                queue_wait_seconds=queue_wait_seconds,
                render_duration_seconds=render_duration_seconds,
            )
        logger.debug("DB record upserted for request_id=%s", request_id)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "DB dual-write skipped for request_id=%s: %s", request_id, exc
        )
        return False
