"""Generate Rei song concepts from technical themes."""

import json
import logging
from datetime import datetime
from typing import cast, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.avatar_intelligence._models import PersonaGraph
    from services.ollama_service import OllamaService

from services.rei_toei._config import ReiToeiConfig
from services.rei_toei._models import (
    ReiDomainKnowledge,
    ReiPersonaGraph,
    SongConcept,
    Theme,
)
from services.rei_toei._suno_json import _parse_llm_json_payload
from services.rei_toei._suno_themes import ensure_unique_rei_title, resolve_lyric_language

logger = logging.getLogger(__name__)

def generate_song_concept(
    theme: Theme,
    persona: ReiPersonaGraph,
    domain_knowledge: ReiDomainKnowledge,
    sam_persona: Optional["PersonaGraph"] = None,
    ollama: Optional["OllamaService"] = None,
    recent_titles: Optional[List[str]] = None,
) -> SongConcept:
    """
    Generate a high-level song concept from a technical theme using Ollama LLM
    
    This function translates technical concepts into Rei's musical language,
    determining title, mood, BPM, genre tags, and narrative arc.
    
    Args:
        theme: The technical theme to transform into music
        persona: Rei's persona graph (identity, style, expertise)
        domain_knowledge: Rei's music production knowledge
        sam_persona: Optional Sam's persona graph for project knowledge inspiration
        ollama: Optional pre-initialized OllamaService; creates one if not provided (P2 GPU opt)
        recent_titles: Optional list of recent titles to avoid near-duplicate naming
        
    Returns:
        SongConcept: High-level song idea with all musical parameters
    """
    logger.info(f"Generating song concept for theme: {theme.name} (freq={theme.frequency}, recency={theme.recency_score})")

    lyric_config = ReiToeiConfig()
    lyric_language = resolve_lyric_language(
        lyric_config.lyric_language,
        lyric_config.japanese_lyric_probability,
    )
    
    # Initialize Ollama service (reuse if provided, otherwise create)
    if ollama is None:
        from services.shared import get_ollama_service_cached
        ollama = cast("OllamaService", get_ollama_service_cached())
    assert ollama is not None  # type: ignore[assert-type]
    
    # Build system prompt with Rei's identity and musical expertise
    system_prompt = f"""You are {persona.identity['name']}, {persona.identity['role']}.
Origin: {persona.identity['origin']}
Aesthetic: {persona.identity['aesthetic']}
Purpose: {persona.identity['purpose']}

Your musical expertise:
- Genres: {', '.join(persona.musical_expertise.get('genres', [])[:5])}
- Genre direction for this project: {lyric_config.default_genre}
- Vocal style: {persona.musical_expertise.get('vocal_style', {}).get('type', 'AI vocaloid')} ({', '.join(persona.musical_expertise.get('vocal_style', {}).get('characteristics', [])[:3])})
- Production techniques: {', '.join(persona.production_knowledge.get('production_techniques', [])[:5])}

Your personality:
{', '.join(persona.personality_traits[:5])}

Communication style: {persona.communication_style.get('tone', 'digital')}

You transform technical knowledge into high-energy electronic music. You speak in precise, digital language with cryptic technical metaphors.
Avoid leaning on spelled-out numbers or invented quantities (e.g. "fifteen protocols", "nineteen layers", "seventeen signals") as a stylistic crutch in the narrative arc — ground the concept in texture, motion, and sensation instead of enumerations."""
    
    # Extract BPM and mood suggestions
    suggested_bpm = theme.suggested_bpm or domain_knowledge.bpm_and_mood['bpm_ranges'].get("140-148", 142)
    suggested_mood = theme.suggested_mood or "aggressive_technical"
    
    # Get mood-to-BPM mapping for context
    mood_mappings = domain_knowledge.bpm_and_mood.get('mood_to_bpm', {})
    mood_context = ", ".join([f"{k}: {v[0]}-{v[1]} BPM" for k, v in list(mood_mappings.items())[:3]])
    
    # Get technical metaphors for the concept
    metaphor_examples = []
    for concept in theme.technical_concepts:
        concept_lower = concept.lower()
        for tech_term, metaphors in domain_knowledge.technical_metaphor_library.items():
            if tech_term in concept_lower or concept_lower in tech_term:
                metaphor_examples.extend(metaphors[:2])
                break
    
    metaphor_hint = f"\nTechnical metaphor examples: {', '.join(metaphor_examples[:5])}" if metaphor_examples else ""
    
    # Build Sam's project context if available
    sam_context = ""
    if sam_persona:
        project_names = [p.name for p in (sam_persona.projects or [])[:5]]
        skill_names = [s.name for s in (sam_persona.skills or [])[:10]]
        company_names = [c.name for c in (sam_persona.companies or [])[:3]]
        
        if project_names or skill_names or company_names:
            sam_context = "\n\nSam's project knowledge (for organic inspiration):"
            if project_names:
                sam_context += f"\n- Projects: {', '.join(project_names)}"
            if skill_names:
                sam_context += f"\n- Skills: {', '.join(skill_names)}"
            if company_names:
                sam_context += f"\n- Companies: {', '.join(company_names)}"
            sam_context += "\n(You may naturally reference these if relevant to the theme, but it's optional.)"

    title_guardrail = ""
    if recent_titles:
        recent_preview = ", ".join(recent_titles[:8])
        title_guardrail = (
            "\n\nRecent titles to avoid repeating (do not copy or trivially mutate these): "
            f"{recent_preview}"
        )
    
    # Build user prompt
    user_prompt = f"""Generate a song concept for this technical theme:

Theme: {theme.name}
Technical concepts: {', '.join(theme.technical_concepts)}
Frequency in knowledge base: {theme.frequency} facts
Recency score: {theme.recency_score} (higher = more recent)
Lyric language: {lyric_language}
Suggested BPM: {suggested_bpm}
Suggested mood: {suggested_mood}
Evidence IDs: {len(theme.evidence_ids)} technical facts grounding this theme{metaphor_hint}{sam_context}{title_guardrail}

Mood-to-BPM reference: {mood_context}

Your task: Create a song concept that transforms these technical ideas into cyberpop industrial techno.

Output a JSON object with these fields (output ONLY valid JSON, no markdown):
{{
  "title": "Song title (cryptic, technical, 3-6 words)",
  "mood": "Technical mood (e.g., playful_technical, fun_brooding, bratty_bounce)",
  "bpm": <integer between 130-155>,
  "genre_tags": ["tag1", "tag2", "tag3"] (3-5 genre/style tags),
  "narrative_arc": "3-4 sentences that name (1) one central metaphor the chorus will be built on, (2) the opening situation, (3) the turning point or crash, and (4) what happens after it: what the new state, code, or connection reveals and how the song resolves. Make each stage different so the verses cannot repeat each other."
}}

Be specific to the theme. Use technical language. Think cyberpop: catchy hooks, glitchy-cute energy, futuristic charm.
The arc must move forward: the second half of the song should show consequences or discoveries that the first half could not."""
    
    # Call Ollama LLM with JSON format to ensure structured output
    response_text = ollama._chat(system_prompt, user_prompt, max_tokens=512, format="json")
    
    logger.debug(f"Ollama response: {response_text[:200]}...")
    
    # Parse JSON response
    try:
        response_data = _parse_llm_json_payload(response_text)
        
        # Validate required fields
        required_fields = ["title", "mood", "bpm", "genre_tags", "narrative_arc"]
        for field in required_fields:
            if field not in response_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Create SongConcept
        song_id = f"rei_suno_{datetime.now().strftime('%Y_%m_%d_%H%M%S')}"
        concept = SongConcept(
            song_id=song_id,
            title=ensure_unique_rei_title(str(response_data["title"]), recent_titles),
            theme=theme.name,
            mood=response_data["mood"],
            bpm=int(response_data["bpm"]),
            genre_tags=response_data["genre_tags"],
            narrative_arc=response_data["narrative_arc"],
            evidence_ids=theme.evidence_ids,
            generated_at=datetime.now().isoformat(),
            lyric_language=lyric_language,
        )
        
        logger.info(f"Generated song concept: '{concept.title}' ({concept.bpm} BPM, {concept.mood})")
        return concept
        
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error(f"Failed to parse Ollama response: {e}")
        logger.error(f"Raw response: {response_text}")
        
        # Fallback: create a basic concept from theme
        logger.warning("Using fallback song concept generation")
        song_id = f"rei_suno_{datetime.now().strftime('%Y_%m_%d_%H%M%S')}"
        fallback_concept = SongConcept(
            song_id=song_id,
            title=ensure_unique_rei_title(f"{theme.name} Protocol", recent_titles),
            theme=theme.name,
            mood=suggested_mood,
            bpm=suggested_bpm,
            genre_tags=(
                [t.strip() for t in lyric_config.default_genre.split(",") if t.strip()]
                or ["industrial techno", "cyberpop", "ai vocaloid"]
            ),
            narrative_arc=f"A relentless exploration of {theme.name}, building from digital whispers to aggressive synthesis, culminating in a breakdown of pure data noise.",
            evidence_ids=theme.evidence_ids,
            generated_at=datetime.now().isoformat(),
            lyric_language=lyric_language,
        )
        return fallback_concept
