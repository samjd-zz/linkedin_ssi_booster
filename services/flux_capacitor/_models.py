"""
FLUX Capacitor Data Models

Request / result contracts, style presets, queue state, and telemetry payloads
for the art-avatar rendering pipeline.

Author: Shawn Jackson Dyck
Version: alpha-v0.0.2.7
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #


class RenderStatus(str, Enum):
    """Outcome of an art-avatar render request."""

    RENDERED = "rendered"
    DEFERRED = "deferred"
    TEXT_ONLY = "text_only"
    FAILED = "failed"


class SourceMode(str, Enum):
    """Which workflow triggered the render request."""

    SCHEDULE = "schedule"
    CURATE = "curate"
    CONSOLE = "console"


class GPUGateOutcome(str, Enum):
    """Outcome returned by the GPU orchestrator gate."""

    ALLOWED = "allowed"
    DEFERRED = "deferred"
    TEXT_ONLY = "text_only"


# --------------------------------------------------------------------------- #
# Style Preset
# --------------------------------------------------------------------------- #


@dataclass
class StylePreset:
    """Constrains the visual aesthetic of a render request.

    All numeric fields are clamped against config hard limits at request time.
    """

    name: str
    palette: str
    geometry_density: float  # 0.0–1.0
    saturation_cap: float    # 0.0–1.0
    surreal_intensity_cap: float  # 0.0–1.0
    prompt_suffix: str


# --------------------------------------------------------------------------- #
# GPU Policy
# --------------------------------------------------------------------------- #


@dataclass
class GPUPolicy:
    """Controls RTX 3060 single-GPU sequencing behavior."""

    ollama_first: bool = True
    flux_after_ollama: bool = True
    max_concurrent_gpu_jobs: int = 1
    queue_wait_timeout_seconds: int = 120
    defer_to_text_only_after_timeout: bool = True
    flux_render_width: int = 768
    flux_render_height: int = 768
    flux_steps: int = 4


# --------------------------------------------------------------------------- #
# Request / Result
# --------------------------------------------------------------------------- #


@dataclass
class ArtAvatarRequest:
    """Represents a render request from schedule, curate, or console flow."""

    request_id: str
    source_mode: SourceMode
    style_profile: str  # name of a StylePreset key
    ollama_priority_context: bool  # True if Ollama is currently active
    requested_at: datetime = field(default_factory=datetime.utcnow)

    # Content — one of these must be provided
    post_text: Optional[str] = None
    concept_text: Optional[str] = None

    # Optional fields
    theme: Optional[str] = None
    channels: List[str] = field(default_factory=list)
    target_width: Optional[int] = None
    target_height: Optional[int] = None
    defer_if_busy: bool = True
    max_wait_seconds: int = 120
    source_post_id: Optional[str] = None
    source_channel: Optional[str] = None
    knowledge_context: Optional[str] = None
    prompt_overrides: Dict[str, Any] = field(default_factory=dict)
    style_overrides: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.post_text and not self.concept_text:
            raise ValueError(
                "ArtAvatarRequest requires either 'post_text' or 'concept_text'."
            )
        if not self.request_id:
            raise ValueError("ArtAvatarRequest.request_id must not be empty.")
        if self.source_mode not in SourceMode:
            raise ValueError(
                f"Invalid source_mode '{self.source_mode}'. "
                f"Expected one of {list(SourceMode)}."
            )


@dataclass
class ArtAvatarTelemetry:
    """Timing and queue metadata attached to every result."""

    queue_wait_seconds: float = 0.0
    render_duration_seconds: float = 0.0
    defer_count: int = 0
    gpu_job_id: Optional[str] = None
    gate_outcome: Optional[GPUGateOutcome] = None


@dataclass
class ArtAvatarResult:
    """Outcome of a render request.

    status == RENDERED  → image_path is populated.
    status == DEFERRED  → defer_reason explains why; image_path is None.
    status == TEXT_ONLY → GPU was busy / minimal mode; no image produced.
    status == FAILED    → render_error describes the failure.
    """

    request_id: str
    status: RenderStatus
    prompt_text: str
    telemetry: ArtAvatarTelemetry = field(default_factory=ArtAvatarTelemetry)
    evidence_ids: List[str] = field(default_factory=list)

    # Populated on success
    image_path: Optional[str] = None
    metadata_path: Optional[str] = None

    # Story artifact linkage
    story_path: Optional[str] = None
    story_metadata_path: Optional[str] = None
    story_save_status: Optional[str] = None  # "saved", "failed", "skipped"

    # Populated on defer / text-only / failure
    defer_reason: Optional[str] = None
    wait_time_seconds: Optional[float] = None
    fallback_text: Optional[str] = None
    render_error: Optional[str] = None


# --------------------------------------------------------------------------- #
# Queue state (internal)
# --------------------------------------------------------------------------- #


@dataclass
class GPUJobSlot:
    """Tracks a single in-flight GPU job inside the orchestrator."""

    job_id: str
    job_type: str  # "ollama" or "flux"
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    priority: int = 0  # lower = higher priority (0 = Ollama, 1 = FLUX)
