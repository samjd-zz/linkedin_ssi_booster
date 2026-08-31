
"""
LinkedIn SSI Booster — main entrypoint
=======================================
Generates and schedules LinkedIn posts via the Buffer API to improve
Social Selling Index (SSI) across all four components.

AI backend: Ollama (local) — requires Ollama running on OLLAMA_BASE_URL

Usage:
    python main.py --schedule [--week N] [--dry-run] [--interactive] [--channel linkedin,youtube,threads]
            # --schedule: generate and schedule posts (or preview with --dry-run)
    python main.py --curate               [--dry-run] [--interactive] [--channel linkedin,youtube,threads] [--type idea|post]
    python main.py --console
    python main.py --report
"""

from __future__ import annotations

import os
import json
import argparse
import logging
import re
import sys
import gc
import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from colorama import Fore, Style, init as _colorama_init

from scheduler import PostScheduler
from services.buffer_service import BufferService, BufferQueueFullError, BufferRateLimitError, BufferChannelNotConnectedError
from services.selection_learning import ACCEPTANCE_WINDOW_DAYS
from services.shared import append_channel_footer, get_rei_toei_dir, get_youtube_scripts_dir
from services.flux_capacitor import get_flux_service, SourceMode, RenderStatus
from services.graph_stats import collect_domain_knowledge_profiles


def _configure_stdio() -> None:
    """Keep emoji/Unicode status output from crashing Windows cp1252 shells."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (TypeError, ValueError, OSError):
            # Some wrapped streams do not allow reconfiguration; best effort only.
            pass


_configure_stdio()
_colorama_init(autoreset=True)
load_dotenv()


def load_content_calendar() -> dict:
    """Load the content calendar, preferring CONTENT_CALENDAR_PATH (per-client JSON) over the local module."""
    calendar_path = os.getenv("CONTENT_CALENDAR_PATH", "").strip()
    if calendar_path:
        path = Path(calendar_path)
        if not path.exists():
            raise FileNotFoundError(f"CONTENT_CALENDAR_PATH set but file not found: {calendar_path}")
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    from content_calendar import CONTENT_CALENDAR as _default_calendar
    return _default_calendar


# --- Intelligent Startup Notice ---
def print_startup_notice():
    print(str(Fore.CYAN) + str(Style.BRIGHT) + "\n👋 Welcome to LinkedIn SSI Booster!" + str(Style.RESET_ALL))
    print(str(Fore.WHITE) + f"Acceptance window: {ACCEPTANCE_WINDOW_DAYS} days" + str(Style.RESET_ALL))
    today = datetime.now(timezone.utc).date()
    cutoff_date = today + timedelta(days=ACCEPTANCE_WINDOW_DAYS)
    print(str(Fore.WHITE) + f"Latest date for 'new' post acceptance: {cutoff_date}" + str(Style.RESET_ALL))
    print(str(Fore.YELLOW) + "\n⚠️  IMPORTANT: Posts scheduled beyond the cutoff may not count for SSI growth!" + str(Style.RESET_ALL))

    # Try to connect to Buffer and check scheduled posts
    buffer_api_key = os.getenv("BUFFER_API_KEY")
    if not buffer_api_key:
        print(str(Fore.YELLOW) + "\n⚠️  BUFFER_API_KEY not set. Buffer scheduling will be disabled." + str(Style.RESET_ALL))
        return
    # Buffer scheduling check logic is commented out for now
    # try:
    #     buffer = BufferService(api_key=buffer_api_key)
    #     channels = buffer.get_channels()
    #     for ch in channels:
    #         ch_id = ch.get("id")
    #         ch_name = ch.get("name")
    #         ch_service = ch.get("service")
    #         scheduled = buffer.get_scheduled_posts(ch_id)
    #         if not scheduled:
    #             continue
    #         # Find the latest scheduled post date
    #         max_due = None
    #         for post in scheduled:
    #             due = post.get("dueAt")
    #             if due:
    #                 try:
    #                     due_dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
    #                     if not max_due or due_dt > max_due:
    #                         max_due = due_dt
    #                 except Exception:
    #                     continue
    #         if max_due and max_due.date() > cutoff_date:
    #             print(str(Fore.YELLOW) + f"\n⚠️  WARNING: Buffer queue for {ch_name} has posts scheduled beyond the acceptance window!" + str(Style.RESET_ALL))
    # except Exception as e:
    #     print(str(Fore.YELLOW) + f"\n⚠️  Could not check Buffer queue: {e}" + str(Style.RESET_ALL))

# --- Coloured log formatter ---
class _ColourFormatter(logging.Formatter):
    _LEVEL = {
        logging.DEBUG:    str(Fore.CYAN)   + "DEBUG"    + str(Style.RESET_ALL),
        logging.INFO:     str(Fore.GREEN)  + "INFO"     + str(Style.RESET_ALL),
        logging.WARNING:  str(Fore.YELLOW) + "WARN"     + str(Style.RESET_ALL),
        logging.ERROR:    str(Fore.RED)    + "ERROR"    + str(Style.RESET_ALL),
        logging.CRITICAL: str(Fore.RED)    + str(Style.BRIGHT) + "CRITICAL" + str(Style.RESET_ALL),
    }
    def format(self, record: logging.LogRecord) -> str:
        record = logging.makeLogRecord(record.__dict__)
        record.levelname = self._LEVEL.get(record.levelno, record.levelname)
        return super().format(record)

_handler = logging.StreamHandler()
_handler.setFormatter(_ColourFormatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_handler])
logging.getLogger("httpx").setLevel(logging.WARNING)   # suppress "HTTP Request: POST ..." at INFO
logging.getLogger("httpcore").setLevel(logging.WARNING) # suppress underlying transport logs
logger = logging.getLogger(__name__)


def _run_post_generation_cleanup(ai: OllamaService, source_mode: str) -> None:
    """Release model/runtime memory after schedule/curate runs.

    This performs best-effort cleanup only and never raises.
    """
    logger.info("🧹 Running post-%s memory cleanup...", source_mode)

    # 1) Ask Ollama to evict loaded models from VRAM/RAM.
    try:
        ai.unload(wait_seconds=10.0)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Post-%s Ollama unload skipped: %s", source_mode, exc)

    # 2) Ask flux-app service to unload cached FLUX runtime (if service mode is active).
    flux_service_url = os.getenv("FLUX_SERVICE_URL", "").rstrip("/")
    if flux_service_url:
        try:
            import requests as _requests

            resp = _requests.post(f"{flux_service_url}/unload", timeout=30)
            if resp.ok:
                logger.info("FLUX runtime unload requested via %s/unload", flux_service_url)
            else:
                logger.warning(
                    "FLUX runtime unload endpoint returned status=%s body=%s",
                    resp.status_code,
                    resp.text,
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Post-%s flux-app unload skipped: %s", source_mode, exc)

    # 3) If in-process FLUX runtime is present (fallback mode), unload it too.
    try:
        from services.image_generation import unload_flux_runtime

        unload_flux_runtime()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Post-%s in-process FLUX unload skipped: %s", source_mode, exc)

    # 4) Final Python heap collection pass.
    gc.collect()
    gc.collect()

    # 5) Linux/glibc heap trim (best-effort) to return freed pages to OS.
    if sys.platform.startswith("linux"):
        try:
            import ctypes

            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Post-%s malloc_trim skipped: %s", source_mode, exc)


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


def _display_art_in_terminal(image_path: str | None, width: int | None = None) -> None:
    """Render a FLUX-generated image inline in the terminal using term-image.

    ``width`` is the number of terminal columns to occupy.  ``None`` (default)
    lets term-image auto-fit to the full terminal width, which gives the highest
    possible cell resolution for the active renderer protocol (kitty / iterm2 /
    sixel / unicode-blocks).  Override with the ``FLUX_DISPLAY_WIDTH`` env var
    (e.g. ``FLUX_DISPLAY_WIDTH=80``) to cap the width when needed.

    Silently skips if the path is missing, the file does not exist, or
    term-image is unavailable / the terminal does not support inline graphics.
    """
    if not image_path:
        return

    from pathlib import Path as _Path
    import shutil as _shutil

    if not _Path(image_path).is_file():
        return

    _env_width_raw = os.getenv("FLUX_DISPLAY_WIDTH", "").strip()
    _env_width: int | None = int(_env_width_raw) if _env_width_raw.isdigit() else None
    _requested_width = width if width is not None else _env_width

    _terminal_columns = _shutil.get_terminal_size(fallback=(120, 40)).columns
    _render_width: int | None = _requested_width
    if _render_width is not None:
        # Clamp to the active terminal pane so fixed values do not crash rendering.
        _render_width = max(10, min(_render_width, max(10, _terminal_columns - 2)))

    _render_image_path = image_path
    _temp_upsampled_path: str | None = None
    _upsample_factor_raw = os.getenv("FLUX_DISPLAY_UPSCALE_FACTOR", "2").strip()
    _upsample_factor = int(_upsample_factor_raw) if _upsample_factor_raw.isdigit() else 2
    _upsample_factor = max(1, min(_upsample_factor, 6))

    # Upsample with nearest-neighbor so terminal downscaling keeps edge contrast.
    if _upsample_factor > 1:
        try:
            _pil_image_mod = importlib.import_module("PIL.Image")
            import tempfile as _tempfile

            _resampling = getattr(_pil_image_mod, "Resampling", _pil_image_mod)
            _nearest = getattr(_resampling, "NEAREST")

            with _pil_image_mod.open(image_path) as _source_img:
                _upsampled_img = _source_img.resize(
                    (_source_img.width * _upsample_factor, _source_img.height * _upsample_factor),
                    _nearest,
                )

                with _tempfile.NamedTemporaryFile(
                    mode="wb",
                    prefix="flux-term-upsample-",
                    suffix=".png",
                    delete=False,
                ) as _tmp:
                    _temp_upsampled_path = _tmp.name

                _upsampled_img.save(_temp_upsampled_path, format="PNG")
                _render_image_path = _temp_upsampled_path
        except Exception as _upsample_err:  # noqa: BLE001
            logger.warning("terminal upsampling skipped: %s", _upsample_err)

    try:
        _ti_image_mod = importlib.import_module("term_image.image")
        _ti_from_file = getattr(_ti_image_mod, "from_file")
        _img = _ti_from_file(_render_image_path, width=_render_width)
        _img.draw()
    except Exception as _ti_err:  # noqa: BLE001
        if _render_width is not None:
            # Fallback to auto-fit if fixed-width rendering fails in the current pane.
            try:
                _ti_image_mod = importlib.import_module("term_image.image")
                _ti_from_file = getattr(_ti_image_mod, "from_file")
                _img = _ti_from_file(_render_image_path, width=None)
                _img.draw()
                logger.warning(
                    "term-image fixed-width render failed (requested=%s, clamped=%s, cols=%s); fell back to auto-fit: %s",
                    _requested_width,
                    _render_width,
                    _terminal_columns,
                    _ti_err,
                )
                return
            except Exception as _fallback_err:  # noqa: BLE001
                logger.warning(
                    "term-image display skipped after fixed-width and auto-fit failures: %s",
                    _fallback_err,
                )
                return

        logger.warning("term-image display skipped: %s", _ti_err)
    finally:
        if _temp_upsampled_path:
            try:
                _Path(_temp_upsampled_path).unlink(missing_ok=True)
            except OSError:
                pass


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

    Intentionally does NOT gate on FLUX_CAPACITOR_ENABLED — the caller decides
    whether to invoke optimization, and flux_service.render() handles the
    feature-disabled path by returning TEXT_ONLY.  Checking the env flag here
    caused make_request(post_text="") when the feature was off, breaking tests.
    """
    story_text = (story_text or "").strip()
    if not story_text:
        return ""
    try:
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


from services.console_grounding import (
    parse_query_constraints,
    retrieve_relevant_facts,
    build_deterministic_grounded_reply,
    build_katzilla_citation_reply,
    get_latest_extracted_knowledge,
    build_learned_knowledge_context,
    build_grounding_facts_block,
)
from services.ollama_service import OllamaService
from services.github_service import build_github_profile_context
from services.piper_service import speak_text

def run_console(ai: OllamaService, github_context: str = "", verify: bool = False, avatar_explain: bool = False, dot_report: bool = False) -> None:
    """Run interactive persona chat mode in the terminal.
    
    When verify=True, DoT report scanning and spaCy similarity checks are displayed
    for each generated response.
    When avatar_explain=True, evidence IDs and grounding summary are printed after each LLM reply.
    When dot_report=True, Derivative of Truth report is printed after each LLM reply.
    """
    # Patterns that should always route to LLM (not deterministic fact citation)
    GENERATIVE_REQUEST_PHRASES = [
        "write", "generate", "give me", "post", "reply", "respond", "script", "make me", "create",
        "linkedin", "youtube", "x", "bluesky", "twitter", "tiktok", "thread", "mastodon", "deck", "slide"
    ]

    def _print_status() -> None:
        """Print current console mode status."""
        _status_line = str(Style.DIM) + "  Status: " + str(Style.RESET_ALL)
        _status_line += str(Fore.GREEN if verify else Fore.RED) + f"verify={'ON' if verify else 'OFF'}" + str(Style.RESET_ALL)
        _status_line += str(Style.DIM) + " | " + str(Style.RESET_ALL)
        _status_line += str(Fore.GREEN if avatar_explain else Fore.RED) + f"avatar-explain={'ON' if avatar_explain else 'OFF'}" + str(Style.RESET_ALL)
        _status_line += str(Style.DIM) + " | " + str(Style.RESET_ALL)
        _status_line += str(Fore.GREEN if dot_report else Fore.RED) + f"dot-report={'ON' if dot_report else 'OFF'}" + str(Style.RESET_ALL)
        print(_status_line)

    print(str(Fore.CYAN) + str(Style.BRIGHT) + "\n🧠 Persona Console Mode — Enhanced Query Routing" + str(Style.RESET_ALL))
    print("- No Buffer actions will be performed in this mode.")
    print()
    _print_status()
    print()
    print(str(Fore.WHITE) + str(Style.BRIGHT) + "3 Query Routing Modes:" + str(Style.RESET_ALL))
    print()
    print(str(Fore.YELLOW) + "  1️⃣  Explicit File Request → Deterministic citation (raw facts)" + str(Style.RESET_ALL))
    print("    • persona_graph")
    print("    • extracted_knowledge")
    print("    • domain_knowledge")
    print("    • narrative_memory")
    print()
    print(str(Fore.YELLOW) + "  2️⃣  Learned Knowledge → Latest 5 extracted facts as context (or search)" + str(Style.RESET_ALL))
    print("    • from your learned knowledge, what are the AI trends?")
    print("    • based on what you learned, explain...")
    print("    • search your learned knowledge for RAG techniques")
    print("    • find in your learned knowledge about microservices")
    print()
    print(str(Fore.YELLOW) + "  3️⃣  Everything Else → LLM with graph-enhanced retrieval (default)" + str(Style.RESET_ALL))
    print("    • What is RAG?")
    print("    • Explain vector search")
    print("    • What projects have you worked on?")
    print("    • write a LinkedIn post about...")
    print("    • How are you today?")
    print()
    print(str(Fore.WHITE) + str(Style.BRIGHT) + "🔗 Knowledge Graph Integration:" + str(Style.RESET_ALL))
    print("    • 70% BM25 keyword matching")
    print("    • 20% graph proximity (facts closer to persona node rank higher)")
    print("    • 10% claim support (facts with more supporting edges rank higher)")
    print()
    _hr = "─" * 63
    print(str(Fore.CYAN) + f"  {_hr}" + str(Style.RESET_ALL))
    print(str(Fore.WHITE) + str(Style.BRIGHT) + "  Commands" + str(Style.RESET_ALL))
    print(str(Fore.CYAN) + f"  {_hr}" + str(Style.RESET_ALL))
    print(str(Fore.YELLOW) + "  Session   " + str(Style.RESET_ALL) + str(Fore.WHITE) + "/help  /reset  /reload  /exit  /quit" + str(Style.RESET_ALL))
    print(str(Fore.YELLOW) + "  Reports   " + str(Style.RESET_ALL) + str(Fore.WHITE) + "/verify  /avatar-explain  /dot-report  /graph-stats  /katzilla <query>" + str(Style.RESET_ALL))
    print(str(Fore.YELLOW) + "  Identity  " + str(Style.RESET_ALL) + str(Fore.WHITE) + "/rei  /rei-toei  (sticky Rei mode)    /sam  (back to Sam)" + str(Style.RESET_ALL))
    print(str(Fore.YELLOW) + "  Creative  " + str(Style.RESET_ALL) + str(Fore.WHITE) + "/art [topic]  — FLUX render from most recent AI reply" + str(Style.RESET_ALL))
    print(str(Fore.CYAN) + f"  {_hr}" + str(Style.RESET_ALL))
    print()


    history: list[dict[str, str]] = []
    active_console_avatar = "sam"
    max_turns = 24

    def _print_console_reply(avatar: str, reply: str) -> None:
        if avatar == "rei":
            print(str(Fore.MAGENTA) + f"Rei> {reply}" + str(Style.RESET_ALL))
            return
        print(str(Fore.GREEN) + f"Sam> {reply}" + str(Style.RESET_ALL))

    def _print_console_error(avatar: str, error: str) -> None:
        speaker = "Rei" if avatar == "rei" else "Sam"
        print(str(Fore.RED) + f"{speaker}> Error: {error}" + str(Style.RESET_ALL))

    def _show_console_thinking(avatar: str) -> int:
        if avatar == "rei":
            label = "🎚️ Rei Composing..."
            color = Fore.MAGENTA
        else:
            label = "🤔 Sam Thinking..."
            color = Fore.CYAN
        print(str(color) + label + str(Style.RESET_ALL), end="", flush=True)
        return len(label)

    def _clear_console_status(width: int = 24) -> None:
        print("\r" + " " * width + "\r", end="", flush=True)

    # Load persona graph for deterministic grounding and persona chat context
    from services.avatar_intelligence import (
        load_avatar_state as _lav_console,
        normalize_evidence_facts,
        normalize_domain_facts,
        normalize_extracted_facts,
        evidence_facts_to_project_facts,
        domain_facts_to_project_facts,
        build_grounding_context,
    )
    
    from services.console_grounding._models import ProjectFact as _ProjectFact
    from services.knowledge_graph import KnowledgeGraphManager
    from services.hybrid_retriever import HybridRetriever

    # Initialize Knowledge Graph Manager
    _kg: KnowledgeGraphManager | None = None
    _hybrid_retriever: HybridRetriever | None = None

    def _load_knowledge_state() -> tuple[list, str, list, list, list]:
        """Load (or reload) avatar knowledge state.
        
        Returns: (_profile_facts, _grounding_context, _raw_evidence_facts, _raw_domain_facts, _raw_extracted_facts)
        """
        avatar_state = _lav_console()
        avatar_facts = normalize_evidence_facts(avatar_state)
        
        domain_facts_raw = []
        domain_pf: list = []
        try:
            domain_facts_raw = normalize_domain_facts(avatar_state)
            domain_pf = domain_facts_to_project_facts(domain_facts_raw)
        except Exception as exc:
            logger.warning("Domain knowledge not loaded for console mode: %s", exc)
        
        extracted_raw = []
        extracted_pf: list = []
        try:
            extracted_raw = normalize_extracted_facts(avatar_state)
            extracted_pf = [
                _ProjectFact(
                    project=f.source_title or "Extracted Knowledge",
                    company="",
                    years="",
                    details=f.statement,
                    source=f"extracted_knowledge:{f.evidence_id}",
                    tags=set(f.tags or []),
                )
                for f in extracted_raw
            ]
        except Exception as exc:
            logger.warning("Extracted knowledge not loaded for console mode: %s", exc)
        
        profile_facts = evidence_facts_to_project_facts(avatar_facts) + domain_pf + extracted_pf
        grounding_ctx = build_grounding_context(avatar_facts)
        if github_context:
            grounding_ctx = f"{grounding_ctx}\n\n{github_context}" if grounding_ctx else github_context
        return profile_facts, grounding_ctx, list(avatar_facts), domain_facts_raw, extracted_raw

    _profile_facts, _grounding_context, _raw_evidence_facts, _raw_domain_facts, _raw_extracted_facts = _load_knowledge_state()
    logger.debug(
        "Console mode: loaded %d grounding facts (%d total)",
        len(_profile_facts),
        len(_profile_facts),
    )

    # Bootstrap Knowledge Graph from avatar state
    try:
        _kg = KnowledgeGraphManager()
        _kg.bootstrap_from_avatar_state(_lav_console())
        _hybrid_retriever = HybridRetriever(kg=_kg)
        logger.debug(
            "Knowledge Graph initialized: %d nodes, %d edges",
            _kg.node_count,
            _kg.edge_count,
        )
    except Exception as kg_err:
        logger.warning("Knowledge Graph initialization failed: %s — using fallback retrieval", kg_err)
        _kg = None
        _hybrid_retriever = None

    _console_cleanup_done = False
    _original_excepthook = sys.excepthook

    def _run_console_exit_cleanup() -> None:
        """Best-effort memory cleanup for console shutdown."""
        nonlocal _console_cleanup_done
        if _console_cleanup_done:
            return
        _console_cleanup_done = True

        logger.info("🧹 Running console shutdown cleanup...")

        # Drop large in-memory console state before forcing collection.
        history.clear()
        _profile_facts.clear()
        _raw_evidence_facts.clear()
        _raw_domain_facts.clear()
        _raw_extracted_facts.clear()

        # Restore the process-level exception hook after console shutdown.
        try:
            sys.excepthook = _original_excepthook
        except Exception as exc:  # noqa: BLE001
            logger.debug("Console excepthook restore skipped: %s", exc)

        # Reuse the existing post-run cleanup for Ollama/FLUX/Python heap trim.
        _run_post_generation_cleanup(ai, source_mode="console")

    def _console_excepthook(exc_type, exc_value, exc_traceback) -> None:
        """Ensure cleanup runs if console mode terminates on an unhandled exception."""
        try:
            logger.error("Unhandled exception in console mode", exc_info=(exc_type, exc_value, exc_traceback))
            _run_console_exit_cleanup()
        finally:
            _original_excepthook(exc_type, exc_value, exc_traceback)

    # Protect console-mode exits not covered by explicit /exit or EOF handlers.
    sys.excepthook = _console_excepthook

    from services.console_grounding import truth_gate_result as _tg_result

    def _print_truth_score(reply: str) -> None:
        """Print a minimal 1-line DoT + fact-sim bar after a generated reply.

        spaCy article sim is intentionally excluded — it requires a source article
        text and is always empty when article_text="" (console mode has no article).
        Fact-pool sim (best match across persona/domain facts) works in all contexts.
        
        Only runs when verify=True.
        """
        if not verify:
            return
        try:
            _, _meta = _tg_result(reply, "", _profile_facts)
            dot = _meta.truth_gradient

            if dot >= 0.75:
                _dot_col = str(Fore.GREEN)
                _dot_sym = "●"
            elif dot >= 0.45:
                _dot_col = str(Fore.YELLOW)
                _dot_sym = "◑"
            else:
                _dot_col = str(Fore.RED)
                _dot_sym = "○"

            _fsim_vals = list(_meta.fact_sim_scores.values())
            _fsim = max(_fsim_vals) if _fsim_vals else None

            def _bar(score: float, width: int = 20) -> str:
                filled = round(score * width)
                return "█" * filled + "░" * (width - filled)

            _dot_bar = _bar(dot)
            _line = (
                str(Style.DIM) + "  "
                + _dot_col + _dot_sym + str(Style.RESET_ALL)
                + str(Style.DIM) + f" DoT {dot:.2f}  " + str(Style.RESET_ALL)
                + _dot_col + _dot_bar + str(Style.RESET_ALL)
            )
            if _fsim is not None:
                if _fsim >= 0.75:
                    _fsim_col = str(Fore.GREEN)
                elif _fsim >= 0.45:
                    _fsim_col = str(Fore.YELLOW)
                else:
                    _fsim_col = str(Fore.RED)
                _fsim_bar = _bar(_fsim)
                _line += (
                    str(Style.DIM) + f"   fact sim {_fsim:.2f}  " + str(Style.RESET_ALL)
                    + _fsim_col + _fsim_bar + str(Style.RESET_ALL)
                )
            print(_line)
        except Exception:
            pass  # never interrupt the conversation for a scoring failure

    def print_graph_statistics(summary, domain_profiles=None):
        """Print graph and domain-knowledge diagnostics with aligned tables."""
        width = 76
        print("\n" + "=" * width)
        print(f"{Fore.CYAN}{Style.BRIGHT}{'GRAPH STRUCTURE ANALYSIS':^{width}}")
        print("=" * width)

        # --- 1. Core Metrics ---
        print(f"\n{Fore.YELLOW}{'--- CORE METRICS ---':^{width}}")
        print(f"{'Metric':<24} {'Count':>10}    {'Metric':<24} {'Count':>10}")
        print("-" * width)
        print(f"{'Nodes':<24} {int(summary.get('nodes', 0)):>10}    {'Edges':<24} {int(summary.get('edges', 0)):>10}")

        # --- 2. Component Breakdown ---
        print(f"\n{Fore.YELLOW}{'--- COMPONENT BREAKDOWN ---':^{width}}")
        node_types = summary.get("node_types", {})
        if node_types:
            print(f"{'Node Type':<32} {'Count':>10}")
            print("-" * 44)
            for node_type, count in sorted(node_types.items(), key=lambda item: item[1], reverse=True):
                print(f"  {str(node_type):<30} {int(count):>10}")
        else:
            print("No specific node type breakdown available.")

        # --- 3. Domain Knowledge Profiles (Sam + Rei) ---
        print(f"\n{Fore.YELLOW}{'--- DOMAIN KNOWLEDGE PROFILES ---':^{width}}")

        sam = (domain_profiles or {}).get("sam", {}) if domain_profiles else {}
        sam_totals = sam.get("totals", {}) if isinstance(sam, dict) else {}
        sam_files_loaded = int(sam.get("files_loaded", 0)) if isinstance(sam, dict) else 0
        print(f"{Fore.GREEN}Sam Domain Knowledge{Style.RESET_ALL} (files={sam_files_loaded})")
        print(
            f"  domains={int(sam_totals.get('domains', 0))}  "
            f"facts={int(sam_totals.get('facts', 0))}  "
            f"relationships={int(sam_totals.get('relationships', 0))}"
        )
        sam_files = sam.get("files", []) if isinstance(sam, dict) else []
        if sam_files:
            file_col = 44
            print(f"{'  file':<{file_col}} {'domains':>8} {'facts':>8} {'rels':>8}")
            print("  " + "-" * (file_col + 28))
            for row in sam_files:
                file_name = str(row.get("file", "unknown"))
                if len(file_name) > file_col - 2:
                    file_name = file_name[: file_col - 5] + "..."
                print(
                    f"  {file_name:<{file_col - 2}} "
                    f"{int(row.get('domains', 0)):>8} "
                    f"{int(row.get('facts', 0)):>8} "
                    f"{int(row.get('relationships', 0)):>8}"
                )
        sam_errors = sam.get("errors", []) if isinstance(sam, dict) else []
        if sam_errors:
            print(f"  {Fore.YELLOW}notes:{Style.RESET_ALL} {len(sam_errors)} Sam domain file(s) were skipped due to load errors")

        rei = (domain_profiles or {}).get("rei", {}) if domain_profiles else {}
        rei_file = str(rei.get("file", "rei_toei_domain_knowledge.json"))
        print(f"\n{Fore.MAGENTA}Rei Domain Knowledge{Style.RESET_ALL} (file={rei_file})")
        if rei.get("exists"):
            shape = rei.get("shape", {})
            print(
                f"  sections={int(rei.get('section_count', 0))}  "
                f"dict_keys={int(shape.get('dict_keys', 0))}  "
                f"list_items={int(shape.get('list_items', 0))}"
            )
            top_sections = rei.get("sections", [])[:5]
            if top_sections:
                section_col = 44
                print(f"{'  top section':<{section_col}} {'type':>10} {'size':>8}")
                print("  " + "-" * (section_col + 22))
                for section in top_sections:
                    section_name = str(section.get("name", "unknown"))
                    if len(section_name) > section_col - 2:
                        section_name = section_name[: section_col - 5] + "..."
                    print(
                        f"  {section_name:<{section_col - 2}} "
                        f"{str(section.get('type', 'n/a')):>10} "
                        f"{int(section.get('size', 0)):>8}"
                    )
        else:
            print(f"  {Fore.YELLOW}Rei domain knowledge file not available or invalid JSON.{Style.RESET_ALL}")

        print("\n" + "=" * width)
        print(f"{Fore.CYAN}{Style.BRIGHT}{'ANALYSIS COMPLETE':^{width}}")
        print("=" * width)

    while True:
        try:
            user_input = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting console.")
            _run_console_exit_cleanup()
            return

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in {"/exit", "/quit"}:
            print("Exiting console.")
            _run_console_exit_cleanup()
            return
        if cmd == "/help":
            _hr = "─" * 63
            print(str(Fore.CYAN) + _hr + str(Style.RESET_ALL))
            print(str(Fore.WHITE) + str(Style.BRIGHT) + "Commands" + str(Style.RESET_ALL))
            print(str(Fore.CYAN) + _hr + str(Style.RESET_ALL))
            print(str(Fore.YELLOW) + "Session" + str(Style.RESET_ALL))
            print("  /help            show this help")
            print("  /reset           clear conversation history")
            print("  /reload          re-read persona graph, domain packs, extracted knowledge")
            print("  /exit  /quit     leave console")
            print()
            print(str(Fore.YELLOW) + "Reports & Diagnostics" + str(Style.RESET_ALL))
            print("  /verify          toggle DoT + similarity verification on/off")
            print("  /avatar-explain  toggle avatar-explain report on/off")
            print("  /dot-report      toggle DoT report on/off")
            print("  /graph-stats     show knowledge graph statistics")
            print("  /katzilla <q>    deterministic external evidence citations")
            print()
            print(str(Fore.YELLOW) + "Identity" + str(Style.RESET_ALL))
            print("  /rei  /rei-toei  switch to Rei Toei music avatar (sticky until /sam)")
            print("  /sam             switch back to Sam")
            print()
            print(str(Fore.YELLOW) + "Creative" + str(Style.RESET_ALL))
            print("  /art [topic]     FLUX render from the most recent AI reply")
            print("                   optional topic hint narrows visual direction")
            print(str(Fore.CYAN) + _hr + str(Style.RESET_ALL))
            continue
        if cmd == "/reset":
            history.clear()
            print("Conversation history cleared.")
            continue
        if cmd.startswith("/sam"):
            active_console_avatar = "sam"
            sam_input = user_input[len("/sam"):].strip()
            if not sam_input:
                print(str(Fore.GREEN) + "Sam> Back on the main console voice." + str(Style.RESET_ALL))
                continue
            user_input = sam_input
            cmd = user_input.lower()
        if cmd == "/reload":
            _profile_facts, _grounding_context, _raw_evidence_facts, _raw_domain_facts, _raw_extracted_facts = _load_knowledge_state()
            print(
                str(Fore.CYAN)
                + f"Knowledge reloaded — {len(_profile_facts)} grounding facts now active."
                + str(Style.RESET_ALL)
            )
            continue
        if cmd == "/verify":
            verify = not verify
            _status = str(Fore.GREEN) + "ON" + str(Style.RESET_ALL) if verify else str(Fore.RED) + "OFF" + str(Style.RESET_ALL)
            print(f"Verify mode: {_status}")
            _print_status()
            continue
        if cmd == "/avatar-explain":
            avatar_explain = not avatar_explain
            _status = str(Fore.GREEN) + "ON" + str(Style.RESET_ALL) if avatar_explain else str(Fore.RED) + "OFF" + str(Style.RESET_ALL)
            print(f"Avatar-explain mode: {_status}")
            _print_status()
            continue
        if cmd == "/dot-report":
            dot_report = not dot_report
            _status = str(Fore.GREEN) + "ON" + str(Style.RESET_ALL) if dot_report else str(Fore.RED) + "OFF" + str(Style.RESET_ALL)
            print(f"DoT report mode: {_status}")
            _print_status()
            continue
        if cmd == "/graph-stats":
            if _kg is None:
                print(str(Fore.RED) + "Knowledge Graph is not available." + str(Style.RESET_ALL))
            else:
                summary = _kg.summary()
                domain_profiles = collect_domain_knowledge_profiles(Path("data/avatar"))
                print(f"  Persona ID: {summary['persona_id']}")
                print_graph_statistics(summary, domain_profiles)
            continue
        
        # Rei Toei routing: explicit /rei command or sticky Rei mode turns
        from services.console_grounding._rei_console import (
            REI_DEFAULT_PROMPT,
            extract_rei_input,
            handle_rei_console,
            is_rei_command,
            should_handle_rei_turn,
        )

        if should_handle_rei_turn(user_input, active_console_avatar):
            import asyncio

            active_console_avatar = "rei"
            rei_input = extract_rei_input(user_input) if is_rei_command(user_input) else user_input.strip()

            if not rei_input:
                rei_input = REI_DEFAULT_PROMPT
            
            try:
                _status_width = _show_console_thinking("rei")
                reply, history = asyncio.run(handle_rei_console(rei_input, ai, history, max_tokens=600))
                _clear_console_status(_status_width + 2)
                _print_console_reply("rei", reply)
                speak_text(reply)
            except Exception as rei_err:
                logger.error(f"Rei console error: {rei_err}")
                _clear_console_status(32)
                print(str(Fore.RED) + f"⚠️ Rei error: {rei_err}" + str(Style.RESET_ALL))
            continue

        if cmd.startswith("/art"):
            _art_topic_hint = user_input[len("/art"):].strip() or None
            _art_src = next(
                (m["content"] for m in reversed(history) if m["role"] == "assistant"),
                None,
            )
            if not _art_src:
                print(str(Fore.YELLOW) + "⚠️  No previous reply to render art from. Generate a response first." + str(Style.RESET_ALL))
            else:
                print(str(Fore.CYAN) + "🎨 Requesting art avatar..." + str(Style.RESET_ALL))
                _art_result = _render_console_art_avatar(ai, _art_src, _art_topic_hint)
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
            continue

        if cmd.startswith("/katzilla"):
            query = user_input[len("/katzilla"):].strip()
            if not query:
                print(str(Fore.YELLOW) + "Usage: /katzilla <query>" + str(Style.RESET_ALL))
                continue
            try:
                from services.avatar_intelligence._retrieval import _retrieve_external_evidence

                external = _retrieve_external_evidence(query=query, category_filter=None, limit=5)
                from services.avatar_intelligence import ExternalEvidenceFact as _ExtFact
                reply = build_katzilla_citation_reply(query, [e for e in external if isinstance(e, _ExtFact)])
                history.append({"role": "user", "content": user_input})
                history.append({"role": "assistant", "content": reply})
                if len(history) > max_turns * 2:
                    history = history[-max_turns * 2 :]
                _print_console_reply("sam", reply)
            except Exception as exc:
                print(str(Fore.RED) + f"⚠️ Katzilla request failed: {exc}" + str(Style.RESET_ALL))
            continue

        # Parse query to determine routing mode
        constraints = parse_query_constraints(user_input)
        
        # Route 1: Explicit file name requests → Deterministic citation (raw facts)
        if constraints.explicit_artifact_request:
            if constraints.list_domain_characters or constraints.list_domain_terms:
                facts = [
                    f
                    for f in _profile_facts
                    if f.source.startswith("domain:") or f.company == "Domain Knowledge"
                ]
            else:
                facts = retrieve_relevant_facts(_profile_facts, constraints, query=user_input, limit=8)
            reply = build_deterministic_grounded_reply(user_input, facts, constraints)
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": reply})
            if len(history) > max_turns * 2:
                history = history[-max_turns * 2 :]
            _print_console_reply("sam", reply)
            speak_text(reply)
            continue

        # Route 2: "From your learned knowledge" → Use latest 8 extracted knowledge as context
        # If user asks to search, use keyword-based search instead of latest 8
        if constraints.use_learned_knowledge:
            if constraints.search_learned_knowledge:
                from services.console_grounding._retrieval import search_learned_knowledge
                learned_facts = search_learned_knowledge(user_input, _profile_facts, limit=8)
            else:
                learned_facts = get_latest_extracted_knowledge(_profile_facts, limit=8)
            # Filter the raw lists based on the 'learned_facts' we actually retrieved
            used_extracted = [f for f in _raw_extracted_facts if any(lf.source.endswith(f.evidence_id) for lf in learned_facts)]
            learned_context = build_learned_knowledge_context(learned_facts)
            history.append({"role": "user", "content": user_input})
            if len(history) > max_turns * 2:
                history = history[-max_turns * 2 :]
            try:
                # Use learned knowledge as PRIMARY context (put it first and emphasize it)
                # The learned knowledge should be the focus, with persona context as background
                enhanced_context = f"{learned_context}\n\n{_grounding_context}" if _grounding_context else learned_context
                _status_width = _show_console_thinking("sam")
                reply = ai.chat_as_persona(history, grounding_context=enhanced_context, max_tokens=600)
                _clear_console_status(_status_width + 2)
            except Exception as e:
                _clear_console_status(24)
                _print_console_error("sam", str(e))
                continue
            history.append({"role": "assistant", "content": reply})
            _print_console_reply("sam", reply)
            speak_text(reply)
            
            if verify:
                print(str(Fore.CYAN) + "📊 Verifying..." + str(Style.RESET_ALL), end="", flush=True)
                _print_truth_score(reply)
                print("\r" + " " * 20 + "\r", end="", flush=True)  # Clear the "Verifying..." line
            
            
            from services.shared import print_validation_reports

            print_validation_reports(
                post_text=reply,
                context_text=user_input,
                grounding_facts=_profile_facts,
                raw_evidence=[],
                raw_domain=[],
                raw_extracted=used_extracted,
                raw_external=[],
                facts_used_for_dot=learned_facts,
                verify=verify,
                avatar_explain=avatar_explain,
                dot_report=dot_report
            )

            continue

        # Route 3: Everything else → LLM with artifact context (default)
        # This includes: domain/project/tech queries, generative requests, general chat
        # Always retrieve relevant facts and use as context
        if _hybrid_retriever is not None:
            # Use hybrid retriever (BM25 + graph proximity + claim support)
            # Combine all raw facts (evidence + domain + extracted) for hybrid scoring
            _all_candidates = list(_raw_evidence_facts) + _raw_domain_facts + _raw_extracted_facts
            facts_ranked = _hybrid_retriever.find_facts(user_input, _all_candidates, limit=8)
            # Convert results back to ProjectFact for compatibility with build_grounding_facts_block
            from services.avatar_intelligence import EvidenceFact, DomainEvidenceFact, ExtractedEvidenceFact
            facts = []
            for f in facts_ranked:
                if isinstance(f, EvidenceFact):
                    # Find matching ProjectFact from _profile_facts
                    matching = [
                        pf
                        for pf in _profile_facts
                        if pf.source.startswith("avatar:")
                        and (f.source_project_id and pf.source.endswith(f.source_project_id))
                    ]
                    facts.extend(matching[:1])  # Add first match
                elif isinstance(f, DomainEvidenceFact):
                    matching = [
                        pf
                        for pf in _profile_facts
                        if pf.source.startswith("domain:")
                        and (
                            (f.source_fact_id and pf.source.endswith(f.source_fact_id))
                            or f.evidence_id in pf.source
                        )
                    ]
                    facts.extend(matching[:1])
                elif isinstance(f, ExtractedEvidenceFact):
                    matching = [
                        pf
                        for pf in _profile_facts
                        if pf.source.startswith("extracted_knowledge:")
                        and (
                            (f.evidence_id and pf.source.endswith(f.evidence_id))
                            or (f.source_fact_id and f.source_fact_id in pf.source)
                        )
                    ]
                    facts.extend(matching[:1])
            # Categorize only the top facts for the validation report
            # This ensures build_explain_output only sees what was actually used
            used_ev = [f for f in facts_ranked[:8] if isinstance(f, EvidenceFact)]
            used_dom = [f for f in facts_ranked[:8] if isinstance(f, DomainEvidenceFact)]
            used_ext = [f for f in facts_ranked[:8] if isinstance(f, ExtractedEvidenceFact)]
            used_external = []
            # Ensure we have at least some facts even if conversion failed
            if not facts:
                facts = retrieve_relevant_facts(_profile_facts, constraints, query=user_input, limit=8)
        else:
            # Fallback to simple retrieval when graph not available
            facts = retrieve_relevant_facts(_profile_facts, constraints, query=user_input, limit=8)
            used_ev, used_dom, used_ext, used_external = [], [], [], []

        external_context = ""
        try:
            from services.avatar_intelligence import retrieve_evidence, ExternalEvidenceFact, build_external_grounding_context

            external_candidates = retrieve_evidence(
                user_input,
                list(_raw_evidence_facts) + list(_raw_domain_facts),
                limit=2,
            )
            used_external = [f for f in external_candidates if isinstance(f, ExternalEvidenceFact)]
            external_context = build_external_grounding_context(used_external)
        except Exception:
            used_external = []

        facts_context = build_grounding_facts_block(facts, limit=8)
        history.append({"role": "user", "content": user_input})
        if len(history) > max_turns * 2:
            history = history[-max_turns * 2 :]
        try:
            # Use retrieved facts as additional context
            enhanced_context = f"{_grounding_context}\n\n{facts_context}" if _grounding_context else facts_context
            if external_context:
                enhanced_context = f"{enhanced_context}\n\n{external_context}".strip()
            _status_width = _show_console_thinking("sam")
            reply = ai.chat_as_persona(history, grounding_context=enhanced_context, max_tokens=600)
            _clear_console_status(_status_width + 2)
        except Exception as e:
            _clear_console_status(24)
            _print_console_error("sam", str(e))
            continue
        history.append({"role": "assistant", "content": reply})
        _print_console_reply("sam", reply)
        speak_text(reply)
        
        if verify:
            print(str(Fore.CYAN) + "📊 Verifying..." + str(Style.RESET_ALL), end="", flush=True)
            _print_truth_score(reply)
            print("\r" + " " * 20 + "\r", end="", flush=True)  # Clear the "Verifying..." line

        from services.shared import print_validation_reports
        print_validation_reports(
            post_text=reply,
            context_text=user_input,
            grounding_facts=_profile_facts,
            raw_evidence=used_ev,
            raw_domain=used_dom,
            raw_extracted=used_ext,
            raw_external=used_external,
            facts_used_for_dot=facts,
            verify=verify,
            avatar_explain=avatar_explain,
            dot_report=dot_report
        )

def main():
    parser = argparse.ArgumentParser(description="LinkedIn SSI Booster via Buffer API")
    parser.add_argument("--schedule",  action="store_true", help="Generate and schedule posts to Buffer (use with --dry-run to preview only)")
    parser.add_argument("--curate",    action="store_true", help="Curate AI news and create ideas in Buffer")
    parser.add_argument("--console",   action="store_true", help="Open interactive persona chat mode (no Buffer calls)")
    parser.add_argument("--verify",    action="store_true", help="Enable DoT report scanning and spaCy similarity checks in console mode (requires --console)")
    parser.add_argument("--report",    action="store_true", help="Print SSI component report")
    parser.add_argument("--save-ssi",  nargs=4, metavar=("BRAND", "FIND", "ENGAGE", "BUILD"),
                        type=float, help="Record today's SSI scores: --save-ssi 10.49 9.69 11.0 12.15")
    parser.add_argument("--bsky-stats", action="store_true", help="Fetch and display live Bluesky profile stats")
    parser.add_argument("--week",      type=int, default=1, help="Week number from content calendar (1-4)")
    parser.add_argument("--dry-run",   action="store_true", help="Preview posts without pushing to Buffer")
    _VALID_CHANNELS = {"linkedin", "x", "bluesky", "threads", "youtube", "facebook", "all"}

    def _parse_channels(value: str) -> list[str]:
        parts = [v.strip() for v in value.split(",") if v.strip()]
        invalid = [p for p in parts if p not in _VALID_CHANNELS]
        if invalid:
            parser.error(f"invalid --channel value(s): {', '.join(invalid)}. Choose from: {', '.join(sorted(_VALID_CHANNELS))}")
        if "all" in parts:
            # Expand "all" to individual channels for generation loop
            return ["linkedin", "x", "bluesky", "threads", "youtube", "facebook"]
        return parts

    parser.add_argument("--channel",   type=_parse_channels, default=["linkedin"],
                        help="Target channel(s) as comma-separated list: linkedin,x,bluesky,threads,youtube,all (default: linkedin)")
    parser.add_argument("--type",      choices=["idea", "post"], default="idea",
                        help="idea: add to Buffer Ideas board; post: schedule directly to next available queue slot (default: idea)")
    parser.add_argument("--debug",     action="store_true", help="Enable DEBUG-level logging (shows raw API payloads and responses)")
    parser.add_argument("--interactive", action="store_true", help="Pause for user confirmation on each truth gate removal")
    parser.add_argument("--avatar-explain", action="store_true", help="Print evidence IDs and grounding summary after each generation")
    parser.add_argument("--avatar-learn-report", action="store_true", help="Print learning report from captured moderation events and exit")
    parser.add_argument("--confidence-policy", choices=["strict", "balanced", "draft-first"], default=None,
                        help="Confidence policy for curate path: strict|balanced|draft-first (default: AVATAR_CONFIDENCE_POLICY env var, else balanced)")
    parser.add_argument("--dot-report", action="store_true",
                        help="Display Derivative of Truth (truth gradient, uncertainty, evidence breakdown) for each generated post")
    parser.add_argument("--learn", action="store_true",
                        help="Extract and persist knowledge from curated articles into extracted_knowledge.json (skipped on --dry-run unless this flag is also set)")
    parser.add_argument("--reconcile", action="store_true",
                        help="Fetch published Buffer posts and reconcile with generated candidates to build acceptance priors")
    parser.add_argument("--classify", action="store_true",
                        help="Batch-classify articles via Model2Vec before curation (requires: pip install model2vec)")
    parser.add_argument("--add-category", nargs=3, metavar=("NAME", "DESCRIPTION", "SSI_COMPONENT"),
                        help="Add a custom category: --add-category 'AI Research' 'Machine learning papers and studies' establish_brand")
    parser.add_argument("--list-categories", action="store_true",
                        help="List all available Model2Vec categories with descriptions and SSI component mapping")
    parser.add_argument("--remove-category", nargs="+", metavar="NAME",
                        help="Remove custom categories by name: --remove-category 'AI Research' 'Government Tech'")
    
    # Rei Toei Music Generation
    rei_group = parser.add_argument_group("Rei Toei Music Generation")
    rei_group.add_argument("--rei-generate", action="store_true",
                           help="Generate Suno song from recent knowledge")
    rei_group.add_argument("--rei-generate-strudel", action="store_true",
                           help="Generate Strudel pattern instead of Suno")
    rei_group.add_argument("--rei-theme", type=str,
                           help="Generate music for specific theme")
    rei_group.add_argument("--rei-explain", action="store_true",
                           help="Show reasoning for generation choices")
    rei_group.add_argument("--rei-preview", action="store_true",
                           help="Preview without saving/executing")
    rei_group.add_argument("--rei-execute", action="store_true",
                           help="Execute Strudel pattern (requires --rei-generate-strudel)")
    
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("httpx").setLevel(logging.WARNING)  # suppress noisy HTTP client logs

    if args.console:
        incompatible = []
        if args.schedule:
            incompatible.append("--schedule")
        if args.curate:
            incompatible.append("--curate")
        if args.report:
            incompatible.append("--report")
        if args.save_ssi:
            incompatible.append("--save-ssi")
        if args.bsky_stats:
            incompatible.append("--bsky-stats")
        if args.reconcile:
            incompatible.append("--reconcile")
        if incompatible:
            print(
                str(Fore.YELLOW)
                + f"\n⚠️  --console cannot be combined with: {', '.join(incompatible)}"
                + str(Style.RESET_ALL)
            )
            return
    def build_buffer_service() -> BufferService:
        buffer_api_key = os.getenv("BUFFER_API_KEY")
        if not buffer_api_key:
            raise ValueError("BUFFER_API_KEY environment variable is required")
        return BufferService(api_key=buffer_api_key)

    if args.avatar_learn_report:
        from services.avatar_intelligence import build_learning_report, format_learning_report
        report = build_learning_report()
        print(format_learning_report(report))
        return

    from services.ssi_tracker import SSITracker
    tracker = SSITracker()

    if args.report:
        tracker.print_report()
        return

    if args.reconcile:
        from services.selection_learning import reconcile_published
        buffer = build_buffer_service()
        channel_ids: dict[str, str | None] = {"linkedin": buffer.get_linkedin_channel_id()}
        x_id = os.getenv("BUFFER_X_CHANNEL_ID")
        bsky_id = os.getenv("BUFFER_BLUESKY_CHANNEL_ID")
        threads_id = os.getenv("BUFFER_THREADS_CHANNEL_ID")
        facebook_id = os.getenv("BUFFER_FACEBOOK_CHANNEL_ID")
        if x_id:
            channel_ids["x"] = x_id
        if bsky_id:
            channel_ids["bluesky"] = bsky_id
        if threads_id:
            channel_ids["threads"] = threads_id
        if facebook_id:
            channel_ids["facebook"] = facebook_id
        stats = reconcile_published(buffer, {k: v for k, v in channel_ids.items() if v is not None})
        print(str(Fore.GREEN) + "\n✅  Reconcile complete" + str(Style.RESET_ALL))
        for k, v in stats.items():
            print(f"   {k}: {v}")

    if args.save_ssi:
        brand, find, engage, build = args.save_ssi
        tracker.save_scores(establish=brand, find=find, engage=engage, build=build)
        total = brand + find + engage + build
        print(str(Fore.GREEN) + f"✅  Saved SSI scores: brand={brand} find={find} engage={engage} build={build} total={total:.2f}" + str(Style.RESET_ALL))
        return

    if args.bsky_stats:
        from services.ssi_tracker import fetch_bluesky_stats
        stats = fetch_bluesky_stats()
        if stats:
            print(str(Fore.CYAN) + str(Style.BRIGHT) + f"\n📊 Bluesky stats for @{stats['handle']}" + str(Style.RESET_ALL))
            print(f"  👥 Followers    : {str(Fore.WHITE)}{stats['followers']}{str(Style.RESET_ALL)}")
            print(f"  ➡️  Following    : {stats['following']}")
            print(f"  📝 Total posts  : {stats['posts']}")
            print(str(Fore.CYAN) + f"\n  Last {stats['analysed']} posts (engagement)" + str(Style.RESET_ALL))
            print(f"  ❤️  Likes        : {stats['total_likes']}")
            print(f"  💬 Replies      : {stats['total_replies']}")
            print(f"  🔁 Reposts      : {stats['total_reposts']}")
            print(f"  🗨️  Quotes       : {stats['total_quotes']}")
            print(f"  📈 Avg / post   : {stats['avg_engagement']}")
            if stats.get("top_post"):
                tp = stats["top_post"]
                print(str(Fore.YELLOW) + f"\n  🏆 Top post ({tp['likes']}L {tp['replies']}R {tp['reposts']}RT)" + str(Style.RESET_ALL))
                print(f"  '{tp['text']}'")
                if tp["url"]:
                    print(f"  {tp['url']}")
        return

    if args.list_categories:
        from services.model2vec_service import get_model2vec_service
        svc = get_model2vec_service()
        if not svc.is_available():
            print(str(Fore.YELLOW) + "\n⚠️  Model2Vec is not available (install with: pip install model2vec numpy)" + str(Style.RESET_ALL))
            return
        categories = svc.list_categories()
        if not categories:
            print(str(Fore.YELLOW) + "\n⚠️  No categories found" + str(Style.RESET_ALL))
            return
        print(str(Fore.CYAN) + str(Style.BRIGHT) + f"\n🏷️  Model2Vec Categories ({len(categories)} total)" + str(Style.RESET_ALL))
        print()
        for name, meta in sorted(categories.items()):
            is_custom = meta.get("custom", "False") == "True"
            ssi = meta.get("ssi_component", "general")
            desc = meta.get("description", "")
            custom_marker = str(Fore.MAGENTA) + " [custom]" + str(Style.RESET_ALL) if is_custom else ""
            print(str(Fore.WHITE) + str(Style.BRIGHT) + f"  {name}" + str(Style.RESET_ALL) + custom_marker)
            print(f"    {desc[:100]}{'...' if len(desc) > 100 else ''}")
            print(str(Fore.YELLOW) + f"    → {ssi}" + str(Style.RESET_ALL))
            print()
        return

    if args.add_category:
        from services.model2vec_service import get_model2vec_service
        svc = get_model2vec_service()
        if not svc.is_available():
            print(str(Fore.YELLOW) + "\n⚠️  Model2Vec is not available (install with: pip install model2vec numpy)" + str(Style.RESET_ALL))
            return
        name, description, ssi_component = args.add_category
        valid_ssi = {"establish_brand", "find_right_people", "engage_with_insights", "build_relationships"}
        if ssi_component not in valid_ssi:
            print(str(Fore.RED) + f"\n❌  Invalid SSI component: {ssi_component}" + str(Style.RESET_ALL))
            print(f"    Valid options: {', '.join(sorted(valid_ssi))}")
            return
        success = svc.add_category(name, description, ssi_component)
        if success:
            print(str(Fore.GREEN) + f"\n✅  Added custom category: '{name}'" + str(Style.RESET_ALL))
            print(f"    Description: {description[:80]}{'...' if len(description) > 80 else ''}")
            print(str(Fore.YELLOW) + f"    SSI Component: {ssi_component}" + str(Style.RESET_ALL))
        else:
            print(str(Fore.RED) + f"\n❌  Failed to add category '{name}' (may already exist)" + str(Style.RESET_ALL))
        return

    if args.remove_category:
        from services.model2vec_service import get_model2vec_service
        svc = get_model2vec_service()
        if not svc.is_available():
            print(str(Fore.YELLOW) + "\n⚠️  Model2Vec is not available (install with: pip install model2vec numpy)" + str(Style.RESET_ALL))
            return
        names = args.remove_category
        results = svc.remove_categories(names)
        successes = [n for n, r in zip(names, results) if r]
        failures = [n for n, r in zip(names, results) if not r]
        if successes:
            print(str(Fore.GREEN) + f"\n✅  Removed {len(successes)} category(ies):" + str(Style.RESET_ALL))
            for name in successes:
                print(f"    • {name}")
        if failures:
            print(str(Fore.RED) + f"\n❌  Failed to remove {len(failures)} category(ies):" + str(Style.RESET_ALL))
            for name in failures:
                print(f"    • {name} (not found or is a default category)")
        return

    if not (args.schedule or args.curate or args.console or args.rei_generate or args.rei_generate_strudel):
        parser.print_help()
        return

    print_startup_notice()

    _github_context = build_github_profile_context(
        max_chars=int(os.getenv("GITHUB_CONTEXT_MAX_CHARS", "30000"))
    )
    if _github_context:
        logger.info("GitHub context loaded: %d chars", len(_github_context))

    ai = OllamaService(
        model=os.getenv("OLLAMA_MODEL", "llama3.2"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )

    if args.console:
        run_console(ai=ai, github_context=_github_context, verify=args.verify, avatar_explain=args.avatar_explain, dot_report=args.dot_report)
        return

    # Handle Rei Toei CLI commands — Phase 1E full implementation
    if args.rei_generate or args.rei_generate_strudel:
        import asyncio
        import types as _types
        import uuid as _uuid
        from services.rei_toei_service import (
            ReiToeiConfig,
            load_rei_persona,
            load_rei_domain_knowledge,
            load_strudel_patterns,
            extract_themes,
            choose_diverse_theme,
            load_recent_rei_titles,
            generate_song_concept,
            compose_lyrics,
            assemble_suno_prompt,
            submit_to_suno,
            validate_lyrics_with_dot,
            map_concept_to_pattern,
            generate_strudel_code,
            validate_strudel_syntax,
            execute_strudel_pattern,
            save_pattern_to_library,
            Theme,
            StrudelPattern,
        )
        from services.avatar_intelligence import (
            load_avatar_state as _lav_rei,
            normalize_extracted_facts as _nef_rei,
        )

        rei_config = ReiToeiConfig()

        async def _handle_rei_generate() -> None:
            """Suno song generation pipeline."""
            import asyncio
            from services.shared import get_ollama_service_cached
            
            rei_persona = load_rei_persona()
            rei_domain = load_rei_domain_knowledge()
            avatar_state = _lav_rei()
            # Use normalize_extracted_facts (same pattern as curator.py) to get
            # List[ExtractedEvidenceFact] — the normalized runtime representation.
            _extracted_facts = _nef_rei(avatar_state)

            if args.rei_theme:
                theme = Theme(
                    id=f"cli_{args.rei_theme.replace(' ', '_')}",
                    name=args.rei_theme,
                    technical_concepts=[args.rei_theme],
                    evidence_ids=[],
                    frequency=1,
                    recency_score=1.0,
                )
                print(str(Fore.CYAN) + f"\U0001f3b5 Using theme: {args.rei_theme}" + str(Style.RESET_ALL))
            else:
                themes = extract_themes(_extracted_facts, limit=rei_config.theme_pool_size)
                if not themes:
                    print(
                        str(Fore.YELLOW)
                        + "\u26a0\ufe0f  No themes found in extracted knowledge. "
                        + "Run --curate --learn first to populate knowledge."
                        + str(Style.RESET_ALL)
                    )
                    return
                recent_titles = load_recent_rei_titles(
                    get_rei_toei_dir(create=False),
                    limit=rei_config.recent_title_window,
                )
                theme = choose_diverse_theme(
                    themes,
                    recent_theme_names=recent_titles,
                    repeat_penalty=rei_config.theme_repeat_penalty,
                    jitter_ratio=rei_config.theme_jitter_ratio,
                )
                print(str(Fore.CYAN) + f"\U0001f3b5 Selected theme: {theme.name} (frequency={theme.frequency}, recency={theme.recency_score:.2f})" + str(Style.RESET_ALL))

            recent_titles = load_recent_rei_titles(
                get_rei_toei_dir(create=False),
                limit=rei_config.recent_title_window,
            )

            print(str(Fore.CYAN) + "\U0001f3bc Generating song concept..." + str(Style.RESET_ALL))
            # P1 fix: Wrap blocking Ollama calls in asyncio.to_thread() to prevent event loop blocking
            import asyncio
            from services.shared import get_ollama_service_cached
            from services.ollama_service import OllamaService as _OllamaSvc
            ollama_service: _OllamaSvc = get_ollama_service_cached()  # type: ignore[assignment]
            concept = await asyncio.to_thread(
                generate_song_concept,
                theme,
                rei_persona,
                rei_domain,
                None,
                ollama_service,
                recent_titles,
            )

            print(str(Fore.CYAN) + "\u270d\ufe0f  Composing lyrics..." + str(Style.RESET_ALL))
            # P1 fix: Wrap blocking Ollama calls in asyncio.to_thread() to prevent event loop blocking
            lyrics = await asyncio.to_thread(compose_lyrics, concept, rei_persona, rei_domain, None, ollama_service)

            suno_prompt = assemble_suno_prompt(concept, lyrics, rei_domain)

            # Display
            print(str(Fore.MAGENTA) + str(Style.BRIGHT) + "\n\U0001f3b5 REI TOEI \u2014 SUNO SONG" + str(Style.RESET_ALL))
            print(str(Fore.WHITE) + str(Style.BRIGHT) + f"Title: {suno_prompt.title}" + str(Style.RESET_ALL))
            print(str(Fore.CYAN) + f"Tags:  {suno_prompt.suno_prompt}" + str(Style.RESET_ALL))
            print()
            print(str(Fore.WHITE) + "Lyrics:" + str(Style.RESET_ALL))
            print(suno_prompt.lyrics)

            if args.rei_explain:
                print(str(Fore.YELLOW) + "\n\U0001f4ca Generation Reasoning:" + str(Style.RESET_ALL))
                print(f"  Theme       : {theme.name}")
                print(f"  Mood        : {concept.mood}")
                print(f"  BPM         : {concept.bpm}")
                print(f"  Genre tags  : {', '.join(concept.genre_tags)}")
                print(f"  Narrative   : {concept.narrative_arc}")
                if suno_prompt.evidence_ids:
                    print(f"  Evidence IDs: {', '.join(suno_prompt.evidence_ids[:5])}")
                dot = validate_lyrics_with_dot(lyrics, _extracted_facts)
                _dot_col = (
                    str(Fore.GREEN) if dot.overall_truth_score >= 0.7
                    else (str(Fore.YELLOW) if dot.overall_truth_score >= 0.4 else str(Fore.RED))
                )
                print(_dot_col + f"  DoT score   : {dot.overall_truth_score:.2f}" + str(Style.RESET_ALL))
                if dot.flagged_claims:
                    print(
                        str(Fore.YELLOW)
                        + f"  Flagged     : {'; '.join(dot.flagged_claims[:3])}"
                        + str(Style.RESET_ALL)
                    )

            if args.rei_preview:
                print(str(Fore.YELLOW) + "\n\U0001f441\ufe0f  Preview mode \u2014 not saved or submitted." + str(Style.RESET_ALL))
                return

            # Save to file
            output_dir = get_rei_toei_dir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = re.sub(r"[^\w\-]", "_", suno_prompt.title[:60]).strip("_")
            output_path = output_dir / f"rei_{timestamp}_{safe_title}_suno.json"
            with open(output_path, "w", encoding="utf-8") as _f:
                json.dump(
                    {
                        "song_id": suno_prompt.song_id,
                        "title": suno_prompt.title,
                        "suno_prompt": suno_prompt.suno_prompt,
                        "lyrics": suno_prompt.lyrics,
                        "evidence_ids": suno_prompt.evidence_ids,
                        "generated_at": suno_prompt.generated_at,
                    },
                    _f,
                    indent=2,
                )
            print(str(Fore.GREEN) + f"\n\u2705  Saved to: {output_path}" + str(Style.RESET_ALL))

            # Submit to Suno if API key available
            suno_api_key = os.getenv("SUNO_API_KEY")
            if suno_api_key:
                print(str(Fore.CYAN) + "\U0001f680 Submitting to Suno API..." + str(Style.RESET_ALL))
                try:
                    task = await submit_to_suno(
                        suno_prompt,
                        wait_for_completion=True,
                        api_key=suno_api_key,
                        poll_interval_seconds=10,
                        max_wait_seconds=600,
                    )
                    print(str(Fore.GREEN) + f"\u2705  Suno task submitted: {task.id}" + str(Style.RESET_ALL))
                    print(f"   Status: {task.status}")

                    # Persist task result back into the saved JSON artifact
                    try:
                        with open(output_path, "r", encoding="utf-8") as _rf:
                            _saved = json.load(_rf)
                        _saved["suno_task_id"] = task.id
                        _saved["suno_status"] = task.status
                        if task.audio_url:
                            _saved["suno_audio_url"] = task.audio_url
                        if task.video_url:
                            _saved["suno_video_url"] = task.video_url
                        with open(output_path, "w", encoding="utf-8") as _wf:
                            json.dump(_saved, _wf, indent=2)
                        logger.info("Updated saved artifact with Suno task result")
                    except Exception as _upd_err:
                        logger.warning(f"Could not update saved artifact with task result: {_upd_err}")

                    if task.status == "complete":
                        async def _download_media(url: str, dest: "Path", label: str) -> bool:
                            """Download a single media URL to dest; returns True on success."""
                            _aiohttp = importlib.import_module("aiohttp")
                            print(str(Fore.CYAN) + f"   \u2b07\ufe0f  Downloading {label} \u2192 {dest.name} ..." + str(Style.RESET_ALL))
                            try:
                                async with _aiohttp.ClientSession() as _dl_session:
                                    async with _dl_session.get(url) as _dl_resp:
                                        if _dl_resp.status == 200:
                                            dest.write_bytes(await _dl_resp.read())
                                            print(str(Fore.GREEN) + f"   \u2705  {label} saved: {dest}" + str(Style.RESET_ALL))
                                            return True
                                        else:
                                            print(str(Fore.YELLOW) + f"   \u26a0\ufe0f  {label} download failed (HTTP {_dl_resp.status})" + str(Style.RESET_ALL))
                                            print(f"         Download manually: {url}")
                                            return False
                            except Exception as _dl_err:
                                print(str(Fore.YELLOW) + f"   \u26a0\ufe0f  {label} download error: {_dl_err}" + str(Style.RESET_ALL))
                                print(f"         Download manually: {url}")
                                return False

                        # Download MP4 (video — primary target for Instagram)
                        if task.video_url:
                            print(str(Fore.GREEN) + f"   \U0001f3ac Video URL: {task.video_url}" + str(Style.RESET_ALL))
                            await _download_media(task.video_url, output_path.with_suffix(".mp4"), "MP4 video")
                        else:
                            print(str(Fore.YELLOW) + "   \u26a0\ufe0f  No video URL yet (Suno may still be rendering). Check back shortly." + str(Style.RESET_ALL))

                        # Download MP3 (audio — always useful as a standalone track)
                        if task.audio_url:
                            print(str(Fore.GREEN) + f"   \U0001f3b5 Audio URL: {task.audio_url}" + str(Style.RESET_ALL))
                            await _download_media(task.audio_url, output_path.with_suffix(".mp3"), "MP3 audio")
                    elif task.status == "error":
                        print(str(Fore.YELLOW) + f"   \u26a0\ufe0f  Suno generation failed for task {task.id}" + str(Style.RESET_ALL))

                except TimeoutError as _timeout_err:
                    print(str(Fore.YELLOW) + f"\u26a0\ufe0f  {_timeout_err}" + str(Style.RESET_ALL))
                    print("   Poll the status endpoint manually with the task ID above.")
                except Exception as _suno_err:
                    print(str(Fore.YELLOW) + f"\u26a0\ufe0f  Suno submission failed: {_suno_err}" + str(Style.RESET_ALL))
            else:
                print(
                    str(Fore.YELLOW)
                    + "\n\U0001f4a1 Set SUNO_API_KEY in .env to submit directly to Suno API."
                    + str(Style.RESET_ALL)
                )

        async def _handle_rei_generate_strudel() -> None:
            """Strudel pattern generation pipeline."""
            import asyncio
            from services.shared import get_ollama_service_cached
            
            rei_persona = load_rei_persona()
            rei_domain = load_rei_domain_knowledge()
            pattern_library = load_strudel_patterns()
            avatar_state = _lav_rei()
            # Use normalize_extracted_facts (same pattern as curator.py) to get
            # List[ExtractedEvidenceFact] — the normalized runtime representation.
            _extracted_facts = _nef_rei(avatar_state)

            if args.rei_theme:
                theme = Theme(
                    id=f"cli_{args.rei_theme.replace(' ', '_')}",
                    name=args.rei_theme,
                    technical_concepts=[args.rei_theme],
                    evidence_ids=[],
                    frequency=1,
                    recency_score=1.0,
                )
                print(str(Fore.CYAN) + f"\U0001f3b5 Using theme: {args.rei_theme}" + str(Style.RESET_ALL))
            else:
                themes = extract_themes(_extracted_facts, limit=rei_config.theme_pool_size)
                if not themes:
                    print(
                        str(Fore.YELLOW)
                        + "\u26a0\ufe0f  No themes found in extracted knowledge. "
                        + "Run --curate --learn first to populate knowledge."
                        + str(Style.RESET_ALL)
                    )
                    return
                recent_titles = load_recent_rei_titles(
                    get_rei_toei_dir(create=False),
                    limit=rei_config.recent_title_window,
                )
                theme = choose_diverse_theme(
                    themes,
                    recent_theme_names=recent_titles,
                    repeat_penalty=rei_config.theme_repeat_penalty,
                    jitter_ratio=rei_config.theme_jitter_ratio,
                )
                print(str(Fore.CYAN) + f"\U0001f3b5 Selected theme: {theme.name} (frequency={theme.frequency}, recency={theme.recency_score:.2f})" + str(Style.RESET_ALL))

            template = map_concept_to_pattern(theme, pattern_library)
            if template is None:
                # Fallback: use first available template
                if pattern_library.templates:
                    template = pattern_library.templates[0]
                else:
                    print(str(Fore.YELLOW) + "\u26a0\ufe0f  No Strudel pattern templates available." + str(Style.RESET_ALL))
                    return

            print(
                str(Fore.CYAN)
                + f"\U0001f3bc Generating Strudel pattern (template: {template.name})..."
                + str(Style.RESET_ALL)
            )
            # P1 fix: Wrap blocking Ollama calls in asyncio.to_thread() to prevent event loop blocking
            import asyncio
            from services.shared import get_ollama_service_cached
            from services.ollama_service import OllamaService as _OllamaSvc
            ollama_service: _OllamaSvc = get_ollama_service_cached()  # type: ignore[assignment]
            strudel_pattern = await asyncio.to_thread(generate_strudel_code, theme, template, rei_persona, rei_domain, None, ollama_service)
            strudel_code = strudel_pattern.strudel_code
            validation = validate_strudel_syntax(strudel_code)

            # Display
            print(str(Fore.MAGENTA) + str(Style.BRIGHT) + "\n\U0001f3b5 REI TOEI \u2014 STRUDEL PATTERN" + str(Style.RESET_ALL))
            print(str(Fore.WHITE) + str(Style.BRIGHT) + f"Theme   : {theme.name}" + str(Style.RESET_ALL))
            print(str(Fore.CYAN) + f"Template: {template.name}" + str(Style.RESET_ALL))
            print()
            print(str(Fore.WHITE) + "Strudel Code:" + str(Style.RESET_ALL))
            print(str(Fore.GREEN) + strudel_code + str(Style.RESET_ALL))

            if validation.valid:
                print(str(Fore.GREEN) + "\n\u2705  Syntax valid" + str(Style.RESET_ALL))
            else:
                print(
                    str(Fore.YELLOW)
                    + f"\n\u26a0\ufe0f  Syntax warnings: {'; '.join(validation.errors)}"
                    + str(Style.RESET_ALL)
                )

            if args.rei_explain:
                print(str(Fore.YELLOW) + "\n\U0001f4ca Generation Reasoning:" + str(Style.RESET_ALL))
                print(f"  Theme        : {theme.name}")
                print(f"  Template     : {template.name}")
                print(f"  Description  : {template.description}")
                print(f"  Suitable for : {', '.join(template.suitable_for_concepts[:3])}")
                if theme.evidence_ids:
                    print(f"  Evidence IDs : {', '.join(theme.evidence_ids[:5])}")

            if args.rei_preview:
                print(str(Fore.YELLOW) + "\n\U0001f441\ufe0f  Preview mode \u2014 not saved or executed." + str(Style.RESET_ALL))
                return

            # Save pattern to library (strudel_pattern already has all fields set)
            save_pattern_to_library(strudel_pattern)
            print(str(Fore.GREEN) + f"\n\u2705  Pattern saved to library (ID: {strudel_pattern.pattern_id})" + str(Style.RESET_ALL))

            # Execute if requested
            if args.rei_execute:
                print(str(Fore.CYAN) + "\U0001f680 Executing Strudel pattern via MCP agent..." + str(Style.RESET_ALL))
                try:
                    # execute_strudel_pattern takes a StrudelPattern object
                    result = await execute_strudel_pattern(strudel_pattern)
                    if result.success:
                        print(str(Fore.GREEN) + "\u2705  Pattern executing in Strudel!" + str(Style.RESET_ALL))
                        if result.message:
                            print(str(Fore.CYAN) + f"   {result.message}" + str(Style.RESET_ALL))
                    else:
                        print(str(Fore.YELLOW) + f"\u26a0\ufe0f  Execution failed: {result.error}" + str(Style.RESET_ALL))
                except Exception as _exec_err:
                    print(
                        str(Fore.YELLOW)
                        + f"\u26a0\ufe0f  Strudel MCP agent unavailable: {_exec_err}"
                        + str(Style.RESET_ALL)
                    )
                    print("   Start the Strudel service: bash run.sh --profile full up -d")

        try:
            if args.rei_generate:
                asyncio.run(_handle_rei_generate())
            elif args.rei_generate_strudel:
                asyncio.run(_handle_rei_generate_strudel())
        except KeyboardInterrupt:
            print("\nRei Toei generation cancelled.")
        except Exception as _rei_err:
            logger.error("Rei Toei CLI error: %s", _rei_err)
            print(str(Fore.RED) + f"\n\u274c  Rei Toei error: {_rei_err}" + str(Style.RESET_ALL))
        return

    if args.curate:
        try:
            buffer = None if args.dry_run else build_buffer_service()
            from services.shared import AVATAR_CONFIDENCE_POLICY
            from services.content_curator import ContentCurator

            confidence_policy = args.confidence_policy or AVATAR_CONFIDENCE_POLICY
            curator = ContentCurator(ai_service=ai, buffer_service=buffer, confidence_policy=confidence_policy, github_context=_github_context, classify=args.classify)

            try:
                ideas = curator.curate_and_create_ideas(dry_run=args.dry_run, channel=args.channel, message_type=args.type, request_delay=5.0, interactive=args.interactive, avatar_explain=args.avatar_explain, dot_report=args.dot_report, learn=args.learn, classify=args.classify)
            except BufferQueueFullError as e:
                print(str(Fore.YELLOW) + f"\n⚠️  Buffer queue is full — no new posts were scheduled.\n   {e}\n   Free up slots at https://publish.buffer.com before running again." + str(Style.RESET_ALL))
                return
            except BufferRateLimitError as e:
                print(
                    str(Fore.YELLOW)
                    + f"\n⚠️  Buffer API rate limit reached.\n   {e}\n"
                    + "   Wait for the retry window, then run the command again."
                    + str(Style.RESET_ALL)
                )
                return
            except BufferChannelNotConnectedError as e:
                print(
                    str(Fore.YELLOW)
                    + f"\n⚠️  Requested channel is not connected in Buffer.\n   {e}\n"
                    + "   Connect the channel in Buffer or run with a different --channel value."
                    + str(Style.RESET_ALL)
                )
                return
            noun = "posts" if args.type == "post" else "ideas"

            if ideas:
                for _idea_idx, _idea in enumerate(ideas, start=1):
                    if not isinstance(_idea, dict):
                        continue
                    _idea_channel = _idea.get("channel", "linkedin")
                    if _idea.get("dry_run") or _idea_channel in ("youtube", "all"):
                        continue
                    _idea_post_text = str(_idea.get("generated_text") or _idea.get("text") or "").strip()
                    if not _idea_post_text:
                        continue
                    _idea["_flux_optimized_post_text"] = _optimize_flux_story_for_render(
                        ai,
                        _idea_post_text,
                        source_mode=SourceMode.CURATE,
                        channel=str(_idea_channel),
                        title=_idea.get("title", ""),
                        angle=_idea.get("summary", ""),
                        theme=_idea.get("title", ""),
                        knowledge_context=(_idea.get("summary") or _idea.get("article_text") or ""),
                    )
                    if _idea_idx % 3 == 0:
                        gc.collect()

            # Step 6: Render art avatars for curated ideas (non-dry-run, non-youtube, non-all-channel)
            if ideas:
                for _idea_idx, _idea in enumerate(ideas, start=1):
                    if not isinstance(_idea, dict):
                        continue
                    _idea_channel = _idea.get("channel", "linkedin")
                    if _idea.get("dry_run") or _idea_channel in ("youtube", "all"):
                        continue
                    _optimized_story = (_idea.get("_flux_optimized_post_text", "") or "").strip()
                    if _optimized_story:
                        _art_meta = _render_curate_art_avatar(
                            ai,
                            _idea,
                            str(_idea_channel),
                            optimize_story=False,
                        )
                        _idea.pop("_flux_optimized_post_text", None)
                    else:
                        _art_meta = _render_curate_art_avatar(ai, _idea, str(_idea_channel))
                    if _art_meta:
                        _idea.update(_art_meta)
                        _art_status = _art_meta.get("art_avatar_status", "")
                        if _art_status == RenderStatus.RENDERED.value:
                            print(
                                str(Fore.GREEN)
                                + f"🎨  Art avatar rendered → {_art_meta.get('art_avatar_image_path', '')}"
                                + str(Style.RESET_ALL)
                            )
                            _display_art_in_terminal(_art_meta.get("art_avatar_image_path"))
                        elif _art_status in (RenderStatus.DEFERRED.value, RenderStatus.TEXT_ONLY.value):
                            print(
                                str(Fore.YELLOW)
                                + f"⏳  Art avatar deferred: {_art_meta.get('art_avatar_defer_reason', 'GPU busy')}"
                                + str(Style.RESET_ALL)
                            )

                    # Drop heavyweight fields after FLUX/render operations to reduce peak RAM.
                    _idea.pop("article_text", None)
                    _idea.pop("content", None)
                    _idea.pop("raw_content", None)

                    if _idea_idx % 2 == 0:
                        gc.collect()
            return
        finally:
            _run_post_generation_cleanup(ai, "curate")


    if args.schedule:
        try:
            content_calendar = load_content_calendar()
            week_topics = content_calendar.get(f"week_{args.week}", [])
            if not week_topics:
                logger.error("No content found for week %d", args.week)
                return

            # args.channel is already a list from _parse_channels
            for channel in args.channel:
                logger.info("📝 Generating %d posts for week %d (channel: %s)...", len(week_topics), args.week, channel)
                posts = []
                from services.avatar_intelligence import (
                    load_avatar_state as _lav_gen,
                    normalize_evidence_facts,
                    normalize_domain_facts,
                    retrieve_evidence,
                    evidence_facts_to_project_facts,
                    EvidenceFact,
                    DomainEvidenceFact,
                    domain_facts_to_project_facts,
                )
                _gen_avatar_state = _lav_gen()
                if channel == "youtube" and not args.dry_run:
                    get_youtube_scripts_dir()
                if args.avatar_explain:
                    from services.avatar_intelligence import build_explain_output, format_explain_output

                for _topic_idx, topic in enumerate(week_topics, start=1):
                    logger.info("  Generating: %s", topic['title'])
                    grounding_query = f"{topic['title']}. {topic['angle']}. {topic.get('ssi_component', 'establish_brand')}"
                    # Combine both fact types
                    _gen_avatar_facts = normalize_evidence_facts(_gen_avatar_state)
                    _gen_domain_facts = normalize_domain_facts(_gen_avatar_state)
                    all_facts = list(_gen_avatar_facts) + list(_gen_domain_facts)
                    _ev_proj = int(os.getenv("EVIDENCE_PROJECT_COUNT", "3"))
                    _ev_dom = int(os.getenv("EVIDENCE_DOMAIN_COUNT", "2"))
                    relevant = retrieve_evidence(grounding_query, all_facts, limit=_ev_proj + _ev_dom)  # type: ignore[arg-type]

                    # Split by type and convert
                    persona_facts = [f for f in relevant if isinstance(f, EvidenceFact)]
                    domain_facts = [f for f in relevant if isinstance(f, DomainEvidenceFact)]
                    grounding_facts = (
                        evidence_facts_to_project_facts(persona_facts)
                        + domain_facts_to_project_facts(domain_facts)
                    )

                    flux_service = get_flux_service()
                    ollama_job_id = flux_service.notify_ollama_start()
                    try:
                        if channel == "youtube":
                            post = ai.generate_youtube_short_script(
                                title=topic["title"],
                                angle=topic["angle"],
                                ssi_component=topic.get("ssi_component", "establish_brand"),
                                grounding_facts=grounding_facts,
                                interactive=args.interactive,
                            )
                        else:
                            post = ai.generate_linkedin_post(
                                title=topic["title"],
                                angle=topic["angle"],
                                ssi_component=topic.get("ssi_component", "establish_brand"),
                                hashtags=topic.get("hashtags", []),
                                grounding_facts=grounding_facts,
                                channel=channel,
                                interactive=args.interactive,
                            )
                    finally:
                        flux_service.notify_ollama_done(ollama_job_id)

                    if channel == "youtube":
                        safe_title = re.sub(r"[^\w\-]", "_", topic["title"][:60]).strip("_")
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        script_path = get_youtube_scripts_dir() / f"{timestamp}_{safe_title}.txt"
                        script_content = (
                            f"TITLE: {topic['title']}\n"
                            f"SSI COMPONENT: {topic.get('ssi_component', 'establish_brand')}\n\n"
                            f"{post}\n"
                        )
                        if not args.dry_run:
                            script_path.write_text(script_content, encoding="utf-8")
                        print(str(Fore.RED) + str(Style.BRIGHT) + f"🎬 YOUTUBE SHORT SCRIPT (channel: {channel}):" + str(Style.RESET_ALL))
                        print(str(Fore.WHITE) + f"📄 TITLE:  {topic['title']}" + str(Style.RESET_ALL))
                        print(str(Fore.CYAN) + f"🎯 SSI:    {topic.get('ssi_component', 'establish_brand')}" + str(Style.RESET_ALL))
                        print(f"\n{post}\n")
                        print("GitHub: https://buff.ly/tfajNLI")
                        print("Sign up for Buffer with my partner link — join.buffer.com/samjd42  — to start scheduling, publishing, and analyzing your social posts in one place while supporting my work.")
                        if not args.dry_run:
                            print(str(Fore.GREEN) + f"💾 Saved to: {script_path}" + str(Style.RESET_ALL))
                        posts.append({**topic, "generated_text": post})
                    else:
                        # Hashtags are only appended for LinkedIn-style posts.
                        if channel not in ("x", "bluesky", "threads", "youtube"):
                            hashtag_str = " ".join(f"#{h.lstrip('#')}" for h in topic.get("hashtags", []))
                            if hashtag_str and hashtag_str not in post:
                                post = post.rstrip() + f"\n\n{hashtag_str}"
                        post = append_channel_footer(post, channel)
                        optimized_post = _optimize_flux_story_for_render(
                            ai,
                            post,
                            source_mode=SourceMode.SCHEDULE,
                            channel=channel,
                            title=topic.get("title", ""),
                            angle=topic.get("angle", ""),
                            theme=topic.get("title", ""),
                            knowledge_context=topic.get("angle", ""),
                        )
                        posts.append({**topic, "generated_text": post, "_flux_optimized_post_text": optimized_post})

                    if channel != "youtube":
                        print(str(Fore.CYAN) + f"\n{'='*60}" + str(Style.RESET_ALL))
                        print(str(Fore.WHITE) + str(Style.BRIGHT) + f"📝 TOPIC: {topic['title']} (channel: {channel})" + str(Style.RESET_ALL))
                        print(str(Fore.CYAN) + f"🎯 SSI COMPONENT: {topic.get('ssi_component', 'establish_brand')}" + str(Style.RESET_ALL))
                        print(f"\n{post}\n")

                    if args.dot_report:
                        try:
                            from services.derivative_of_truth import (
                                EvidencePath,
                                EVIDENCE_TYPE_SECONDARY,
                                REASONING_TYPE_LOGICAL,
                                score_claim_with_truth_gradient,
                                report_truth_gradient,
                                format_truth_gradient_report,
                            )
                            _dot_paths = [
                                EvidencePath(
                                    source=f.source if hasattr(f, "source") else str(f),
                                    evidence_type=EVIDENCE_TYPE_SECONDARY,
                                    reasoning_type=REASONING_TYPE_LOGICAL,
                                    credibility=0.7,
                                )
                                for f in grounding_facts
                            ]
                            _dot_result = score_claim_with_truth_gradient(post, _dot_paths)
                            _dot_report_dict = report_truth_gradient(post, _dot_result, verbose=True)
                            _dot_colour = str(Fore.RED) if _dot_result.flagged else str(Fore.CYAN)
                            from services.derivative_of_truth._reporting import format_dot_report_header
                            print(format_dot_report_header())
                            print(format_truth_gradient_report(_dot_report_dict))
                            print()
                        except Exception as _dot_err:
                            logger.debug("DoT report unavailable: %s", _dot_err)

                    if args.avatar_explain:
                        # Combine project and domain facts for retrieval
                        from services.avatar_intelligence import EvidenceFact, DomainEvidenceFact, normalize_extracted_facts
                        from services.console_grounding import truth_gate_result as _tgr_exp
                        _all_facts = list(_gen_avatar_facts) + list(_gen_domain_facts)
                        _ev_proj2 = int(os.getenv("EVIDENCE_PROJECT_COUNT", "3"))
                        _ev_dom2 = int(os.getenv("EVIDENCE_DOMAIN_COUNT", "2"))
                        _relevant = retrieve_evidence(grounding_query, _all_facts, limit=_ev_proj2 + _ev_dom2)  # type: ignore[arg-type]
                        
                        # Score and filter extracted facts by relevance (retrieve_evidence doesn't support ExtractedEvidenceFact type)
                        _gen_extracted_facts_all = normalize_extracted_facts(_gen_avatar_state)
                        _ev_extracted = int(os.getenv("EVIDENCE_EXTRACTED_COUNT", "2"))
                        _q_tokens = set(re.findall(r"[a-zA-Z0-9_+#.-]{2,}", grounding_query.lower()))
                        _scored_extracted = []
                        for _fact in _gen_extracted_facts_all:
                            _text = " ".join([
                                getattr(_fact, "statement", ""),
                                getattr(_fact, "source_title", ""),
                                " ".join(getattr(_fact, "tags", []) or []),
                                " ".join(getattr(_fact, "entities", []) or []),
                            ])
                            _tokens = set(re.findall(r"[a-zA-Z0-9_+#.-]{2,}", _text.lower()))
                            _score = len(_q_tokens & _tokens)
                            _scored_extracted.append((_score, _fact))
                        _scored_extracted.sort(key=lambda x: x[0], reverse=True)
                        _relevant_extracted = [f for s, f in _scored_extracted if s > 0][:_ev_extracted]
                        if not _relevant_extracted and _gen_extracted_facts_all:
                            _relevant_extracted = list(_gen_extracted_facts_all)[:_ev_extracted]
                        
                        _, _gate_meta = _tgr_exp(post, topic.get("angle", ""), grounding_facts)
                        _explain = build_explain_output(
                            evidence_facts=_relevant,
                            article_ref=topic.get("title", ""),
                            channel=channel,
                            ssi_component=topic.get('ssi_component', 'establish_brand'),
                            dot_per_sentence_scores=_gate_meta.dot_per_sentence_scores,
                            spacy_sim_scores=_gate_meta.spacy_sim_scores,
                            extracted_facts=_relevant_extracted,
                        )
                        print(format_explain_output(_explain))

                    # Release large per-topic structures before moving to next topic.
                    del all_facts, relevant, persona_facts, domain_facts, grounding_facts
                    if args.avatar_explain:
                        del _all_facts, _relevant, _gen_extracted_facts_all, _scored_extracted, _relevant_extracted
                    if _topic_idx % 2 == 0:
                        gc.collect()

                if channel != "youtube":
                    for _scheduled_post in posts:
                        _optimized_story = (_scheduled_post.pop("_flux_optimized_post_text", "") or "").strip()
                        if not _optimized_story:
                            _optimized_story = str(_scheduled_post.get("generated_text", "")).strip()
                        _art_meta = _render_schedule_art_avatar(
                            ai,
                            _optimized_story,
                            channel,
                            _scheduled_post,
                            optimize_story=False,
                        )
                        _scheduled_post.update(_art_meta)
                        if _art_meta.get("art_avatar_status") == RenderStatus.RENDERED.value:
                            _display_art_in_terminal(_art_meta.get("art_avatar_image_path"))

                # Only schedule if not dry-run and not YouTube
                if not args.dry_run:
                    if channel == "youtube":
                        print(
                            str(Fore.YELLOW)
                            + "\n⚠️  YouTube scripts were generated and saved locally, but not scheduled to Buffer.\n"
                            + "   Buffer YouTube scheduling requires a video file upload (title/category/video).\n"
                            + "   Render with lipsync.video, then upload manually."
                            + str(Style.RESET_ALL)
                        )
                        continue
                    buffer = build_buffer_service()
                    scheduler = PostScheduler(buffer_service=buffer)
                    try:
                        scheduled = scheduler.schedule_week(posts=posts, week_number=args.week, channel=channel)
                        print(str(Fore.GREEN) + f"\n✅  Scheduled {len(scheduled)} posts to Buffer ({channel})" + str(Style.RESET_ALL))
                    except BufferQueueFullError as e:
                        print(str(Fore.YELLOW) + f"\n⚠️  Buffer queue is full — no new posts were scheduled.\n   {e}\n   Free up slots at https://publish.buffer.com before running again." + str(Style.RESET_ALL))
                    except BufferRateLimitError as e:
                        print(
                            str(Fore.YELLOW)
                            + f"\n⚠️  Buffer API rate limit reached.\n   {e}\n"
                            + "   Wait for the retry window, then run the command again."
                            + str(Style.RESET_ALL)
                        )
                    except BufferChannelNotConnectedError as e:
                        print(
                            str(Fore.YELLOW)
                            + f"\n⚠️  Requested channel is not connected in Buffer.\n   {e}\n"
                            + "   Connect the channel in Buffer or run with a different --channel value."
                            + str(Style.RESET_ALL)
                        )

                # Channel-level cleanup before processing the next channel.
                posts.clear()
                gc.collect()
        finally:
            _run_post_generation_cleanup(ai, "schedule")



if __name__ == "__main__":
    main()
