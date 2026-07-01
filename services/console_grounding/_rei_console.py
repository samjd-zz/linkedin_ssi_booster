"""Rei Toei console handler for interactive music generation.

This module provides the console interface for Rei Toei, the AI music avatar.
It handles routing for /rei-toei and /rei commands, providing an interactive
music generation experience via both Suno (vocal songs) and Strudel (algorithmic patterns).
"""

from __future__ import annotations

import logging
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
    
    # Check for specific music generation commands
    user_lower = user_input.lower()
    
    # Command: generate Strudel pattern
    if any(keyword in user_lower for keyword in ["strudel", "pattern", "live code", "tidal"]):
        return await _handle_strudel_request(user_input, rei_persona, rei_domain, strudel_patterns, history)
    
    # Command: generate Suno song
    if any(keyword in user_lower for keyword in ["song", "suno", "lyrics", "music"]):
        return await _handle_suno_request(user_input, rei_persona, rei_domain, history)
    
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


async def _handle_suno_request(
    user_input: str,
    rei_persona: Any,
    rei_domain: Any,
    history: list[dict[str, str]],
) -> tuple[str, list[dict[str, str]]]:
    """Generate a Suno song concept with lyrics.
    
    Args:
        user_input: User's request
        rei_persona: Rei's persona graph
        rei_domain: Rei's domain knowledge
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
                "🎵 I need more knowledge to write a song. "
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
        
        # Format response
        reply = (
            f"🎵 Song Concept: {concept.title}\n"
            f"Theme: {concept.theme}\n"
            f"Mood: {concept.mood} | BPM: {concept.bpm} | Genre: {', '.join(concept.genre_tags)}\n\n"
            f"**Lyrics:**\n"
            f"[Verse 1]\n{lyrics.verse_1}\n\n"
            f"[Chorus]\n{lyrics.chorus}\n\n"
            f"[Verse 2]\n{lyrics.verse_2}\n\n"
            f"[Bridge]\n{lyrics.bridge}\n\n"
        )
        
        if lyrics.breakdown:
            reply += f"[Breakdown]\n{lyrics.breakdown}\n\n"
        
        reply += f"\n**Suno Prompt:**\n{suno_prompt.suno_prompt}"
        
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": reply})
        
        return reply, history
        
    except Exception as e:
        logger.error(f"Suno generation failed: {e}")
        reply = f"⚠️ Song generation failed: {str(e)}"
        return reply, history


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
    try:
        # Build grounding context from Rei's persona and domain knowledge
        grounding_context = _build_rei_grounding_context(rei_persona, rei_domain)
        
        # Add user message to history
        history.append({"role": "user", "content": user_input})
        
        # Trim history if too long
        if len(history) > 20:
            history = history[-20:]
        
        # Generate response using Rei's persona
        # Note: We use chat_as_persona but with Rei's context
        reply = ai.chat_as_persona(history, grounding_context=grounding_context, max_tokens=max_tokens)
        
        # Add assistant response to history
        history.append({"role": "assistant", "content": reply})
        
        return reply, history
        
    except Exception as e:
        logger.error(f"Conversation generation failed: {e}")
        reply = f"⚠️ Response generation failed: {str(e)}"
        return reply, history


def _build_rei_grounding_context(rei_persona: Any, rei_domain: Any) -> str:
    """Build grounding context from Rei's persona and domain knowledge.
    
    Args:
        rei_persona: Rei's persona graph
        rei_domain: Rei's domain knowledge
        
    Returns:
        Formatted grounding context string
    """
    context_parts = []
    
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
        expertise = ', '.join(rei_persona.musical_expertise)
        context_parts.append(f"Musical expertise: {expertise}")
    
    # Add domain knowledge summary
    if hasattr(rei_domain, 'music_theory') and rei_domain.music_theory:
        context_parts.append("You have deep knowledge of music theory, production techniques, and Tidal Cycles syntax.")
    
    return "\n".join(context_parts)