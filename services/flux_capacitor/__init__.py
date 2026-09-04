"""
FLUX Capacitor Service Package

Public API for the art-avatar rendering pipeline.

Typical usage (schedule/curate flows)::

    from services.flux_capacitor import (
        get_flux_service,
        ArtAvatarRequest,
        SourceMode,
        RenderStatus,
    )

    svc = get_flux_service()
    result = svc.render(request)
    if result.status == RenderStatus.RENDERED:
        print("Image saved to", result.image_path)

Author: Shawn Jackson Dyck
Version: alpha-v0.0.3.5
"""

import logging
import uuid
from datetime import datetime
from threading import Lock
from typing import Optional

from services.flux_capacitor._config import FluxCapacitorConfig, STYLE_PRESETS, DEFAULT_STYLE_PRESET
from services.flux_capacitor._models import (
    ArtAvatarRequest,
    ArtAvatarResult,
    ArtAvatarTelemetry,
    GPUPolicy,
    RenderStatus,
    SourceMode,
    GPUGateOutcome,
    StylePreset,
    GPUJobSlot,
)
from services.flux_capacitor._pipeline import GPUOrchestrator, run_art_avatar
from services.flux_capacitor._prompting import build_prompt, build_negative_prompt, resolve_style_preset
from services.flux_capacitor._storage import (
    save_story_artifact,
    save_image_metadata,
    build_image_path,
    build_story_path,
)

logger = logging.getLogger(__name__)

__all__ = [
    # Config
    "FluxCapacitorConfig",
    "STYLE_PRESETS",
    "DEFAULT_STYLE_PRESET",
    # Models
    "ArtAvatarRequest",
    "ArtAvatarResult",
    "ArtAvatarTelemetry",
    "GPUPolicy",
    "GPUGateOutcome",
    "GPUJobSlot",
    "RenderStatus",
    "SourceMode",
    "StylePreset",
    # Prompting
    "build_prompt",
    "build_negative_prompt",
    "resolve_style_preset",
    # Storage helpers
    "save_story_artifact",
    "save_image_metadata",
    "build_image_path",
    "build_story_path",
    # Pipeline
    "GPUOrchestrator",
    "run_art_avatar",
    # Service
    "FluxCapacitorService",
    "get_flux_service",
]


class FluxCapacitorService:
    """High-level API for art-avatar rendering.

    A single instance is shared across schedule, curate, and console flows
    so that the GPU orchestrator remains consistent and single-use.
    """

    def __init__(self, config: Optional[FluxCapacitorConfig] = None) -> None:
        self._config = config or FluxCapacitorConfig()
        self._policy = GPUPolicy(
            ollama_first=self._config.ollama_first,
            flux_after_ollama=self._config.flux_after_ollama,
            max_concurrent_gpu_jobs=self._config.max_concurrent_gpu_jobs,
            queue_wait_timeout_seconds=self._config.queue_wait_timeout_seconds,
            flux_render_width=self._config.render_width,
            flux_render_height=self._config.render_height,
            flux_steps=self._config.render_steps,
        )
        self._orchestrator = GPUOrchestrator(self._policy)

    # ------------------------------------------------------------------ #
    # Ollama lifecycle — call from any flow that drives LLM generation
    # ------------------------------------------------------------------ #

    def notify_ollama_start(self, job_id: Optional[str] = None) -> str:
        """Signal that Ollama GPU work is beginning.  Returns the job_id."""
        return self._orchestrator.mark_ollama_start(job_id)

    def notify_ollama_done(self, job_id: Optional[str] = None) -> None:
        """Signal that Ollama GPU work is complete."""
        self._orchestrator.mark_ollama_done(job_id)

    # ------------------------------------------------------------------ #
    # Render entry point
    # ------------------------------------------------------------------ #

    def render(self, request: ArtAvatarRequest) -> ArtAvatarResult:
        """Execute the art-avatar pipeline for *request*.

        Always returns an ArtAvatarResult — never raises for GPU / render errors.
        Check result.status to determine the outcome.
        """
        if not self._config.enabled:
            return ArtAvatarResult(
                request_id=request.request_id,
                status=RenderStatus.TEXT_ONLY,
                prompt_text="",
                defer_reason="feature_disabled",
            )
        return run_art_avatar(request, self._config, self._orchestrator)

    def make_request(
        self,
        post_text: Optional[str] = None,
        concept_text: Optional[str] = None,
        source_mode: SourceMode = SourceMode.SCHEDULE,
        channel: Optional[str] = None,
        theme: Optional[str] = None,
        knowledge_context: Optional[str] = None,
        defer_if_busy: bool = True,
    ) -> ArtAvatarRequest:
        """Convenience factory for building a request from the schedule/curate/console paths."""
        request_id = str(uuid.uuid4())
        return ArtAvatarRequest(
            request_id=request_id,
            source_mode=source_mode,
            style_profile=self._config.style_preset,
            ollama_priority_context=self._orchestrator.ollama_active,
            post_text=post_text,
            concept_text=concept_text,
            source_channel=channel,
            theme=theme,
            knowledge_context=knowledge_context,
            defer_if_busy=defer_if_busy,
            max_wait_seconds=self._config.queue_wait_timeout_seconds,
        )

    @property
    def config(self) -> FluxCapacitorConfig:
        return self._config

    @property
    def orchestrator(self) -> GPUOrchestrator:
        return self._orchestrator


# --------------------------------------------------------------------------- #
# Singleton accessor
# --------------------------------------------------------------------------- #

_service_lock = Lock()
_service_instance: Optional[FluxCapacitorService] = None


def get_flux_service() -> FluxCapacitorService:
    """Return the process-wide FluxCapacitorService singleton."""
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = FluxCapacitorService()
                logger.info(
                    "FluxCapacitorService initialised (enabled=%s, style_preset=%s)",
                    _service_instance.config.enabled,
                    _service_instance.config.style_preset,
                )
    return _service_instance
