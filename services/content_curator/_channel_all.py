"""All-channel curation: LinkedIn, X, Threads, Bluesky, and YouTube per article."""

import logging
import re
import time
from typing import Any, Callable

from colorama import Fore, Style

from services.buffer_service import BufferQueueFullError, BufferChannelNotConnectedError
from services.console_grounding import ProjectFact
from services.content_curator._curator_base import _CURATE_RUN_ID
from services.content_curator._reporting import CuratorReportingMixin
from services.content_curator._text_utils import (
    truncate_at_sentence,
    append_url_and_hashtags,
    build_source_article_block,
)
from services.shared import (
    append_channel_footer,
    X_CHAR_LIMIT,
    X_URL_CHARS,
    THREADS_CHAR_LIMIT,
    get_youtube_scripts_dir,
)

logger = logging.getLogger(__name__)


class CuratorAllChannelsMixin(CuratorReportingMixin):
    """Generate and push one article across every supported channel."""

    def _process_all_channels(
        self,
        article: dict[str, Any],
        ssi_component: str,
        grounding_facts: list[ProjectFact],
        extracted_facts: list[Any],
        external_facts: list[Any],
        dry_run: bool,
        request_delay: float,
        message_type: str,
        interactive: bool,
        avatar_explain: bool,
        dot_report: bool,
        candidate_id: str,
        created_ideas: list,
        update_published_cache: Callable[[str], None],
    ) -> list | None:
        """Generate LinkedIn + X + Bluesky + Threads + YouTube posts for one article."""
        _conf_route = "n/a"
        _conf_reason = "not generated"

        li_text = self.ai.summarise_for_curation(
            article_text=f"Title: {article['title']}\n{article['summary']}",
            source_url=article["link"],
            ssi_component=ssi_component,
            channel="linkedin",
            post_mode=True,
            grounding_facts=grounding_facts,
            extracted_facts=extracted_facts,
            interactive=interactive,
            github_context=self.github_context,
        )
        if not li_text:
            logger.info("Skipping article with no usable content: %s", article["title"][:60])
            return created_ideas

        _conf_route, _conf_reason = self._score_and_route(
            post_text=li_text,
            article_summary=article["summary"],
            grounding_facts=grounding_facts,
            channel="linkedin",
            article_ref=article.get("link", article["title"]),
            requested_mode=message_type,
        )
        _li_source_ref = build_source_article_block(article.get("title", ""), article.get("link", ""))
        li_text = append_url_and_hashtags(li_text, _li_source_ref)
        li_text = append_channel_footer(li_text, "linkedin")
        # print_validation_reports(
        #     post_text=li_text,
        #     context_text=article["summary"],
        #     grounding_facts=grounding_facts,
        #     raw_evidence=self._avatar_facts,
        #     raw_domain=self._domain_facts,
        #     raw_extracted=extracted_facts,
        #     facts_used_for_dot=grounding_facts + (extracted_facts or []),
        #     avatar_explain=avatar_explain,
        #     dot_report=dot_report,
        #     channel="all",
        #     ssi_component=ssi_component
        # )

        time.sleep(request_delay)
        x_post = self.ai.summarise_for_curation(
            f"Title: {article['title']}\n{article['summary']}", article["link"], ssi_component, "x",
            grounding_facts=grounding_facts, extracted_facts=extracted_facts,
            interactive=interactive, github_context=self.github_context,
        )
        if x_post:
            x_budget = X_CHAR_LIMIT - X_URL_CHARS
            x_post = truncate_at_sentence(x_post, x_budget)
            if article["link"] and article["link"] not in x_post:
                x_post = x_post.rstrip() + f"\n\n{article['link']}"

        time.sleep(request_delay)
        threads_post = self.ai.summarise_for_curation(
            f"Title: {article['title']}\n{article['summary']}", article["link"], ssi_component, "threads",
            grounding_facts=grounding_facts, extracted_facts=extracted_facts,
            interactive=interactive, github_context=self.github_context,
        )
        if threads_post:
            url_overhead = (2 + len(article["link"])) if article.get("link") else 0
            threads_budget = max(80, THREADS_CHAR_LIMIT - url_overhead)
            threads_post = truncate_at_sentence(threads_post, threads_budget)
            if article["link"] and article["link"] not in threads_post:
                threads_post = threads_post.rstrip() + f"\n\n{article['link']}"

        time.sleep(request_delay)
        bsky_post = self.ai.summarise_for_curation(
            f"Title: {article['title']}\n{article['summary']}", article["link"], ssi_component, "bluesky",
            grounding_facts=grounding_facts, extracted_facts=extracted_facts,
            interactive=interactive, github_context=self.github_context,
        )
        if bsky_post:
            url_overhead = (2 + len(article["link"])) if article.get("link") else 0
            bsky_budget = 300 - url_overhead
            bsky_post = truncate_at_sentence(bsky_post, bsky_budget)
            if article["link"] and article["link"] not in bsky_post:
                bsky_post = bsky_post.rstrip() + f"\n\n{article['link']}"

        time.sleep(request_delay)
        yt_script = self.ai.summarise_for_curation(
            f"Title: {article['title']}\n{article['summary']}", article["link"], ssi_component, "youtube",
            post_mode=True, grounding_facts=grounding_facts, extracted_facts=extracted_facts,
            interactive=interactive, github_context=self.github_context,
        )
        if yt_script:
            yt_script = truncate_at_sentence(yt_script, 500)

        yt_script_path = None
        if yt_script and not dry_run:
            yt_dir = get_youtube_scripts_dir()
            safe_title = re.sub(r"[^\w\-]", "_", article["title"][:60]).strip("_")
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            yt_script_path = yt_dir / f"{timestamp}_{safe_title}.txt"
            yt_script_path.write_text(
                f"TITLE: {article['title']}\nSSI COMPONENT: {ssi_component}\nSOURCE: {article['link']}\n\n{yt_script}\n",
                encoding="utf-8",
            )

        self._print_article_header(article, "all", ssi_component, _conf_route, _conf_reason)
        print(str(Fore.GREEN) + f"\n🔵 LINKEDIN POST:" + str(Style.RESET_ALL) + f"\n{li_text}")
        print(str(Fore.BLUE) + f"\n𝕏  X POST:" + str(Style.RESET_ALL) + f"\n{x_post}")
        print(str(Fore.WHITE) + f"\nTHREADS POST:" + str(Style.RESET_ALL) + f"\n{threads_post}")
        print(str(Fore.MAGENTA) + f"\n🦋 BLUESKY POST:" + str(Style.RESET_ALL) + f"\n{bsky_post}")
        if yt_script:
            print(str(Fore.RED) + str(Style.BRIGHT) + "\n🎬 YOUTUBE SHORT SCRIPT:" + str(Style.RESET_ALL) + f"\n{yt_script}\n")
            print("GitHub: https://buff.ly/tfajNLI")
            print("Sign up for Buffer with my partner link — join.buffer.com/samjd42  — to start scheduling, publishing, and analyzing your social posts in one place while supporting my work.")
        if avatar_explain:
            self._print_avatar_explain(
                li_text,
                article,
                grounding_facts,
                "all",
                ssi_component,
                extracted_facts=extracted_facts,
                external_facts=external_facts,
            )
        if dot_report:
            self._print_dot_report(li_text, article, grounding_facts, extracted_facts, external_facts)
        if dry_run:
            created_ideas.append({"dry_run": True, "title": article["title"], "ssi_component": ssi_component, "channel": "all"})
            return created_ideas

        # Live push
        try:
            from services.selection_learning import log_candidate as _log_cand_all
            _log_cand_all(
                candidate_id=candidate_id,
                article_url=article.get("link", ""),
                article_title=article.get("title", ""),
                article_source=article.get("source", ""),
                ssi_component=ssi_component,
                channel="all",
                post_text=li_text,
                buffer_id=None,
                route="post",
                run_id=_CURATE_RUN_ID,
            )
        except Exception as _cand_exc:
            logger.warning("selection_learning: candidate log failed (continuing): %s", _cand_exc)

        if not self.buffer:
            logger.warning("No buffer_service provided — skipping post creation")
            return created_ideas

        try:
            _li_post = self.buffer.create_scheduled_post(self.buffer.get_linkedin_channel_id(), li_text)
            try:
                from services.selection_learning import update_candidate_buffer_id as _upd_all
                _upd_all(candidate_id, _li_post.get("id", ""))
            except Exception as _upd_exc:
                logger.warning("selection_learning: buffer_id update failed (continuing): %s", _upd_exc)
            if x_post:
                try:
                    self.buffer.create_scheduled_post(self.buffer.get_x_channel_id(), x_post, channel="x")
                except BufferChannelNotConnectedError as exc:
                    logger.warning(str(Fore.YELLOW) + f"⚠️  X channel not configured — skipping. ({exc})" + str(Style.RESET_ALL))
            if threads_post:
                try:
                    self.buffer.create_scheduled_post(self.buffer.get_threads_channel_id(), threads_post, channel="threads")
                except BufferChannelNotConnectedError as exc:
                    logger.warning(str(Fore.YELLOW) + f"⚠️  Threads channel not configured — skipping. ({exc})" + str(Style.RESET_ALL))
            if bsky_post:
                try:
                    self.buffer.create_scheduled_post(self.buffer.get_bluesky_channel_id(), bsky_post, channel="bluesky")
                except BufferChannelNotConnectedError as exc:
                    logger.warning(str(Fore.YELLOW) + f"⚠️  Bluesky channel not configured — skipping. ({exc})" + str(Style.RESET_ALL))
            if yt_script:
                print(str(Fore.RED) + str(Style.BRIGHT) + "\n🎬 YOUTUBE SHORT SCRIPT (all-channel mode):" + str(Style.RESET_ALL))
                print(str(Fore.WHITE) + f"📄 TITLE:  {article['title']}" + str(Style.RESET_ALL))
                print(str(Fore.CYAN) + f"🎯 SSI:    {ssi_component}" + str(Style.RESET_ALL))
                print(f"\n{yt_script}\n")
                if yt_script_path:
                    print(str(Fore.GREEN) + f"💾 Saved to: {yt_script_path}" + str(Style.RESET_ALL))
                print(str(Fore.YELLOW) + "⚠️  YouTube requires a video upload — script not pushed to Buffer." + str(Style.RESET_ALL))
            update_published_cache(article["title"])
            created_ideas.append({"title": article["title"], "channel": "all", "ssi_component": ssi_component})
        except BufferQueueFullError as exc:
            logger.warning(str(Fore.YELLOW) + f"⚠️  Buffer queue full — stopping early. ({exc})" + str(Style.RESET_ALL))
            return None  # signal caller to break

        return created_ideas
