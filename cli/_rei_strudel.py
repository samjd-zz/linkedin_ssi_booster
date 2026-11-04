"""Rei Toei Strudel pattern generation CLI handler (--rei-generate-strudel)."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from colorama import Fore, Style

from services.performance import timed_stage
from services.shared import get_rei_toei_dir

if TYPE_CHECKING:
    from services.rei_toei_service import ReiToeiConfig

logger = logging.getLogger(__name__)


async def handle_rei_generate_strudel(args, ai, rei_config: ReiToeiConfig) -> None:
    """Strudel pattern generation pipeline."""
    from services.rei_toei_service import (
        Theme,
        load_rei_persona,
        load_rei_domain_knowledge,
        load_strudel_patterns,
        extract_themes,
        choose_diverse_theme,
        load_recent_rei_titles,
        map_concept_to_pattern,
        generate_strudel_code,
        validate_strudel_syntax,
        execute_strudel_pattern,
        save_pattern_to_library,
    )
    from services.avatar_intelligence import (
        load_avatar_state as _lav_rei,
        normalize_extracted_facts as _nef_rei,
    )

    rei_persona = load_rei_persona()
    rei_domain = load_rei_domain_knowledge()
    pattern_library = load_strudel_patterns()

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
        avatar_state = _lav_rei()
        _extracted_facts = _nef_rei(avatar_state)
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
    with timed_stage(logger, "rei.strudel"):
        strudel_pattern = await asyncio.to_thread(
            generate_strudel_code, theme, template, rei_persona, rei_domain, None, ai,
        )
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
