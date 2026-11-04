"""FLUX art-avatar render helpers and post-generation cleanup for CLI flows."""

from __future__ import annotations

import gc
import logging
import os
import sys
from typing import Any

from colorama import Fore, Style

from services.flux_capacitor import get_flux_service, SourceMode, RenderStatus
from services.flux_capacitor._terminal import _display_art_in_terminal
from services.ollama_service import OllamaService
from services.performance import timed_stage

logger = logging.getLogger(__name__)


@timed_stage(logger, "cleanup.total")
def _run_post_generation_cleanup(ai: OllamaService, source_mode: str) -> None:
    """Release model/runtime memory after schedule/curate runs.

    This performs best-effort cleanup only and never raises.
    """
    logger.info("🧹 Running post-%s memory cleanup...", source_mode)

    # 1) Ask Ollama to evict loaded models from VRAM/RAM.
    try:
        with timed_stage(logger, "cleanup.ollama"):
            ai.unload(wait_seconds=10.0)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Post-%s Ollama unload skipped: %s", source_mode, exc)

    # 2) Ask flux-app service to unload cached FLUX runtime (if service mode is active).
    flux_service_url = os.getenv("FLUX_SERVICE_URL", "").rstrip("/")
    from services.flux_capacitor import _pipeline as _flux_pipeline
    if flux_service_url and _flux_pipeline._REMOTE_RUNTIME_USED:
        try:
            import requests as _requests

            with timed_stage(logger, "cleanup.flux_remote"):
                resp = _requests.post(f"{flux_service_url}/unload", timeout=30)
            if resp.ok:
                _flux_pipeline._REMOTE_RUNTIME_USED = False
                logger.info("FLUX runtime unload requested via %s/unload", flux_service_url)
            else:
                logger.warning(
                    "FLUX runtime unload endpoint returned status=%s body=%s",
                    resp.status_code,
                    resp.text,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Post-%s flux-app unload failed: %s", source_mode, exc)

    # 3) If in-process FLUX runtime is present (fallback mode), unload it too.
    try:
        _image_module = sys.modules.get("services.image_generation")
        if _image_module is not None:
            with timed_stage(logger, "cleanup.flux_local"):
                _image_module.unload_flux_runtime()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Post-%s in-process FLUX unload skipped: %s", source_mode, exc)

    # 4) Final Python heap collection pass.
    with timed_stage(logger, "cleanup.heap"):
        gc.collect()
        gc.collect()

    # 5) Linux/glibc heap trim (best-effort) to return freed pages to OS.
    if sys.platform.startswith("linux"):
        try:
            import ctypes

            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Post-%s malloc_trim skipped: %s", source_mode, exc)


@timed_stage(logger, "schedule.art")
def _render_schedule_art_avatar(
    ai: OllamaService,
    post_text: str,
    channel: str,
    topic: dict,
    *,
    optimize_story: bool = True,
) -> dict:
    """Run FLUX art-avatar rendering for schedule flow and return metadata.

    Returns an empty dict when rendering is not available.
    """
    if not post_text or channel == "youtube":
        return {}

    try:
        optimized_post_text = (post_text or "").strip()
        if optimize_story:
            optimized_post_text = _optimize_flux_story_for_render(
                ai,
                post_text,
                source_mode=SourceMode.SCHEDULE,
                channel=channel,
                title=topic.get("title", ""),
                angle=topic.get("angle", ""),
                theme=topic.get("title", ""),
                knowledge_context=topic.get("angle", ""),
            )
        flux_service = get_flux_service()
        request = flux_service.make_request(
            post_text=optimized_post_text,
            source_mode=SourceMode.SCHEDULE,
            channel=channel,
            theme=topic.get("title"),
            knowledge_context=topic.get("angle"),
            defer_if_busy=True,
        )
        result = flux_service.render(request)

        if result.status == RenderStatus.RENDERED:
            logger.info(
                "🎨 FLUX rendered for topic='%s' channel=%s image=%s",
                topic.get("title", ""),
                channel,
                result.image_path,
            )
        else:
            logger.info(
                "🎨 FLUX status=%s for topic='%s' channel=%s reason=%s",
                result.status.value,
                topic.get("title", ""),
                channel,
                result.defer_reason or result.render_error or "",
            )

        return {
            "art_avatar_status": result.status.value,
            "art_avatar_image_path": result.image_path,
            "art_avatar_metadata_path": result.metadata_path,
            "art_avatar_story_path": result.story_path,
            "art_avatar_story_metadata_path": result.story_metadata_path,
            "art_avatar_story_save_status": result.story_save_status,
            "art_avatar_defer_reason": result.defer_reason,
            "art_avatar_render_error": result.render_error,
            "art_avatar_wait_seconds": result.wait_time_seconds,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "FLUX schedule integration failed for topic='%s' channel=%s: %s",
            topic.get("title", ""),
            channel,
            exc,
        )
        return {"art_avatar_status": "failed", "art_avatar_render_error": str(exc)}


def _render_curate_art_avatar(
    ai: OllamaService,
    idea: dict,
    channel: str,
    *,
    optimize_story: bool = True,
) -> dict:
    """Run FLUX art-avatar rendering for the curate flow and return metadata.

    Returns an empty dict when rendering is not available or not applicable.
    """
    post_text: str = idea.get("generated_text") or idea.get("text", "")  # type: ignore[assignment]
    if not optimize_story:
        _preoptimized_text = str(idea.get("_flux_optimized_post_text") or "").strip()
        if _preoptimized_text:
            post_text = _preoptimized_text
    if not post_text or channel in ("youtube", "all"):
        return {}

    try:
        optimized_post_text = post_text.strip()
        if optimize_story:
            optimized_post_text = _optimize_flux_story_for_render(
                ai,
                post_text,
                source_mode=SourceMode.CURATE,
                channel=channel,
                title=idea.get("title", ""),
                angle=idea.get("summary", ""),
                theme=idea.get("title", ""),
                knowledge_context=(idea.get("summary") or idea.get("article_text") or ""),
            )
        flux_service = get_flux_service()
        _knowledge_ctx: str = (idea.get("summary") or idea.get("article_text") or "").strip()
        request = flux_service.make_request(
            post_text=optimized_post_text,
            source_mode=SourceMode.CURATE,
            channel=channel,
            theme=idea.get("title"),
            knowledge_context=_knowledge_ctx or None,
            defer_if_busy=True,
        )
        result = flux_service.render(request)

        if result.status == RenderStatus.RENDERED:
            logger.info(
                "🎨 FLUX rendered for idea='%s' channel=%s image=%s",
                idea.get("title", ""),
                channel,
                result.image_path,
            )
        else:
            logger.info(
                "🎨 FLUX status=%s for idea='%s' channel=%s reason=%s",
                result.status.value,
                idea.get("title", ""),
                channel,
                result.defer_reason or result.render_error or "",
            )

        return {
            "art_avatar_status": result.status.value,
            "art_avatar_image_path": result.image_path,
            "art_avatar_metadata_path": result.metadata_path,
            "art_avatar_story_path": result.story_path,
            "art_avatar_story_metadata_path": result.story_metadata_path,
            "art_avatar_story_save_status": result.story_save_status,
            "art_avatar_defer_reason": result.defer_reason,
            "art_avatar_render_error": result.render_error,
            "art_avatar_wait_seconds": result.wait_time_seconds,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "FLUX curate integration failed for idea='%s' channel=%s: %s",
            idea.get("title", ""),
            channel,
            exc,
        )
        return {"art_avatar_status": "failed", "art_avatar_render_error": str(exc)}


@timed_stage(logger, "console.art")
def _render_console_art_avatar(
    ai: OllamaService,
    post_text: str,
    topic_hint: str | None = None,
) -> dict:
    """Run FLUX art-avatar rendering for the console flow and return metadata.

    Returns an empty dict when rendering is not available.
    """
    if not post_text:
        return {}

    try:
        optimized_post_text = _optimize_flux_story_for_render(
            ai,
            post_text,
            source_mode=SourceMode.CONSOLE,
            channel="linkedin",
            theme=topic_hint or "",
            knowledge_context=topic_hint or "",
        )
        flux_service = get_flux_service()
        request = flux_service.make_request(
            post_text=optimized_post_text,
            source_mode=SourceMode.CONSOLE,
            channel="linkedin",
            theme=topic_hint,
            defer_if_busy=True,
        )
        result = flux_service.render(request)

        if result.status == RenderStatus.RENDERED:
            logger.info(
                "🎨 FLUX rendered for console reply image=%s",
                result.image_path,
            )
        else:
            logger.info(
                "🎨 FLUX status=%s for console reply reason=%s",
                result.status.value,
                result.defer_reason or result.render_error or "",
            )

        return {
            "art_avatar_status": result.status.value,
            "art_avatar_image_path": result.image_path,
            "art_avatar_metadata_path": result.metadata_path,
            "art_avatar_story_path": result.story_path,
            "art_avatar_story_metadata_path": result.story_metadata_path,
            "art_avatar_story_save_status": result.story_save_status,
            "art_avatar_defer_reason": result.defer_reason,
            "art_avatar_render_error": result.render_error,
            "art_avatar_wait_seconds": result.wait_time_seconds,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("FLUX console integration failed: %s", exc)
        return {"art_avatar_status": "failed", "art_avatar_render_error": str(exc)}


def _auto_render_art_if_requested(
    ai: OllamaService,
    reply_text: str,
    constraints: Any,
    user_input: str,
) -> None:
    """Automatically trigger FLUX art avatar render when user requests an image/artwork."""
    if not getattr(constraints, "is_japanese_art_request", False) and not getattr(constraints, "has_image_request", False):
        return

    _art_topic_hint = getattr(constraints, "art_subject_hint", "") or user_input
    print(str(Fore.CYAN) + f"\n🎨 Auto-rendering artwork ('{_art_topic_hint}') via FLUX.1..." + str(Style.RESET_ALL))
    _art_result = _render_console_art_avatar(ai, reply_text, _art_topic_hint)
    _art_status = _art_result.get("art_avatar_status", "unavailable")
    if _art_status == RenderStatus.RENDERED.value:
        print(str(Fore.GREEN) + f"✅  Art rendered → {_art_result.get('art_avatar_image_path', '')}" + str(Style.RESET_ALL))
        _display_art_in_terminal(_art_result.get("art_avatar_image_path"))
        _story = _art_result.get("art_avatar_story_path")
        if _story:
            print(str(Fore.GREEN) + f"   Story → {_story}" + str(Style.RESET_ALL))
    elif _art_status in (RenderStatus.DEFERRED.value, RenderStatus.TEXT_ONLY.value):
        print(str(Fore.YELLOW) + f"⏳  GPU busy — {_art_result.get('art_avatar_defer_reason', 'image deferred')}" + str(Style.RESET_ALL))
    else:
        print(str(Fore.RED) + f"⚠️  Art generation: {_art_status} — {_art_result.get('art_avatar_render_error', '')}" + str(Style.RESET_ALL))


def _optimize_flux_story_for_render(
    ai: OllamaService,
    story_text: str,
    *,
    source_mode: SourceMode,
    channel: str,
    title: str = "",
    angle: str = "",
    theme: str = "",
    knowledge_context: str = "",
) -> str:
    """Rewrite story text into a FLUX-ready visual prompt.

    Text-only flows keep the original story without making an LLM request.
    """
    story_text = (story_text or "").strip()
    if not story_text:
        return ""
    try:
        config = get_flux_service().config
        if not config.enabled or config.minimal_mode:
            logger.debug("FLUX prompt optimization skipped (text-only mode)")
            return story_text
        return ai.optimise_flux_art_prompt(
            story_text,
            title=title,
            angle=angle,
            theme=theme,
            knowledge_context=knowledge_context,
            channel=channel,
            source_mode=source_mode.value,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "FLUX prompt optimization failed for source_mode=%s channel=%s: %s",
            source_mode.value,
            channel,
            exc,
        )
        return story_text
