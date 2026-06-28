"""
FLUX Capacitor GPU Orchestrator and Pipeline

Single-GPU sequencing gate for RTX 3060.

Priority tiers:
  Tier 1 (priority 0) — Ollama jobs
  Tier 2 (priority 1) — FLUX art-avatar jobs

Behavior:
  • FLUX requests wait behind any active Ollama work.
  • If queue pressure exceeds queue_wait_timeout_seconds the gate returns
    GPUGateOutcome.TEXT_ONLY so the caller flow does not stall.
  • At most one active GPU job runs at a time.
  • All gate decisions are logged with timing so operators can tune thresholds.

Author: Shawn Jackson Dyck
Version: alpha-v0.0.2.7
"""

import gc
import logging
import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from threading import Lock
from typing import Generator, Optional

from services.flux_capacitor._config import STYLE_PRESETS, DEFAULT_STYLE_PRESET, FluxCapacitorConfig
from services.flux_capacitor._models import (
    ArtAvatarRequest,
    ArtAvatarResult,
    ArtAvatarTelemetry,
    GPUGateOutcome,
    GPUJobSlot,
    GPUPolicy,
    RenderStatus,
    StylePreset,
)
from services.flux_capacitor._prompting import build_prompt, build_negative_prompt, resolve_style_preset
from services.flux_capacitor._storage import (
    build_image_path,
    save_image_metadata,
    save_story_artifact,
    save_to_db,
)

logger = logging.getLogger(__name__)

# Module-level import with graceful fallback so the symbol is patchable in tests
try:
    from services.image_generation import generate_flux_image as _generate_flux_image  # type: ignore
except ImportError:  # 'full' profile not installed
    _generate_flux_image = None  # type: ignore[assignment]


def _evict_ollama_from_vram(max_wait_seconds: int) -> None:
    """Force the Ollama model out of VRAM before a FLUX render starts.

    keep_alive=0 on chat calls only schedules an async unload; this blocks
    until `ollama ps` confirms the model is gone so FLUX can allocate the GPU.
    Fully defensive — never raises into the render path.
    """
    if os.getenv("FLUX_CAPACITOR_FORCE_OLLAMA_UNLOAD", "true").lower() != "true":
        return
    try:
        from services.ollama_service import OllamaService

        svc = OllamaService(
            model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
        if not svc.unload(wait_seconds=min(float(max_wait_seconds), 60.0)):
            logger.warning("FLUX gate: Ollama VRAM not confirmed freed before render")
    except Exception as exc:  # noqa: BLE001 — never block the render path
        logger.warning("FLUX gate: Ollama unload hook failed: %s", exc)


# --------------------------------------------------------------------------- #
# GPU Orchestrator
# --------------------------------------------------------------------------- #


class GPUOrchestrator:
    """In-process single-GPU serialization gate.

    Thread-safe: backed by a threading.Lock so concurrent callers block
    rather than racing.
    """

    def __init__(self, policy: GPUPolicy) -> None:
        self._policy = policy
        self._lock = Lock()
        self._active_job: Optional[GPUJobSlot] = None
        self._ollama_active: bool = False

    # ------------------------------------------------------------------ #
    # Ollama lifecycle hooks (called by orchestration code around LLM work)
    # ------------------------------------------------------------------ #

    def mark_ollama_start(self, job_id: Optional[str] = None) -> str:
        """Signal that an Ollama GPU job has begun.  Returns the job_id."""
        jid = job_id or str(uuid.uuid4())[:8]
        with self._lock:
            self._ollama_active = True
            self._active_job = GPUJobSlot(
                job_id=jid, job_type="ollama", priority=0
            )
        logger.debug("GPU orchestrator: Ollama job started (id=%s)", jid)
        return jid

    def mark_ollama_done(self, job_id: Optional[str] = None) -> None:
        """Signal that an Ollama GPU job has completed."""
        with self._lock:
            self._ollama_active = False
            if self._active_job and self._active_job.job_type == "ollama":
                self._active_job.completed_at = datetime.utcnow()
                self._active_job = None
        logger.debug("GPU orchestrator: Ollama job done (id=%s)", job_id)

    # ------------------------------------------------------------------ #
    # Gate check for FLUX
    # ------------------------------------------------------------------ #

    def request_flux_slot(
        self,
        request_id: str,
        max_wait_seconds: int,
    ) -> tuple[GPUGateOutcome, float]:
        """Attempt to acquire a FLUX GPU slot.

        Waits up to *max_wait_seconds* for Ollama work to drain.
        Returns (outcome, wait_seconds_elapsed).
        """
        if not self._policy.ollama_first:
            return GPUGateOutcome.ALLOWED, 0.0

        poll_interval = 1.0  # seconds between checks
        elapsed = 0.0

        while elapsed < max_wait_seconds:
            with self._lock:
                if not self._ollama_active and self._active_job is None:
                    # Slot available — acquire it
                    self._active_job = GPUJobSlot(
                        job_id=request_id, job_type="flux", priority=1
                    )
                    logger.info(
                        "GPU gate ALLOWED FLUX request_id=%s (waited %.1fs)",
                        request_id,
                        elapsed,
                    )
                    return GPUGateOutcome.ALLOWED, elapsed

            time.sleep(poll_interval)
            elapsed += poll_interval
            logger.debug(
                "GPU gate: waiting for Ollama to drain (elapsed=%.1fs, max=%ds)",
                elapsed,
                max_wait_seconds,
            )

        # Timeout — return text-only outcome
        logger.warning(
            "GPU gate TIMEOUT for request_id=%s after %.1fs; falling back to TEXT_ONLY.",
            request_id,
            elapsed,
        )
        return GPUGateOutcome.TEXT_ONLY, elapsed

    def release_flux_slot(self, request_id: str) -> None:
        """Release a previously acquired FLUX GPU slot."""
        with self._lock:
            if self._active_job and self._active_job.job_id == request_id:
                self._active_job.completed_at = datetime.utcnow()
                self._active_job = None
                logger.debug(
                    "GPU gate: FLUX slot released (request_id=%s)", request_id
                )

    @contextmanager
    def flux_slot(
        self, request_id: str, max_wait_seconds: int
    ) -> Generator[tuple[GPUGateOutcome, float], None, None]:
        """Context manager that acquires and releases a FLUX GPU slot."""
        outcome, wait = self.request_flux_slot(request_id, max_wait_seconds)
        try:
            yield outcome, wait
        finally:
            if outcome == GPUGateOutcome.ALLOWED:
                self.release_flux_slot(request_id)

    @property
    def ollama_active(self) -> bool:
        return self._ollama_active


# --------------------------------------------------------------------------- #
# Pipeline entry point
# --------------------------------------------------------------------------- #


def run_art_avatar(
    request: ArtAvatarRequest,
    config: FluxCapacitorConfig,
    orchestrator: GPUOrchestrator,
) -> ArtAvatarResult:
    """Orchestrate a full art-avatar render for *request*.

    Checks the GPU gate, builds the prompt, calls FLUX if permitted,
    persists artifacts, and returns an ArtAvatarResult.

    The FLUX inference call is wrapped in a try/except so render failures
    degrade to TEXT_ONLY without breaking the caller's post flow.
    """
    telemetry = ArtAvatarTelemetry()

    # ------------------------------------------------------------------ #
    # 1. Check feature flags
    # ------------------------------------------------------------------ #
    if not config.enabled or config.minimal_mode:
        reason = "minimal_mode" if config.minimal_mode else "feature_disabled"
        logger.info(
            "FLUX art avatar pipeline skipped: %s (request_id=%s)",
            reason,
            request.request_id,
        )
        return ArtAvatarResult(
            request_id=request.request_id,
            status=RenderStatus.TEXT_ONLY,
            prompt_text="",
            telemetry=telemetry,
            defer_reason=reason,
        )

    # ------------------------------------------------------------------ #
    # 2. Build prompt (CPU work — outside the GPU gate)
    # ------------------------------------------------------------------ #
    try:
        prompt_text = build_prompt(request, config)
        negative_prompt = build_negative_prompt()
    except ValueError as exc:
        return ArtAvatarResult(
            request_id=request.request_id,
            status=RenderStatus.FAILED,
            prompt_text="",
            telemetry=telemetry,
            render_error=str(exc),
        )

    # ------------------------------------------------------------------ #
    # 3. Acquire GPU gate
    # ------------------------------------------------------------------ #
    with orchestrator.flux_slot(
        request.request_id, request.max_wait_seconds
    ) as (gate_outcome, wait_seconds):
        telemetry.queue_wait_seconds = wait_seconds
        telemetry.gate_outcome = gate_outcome

        if gate_outcome != GPUGateOutcome.ALLOWED:
            return ArtAvatarResult(
                request_id=request.request_id,
                status=RenderStatus.TEXT_ONLY,
                prompt_text=prompt_text,
                telemetry=telemetry,
                defer_reason=f"gpu_gate_{gate_outcome.value}",
                wait_time_seconds=wait_seconds,
                fallback_text=request.post_text or request.concept_text,
            )

        # ---------------------------------------------------------------- #
        # 4. FLUX inference
        # ---------------------------------------------------------------- #
        render_start = time.monotonic()
        image_path = build_image_path(
            request.request_id, request.source_channel, config
        )
        render_ok = False
        render_error: Optional[str] = None

        # Free the Ollama model from VRAM before FLUX allocates on the same GPU.
        if config.ollama_first:
            _evict_ollama_from_vram(request.max_wait_seconds)

        flux_service_url = os.getenv("FLUX_SERVICE_URL", "").rstrip("/")

        try:
            if flux_service_url:
                # Call the FLUX HTTP service (full Docker profile).
                import requests as _requests
                resp = _requests.post(
                    f"{flux_service_url}/generate",
                    json={"prompt": prompt_text, "output_path": str(image_path)},
                    timeout=300,
                )
                if not resp.ok:
                    raise RuntimeError(resp.json().get("error", resp.text))
                render_ok = True
            elif _generate_flux_image is not None:
                # Fallback: direct in-process call (only works in full_build image).
                _generate_flux_image(
                    prompt=prompt_text,
                    output_path=str(image_path),
                    model_dir=str(
                        __import__("pathlib").Path("models/flux")
                    ),
                )
                render_ok = True
            else:
                raise ImportError("FLUX model not available: set FLUX_SERVICE_URL or install torch/diffusers.")
        except ImportError as exc:
            render_error = str(exc)
            logger.warning(
                "FLUX image generation unavailable (import error): %s", render_error
            )
        except Exception as exc:  # noqa: BLE001
            render_error = str(exc)
            logger.error(
                "FLUX render FAILED for request_id=%s: %s",
                request.request_id,
                exc,
                exc_info=True,
            )

        telemetry.render_duration_seconds = time.monotonic() - render_start
        telemetry.gpu_job_id = request.request_id

    # ------------------------------------------------------------------ #
    # 4b. Post-render memory cleanup (runs after GPU slot released above)
    # ------------------------------------------------------------------ #
    # For the HTTP-service path the cleanup happens inside generate_flux_image.
    # For any remaining Python-side references (request objects, prompt strings,
    # etc.) we nudge the GC so RAM returns to the OS before Ollama reloads.
    gc.collect()

    # ------------------------------------------------------------------ #
    # 5. Persist story artifact (always — independent of render outcome)
    # ------------------------------------------------------------------ #
    story_text = request.post_text or request.concept_text or ""
    story_path_str, story_meta_str, story_status = save_story_artifact(
        story_text=story_text,
        request_id=request.request_id,
        source_mode=request.source_mode.value,
        channel=request.source_channel,
        source_url=None,
        source_title=None,
        image_path=str(image_path) if render_ok else None,
        config=config,
    )

    # ------------------------------------------------------------------ #
    # 6. Persist image metadata sidecar (only on success)
    # ------------------------------------------------------------------ #
    meta_path_str: Optional[str] = None
    if render_ok:
        preset = resolve_style_preset(request.style_profile, config)
        meta_path_str = save_image_metadata(
            image_path=image_path,
            request_id=request.request_id,
            prompt_text=prompt_text,
            style_preset=request.style_profile,
            wait_time_seconds=telemetry.queue_wait_seconds,
            render_duration_seconds=telemetry.render_duration_seconds,
            evidence_ids=request.prompt_overrides.get("evidence_ids", []),
            story_path=story_path_str,
            config=config,
        )

    # ------------------------------------------------------------------ #
    # 7. Optional DB dual-write (local files are canonical)
    # ------------------------------------------------------------------ #
    final_render_status = RenderStatus.RENDERED.value if render_ok else RenderStatus.FAILED.value
    save_to_db(
        request_id=request.request_id,
        run_id=request.run_id or request.request_id,
        source_mode=request.source_mode.value,
        render_status=final_render_status,
        generated_at=datetime.utcnow(),
        candidate_id=request.candidate_id,
        channel=request.source_channel,
        ssi_component=request.ssi_component,
        source_url=None,
        source_title=None,
        story_path=story_path_str,
        story_metadata_path=story_meta_str,
        image_path=str(image_path) if render_ok else None,
        image_metadata_path=meta_path_str,
        save_status=story_status,
        style_preset=request.style_profile,
        prompt_text=prompt_text,
        evidence_ids=request.prompt_overrides.get("evidence_ids", []),
        queue_wait_seconds=telemetry.queue_wait_seconds,
        render_duration_seconds=telemetry.render_duration_seconds,
    )

    # ------------------------------------------------------------------ #
    # 8. Build result
    # ------------------------------------------------------------------ #
    if render_ok:
        return ArtAvatarResult(
            request_id=request.request_id,
            status=RenderStatus.RENDERED,
            prompt_text=prompt_text,
            telemetry=telemetry,
            image_path=str(image_path),
            metadata_path=meta_path_str,
            story_path=story_path_str,
            story_metadata_path=story_meta_str,
            story_save_status=story_status,
        )

    return ArtAvatarResult(
        request_id=request.request_id,
        status=RenderStatus.FAILED,
        prompt_text=prompt_text,
        telemetry=telemetry,
        render_error=render_error,
        story_path=story_path_str,
        story_metadata_path=story_meta_str,
        story_save_status=story_status,
        fallback_text=request.post_text or request.concept_text,
    )
