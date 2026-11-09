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
    _backfill_missing_romaji_cues as _backfill_missing_romaji_cues,
    _bilingual_mix_ok,
    _has_chinese_leakage,
    _has_japanese_script,
    _learning_annotation_stats as _learning_annotation_stats,
    _learning_annotations_ok,
    _sections_are_distinct,
    chorus_line_deficit,
    chorus_revision_feedback,
)
from services.rei_toei._lyric_prompts import build_lyric_prompts
from services.rei_toei._lyric_repetition import expand_payload_word_count_markers
from services.rei_toei._lyric_romaji import (
    _generate_hepburn_romaji as _generate_hepburn_romaji,
    _join_split_japanese_acronyms,
    _ROMAJI_FIRST_RE as _ROMAJI_FIRST_RE,
    _strip_cue_noise as _strip_cue_noise,
    _verify_and_correct_romaji_lines as _verify_and_correct_romaji_lines,
)
from services.rei_toei._models import (
    LyricCompositionError,
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
    missing_required_sections,
    missing_sections_feedback,
    verse_two_repeats_verse_one,
)
from services.rei_toei._style_policy import apply_song_style, fit_style_tempo, style_template_key
from services.rei_toei._song_tidy import tidy_song_sections
from services.rei_toei._stage_policy import load_stage_policy
from services.rei_toei._suno_blocks import (
    _append_normalized_section as _append_normalized_section,
    _build_suno_lyric_blocks,
    _normalize_freeform_suno_reply as _normalize_freeform_suno_reply,
)
from services.rei_toei._suno_concept import generate_song_concept as generate_song_concept
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
    record_rei_title as record_rei_title,
    resolve_lyric_language as resolve_lyric_language,
)

logger = logging.getLogger(__name__)
MAX_LYRIC_ATTEMPTS = 5


def _describe_lyric_error(exc: ValueError | KeyError) -> str:
    if isinstance(exc, json.JSONDecodeError):
        reason = "invalid backslash escape" if exc.msg == r"Invalid \escape" else exc.msg
        return f"{reason} in JSON (line {exc.lineno}, column {exc.colno})"
    return str(exc).rstrip(".")


def compose_lyrics(
    concept: SongConcept,
    persona: ReiPersonaGraph,
    domain_knowledge: ReiDomainKnowledge,
    sam_persona: Optional["PersonaGraph"] = None,
    ollama: Optional["OllamaService"] = None
) -> Lyrics:
    """
    Compose structured lyrics using Rei's voice and the selected musical profile.
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

    Raises:
        LyricCompositionError: All five drafts failed parsing or quality checks.
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
    stage_policy = load_stage_policy(domain_knowledge.lyrical_structure)
    apply_song_style(concept, stage_policy.style)
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
        max_attempts = MAX_LYRIC_ATTEMPTS
        response_data: Dict[str, Any] = {}
        structure_feedback = ""
        format_feedback = ""

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
                    "Use only the enabled sung fields from the active profile: "
                    + ", ".join(rule.field for rule in stage_policy.sections if rule.content == "sung")
                    + ". Do not add disabled sections or lyrics to instrumental sections.\n"
                    "- In enabled verses, use English narrative and one Japanese line (Kanji/Kana) per stanza.\n"
                    "- If included, make the chorus a Japanese hook followed by a concise English sung echo.\n"
                    "- If included, alternate Japanese and English in the bridge; mix both in other sung sections."
                )
            else:
                attempt_user_prompt = user_prompt
            if structure_feedback:
                attempt_user_prompt += structure_feedback
            attempt_user_prompt += format_feedback

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
                if "chorus" not in response_data:
                    for k in list(response_data.keys()):
                        if "chorus" in k or "refrain" in k:
                            response_data["chorus"] = response_data.pop(k)
                            break
                response_data = {
                    field: value for field, value in response_data.items()
                    if stage_policy.rule(field) is not None
                }
                expand_payload_word_count_markers(response_data, stage_policy)
            except (ValueError, KeyError) as exc:
                if attempt < max_attempts:
                    logger.warning(
                        "Ollama lyric draft %s/%s was rejected: %s. "
                        "Discarding it and requesting a fresh draft (attempt %s/%s).",
                        attempt, max_attempts, _describe_lyric_error(exc), attempt + 1, max_attempts,
                    )
                    format_feedback = (
                        "\n\nREVISION REQUIRED: Return one complete JSON object containing "
                        "finished song lyrics, not schema instructions or a JSON array. "
                        "Write the hook words again as sung lyrics, not a word-count placeholder."
                    )
                    continue
                raise

            # 1. Structural Validation
            # Judge sections as they will ship: tidying can empty a cue-only section.
            gate_view = dict(response_data)
            tidy_song_sections(gate_view, stage_policy)
            missing_fields = missing_required_sections(gate_view, stage_policy)
            if missing_fields:
                if attempt < max_attempts:
                    logger.warning("Missing required fields %s on attempt %s. Retrying.", missing_fields, attempt)
                    structure_feedback = missing_sections_feedback(missing_fields, stage_policy)
                    continue
                raise ValueError(f"Missing required fields after final retry: {missing_fields}")

            # 2. Schema Leakage Check
            if _has_prompt_schema_leakage(response_data):
                if attempt < max_attempts:
                    logger.warning("Schema instructions leaked as content on attempt %s. Retrying.", attempt)
                    structure_feedback = (
                        "\n\nREVISION REQUIRED: Write actual lyrics in every enabled field. "
                        "Do not copy the JSON schema's descriptions or formatting instructions."
                    )
                    continue
                raise ValueError("Ollama returned lyric schema instructions as content")

            # 3. Japanese Script Presence
            if generation_language in {"japanese", "bilingual"} and not _has_japanese_script(response_data):
                if attempt < max_attempts:
                    logger.warning("Japanese script missing on attempt %s. Retrying.", attempt)
                    continue
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

            # 5b. Song development: Verse 2 must move the story on; bridge should climb
            if verse_two_repeats_verse_one(response_data, stage_policy.style.verse_repeat_threshold):
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
            if len(copied) > stage_policy.style.max_borrowed_lines:
                if attempt < max_attempts:
                    logger.warning(
                        "Draft reused %d line(s) across sections on attempt %s. Retrying.",
                        len(copied), attempt,
                    )
                    structure_feedback = borrowed_lines_feedback(copied)
                    continue
                logger.warning("Draft still reuses %d line(s) across sections; keeping it.", len(copied))
            bridge_rule = stage_policy.rule("bridge")
            if bridge_rule and bridge_rule.content == "sung" and gate_view.get("bridge") and bridge_is_underdeveloped(gate_view, stage_policy.style.min_bridge_lines):
                logger.info(
                    "Bridge has fewer than %d sung lines; climax may be thin.",
                    stage_policy.style.min_bridge_lines,
                )

            short_chorus = chorus_line_deficit(gate_view.get("chorus"), stage_policy)
            if short_chorus is not None:
                if attempt < max_attempts:
                    logger.warning(
                        "Chorus has only %d distinct sung line(s) on attempt %s; retrying with at least %d.",
                        short_chorus, attempt, stage_policy.style.min_chorus_lines,
                    )
                    structure_feedback = chorus_revision_feedback(short_chorus, stage_policy.style.min_chorus_lines)
                    continue
                raise ValueError(
                    f"Chorus remained under {stage_policy.style.min_chorus_lines} sung lines after final retry."
                )

            # 6. Bilingual Ratio Threshold Validation
            if generation_language == "bilingual":
                mix_ok, mix_summary = _bilingual_mix_ok(response_data, japanese_mix_ratio)
                if not mix_ok:
                    if attempt < max_attempts:
                        logger.warning("Bilingual mix rejected on attempt %s (%s). Retrying.", attempt, mix_summary)
                        continue
                    logger.error("Bilingual lyric mix failed after %s attempts (%s).", max_attempts, mix_summary)
                    raise ValueError(f"Bilingual lyric ratio constraint violated: {mix_summary}")

            # All validations passed
            logger.info(f"Lyric composition succeeded on attempt {attempt}")
            break

        tidy_song_sections(response_data, stage_policy)
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
            response_data.get("chorus") or ""
            if generation_language in {"japanese", "bilingual"} or not stage_policy.style.uppercase_chorus
            else (response_data.get("chorus") or "").upper()
        )
        
        # Create Lyrics object
        lyrics = Lyrics(
            verse_1=response_data.get("verse_1") or "",
            chorus=processed_chorus,
            verse_2=response_data.get("verse_2") or "",
            bridge=response_data.get("bridge") or "",
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
        
    except (ValueError, KeyError) as exc:
        message = (
            f"Lyric composition failed after {attempt} attempts: {_describe_lyric_error(exc)}. "
            "No song was generated; please try again."
        )
        logger.error("%s", message)
        raise LyricCompositionError(message) from exc


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

    stage_policy = load_stage_policy(domain_knowledge.lyrical_structure)
    apply_song_style(concept, stage_policy.style)
    template_key = style_template_key(stage_policy.style, domain_knowledge, _select_suno_template_key(concept))
    lyric_blocks = _build_suno_lyric_blocks(concept, lyrics, stage_policy)

    # Join structural blocks cleanly with double line breaks
    formatted_lyrics = ensure_suno_quality("\n\n".join(lyric_blocks), stage_policy)

    # The concept BPM predates the lyrics; let the finished lines set the tempo.
    # concept.bpm is updated so callers display the BPM the tags carry.
    tempo = fit_style_tempo(concept, formatted_lyrics, domain_knowledge, stage_policy.style)

    # Build richer Suno tags string (genre, BPM, delivery, texture, production hints)
    suno_tags = _build_rich_suno_tags(
        concept, domain_knowledge, template_key, delivery=tempo.delivery, style=stage_policy.style
    )

    # Check style tag character boundaries (Suno style tags can truncate if overlong)
    if len(suno_tags) > 220:
        logger.warning(f"Suno style tags string length ({len(suno_tags)}) is high. Potential truncation risk.")
    
    # Create metadata for tracking
    metadata = {
        "theme": concept.theme,
        "mood": concept.mood,
        "bpm": concept.bpm,
        "concept_bpm": tempo.concept_bpm,
        "median_line_syllables": tempo.median_syllables,
        "vocal_delivery": tempo.delivery,
        "genre_tags": concept.genre_tags,
        "narrative_arc": concept.narrative_arc,
        "suno_description_prompt": _build_suno_description_prompt(concept, stage_policy.style),
        "template_used": template_key,
        "stage_cue_profile": stage_policy.name,
        **{
            f"has_{field}": bool(
                (rule := stage_policy.rule(field)) and f"[{rule.label}]" in formatted_lyrics
            )
            for field in ("intro", "pre_chorus", "drop", "solo", "outro")
        },
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
