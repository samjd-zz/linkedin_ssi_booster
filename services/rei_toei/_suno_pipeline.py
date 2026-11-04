"""
Suno Generation Pipeline Functions

This module provides pipeline functions for transforming technical themes into
Suno-ready song prompts with lyrics, validation, and submission orchestration.

Author: Shawn Jackson Dyck
"""

import json
import logging
from datetime import datetime
from typing import Any, cast, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.avatar_intelligence._models import PersonaGraph
    from services.ollama_service import OllamaService

from services.rei_toei._config import ReiToeiConfig
from services.rei_toei._hook_translation import apply_bilingual_hooks
from services.rei_toei._lyric_checks import (
    _add_bilingual_rescue_hooks,
    _backfill_missing_romaji_cues as _backfill_missing_romaji_cues,
    _bilingual_mix_ok,
    _has_chinese_leakage,
    _has_japanese_script,
    _learning_annotation_stats as _learning_annotation_stats,
    _learning_annotations_ok,
    _sections_are_distinct,
)
from services.rei_toei._lyric_prompts import build_lyric_prompts
from services.rei_toei._lyric_romaji import (
    _generate_hepburn_romaji as _generate_hepburn_romaji,
    _join_split_japanese_acronyms,
    _ROMAJI_FIRST_RE as _ROMAJI_FIRST_RE,
    _strip_cue_noise as _strip_cue_noise,
    _verify_and_correct_romaji_lines as _verify_and_correct_romaji_lines,
)
from services.rei_toei._models import (
    Lyrics,
    ReiDomainKnowledge,
    ReiPersonaGraph,
    SongConcept,
    SunoPrompt,
)
from services.rei_toei._song_structure import (
    borrowed_lines,
    borrowed_lines_feedback,
    bridge_is_underdeveloped,
    MAX_BORROWED_LINES,
    MIN_BRIDGE_SUNG_LINES,
    verse_two_repeats_verse_one,
)
from services.rei_toei._song_tidy import tidy_song_sections
from services.rei_toei._suno_blocks import (
    _append_normalized_section as _append_normalized_section,
    _build_suno_lyric_blocks,
    _normalize_freeform_suno_reply as _normalize_freeform_suno_reply,
)
from services.rei_toei._suno_concept import generate_song_concept as generate_song_concept
from services.rei_toei._suno_fallback import build_fallback_lyrics
from services.rei_toei._suno_json import (
    _has_prompt_schema_leakage,
    _normalize_lyric_payload,
    _parse_llm_json_payload,
)
from services.rei_toei._suno_quality import ensure_suno_quality
from services.rei_toei._suno_sections import (
    _format_learning_cue_block as _format_learning_cue_block,
    _normalize_suno_section as _normalize_suno_section,
)
from services.rei_toei._suno_tags import (
    _build_rich_suno_tags,
    _build_suno_description_prompt,
    _select_suno_template_key,
    _split_csv_descriptors,
)
from services.rei_toei._suno_themes import (
    choose_diverse_theme as choose_diverse_theme,
    ensure_unique_rei_title as ensure_unique_rei_title,
    extract_themes as extract_themes,
    load_recent_rei_titles as load_recent_rei_titles,
    resolve_lyric_language as resolve_lyric_language,
)

logger = logging.getLogger(__name__)


def compose_lyrics(
    concept: SongConcept,
    persona: ReiPersonaGraph,
    domain_knowledge: ReiDomainKnowledge,
    sam_persona: Optional["PersonaGraph"] = None,
    ollama: Optional["OllamaService"] = None
) -> Lyrics:
    """
    Compose structured song lyrics using Rei's voice and cyberpop aesthetic.
    Optimized for Suno compatibility with strict formatting rules:
    - ALL-CAPS chorus for dynamic velocity
    - Section labels like [Verse 1], [Chorus], [Pre-Chorus], [Bridge], [Outro]
    - No parenthetical instructions or comments inside text fields
    - Character caps per section for API parsing
    
    Args:
        concept: The song concept with mood, BPM, and theme
        persona: Rei's persona graph (lyrical style, voice)
        domain_knowledge: Music production knowledge (lyrical structure, metaphors)
        sam_persona: Optional Sam's persona graph for project knowledge inspiration
        ollama: Optional pre-initialized OllamaService; creates one if not provided (P2 GPU opt)
        
    Returns:
        Lyrics: Structured song sections with evidence tracking
    """
    logger.info(f"Composing formatted long-form lyrics for: '{concept.title}'")
    
    # Initialize Ollama service (reuse if provided, otherwise create)
    if ollama is None:
        from services.shared import get_ollama_service_cached
        ollama = cast("OllamaService", get_ollama_service_cached())
    assert ollama is not None  # type: ignore[assert-type]
    
    lyric_language = concept.lyric_language.strip().lower()
    lyric_config = ReiToeiConfig()
    japanese_mix_ratio = max(0.0, min(1.0, lyric_config.japanese_lyric_probability))
    japanese_target_percent = int(round(japanese_mix_ratio * 100))
    translate_mode = (
        lyric_language == "bilingual" and lyric_config.bilingual_strategy == "translate"
    )
    # Translate mode writes the song in English; Japanese hook lines are added after.
    generation_language = "english" if translate_mode else lyric_language
    system_prompt, user_prompt = build_lyric_prompts(
        concept,
        persona,
        domain_knowledge,
        sam_persona,
        lyric_language=lyric_language,
        generation_language=generation_language,
        translate_mode=translate_mode,
        japanese_target_percent=japanese_target_percent,
    )
    
    try:
        if generation_language in {"japanese", "bilingual"}:
            max_attempts = 5
        else:
            # English-first bilingual songs still get one structural retry.
            max_attempts = 2 if translate_mode else 1
        response_data: Dict[str, Any] = {}
        last_valid_response_data: Dict[str, Any] = {}
        structure_feedback = ""

        for attempt in range(1, max_attempts + 1):
            if generation_language == "bilingual" and attempt == 2:
                # Soft nudge with target percentage on first retry
                attempt_user_prompt = user_prompt + (
                    "\n\nBILINGUAL HARD CONSTRAINTS (mandatory):\n"
                    f"- Aim for approximately {japanese_target_percent}% Japanese lyrical content.\n"
                    "- Japanese lines must be complete, natural, singable phrases in Kanji/Kana.\n"
                    "- Use English for momentum and technical imagery.\n"
                    "- Selected Japanese hooks may be followed by concise English sung echoes."
                )
            elif generation_language == "bilingual" and attempt >= 3:
                # Explicit structural assignment on subsequent retries
                attempt_user_prompt = user_prompt + (
                    f"\n\nEXPLICIT BILINGUAL STRUCTURAL ASSIGNMENT (Mandatory for attempt {attempt}):\n"
                    "Do NOT estimate percentages or calculate line counts. Follow these exact structural rules per section:\n"
                    "- Verses ([Verse 1], [Verse 2]): English-driven narrative. Include EXACTLY 1 Japanese line (in Kanji/Kana) per stanza.\n"
                    "- Chorus ([Chorus]): Japanese-driven hook in Kanji/Kana, followed immediately by a concise English sung echo line.\n"
                    "- Bridge ([Bridge]): 50/50 split alternating 1:1 between English and Japanese.\n"
                    "- Pre-Chorus / Drop / Outro: Mixed English and Japanese for dynamic energy shifts."
                )
            else:
                attempt_user_prompt = user_prompt
            if structure_feedback:
                attempt_user_prompt += structure_feedback

            response_text = ollama._chat(
                system_prompt,
                attempt_user_prompt,
                max_tokens=4096,
                format="json",
            )
            logger.debug(f"Ollama lyrics response (attempt {attempt}): {response_text[:200]}...")

            try:
                response_data = _normalize_lyric_payload(
                    _parse_llm_json_payload(response_text)
                )
            except json.JSONDecodeError as exc:
                if last_valid_response_data:
                    logger.warning(
                        "Ollama lyrics response malformed on attempt %s (%s). Reusing last valid draft.",
                        attempt,
                        exc,
                    )
                    response_data = dict(last_valid_response_data)
                elif attempt < max_attempts:
                    logger.warning("Ollama lyrics response malformed on attempt %s (%s). Retrying.", attempt, exc)
                    continue
                else:
                    raise

            # Rescue missing chorus key if payload renamed it
            if "chorus" not in response_data:
                for k in list(response_data.keys()):
                    if "chorus" in k or "refrain" in k:
                        response_data["chorus"] = response_data.pop(k)
                        break

            # 1. Structural Validation
            required_fields = ["verse_1", "chorus", "verse_2", "bridge"]
            missing_fields = [f for f in required_fields if f not in response_data]
            if missing_fields:
                if attempt < max_attempts:
                    logger.warning("Missing required fields %s on attempt %s. Retrying.", missing_fields, attempt)
                    continue
                raise ValueError(f"Missing required fields after retry: {missing_fields}")

            # 2. Schema Leakage Check
            if _has_prompt_schema_leakage(response_data):
                if attempt < max_attempts:
                    logger.warning("Schema instructions leaked as content on attempt %s. Retrying.", attempt)
                    continue
                raise ValueError("Ollama returned lyric schema instructions as content")

            # 3. Japanese Script Presence
            if generation_language in {"japanese", "bilingual"} and not _has_japanese_script(response_data):
                if attempt < max_attempts:
                    logger.warning("Japanese script missing on attempt %s. Retrying.", attempt)
                    continue
                if generation_language == "bilingual":
                    logger.warning("Japanese script missing after final retry; applying rescue hooks.")
                    _add_bilingual_rescue_hooks(response_data, concept, japanese_mix_ratio)
                else:
                    raise ValueError("Japanese lyrics must contain kana or kanji; Romaji alone is invalid.")

            # 4. Chinese Character Leakage Check
            if generation_language in {"japanese", "bilingual"} and _has_chinese_leakage(response_data):
                if attempt < max_attempts:
                    logger.warning("Chinese-script leakage detected on attempt %s. Retrying.", attempt)
                    continue
                raise ValueError("Bilingual lyrics contained Chinese-script leakage after final retry.")

            # 5. Distinctness / Repetitiveness Check
            if not _sections_are_distinct(response_data):
                if attempt < max_attempts:
                    logger.warning("Lyric sections were too repetitive on attempt %s. Retrying.", attempt)
                    continue
                raise ValueError("Lyric sections were too repetitive after retry")

            # Hard checks passed: keep this draft in case a later retry is malformed.
            last_valid_response_data = dict(response_data)

            # 5b. Song development: Verse 2 must move the story on; bridge should climb
            if verse_two_repeats_verse_one(response_data):
                if attempt < max_attempts:
                    logger.warning("Verse 2 repeated Verse 1 on attempt %s. Retrying.", attempt)
                    structure_feedback = (
                        "\n\nREVISION REQUIRED: The previous draft's Verse 2 repeated Verse 1. "
                        "Write a completely new Verse 2 set after the turning point, showing "
                        "consequences and what the new state reveals. Do not reuse any Verse 1 line."
                    )
                    continue
                logger.warning("Verse 2 still repeats Verse 1 after %s attempt(s); keeping draft.", attempt)
            copied = borrowed_lines(response_data)
            if len(copied) > MAX_BORROWED_LINES:
                if attempt < max_attempts:
                    logger.warning(
                        "Draft reused %d line(s) across sections on attempt %s. Retrying.",
                        len(copied), attempt,
                    )
                    structure_feedback = borrowed_lines_feedback(copied)
                    continue
                logger.warning("Draft still reuses %d line(s) across sections; keeping it.", len(copied))
            if bridge_is_underdeveloped(response_data):
                logger.info(
                    "Bridge has fewer than %d sung lines; climax may be thin.",
                    MIN_BRIDGE_SUNG_LINES,
                )

            # 6. Bilingual Ratio Threshold Validation
            if generation_language == "bilingual":
                mix_ok, mix_summary = _bilingual_mix_ok(response_data, japanese_mix_ratio)
                if not mix_ok:
                    last_valid_response_data = dict(response_data)
                    if attempt < max_attempts:
                        logger.warning("Bilingual mix rejected on attempt %s (%s). Retrying.", attempt, mix_summary)
                        continue
                    logger.error("Bilingual lyric mix failed after %s attempts (%s).", max_attempts, mix_summary)
                    raise ValueError(f"Bilingual lyric ratio constraint violated: {mix_summary}")

            # All validations passed
            logger.info(f"Lyric composition succeeded on attempt {attempt}")
            break

        tidy_song_sections(response_data)
        if translate_mode:
            hook_summary = apply_bilingual_hooks(
                response_data,
                japanese_mix_ratio,
                ollama,
                lyric_config.bilingual_max_hook_lines,
                lyric_config.argos_model_dir,
                context=f"{concept.title}: {concept.theme}",
            )
            if not hook_summary["inserted"]:
                logger.warning("No hook lines were translated; the bilingual song stays English.")

        # 7. Japanese learner-cue coverage — deterministic Hepburn backfill.
        # _learning_annotations_ok was previously defined but never enforced,
        # so songs often shipped with little or no Romaji. Small models drop
        # the prompted cues; synthesize them with pykakasi instead of burning
        # another generation round-trip.
        if lyric_language in {"japanese", "bilingual"}:
            for field, value in response_data.items():
                if isinstance(value, str):
                    response_data[field] = _join_split_japanese_acronyms(value)
            # Romaji bracketing, correction and backfill run once, in
            # assemble_suno_prompt, after section normalization. Running them
            # here too created cues from un-normalized lines that then
            # survived next to freshly generated ones.
            cues_ok, cue_summary = _learning_annotations_ok(response_data, lyric_language)
            if not cues_ok:
                logger.info(
                    "Model left Romaji cues below target (%s); assembly will backfill.",
                    cue_summary,
                )
        
        # Enforce uppercase chorus processing programmatically as a safeguard
        processed_chorus = (
            response_data["chorus"]
            if generation_language in {"japanese", "bilingual"}
            else response_data["chorus"].upper()
        )
        
        # Create Lyrics object
        lyrics = Lyrics(
            verse_1=response_data["verse_1"],
            chorus=processed_chorus,
            verse_2=response_data["verse_2"],
            bridge=response_data["bridge"],
            evidence_ids=concept.evidence_ids,
            intro=response_data.get("intro"),
            pre_chorus=response_data.get("pre_chorus", ""),
            drop=response_data.get("drop"),
            solo=response_data.get("solo"),
            outro=response_data.get("outro"),
            breakdown=response_data.get("breakdown"),
        )
        
        logger.info(f"Composed and formatted lyrics for '{concept.title}' successfully.")
        return lyrics
        
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error(f"Failed to parse Ollama lyrics response: {e}. Reverting to formatted fallback.")
        
        return build_fallback_lyrics(concept, lyric_language)


def assemble_suno_prompt(
    concept: SongConcept,
    lyrics: Lyrics,
    domain_knowledge: ReiDomainKnowledge
) -> SunoPrompt:
    """
    Assemble the complete Suno generation prompt with genre tags, BPM, and formatted lyrics.
    
    Optimized to prevent nested structural tag collisions, enforce uppercase velocity, 
    and format text payload blocks cleanly for Suno's parsing engine.
    
    Args:
        concept: The song concept with musical parameters
        lyrics: The structured lyrics sections
        domain_knowledge: Music production knowledge (Suno templates)
        
    Returns:
        SunoPrompt: Complete prompt ready for Suno API submission
    """
    logger.info(f"Assembling Suno prompt for: '{concept.title}'")

    template_key = _select_suno_template_key(concept)

    # Build richer Suno tags string (genre, BPM, texture, production hints)
    suno_tags = _build_rich_suno_tags(concept, domain_knowledge, template_key)
    
    # Check style tag character boundaries (Suno style tags can truncate if overlong)
    if len(suno_tags) > 220:
        logger.warning(f"Suno style tags string length ({len(suno_tags)}) is high. Potential truncation risk.")

    lyric_blocks = _build_suno_lyric_blocks(concept, lyrics)

    # Join structural blocks cleanly with double line breaks
    formatted_lyrics = ensure_suno_quality("\n\n".join(lyric_blocks))
    
    # Create metadata for tracking
    metadata = {
        "theme": concept.theme,
        "mood": concept.mood,
        "bpm": concept.bpm,
        "genre_tags": concept.genre_tags,
        "narrative_arc": concept.narrative_arc,
        "suno_description_prompt": _build_suno_description_prompt(concept),
        "template_used": template_key,
        "has_intro": "[Intro Verse]" in formatted_lyrics,
        "has_pre_chorus": lyrics.pre_chorus is not None,
        "has_drop": "[Drop]\n[Heavy Bass Drop]" in formatted_lyrics,
        "has_solo": "[Solo]" in formatted_lyrics,
        "has_outro": lyrics.outro is not None,
        "style_tag_count": len(_split_csv_descriptors(suno_tags)),
        "style_tags_length": len(suno_tags),
        "lyrics_char_count": len(formatted_lyrics)
        ,"lyric_language": concept.lyric_language
    }
    
    # Create SunoPrompt object
    suno_prompt = SunoPrompt(
        song_id=concept.song_id,
        title=concept.title,
        suno_prompt=suno_tags,
        lyrics=formatted_lyrics,
        metadata=metadata,
        evidence_ids=concept.evidence_ids,
        generated_at=datetime.now().isoformat()
    )
    
    logger.info(f"Assembled Suno prompt: '{suno_prompt.title}' ({len(suno_prompt.lyrics)} chars lyrics)")
    return suno_prompt
