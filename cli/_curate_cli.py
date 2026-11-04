"""--curate CLI handler: curate articles, render FLUX art, and report results."""

import gc
from typing import Callable

from colorama import Fore, Style

from cli._flux_render import (
    _optimize_flux_story_for_render,
    _render_curate_art_avatar,
    _run_post_generation_cleanup,
)
from services.buffer_service import (
    BufferAuthenticationError,
    BufferChannelNotConnectedError,
    BufferQueueFullError,
    BufferRateLimitError,
    BufferService,
)
from services.flux_capacitor import RenderStatus, SourceMode
from services.flux_capacitor._terminal import _display_art_in_terminal
from services.ollama_service import OllamaService


def run_curate_cli(
    args,
    ai: OllamaService,
    github_context: str,
    build_buffer_service: Callable[[], BufferService],
) -> None:
    """Run the --curate flow."""
    try:
        buffer = None if args.dry_run else build_buffer_service()
        from services.shared import AVATAR_CONFIDENCE_POLICY
        from services.content_curator import ContentCurator

        confidence_policy = args.confidence_policy or AVATAR_CONFIDENCE_POLICY
        curator = ContentCurator(ai_service=ai, buffer_service=buffer, confidence_policy=confidence_policy, github_context=github_context, classify=args.classify)

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
        except BufferAuthenticationError as e:
            print(str(Fore.RED) + f"\n❌ Buffer authentication failed: {e}" + str(Style.RESET_ALL))
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
