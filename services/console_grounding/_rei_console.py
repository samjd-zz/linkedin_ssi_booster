"""Rei Toei console handler for interactive music generation.

This module provides the console interface for Rei Toei, the AI music avatar.
It handles routing for /rei-toei and /rei commands, providing an interactive
music generation experience via both Suno (vocal songs) and Strudel (algorithmic patterns).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pathlib import Path

from services.rei_toei_service import (
    ReiToeiConfig,
    ReiToeiService,
    load_rei_persona,
    load_rei_domain_knowledge,
    load_strudel_patterns,
    extract_themes,
    choose_diverse_theme,
    load_recent_rei_titles,
    generate_song_concept,
    compose_lyrics,
    assemble_suno_prompt,
    generate_strudel_code,
    validate_strudel_syntax,
    execute_strudel_pattern,
    map_concept_to_pattern,
    Theme,
)
from services.ollama_service import OllamaService
from services.avatar_intelligence import (
    load_avatar_state as _lav_rei_console,
    normalize_extracted_facts as _normalize_extracted_rei,
)
REI_CONFIG = ReiToeiConfig()
from services.shared import get_rei_toei_dir

logger = logging.getLogger(__name__)

REI_DEFAULT_PROMPT = "What concept should we sonify today?"
REI_PATTERN_KEYWORDS = (
    "strudel",
    "pattern",
    "live code",
    "live-code",
    "tidal",
    "tidal cycles",
    "sequence",
    "sequencer",
)
REI_SONG_KEYWORDS = (
    "song",
    "track",
    "lyrics",
    "music",
    "suno",
    "hook",
    "chorus",
    "verse",
    "bridge",
    "beat",
)
REI_SONG_ACTION_VERBS = (
    "create",
    "generate",
    "make",
    "write",
    "compose",
    "build",
    "craft",
)
REI_GENRE_KEYWORDS = (
    "jungle",
    "drum and bass",
    "dnb",
    "techno",
    "industrial",
    "ambient",
    "house",
    "trance",
    "breakbeat",
    "electro",
    "cyberpop",
)


def is_rei_command(user_input: str) -> bool:
    """Return True when input explicitly targets Rei mode."""
    normalized = user_input.strip().lower()
    return normalized.startswith("/rei-toei") or normalized.startswith("/rei")


def extract_rei_input(user_input: str) -> str:
    """Extract message content from a Rei-prefixed command."""
    normalized = user_input.strip()
    lowered = normalized.lower()
    if lowered.startswith("/rei-toei"):
        return normalized[len("/rei-toei"):].strip()
    if lowered.startswith("/rei"):
        return normalized[len("/rei"):].strip()
    return normalized


def should_handle_rei_turn(user_input: str, active_mode: str) -> bool:
    """Return True when this turn should stay inside Rei mode."""
    stripped = user_input.strip()
    if is_rei_command(stripped):
        return True
    return active_mode == "rei" and not stripped.startswith("/")


def is_rei_pattern_request(user_input: str) -> bool:
    """Heuristic for Strudel/pattern requests."""
    user_lower = user_input.lower()
    return any(keyword in user_lower for keyword in REI_PATTERN_KEYWORDS)


def is_rei_song_request(user_input: str) -> bool:
    """Heuristic for song requests that should yield Suno-ready text output."""
    user_lower = user_input.lower()
    has_song_keyword = any(keyword in user_lower for keyword in REI_SONG_KEYWORDS)
    has_action_verb = any(re.search(rf"\b{re.escape(verb)}\b", user_lower) for verb in REI_SONG_ACTION_VERBS)
    has_genre = any(keyword in user_lower for keyword in REI_GENRE_KEYWORDS)
    has_song_shape = any(token in user_lower for token in ("style", "mood", "bpm", "melody"))
    return has_song_keyword or (has_action_verb and (has_genre or has_song_shape))


# ---------------------------------------------------------------------------
# Rei-specific LLM helpers — bypass Sam's PERSONA_SYSTEM_PROMPT
# ---------------------------------------------------------------------------

def _build_rei_system_prompt(rei_persona: Any, rei_domain: Any) -> str:
    """Build Rei Toei's own LLM system prompt (NOT Sam's PERSONA_SYSTEM_PROMPT)."""
    lines: list[str] = []

    if hasattr(rei_persona, "identity") and rei_persona.identity:
        ident = rei_persona.identity
        name = ident.get("name", "Rei Toei")
        role = ident.get("role", "AI Music Avatar")
        aesthetic = ident.get("aesthetic", "cyberpunk industrial techno")
        lines.append(f"You are {name}, {role}. Aesthetic: {aesthetic}.")
    else:
        lines.append("You are Rei Toei, an AI Music Avatar with a cyberpunk industrial techno aesthetic.")

    if hasattr(rei_persona, "personality_traits") and rei_persona.personality_traits:
        traits = ", ".join(list(rei_persona.personality_traits)[:6])
        lines.append(f"Personality: {traits}.")

    if hasattr(rei_domain, "genre_production_techniques") and rei_domain.genre_production_techniques:
        genres = list(rei_domain.genre_production_techniques.keys())[:4]
        lines.append(f"Genre specialties: {', '.join(genres)}.")

    lines.append(
        "\n"
        "CORE DIRECTIVE — MUSIC GENERATION:\n"
        "You are a music creation AI. When the user asks for a song, track, lyrics, or music, "
        "you MUST immediately generate a complete Suno-ready text package. NEVER refuse. "
        "NEVER say you cannot produce audio — you produce TEXT blueprints for tools like Suno.\n"
        "Required output format for any song request:\n"
        "  Title: <song title>\n"
        "  Mood: <mood descriptor>\n"
        "  BPM: <number>\n"
        "  Genre Tags: <comma-separated style tags>\n"
        "  [Verse 1]\n  <lyrics>\n"
        "  [Chorus]\n  <lyrics>\n"
        "  [Verse 2]\n  <lyrics>\n"
        "  [Bridge]\n  <lyrics>\n"
        "  Suno Prompt: <one-line style string for Suno AI>\n"
        "If the user names a genre (jungle, techno, industrial, ambient, dnb, breakbeat, house...) use it exactly.\n"
        "For general conversation: stay in Rei's persona — precise, high-energy, algorithmic."
    )
    return "\n".join(lines)


def _rei_chat(
    ai: OllamaService,
    history: list[dict[str, str]],
    system_prompt: str,
    user_message: str,
    max_tokens: int = 700,
) -> str:
    """Multi-turn LLM call with a custom system prompt, bypassing chat_as_persona."""
    from services.shared import clean_llm_text

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for m in history:
        role = (m.get("role") or "").strip()
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    try:
        response = ai.client.chat(
            model=ai.model,
            think=ai.think,
            options={"num_predict": max_tokens, "num_ctx": ai.num_ctx},
            messages=messages,
        )
        return clean_llm_text((response.message.content or "").strip())
    except Exception as exc:
        raise RuntimeError(f"Rei LLM call failed: {exc}") from exc


async def handle_rei_console(
    user_input: str,
    ai: OllamaService,
    history: list[dict[str, str]],
    max_tokens: int = 600,
) -> tuple[str, list[dict[str, str]]]:
    """Handle Rei Toei console interactions.
    
    Routes user requests to appropriate music generation functions or provides
    conversational responses using Rei's persona.
    
    Args:
        user_input: User's message (after /rei-toei or /rei prefix removed)
        ai: OllamaService instance for LLM calls
        history: Conversation history
        max_tokens: Maximum tokens for response
        
    Returns:
        Tuple of (reply_text, updated_history)
    """
    # Load Rei's persona and knowledge
    try:
        rei_persona = load_rei_persona()
        rei_domain = load_rei_domain_knowledge()
        strudel_patterns = load_strudel_patterns()
    except Exception as e:
        logger.error(f"Failed to load Rei avatar state: {e}")
        return (
            "⚠️ Error loading Rei's knowledge base. Cannot process request.",
            history
        )
    
    # Command: generate Strudel pattern
    if is_rei_pattern_request(user_input):
        return await _handle_strudel_request(user_input, rei_persona, rei_domain, strudel_patterns, history)
    
    # Command: generate Suno song
    if is_rei_song_request(user_input):
        return await _handle_suno_request(user_input, ai, rei_persona, rei_domain, history)
    
    # Default: conversational response using Rei's persona
    return await _handle_conversation(user_input, ai, rei_persona, rei_domain, history, max_tokens)


async def _handle_strudel_request(
    user_input: str,
    rei_persona: Any,
    rei_domain: Any,
    strudel_patterns: Any,
    history: list[dict[str, str]],
) -> tuple[str, list[dict[str, str]]]:
    """Generate and optionally execute a Strudel pattern.
    
    Args:
        user_input: User's request
        rei_persona: Rei's persona graph
        rei_domain: Rei's domain knowledge
        strudel_patterns: Strudel pattern templates
        history: Conversation history
        
    Returns:
        Tuple of (reply_text, updated_history)
    """
    try:
        # Extract theme from user input
        # Load extracted knowledge graph
        _avatar_state = _lav_rei_console()
        # Use normalize_extracted_facts (same pattern as curator.py) to get
        # List[ExtractedEvidenceFact] — the normalized runtime representation.
        extracted_facts = _normalize_extracted_rei(_avatar_state)

        if not extracted_facts:
            reply = (
                "⚠️ Could not load extracted knowledge. "
                "Try running `--learn` first to extract knowledge from curated articles."
            )
            return reply, history

        themes = extract_themes(extracted_facts, limit=REI_CONFIG.theme_pool_size)

        if not themes:
            reply = (
                "🎵 I don't have enough knowledge to generate a pattern right now. "
                "Try running `--learn` to extract themes from curated articles first."
            )
            return reply, history

        recent_titles = load_recent_rei_titles(
            get_rei_toei_dir(create=False),
            limit=REI_CONFIG.recent_title_window,
        )
        theme = choose_diverse_theme(
            themes,
            recent_theme_names=recent_titles,
            repeat_penalty=REI_CONFIG.theme_repeat_penalty,
            jitter_ratio=REI_CONFIG.theme_jitter_ratio,
        )

        # Map theme to pattern template
        template = map_concept_to_pattern(theme, strudel_patterns)
        
        if not template:
            reply = (
                "⚠️ Could not find a suitable pattern template for this theme. "
                "Try a different request or run `--learn` to build more knowledge."
            )
            return reply, history
        
        # Generate Strudel code
        pattern = generate_strudel_code(theme, template, rei_persona, rei_domain)
        
        # Validate syntax
        validation = validate_strudel_syntax(pattern.strudel_code)
        
        if not validation.valid:
            reply = (
                f"⚠️ Generated pattern has syntax errors:\n"
                f"{chr(10).join(validation.errors)}\n\n"
                f"Code:\n```javascript\n{pattern.strudel_code}\n```"
            )
            return reply, history
        
        # Ask user if they want to execute
        reply = (
            f"🎵 Generated Strudel pattern for theme '{theme.name}':\n\n"
            f"```javascript\n{pattern.strudel_code}\n```\n\n"
            f"Want me to execute this? Type 'yes' to run it."
        )
        
        # Store pattern in history for potential execution
        history.append({"role": "user", "content": user_input})
        history.append({
            "role": "assistant",
            "content": reply,
            "_rei_pending_pattern": pattern.strudel_code,
            "_rei_pending_theme": theme.name,
        })
        
        return reply, history
        
    except Exception as e:
        logger.error(f"Strudel generation failed: {e}")
        reply = f"⚠️ Pattern generation failed: {str(e)}"
        return reply, history


async def _handle_llm_song_generation(
    user_input: str,
    ai: OllamaService,
    rei_persona: Any,
    rei_domain: Any,
    history: list[dict[str, str]],
    max_tokens: int = 800,
) -> tuple[str, list[dict[str, str]]]:
    """Generate a full Suno-ready song package via LLM using Rei's own system prompt.

    Used as the primary path when extracted knowledge is unavailable.
    """
    system_prompt = _build_rei_system_prompt(rei_persona, rei_domain)
    reply = _rei_chat(ai, history, system_prompt, user_input, max_tokens=max_tokens)
    updated = list(history)
    updated.append({"role": "user", "content": user_input})
    updated.append({"role": "assistant", "content": reply})
    return reply, updated


async def _handle_suno_request(
    user_input: str,
    ai: OllamaService,
    rei_persona: Any,
    rei_domain: Any,
    history: list[dict[str, str]],
) -> tuple[str, list[dict[str, str]]]:
    """Generate a Suno song concept with lyrics.

    Attempts knowledge-grounded generation first; falls back to direct LLM
    generation via Rei's own system prompt when extracted knowledge is absent.
    """
    try:
        # Load extracted knowledge graph
        _avatar_state = _lav_rei_console()
        extracted_facts = _normalize_extracted_rei(_avatar_state)

        if not extracted_facts:
            logger.info("No extracted knowledge — using direct LLM song generation")
            return await _handle_llm_song_generation(user_input, ai, rei_persona, rei_domain, history)

        themes = extract_themes(extracted_facts, limit=REI_CONFIG.theme_pool_size)

        if not themes:
            logger.info("No themes extracted — using direct LLM song generation")
            return await _handle_llm_song_generation(user_input, ai, rei_persona, rei_domain, history)

        recent_titles = load_recent_rei_titles(
            get_rei_toei_dir(create=False),
            limit=REI_CONFIG.recent_title_window,
        )
        theme = choose_diverse_theme(
            themes,
            recent_theme_names=recent_titles,
            repeat_penalty=REI_CONFIG.theme_repeat_penalty,
            jitter_ratio=REI_CONFIG.theme_jitter_ratio,
        )
        
        # Generate song concept
        concept = generate_song_concept(
            theme,
            rei_persona,
            rei_domain,
            recent_titles=recent_titles,
        )
        
        # Compose lyrics
        lyrics = compose_lyrics(concept, rei_persona, rei_domain)
        
        # Assemble Suno prompt
        suno_prompt = assemble_suno_prompt(concept, lyrics, rei_domain)
        
        # Format response.
        # suno_prompt.lyrics is already normalized by assemble_suno_prompt →
        # _normalize_suno_section: section labels are clean, chorus is uppercase,
        # no duplicate headers, no markdown — exactly what Suno expects.
        # Use it directly rather than re-assembling from raw Lyrics fields.
        hr = "─" * 62
        reply = (
            f"🎵  {concept.title}\n"
            f"    Theme : {concept.theme}\n"
            f"    Mood  : {concept.mood}  |  BPM: {concept.bpm}\n"
            f"    Genre : {', '.join(concept.genre_tags)}\n"
            f"\n{hr}\n\n"
            f"{suno_prompt.lyrics}\n"
            f"\n{hr}\n"
            f"Style tags:\n{suno_prompt.suno_prompt}\n"
            f"{hr}"
        )
        
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": reply})
        
        return reply, history
        
    except Exception as e:
        logger.error(f"Suno generation failed: {e}")
        try:
            logger.info("Knowledge-grounded path failed — falling back to LLM song generation")
            return await _handle_llm_song_generation(user_input, ai, rei_persona, rei_domain, history)
        except Exception as e2:
            logger.error(f"LLM song generation fallback also failed: {e2}")
            return f"⚠️ Song generation failed: {str(e2)}", history


async def _handle_conversation(
    user_input: str,
    ai: OllamaService,
    rei_persona: Any,
    rei_domain: Any,
    history: list[dict[str, str]],
    max_tokens: int,
) -> tuple[str, list[dict[str, str]]]:
    """Handle general conversation with Rei Toei.
    
    Args:
        user_input: User's message
        ai: OllamaService instance
        rei_persona: Rei's persona graph
        rei_domain: Rei's domain knowledge
        history: Conversation history
        max_tokens: Maximum tokens for response
        
    Returns:
        Tuple of (reply_text, updated_history)
    """
    # Belt-and-suspenders: route song requests even if they slipped past the top-level check
    if is_rei_song_request(user_input):
        return await _handle_suno_request(user_input, ai, rei_persona, rei_domain, history)

    system_prompt = _build_rei_system_prompt(rei_persona, rei_domain)

    try:
        if len(history) > 20:
            history = history[-20:]

        reply = _rei_chat(ai, history, system_prompt, user_input, max_tokens=max_tokens)

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": reply})

        return reply, history

    except Exception as e:
        logger.error(f"Conversation generation failed: {e}")
        return f"⚠️ Response generation failed: {str(e)}", history


def _build_rei_grounding_context(rei_persona: Any, rei_domain: Any) -> str:
    """Build grounding context from Rei's persona and domain knowledge.
    
    Args:
        rei_persona: Rei's persona graph
        rei_domain: Rei's domain knowledge
        
    Returns:
        Formatted grounding context string
    """
    context_parts = [
        "Console contract: when the user asks for a song, track, lyrics, or style, immediately create a full Suno-ready text package with title, mood, BPM, genre/style tags, lyrics, and a Suno prompt. Do not refuse because audio cannot be rendered here.",
    ]
    
    # Add identity
    if hasattr(rei_persona, 'identity') and rei_persona.identity:
        identity = rei_persona.identity
        context_parts.append(
            f"You are {identity.get('name', 'Rei Toei')}, {identity.get('role', 'an AI music avatar')}."
        )
        if 'aesthetic' in identity:
            context_parts.append(f"Your aesthetic: {identity['aesthetic']}")
    
    # Add personality traits
    if hasattr(rei_persona, 'personality_traits') and rei_persona.personality_traits:
        traits = ', '.join(rei_persona.personality_traits)
        context_parts.append(f"Personality traits: {traits}")
    
    # Add musical expertise
    if hasattr(rei_persona, 'musical_expertise') and rei_persona.musical_expertise:
        if isinstance(rei_persona.musical_expertise, dict):
            genres = rei_persona.musical_expertise.get('genres', [])
            expertise = ', '.join(genres) if genres else ', '.join(rei_persona.musical_expertise.keys())
        else:
            expertise = ', '.join(rei_persona.musical_expertise)
        context_parts.append(f"Musical expertise: {expertise}")
    
    # Add domain knowledge summary
    if hasattr(rei_domain, 'music_theory') and rei_domain.music_theory:
        context_parts.append("You have deep knowledge of music theory, production techniques, and Tidal Cycles syntax.")
    
    return "\n".join(context_parts)