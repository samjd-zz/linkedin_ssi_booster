"""Rei Toei Suno song generation CLI handler (--rei-generate)."""

from __future__ import annotations

import asyncio
import logging
import importlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from colorama import Fore, Style

from services.performance import timed_stage
from services.shared import get_rei_toei_dir

if TYPE_CHECKING:
    from services.rei_toei_service import ReiToeiConfig

logger = logging.getLogger(__name__)


async def handle_rei_generate(args, ai, rei_config: ReiToeiConfig) -> None:
    """Suno song generation pipeline."""
    from services.rei_toei_service import (
        Theme,
        load_rei_persona,
        load_rei_domain_knowledge,
        extract_themes,
        choose_diverse_theme,
        load_recent_rei_titles,
        generate_song_concept,
        compose_lyrics,
        assemble_suno_prompt,
        submit_to_suno,
        validate_lyrics_with_dot,
    )
    from services.avatar_intelligence import (
        load_avatar_state as _lav_rei,
        normalize_extracted_facts as _nef_rei,
    )

    with timed_stage(logger, "rei.preparation"):
        rei_persona = load_rei_persona()
        rei_domain = load_rei_domain_knowledge()
        _extracted_facts = []
        if (
            not args.rei_theme
            or args.rei_explain
            or (rei_config.dot_validation_enabled and not args.rei_preview)
        ):
            avatar_state = _lav_rei()
            _extracted_facts = _nef_rei(avatar_state)
        recent_titles = load_recent_rei_titles(
            get_rei_toei_dir(create=False),
            limit=rei_config.recent_title_window,
        )

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
        theme = choose_diverse_theme(
            themes,
            recent_theme_names=recent_titles,
            repeat_penalty=rei_config.theme_repeat_penalty,
            jitter_ratio=rei_config.theme_jitter_ratio,
        )
        print(str(Fore.CYAN) + f"\U0001f3b5 Selected theme: {theme.name} (frequency={theme.frequency}, recency={theme.recency_score:.2f})" + str(Style.RESET_ALL))

    print(str(Fore.CYAN) + "\U0001f3bc Generating song concept..." + str(Style.RESET_ALL))
    with timed_stage(logger, "rei.concept"):
        concept = await asyncio.to_thread(
            generate_song_concept,
            theme,
            rei_persona,
            rei_domain,
            None,
            ai,
            recent_titles,
        )

    print(str(Fore.CYAN) + "\u270d\ufe0f  Composing lyrics..." + str(Style.RESET_ALL))
    with timed_stage(logger, "rei.lyrics"):
        lyrics = await asyncio.to_thread(
            compose_lyrics, concept, rei_persona, rei_domain, None, ai,
        )

    with timed_stage(logger, "rei.suno_formatting"):
        suno_prompt = assemble_suno_prompt(concept, lyrics, rei_domain)

    # Enforce DoT truth validation (REI_TOEI_DOT_VALIDATION_ENABLED).
    # A failing score warns and skips Suno auto-submission; the song is
    # still displayed and saved locally for review. Preview mode skips
    # enforcement — nothing is saved or submitted there.
    dot_result = None
    if rei_config.dot_validation_enabled and not args.rei_preview:
        with timed_stage(logger, "rei.dot_validation"):
            dot_result = validate_lyrics_with_dot(lyrics, _extracted_facts)
        if not dot_result.valid:
            print(
                str(Fore.YELLOW)
                + f"⚠️  DoT validation failed (score {dot_result.overall_truth_score:.2f} "
                + f"< threshold {rei_config.dot_min_truth_gradient}) — Suno submission will be skipped."
                + str(Style.RESET_ALL)
            )
            for _claim in dot_result.flagged_claims[:3]:
                print(str(Fore.YELLOW) + f"   flagged: {_claim[:100]}" + str(Style.RESET_ALL))

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
        dot = dot_result
        if dot is None:
            with timed_stage(logger, "rei.dot_validation"):
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

    # Submit to Suno if API key available and DoT validation passed
    suno_api_key = os.getenv("SUNO_API_KEY")
    if suno_api_key and dot_result is not None and not dot_result.valid:
        print(
            str(Fore.YELLOW)
            + "⚠️  Skipping Suno submission — DoT validation failed. Review the flagged "
            + "claims above, or set REI_TOEI_DOT_VALIDATION_ENABLED=false to bypass."
            + str(Style.RESET_ALL)
        )
    elif suno_api_key:
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
