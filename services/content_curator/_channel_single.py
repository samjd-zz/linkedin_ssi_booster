"""Single-channel curation: generate, score, route, and push one post."""

import logging
import re
from datetime import datetime
from typing import Any, Callable

from colorama import Fore, Style

from services.buffer_service import BufferQueueFullError
from services.console_grounding import ProjectFact, TruthGateMeta
from services.content_curator._curator_base import _CURATE_RUN_ID
from services.content_curator._reporting import CuratorReportingMixin
from services.content_curator._text_utils import (
    truncate_at_sentence,
    append_url_and_hashtags,
    build_source_article_block,
)
from services.performance import timed_stage
from services.shared import (
    append_channel_footer,
    X_CHAR_LIMIT,
    X_URL_CHARS,
    THREADS_CHAR_LIMIT,
    get_youtube_scripts_dir,
)

logger = logging.getLogger(__name__)


class CuratorSingleChannelMixin(CuratorReportingMixin):
    """Generate and route a post for one channel or idea mode."""

    @timed_stage(logger, "curation.channel")
    def _process_single_channel(
        self,
        article: dict[str, Any],
        ssi_component: str,
        grounding_facts: list[ProjectFact],
        extracted_facts: list[Any],
        external_facts: list[Any],
        channel: str,
        message_type: str,
        dry_run: bool,
        interactive: bool,
        avatar_explain: bool,
        dot_report: bool,
        candidate_id: str,
        created_ideas: list,
        update_published_cache: Callable[[str], None],
    ) -> list | None:
        """Generate and route a post for a single channel / idea mode."""
        logger.info("Curation channel=%s starting", channel)

        try:
            from services.avatar_intelligence import build_continuity_context
            _continuity = (
                build_continuity_context(self._narrative_memory)
                if self._narrative_memory is not None
                else ""
            )
        except Exception:
            _continuity = ""

        post_text = self.ai.summarise_for_curation(
            article_text=article["summary"],
            source_url=article["link"],
            ssi_component=ssi_component,
            channel=channel,
            post_mode=(message_type == "post"),
            grounding_facts=grounding_facts,
            extracted_facts=extracted_facts,
            interactive=interactive,
            continuity_context=_continuity,
            github_context=self.github_context,
        )
        if not post_text:
            logger.info("Skipping article with no usable content: %s", article["title"][:60])
            return created_ideas
        generation_meta = getattr(self.ai, "last_truth_gate_meta", None)
        if (
            not isinstance(generation_meta, TruthGateMeta)
            or getattr(self.ai, "last_truth_gate_text", None) != post_text
        ):
            generation_meta = None

        # print_validation_reports(
        #     post_text=post_text,
        #     context_text=article["summary"],
        #     grounding_facts=grounding_facts,
        #     raw_evidence=self._avatar_facts,
        #     raw_domain=self._domain_facts,
        #     raw_extracted=extracted_facts,
        #     facts_used_for_dot=grounding_facts + (extracted_facts or []),
        #     avatar_explain=avatar_explain,
        #     dot_report=dot_report,
        #     channel=channel,
        #     ssi_component=ssi_component
        # )

        try:
            from services.shared import AVATAR_LEARNING_ENABLED
            from services.avatar_intelligence import (
                extract_narrative_updates,
                update_narrative_memory,
                save_narrative_memory,
            )
            if AVATAR_LEARNING_ENABLED and self._narrative_memory is not None:
                _updates = extract_narrative_updates(post_text, ssi_component, article["title"])
                self._narrative_memory = update_narrative_memory(
                    self._narrative_memory,
                    themes=_updates["themes"],
                    claims=_updates["claims"],
                    arcs=_updates["arcs"],
                )
                save_narrative_memory(self._narrative_memory)
        except Exception as _mem_exc:
            logger.warning("Narrative memory update failed (continuing): %s", _mem_exc)

        if channel == "linkedin":
            _source_ref = build_source_article_block(article.get("title", ""), article.get("link", ""))
            post_text = append_url_and_hashtags(post_text, _source_ref)
        elif channel == "facebook":
            _source_ref = build_source_article_block(article.get("title", ""), article.get("link", ""))
            post_text = append_url_and_hashtags(post_text, _source_ref)
        elif channel == "youtube":
            post_text = truncate_at_sentence(post_text, 500)
        elif channel == "x":
            x_budget = X_CHAR_LIMIT - X_URL_CHARS
            post_text = truncate_at_sentence(post_text, x_budget)
            if article["link"] and article["link"] not in post_text:
                post_text = post_text.rstrip() + f"\n\n{article['link']}"

        elif channel == "threads":
            url_overhead = (2 + len(article["link"])) if article.get("link") else 0
            threads_budget = max(80, THREADS_CHAR_LIMIT - url_overhead)
            post_text = truncate_at_sentence(post_text, threads_budget)
            if article["link"] and article["link"] not in post_text:
                post_text = post_text.rstrip() + f"\n\n{article['link']}"
        elif channel == "bluesky":
            url_overhead = (2 + len(article["link"])) if article.get("link") else 0
            bsky_budget = 300 - url_overhead
            post_text = truncate_at_sentence(post_text, bsky_budget)
            if article["link"] and article["link"] not in post_text:
                post_text = post_text.rstrip() + f"\n\n{article['link']}"

        _conf_route, _conf_reason = self._score_and_route(
            post_text=post_text,
            article_summary=article["summary"],
            grounding_facts=grounding_facts,
            channel=channel,
            article_ref=article.get("link", article["title"]),
            requested_mode=message_type,
            gate_meta=generation_meta,
        )

        post_text = append_channel_footer(post_text, channel)

        if not dry_run:
            try:
                from services.selection_learning import log_candidate as _log_cand
                _log_cand(
                    candidate_id=candidate_id,
                    article_url=article.get("link", ""),
                    article_title=article.get("title", ""),
                    article_source=article.get("source", ""),
                    ssi_component=ssi_component,
                    channel=channel,
                    post_text=post_text,
                    buffer_id=None,
                    route=_conf_route,
                    run_id=_CURATE_RUN_ID,
                )
            except Exception as _cand_exc:
                logger.warning("selection_learning: candidate log failed (continuing): %s", _cand_exc)

        self._print_article_header(article, channel, ssi_component, _conf_route, _conf_reason)
        print(str(Fore.GREEN) + f"\n✍️  GENERATED POST:" + str(Style.RESET_ALL) + f"\n{post_text}")

        if avatar_explain:
            self._print_avatar_explain(
                post_text,
                article,
                grounding_facts,
                channel,
                ssi_component,
                extracted_facts=extracted_facts,
                external_facts=external_facts,
            )
        if dot_report:
            self._print_dot_report(post_text, article, grounding_facts, extracted_facts, external_facts)

        if dry_run:
            created_ideas.append({
                "dry_run": True,
                "title": article["title"],
                "generated_text": post_text,
                "grounding_facts": grounding_facts,
                "ssi_component": ssi_component,
                "channel": channel,
                "confidence_route": _conf_route,
            })
            return created_ideas

        if _conf_route == "block":
            logger.warning(
                str(Fore.YELLOW) + f"⚠️  Confidence policy blocked publish for: {article['title'][:60]}" + str(Style.RESET_ALL)
            )
            return created_ideas

        if not self.buffer:
            logger.warning("No buffer_service provided — skipping idea creation")
            return created_ideas

        effective_message_type = "idea" if _conf_route == "idea" else message_type
        if effective_message_type == "post":
            if channel == "youtube":
                yt_dir = get_youtube_scripts_dir()
                safe_title = re.sub(r"[^\w\-]", "_", article["title"][:60]).strip("_")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                script_path = yt_dir / f"{timestamp}_{safe_title}.txt"
                script_path.write_text(
                    f"TITLE: {article['title']}\nSSI COMPONENT: {ssi_component}\nSOURCE: {article['link']}\n\n{post_text}\n",
                    encoding="utf-8",
                )
                print(str(Fore.GREEN) + f"💾 Saved to: {script_path}" + str(Style.RESET_ALL))
                print("GitHub: https://buff.ly/tfajNLI")
                print("Sign up for Buffer with my partner link — join.buffer.com/samjd42  — to start scheduling, publishing, and analyzing your social posts in one place while supporting my work.")
                print(str(Fore.YELLOW) + "⚠️  Buffer YouTube requires a video — script not pushed." + str(Style.RESET_ALL))
                update_published_cache(article["title"])
                created_ideas.append({
                    "title": article["title"], "text": post_text,
                    "ssi_component": ssi_component, "channel": "youtube",
                    "script_path": str(script_path),
                })
                return created_ideas
            elif channel == "x":
                channel_id = self.buffer.get_x_channel_id()
            elif channel == "threads":
                channel_id = self.buffer.get_threads_channel_id()
            elif channel == "bluesky":
                channel_id = self.buffer.get_bluesky_channel_id()
            elif channel == "facebook":
                channel_id = self.buffer.get_facebook_channel_id()
            else:
                channel_id = self.buffer.get_linkedin_channel_id()
            try:
                post = self.buffer.create_scheduled_post(channel_id, post_text, channel=channel)
                update_published_cache(article["title"])
                try:
                    from services.selection_learning import update_candidate_buffer_id as _upd
                    _upd(candidate_id, post.get("id", ""))
                except Exception as _upd_exc:
                    logger.warning("selection_learning: buffer_id update failed (continuing): %s", _upd_exc)
                created_ideas.append({**(post if isinstance(post, dict) else {}), "generated_text": post_text, "grounding_facts": grounding_facts, "channel": channel, "title": article.get("title", ""), "ssi_component": ssi_component})
            except BufferQueueFullError as exc:
                logger.warning(
                    str(Fore.YELLOW) + f"⚠️  Buffer queue full — stopping early. ({exc})" + str(Style.RESET_ALL)
                )
                return None  # signal caller to break
        else:
            idea = self.buffer.create_idea(
                text=post_text,
                title=f"[{channel}|{ssi_component}] {article['title'][:70]}",
            )
            update_published_cache(article["title"])
            try:
                from services.selection_learning import update_candidate_buffer_id as _upd
                _upd(candidate_id, idea.get("id", ""))
            except Exception as _upd_exc:
                logger.warning("selection_learning: buffer_id update failed (continuing): %s", _upd_exc)
            created_ideas.append({**(idea if isinstance(idea, dict) else {}), "generated_text": post_text, "grounding_facts": grounding_facts, "channel": channel, "title": article.get("title", ""), "ssi_component": ssi_component})

        return created_ideas
