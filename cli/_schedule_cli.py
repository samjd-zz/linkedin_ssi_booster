"""--schedule CLI handler: generate calendar posts, render FLUX art, push to Buffer."""

import gc
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Callable

from colorama import Fore, Style

from cli._flux_render import (
    _optimize_flux_story_for_render,
    _render_schedule_art_avatar,
    _run_post_generation_cleanup,
)
from scheduler import PostScheduler
from services.buffer_service import (
    BufferChannelNotConnectedError,
    BufferQueueFullError,
    BufferRateLimitError,
    BufferService,
)
from services.flux_capacitor import get_flux_service, RenderStatus, SourceMode
from services.flux_capacitor._terminal import _display_art_in_terminal
from services.ollama_service import OllamaService
from services.performance import timed_stage
from services.shared import append_channel_footer, get_youtube_scripts_dir

logger = logging.getLogger(__name__)


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


def run_schedule_cli(
    args,
    ai: OllamaService,
    build_buffer_service: Callable[[], BufferService],
) -> None:
    """Run the --schedule flow."""
    try:
        content_calendar = load_content_calendar()
        week_topics = content_calendar.get(f"week_{args.week}", [])
        if not week_topics:
            logger.error("No content found for week %d", args.week)
            return

        from services.avatar_intelligence import (
            load_avatar_state as _lav_gen,
            normalize_evidence_facts,
            normalize_domain_facts,
            normalize_extracted_facts,
            retrieve_evidence,
            evidence_facts_to_project_facts,
            EvidenceFact,
            DomainEvidenceFact,
            domain_facts_to_project_facts,
        )
        with timed_stage(logger, "schedule.preparation"):
            _gen_avatar_state = _lav_gen()
            all_facts = (
                list(normalize_evidence_facts(_gen_avatar_state))
                + list(normalize_domain_facts(_gen_avatar_state))
            )
            _ev_proj = int(os.getenv("EVIDENCE_PROJECT_COUNT", "3"))
            _ev_dom = int(os.getenv("EVIDENCE_DOMAIN_COUNT", "2"))
            _extracted_tokens = []
            if args.avatar_explain:
                from services.avatar_intelligence import build_explain_output, format_explain_output
                # Canonical name first; EVIDENCE_EXTRACTED_COUNT kept as legacy alias.
                _ev_extracted = int(
                    os.getenv("EXTRACTED_EVIDENCE_COUNT")
                    or os.getenv("EVIDENCE_EXTRACTED_COUNT", "2")
                )
                for _fact in normalize_extracted_facts(_gen_avatar_state):
                    _text = " ".join([
                        _fact.statement, _fact.source_title,
                        " ".join(_fact.tags or []), " ".join(_fact.entities or []),
                    ])
                    _extracted_tokens.append((
                        _fact, set(re.findall(r"[a-zA-Z0-9_+#.-]{2,}", _text.lower())),
                    ))
            _grounding_cache: dict[int, tuple[list, list]] = {}

        # args.channel is already a list from _parse_channels
        for channel in args.channel:
            preselected = (
                not args.dry_run and channel != "youtube"
                and PostScheduler._get_posting_slot_limit() is not None
            )
            channel_topics = PostScheduler.select_posts(week_topics) if preselected else week_topics
            logger.info("📝 Generating %d posts for week %d (channel: %s)...", len(channel_topics), args.week, channel)
            posts = []
            if channel == "youtube" and not args.dry_run:
                get_youtube_scripts_dir()

            for _topic_idx, topic in enumerate(channel_topics, start=1):
                logger.info("  Generating: %s", topic['title'])
                grounding_query = f"{topic['title']}. {topic['angle']}. {topic.get('ssi_component', 'establish_brand')}"
                with timed_stage(logger, "schedule.retrieval"):
                    _topic_key = id(topic)
                    if _topic_key not in _grounding_cache:
                        relevant = retrieve_evidence(grounding_query, all_facts, limit=_ev_proj + _ev_dom)  # type: ignore[arg-type]
                        grounding_facts = (
                            evidence_facts_to_project_facts([f for f in relevant if isinstance(f, EvidenceFact)])
                            + domain_facts_to_project_facts([f for f in relevant if isinstance(f, DomainEvidenceFact)])
                        )
                        _grounding_cache[_topic_key] = (relevant, grounding_facts)
                    relevant, grounding_facts = _grounding_cache[_topic_key]

                flux_service = get_flux_service()
                ollama_job_id = flux_service.notify_ollama_start()
                try:
                    with timed_stage(logger, "schedule.generation"):
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

                _generated_post = post
                _cached_text = getattr(ai, "last_truth_gate_text", "")
                _cached_meta = getattr(ai, "last_truth_gate_meta", None)
                _generation_meta = (
                    _cached_meta
                    if _cached_text.split() == _generated_post.split() else None
                )

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
                        with timed_stage(logger, "schedule.dot_report"):
                            _dot_result = getattr(_generation_meta, "dot_result", None)
                            if _dot_result is None:
                                _dot_result = score_claim_with_truth_gradient(_generated_post, _dot_paths)
                            _dot_report_dict = report_truth_gradient(_generated_post, _dot_result, verbose=True)
                        _dot_colour = str(Fore.RED) if _dot_result.flagged else str(Fore.CYAN)
                        from services.derivative_of_truth._reporting import format_dot_report_header
                        print(format_dot_report_header())
                        print("Generated-content score (excludes appended hashtags and footer).")
                        print(format_truth_gradient_report(_dot_report_dict))
                        print()
                    except Exception as _dot_err:
                        logger.debug("DoT report unavailable: %s", _dot_err)

                if args.avatar_explain:
                    # Combine project and domain facts for retrieval
                    from services.console_grounding import truth_gate_result as _tgr_exp
                    _relevant = relevant

                    # Score and filter extracted facts by relevance (retrieve_evidence doesn't support ExtractedEvidenceFact type)
                    _q_tokens = set(re.findall(r"[a-zA-Z0-9_+#.-]{2,}", grounding_query.lower()))
                    _scored_extracted = []
                    for _fact, _tokens in _extracted_tokens:
                        _score = len(_q_tokens & _tokens)
                        _scored_extracted.append((_score, _fact))
                    _scored_extracted.sort(key=lambda x: x[0], reverse=True)
                    _relevant_extracted = [f for s, f in _scored_extracted if s > 0][:_ev_extracted]
                    if not _relevant_extracted and _extracted_tokens:
                        _relevant_extracted = [f for f, _ in _extracted_tokens][:_ev_extracted]

                    _gate_meta = _generation_meta
                    if _gate_meta is None:
                        _, _gate_meta = _tgr_exp(_generated_post, topic.get("angle", ""), grounding_facts)
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
                del relevant, grounding_facts
                if args.avatar_explain:
                    del _relevant, _scored_extracted, _relevant_extracted
                if _topic_idx % 2 == 0:
                    with timed_stage(logger, "schedule.gc"):
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
                    scheduled = scheduler.schedule_week(
                        posts=posts, week_number=args.week, channel=channel,
                        preselected=preselected,
                    )
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
