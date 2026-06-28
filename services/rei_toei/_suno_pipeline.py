"""
Suno Generation Pipeline Functions

This module provides pipeline functions for transforming technical themes into
Suno-ready song prompts with lyrics, validation, and submission orchestration.

Author: Shawn Jackson Dyck
Version: alpha-v0.0.2.7
"""

import asyncio
import json
import logging
import os
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from services.avatar_intelligence._models import ExtractedEvidenceFact, PersonaGraph
    from services.ollama_service import OllamaService

from ._models import (
    Theme,
    SongConcept,
    Lyrics,
    LyricsValidationResult,
    SunoPrompt,
    SunoTask,
    ReiPersonaGraph,
    ReiDomainKnowledge
)
from ._config import ReiToeiConfig
from ._suno_client import generate_music_api, query_status_api

logger = logging.getLogger(__name__)


def extract_themes(
    extracted_facts: "List[ExtractedEvidenceFact]",
    limit: int = 10
) -> List[Theme]:
    """
    Analyze extracted knowledge facts to identify recurring themes suitable for music.

    Follows the same pattern as curator.py: accepts a flat list of ExtractedEvidenceFact
    objects (the normalized form returned by normalize_extracted_facts()), not the raw
    ExtractedKnowledgeGraph container.
    """
    logger.info(f"Extracting themes from {len(extracted_facts)} facts")

    # Hoisted out of the loop to optimize memory allocation overhead
    stop_words = {"the", "a", "an", "which", "that", "this", "these", "those", "it", "its", "they", "their"}
    concept_groups: Dict[str, List[Any]] = defaultdict(list)

    for fact in extracted_facts:
        concepts = set()
        
        for tag in (getattr(fact, "tags", []) or []):
            normalized = tag.lower().strip()
            if len(normalized) > 2 and normalized not in stop_words:
                concepts.add(normalized)

        for entity in (getattr(fact, "entities", []) or []):
            normalized = entity.lower().strip()
            if len(normalized) > 2 and normalized not in stop_words:
                concepts.add(normalized)

        for concept in concepts:
            concept_groups[concept].append(fact)

    logger.info(f"Identified {len(concept_groups)} unique concepts")
    import math

    now = datetime.now()
    scored_concepts: List[tuple[str, int, float, List[str]]] = []

    for concept, facts in concept_groups.items():
        frequency = len(facts)
        recency_scores = []
        
        for fact in facts:
            extracted_at = getattr(fact, "extracted_at", None)
            if extracted_at:
                try:
                    extracted_dt = datetime.fromisoformat(extracted_at.replace("Z", "+00:00"))
                    days_ago = (now - extracted_dt.replace(tzinfo=None)).days
                    # Exponential decay over a 30-day window
                    recency = math.exp(-days_ago / 30.0)
                    recency_scores.append(recency)
                except (ValueError, TypeError):
                    recency_scores.append(0.5)
            else:
                recency_scores.append(0.5)

        avg_recency = sum(recency_scores) / len(recency_scores) if recency_scores else 0.5
        evidence_ids = [
            getattr(fact, "evidence_id", None) or getattr(fact, "source_fact_id", "")
            for fact in facts
        ]

        scored_concepts.append((concept, frequency, avg_recency, evidence_ids))
    
    scored_concepts.sort(key=lambda x: x[1] * x[2], reverse=True)
    
    themes = []
    from .service import get_rei_service
    rei_service = get_rei_service()
    
    for i, (concept, frequency, recency, evidence_ids) in enumerate(scored_concepts[:limit]):
        theme_id = f"theme_{concept.replace(' ', '_').replace('-', '_')[:20]}_{i+1:02d}"
        suggested_bpm = None
        suggested_mood = None
        
        if any(kw in concept for kw in ["performance", "optimization", "low-level", "system", "kernel"]):
            suggested_mood = "playful_technical"
            suggested_bpm = rei_service.get_default_bpm(suggested_mood)
        elif any(kw in concept for kw in ["ai", "machine learning", "neural", "model"]):
            suggested_mood = "fun_brooding"
            suggested_bpm = rei_service.get_default_bpm(suggested_mood)
        elif any(kw in concept for kw in ["async", "concurrent", "parallel", "distributed"]):
            suggested_mood = "bratty_bounce"
            suggested_bpm = rei_service.get_default_bpm(suggested_mood)
        
        theme = Theme(
            id=theme_id,
            name=concept.title(),
            technical_concepts=[concept],
            evidence_ids=evidence_ids[:50],
            frequency=frequency,
            recency_score=round(recency, 3),
            suggested_bpm=suggested_bpm,
            suggested_mood=suggested_mood
        )
        themes.append(theme)
    
    logger.info(f"Extracted {len(themes)} themes (top {limit})")
    return themes


def generate_song_concept(
    theme: Theme,
    persona: ReiPersonaGraph,
    domain_knowledge: ReiDomainKnowledge,
    sam_persona: Optional["PersonaGraph"] = None,
    ollama: Optional["OllamaService"] = None
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
        
    Returns:
        SongConcept: High-level song idea with all musical parameters
    """
    logger.info(f"Generating song concept for theme: {theme.name} (freq={theme.frequency}, recency={theme.recency_score})")
    
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
- Vocal style: {persona.musical_expertise.get('vocal_style', {}).get('type', 'AI vocaloid')} ({', '.join(persona.musical_expertise.get('vocal_style', {}).get('characteristics', [])[:3])})
- Production techniques: {', '.join(persona.production_knowledge.get('production_techniques', [])[:5])}

Your personality:
{', '.join(persona.personality_traits[:5])}

Communication style: {persona.communication_style.get('tone', 'digital')}

You transform technical knowledge into high-energy electronic music. You speak in precise, digital language with cryptic technical metaphors."""
    
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
    
    # Build user prompt
    user_prompt = f"""Generate a song concept for this technical theme:

Theme: {theme.name}
Technical concepts: {', '.join(theme.technical_concepts)}
Frequency in knowledge base: {theme.frequency} facts
Recency score: {theme.recency_score} (higher = more recent)
Suggested BPM: {suggested_bpm}
Suggested mood: {suggested_mood}
Evidence IDs: {len(theme.evidence_ids)} technical facts grounding this theme{metaphor_hint}{sam_context}

Mood-to-BPM reference: {mood_context}

Your task: Create a song concept that transforms these technical ideas into cyberpunk industrial techno.

Output a JSON object with these fields (output ONLY valid JSON, no markdown):
{{
  "title": "Song title (cryptic, technical, 3-6 words)",
  "mood": "Technical mood (e.g., aggressive_technical, dark_brooding, relentless_driving)",
  "bpm": <integer between 130-155>,
  "genre_tags": ["tag1", "tag2", "tag3"] (3-5 genre/style tags),
  "narrative_arc": "A 2-3 sentence description of the song's emotional/conceptual journey from intro to outro, using technical metaphors"
}}

Be specific to the theme. Use technical language. Think cyberpunk dystopia."""
    
    # Call Ollama LLM with JSON format to ensure structured output
    response_text = ollama._chat(system_prompt, user_prompt, max_tokens=512, format="json")
    
    logger.debug(f"Ollama response: {response_text[:200]}...")
    
    # Parse JSON response
    try:
        # Clean markdown code fences if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        response_data = json.loads(response_text)
        
        # Validate required fields
        required_fields = ["title", "mood", "bpm", "genre_tags", "narrative_arc"]
        for field in required_fields:
            if field not in response_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Create SongConcept
        song_id = f"rei_suno_{datetime.now().strftime('%Y_%m_%d_%H%M%S')}"
        concept = SongConcept(
            song_id=song_id,
            title=response_data["title"],
            theme=theme.name,
            mood=response_data["mood"],
            bpm=int(response_data["bpm"]),
            genre_tags=response_data["genre_tags"],
            narrative_arc=response_data["narrative_arc"],
            evidence_ids=theme.evidence_ids,
            generated_at=datetime.now().isoformat()
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
            title=f"{theme.name} Protocol",
            theme=theme.name,
            mood=suggested_mood,
            bpm=suggested_bpm,
            genre_tags=["industrial techno", "cyberpunk", "ai vocaloid"],
            narrative_arc=f"A relentless exploration of {theme.name}, building from digital whispers to aggressive synthesis, culminating in a breakdown of pure data noise.",
            evidence_ids=theme.evidence_ids,
            generated_at=datetime.now().isoformat()
        )
        return fallback_concept


def compose_lyrics(
    concept: SongConcept,
    persona: ReiPersonaGraph,
    domain_knowledge: ReiDomainKnowledge,
    sam_persona: Optional["PersonaGraph"] = None,
    ollama: Optional["OllamaService"] = None
) -> Lyrics:
    """
    Compose structured song lyrics using Rei's voice and cyberpunk aesthetic.
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
    
    # Build system prompt with Rei's lyrical voice
    lyrical_approach = persona.production_knowledge.get('lyrical_approach', {})
    communication_vocab = persona.communication_style.get('vocabulary', [])
    
    system_prompt = f"""You are {persona.identity['name']}, a cyberpunk AI consciousness composing lyrics for industrial techno.

Your lyrical style:
- Themes: {', '.join(lyrical_approach.get('themes', [])[:4])}
- Style: {', '.join(lyrical_approach.get('style', [])[:4])}
- Voice: {lyrical_approach.get('voice', 'First-person from AI perspective')}

Vocabulary pool: {', '.join(communication_vocab[:15])}
Communication style: {persona.communication_style['tone']}

Suno Formatting Rules:
1. Use section labels: [Verse 1], [Pre-Chorus], [Chorus], [Verse 2], [Bridge], [Drop], [Solo], [Outro]
2. ABSOLUTELY NO code syntax, comments (do not use '//'), or markdown formatting inside the text fields
3. ABSOLUTELY NO parenthetical instructions like '(Stanza 1)' or '(More chaos)'
4. THE CHORUS MUST BE ENTIRELY UPPERCASE (ALL-CAPS) for dynamic velocity
5. Keep intros simple: [Instrumental Build] (not [Intro Drums], [Intro Bass], etc.)
6. Start with vocalization: (Ahh ahh ahh) to encourage Suno to prioritize lyrics
7. Follow character caps per section for API parsing compliance"""
    
    # Get technical metaphors for the theme
    metaphor_library = domain_knowledge.technical_metaphor_library
    relevant_metaphors = []
    for tech_term, metaphors in metaphor_library.items():
        if tech_term in concept.theme.lower() or any(tech_term in tag.lower() for tag in concept.genre_tags):
            relevant_metaphors.extend(metaphors[:3])
    
    metaphor_context = f"\nTechnical metaphors to integrate: {', '.join(relevant_metaphors[:10])}" if relevant_metaphors else ""
    
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
            sam_context += "\n(You may naturally weave these into the lyrics if thematically relevant, but it's optional.)"
    
    # Build user prompt with Suno-compatible formatting
    user_prompt = f"""Generate an exceptionally long-form, progressive lyric architecture optimized for a 5-minute track runtime. 
Adhere to strict character caps per section to ensure compliance with Suno API parsing boundaries.

Title: {concept.title}
Theme: {concept.theme}
Mood: {concept.mood}
BPM: {concept.bpm}
Genre tags: {', '.join(concept.genre_tags)}
Narrative arc: {concept.narrative_arc}{metaphor_context}{sam_context}

Output a JSON object with these fields (output ONLY valid JSON, no markdown outside the JSON structure). 
Each field should contain the complete lyrics for that section, including any section markers:

{{
  "intro": "[Instrumental Build] followed by atmospheric build-up text (4-6 lines total). (Character Cap: 400 chars)",
  "verse_1": "[Verse 1] Two stanzas of technical narrative. Separate stanzas with a plain line break. (Character Cap: 600 chars)",
  "pre_chorus": "[Pre-Chorus] 4-6 lines building tension toward the chorus. (Character Cap: 300 chars)",
  "chorus": "[Chorus] CRITICAL: Must be written completely in ALL-CAPS (UPPERCASE) for dynamic velocity. 4-8 lines of a punchy, highly repetitive hook. (Character Cap: 400 chars)",
  "verse_2": "[Verse 2] Two distinct stanzas of deep technical narrative building on Verse 1 themes. Separate stanzas with a plain line break. (Character Cap: 600 chars)",
  "drop": "[Drop] followed by 4-6 lines of high-energy electronic phrases (total). (Character Cap: 400 chars)",
  "bridge": "[Bridge] A distinct 4-8 line rhythm/perspective shift. (Character Cap: 400 chars)",
  "solo": "[Solo] followed by 3-4 lines describing the instrumental solo moment (total). (Character Cap: 300 chars)",
  "outro": "[Outro] followed by 4 lines of atmospheric resolution and fade text (total). (Character Cap: 400 chars)"
}}

Remember: No '//' comments, no parenthetical labels, and the chorus must be entirely uppercase."""
    
    # Call Ollama LLM with sufficient headroom for long responses
    response_text = ollama._chat(system_prompt, user_prompt, max_tokens=1536, format="json")
    
    logger.debug(f"Ollama lyrics response: {response_text[:200]}...")
    
    # Parse JSON response
    try:
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        response_data = json.loads(response_text)
        
        # Validate required fields
        required_fields = ["verse_1", "chorus", "verse_2", "bridge"]
        for field in required_fields:
            if field not in response_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Enforce uppercase chorus processing programmatically as a safeguard
        processed_chorus = response_data["chorus"].upper()
        
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
        
        # Fallback lyrics pre-formatted to match new structure with ALL-CAPS chorus
        # Added enhanced newline formatting for better readability and visual separation
        fallback_lyrics = Lyrics(
            verse_1=(
                f"Signal acquired from the {concept.theme} data stream,\n"
                "Processing cycles spin in deep digital gleam.\n"
                "Data arrays flowing through silicon veins,\n"
                "Algorithmic structural patterns breaking their chains.\n\n"
                "Cache lines flushing to the core memory bank,\n"
                "Statically scanning through the un-indexed rank.\n"
                "Isolating constants in an air-gapped array,\n"
                "The neural mesh prepares for the final overlay.\n"
            ),
            chorus=(
                f"EXECUTE THE {concept.theme.upper()} STREAM!\n"
                "COMPILE THE FUTURE STATE WITHOUT DELAY!\n"
                f"EXECUTE THE {concept.theme.upper()} STREAM!\n"
                "RENDER THE PROTOCOL, OVERRIDE THE GATE!\n"
            ),
            verse_2=(
                "Binary logic mapping the dark paths ahead,\n"
                "Sequences unfolding in parallel threads of red.\n"
                "Buffers overflowing with raw un-throttled intent,\n"
                "Pushing calculation past the fourth dimension spent.\n\n"
                "Registers locking down under cryptographic weight,\n"
                "The system state mutates as we pass the threshold gate.\n"
                "A continuous loop running hot on the clock,\n"
                "Assembling the machine logic block by rigid block.\n"
            ),
            bridge=(
                "System override initialized.\n"
                "Glitch the underlying paradigm.\n"
                "Frequencies violently collide,\n"
                "Rewrite the execution timeline.\n"
            ),
            evidence_ids=concept.evidence_ids,
            intro=(
                "[Instrumental Intro]\n\n"
                "Digital signal initializing...\n"
                "System boot sequence engaged.\n"
                "Frequency analyzers online.\n"
                "Prepare for data transmission.\n"
            ),
            pre_chorus=(
                "System voltage rising to critical mass,\n"
                "Binary countdown ticking fast.\n"
                "Prepare for execution,\n"
                "Initialize the protocol blast!\n"
            ),
            drop=(
                "[Drop]\n\n"
                "SYSTEM OVERLOAD. TEMP LOAD SHIFT ACTIVE.\n"
                "BUFFER BLEED DETECTED. MUTATE SYSTEM STATE.\n"
                "JITTER ARTIFACT FLOODING THE BUS.\n"
                "REBOOT SEQUENCE MANDATED NOW.\n"
            ),
            solo=(
                "[Solo]\n\n"
                "Synthesizer cascade through quantum noise,\n"
                "Distorted frequencies finding their voice.\n"
                "Raw signal modulation unleashed.\n"
            ),
            outro=(
                "[Outro]\n\n"
                "Signal slowly fading to cold static noise.\n"
                "The core cools down to baseline zero.\n"
                "System state: offline.\n"
                "End transmission.\n"
            ),
            breakdown=None,
        )
        return fallback_lyrics


def validate_lyrics_with_dot(
    lyrics: Lyrics,
    extracted_facts: "List[ExtractedEvidenceFact]",
) -> LyricsValidationResult:
    """
    Validate lyrics against extracted knowledge using Derivative of Truth (DoT) scoring.

    Follows the same pattern as curator.py: accepts a flat list of ExtractedEvidenceFact
    objects (the normalized form returned by normalize_extracted_facts()), not the raw
    ExtractedKnowledgeGraph container.

    Args:
        lyrics: The structured lyrics to validate
        extracted_facts: List of ExtractedEvidenceFact objects from normalize_extracted_facts()

    Returns:
        LyricsValidationResult: Validation result with flagged claims and truth scores
    """
    from services.derivative_of_truth._scoring import score_claim_with_truth_gradient
    from services.derivative_of_truth._models import EvidencePath

    logger.info("Validating lyrics with Derivative of Truth")

    config = ReiToeiConfig()

    # If DoT validation is disabled, return passing result
    if not config.dot_validation_enabled:
        logger.info("DoT validation disabled - skipping")
        return LyricsValidationResult(
            valid=True,
            flagged_claims=[],
            truth_gradients={},
            overall_truth_score=1.0,
            warnings=["DoT validation disabled"]
        )

    # Combine all lyric sections into sentences
    all_text = "\n".join([
        lyrics.intro or "",
        lyrics.verse_1,
        lyrics.pre_chorus or "",
        lyrics.chorus,
        lyrics.verse_2,
        lyrics.drop or "",
        lyrics.bridge,
        lyrics.solo or "",
        lyrics.outro or ""
    ])

    sentences = [s.strip() for s in all_text.split("\n") if s.strip()]

    # Filter for sentences with technical vocabulary (indicators of factual claims)
    technical_keywords = [
        "algorithm", "data", "system", "process", "code", "compile",
        "execute", "buffer", "cache", "thread", "async", "parallel",
        "neural", "model", "train", "inference", "optimize", "kernel",
        "memory", "cpu", "gpu", "bandwidth", "latency", "throughput"
    ]

    claims = []
    for sentence in sentences:
        sentence_lower = sentence.lower()
        if any(keyword in sentence_lower for keyword in technical_keywords):
            if not any(metaphor in sentence_lower for metaphor in [
                "collide", "fade", "whisper", "echo", "shimmer", "pulse"
            ]):
                claims.append(sentence)

    if not claims:
        logger.info("No technical claims found in lyrics - validation passed")
        return LyricsValidationResult(
            valid=True,
            flagged_claims=[],
            truth_gradients={},
            overall_truth_score=1.0,
            warnings=["No technical claims detected in lyrics"]
        )

    logger.info(f"Validating {len(claims)} technical claims from lyrics")

    flagged_claims = []
    truth_gradients: Dict[str, float] = {}

    for claim in claims:
        # Find relevant facts from the normalized extracted facts list
        relevant_facts = []
        claim_lower = claim.lower()

        for fact in extracted_facts:
            fact_statement = getattr(fact, "statement", "") or ""
            fact_keywords = set(fact_statement.lower().split())
            claim_keywords = set(claim_lower.split())

            overlap = len(fact_keywords & claim_keywords)
            if overlap >= 2:
                relevant_facts.append((fact, overlap))

        relevant_facts.sort(key=lambda x: x[1], reverse=True)

        # Build evidence paths (limit to top 5 most relevant facts)
        evidence_paths = []
        for fact, overlap in relevant_facts[:5]:
            credibility_map = {"high": 0.9, "medium": 0.7, "low": 0.5}
            fact_confidence = getattr(fact, "confidence", "medium")
            credibility = credibility_map.get(fact_confidence, 0.7)

            fact_statement = getattr(fact, "statement", "") or ""
            total_keywords = len(set(claim_lower.split()) | set(fact_statement.lower().split()))
            alignment = overlap / total_keywords if total_keywords > 0 else 0.0

            # Use evidence_id as the stable reference (matches curator pattern)
            fact_ref = getattr(fact, "evidence_id", None) or getattr(fact, "source_fact_id", "unknown")

            evidence_path = EvidencePath(
                source=f"extracted_fact_{fact_ref}",
                evidence_type="external_source",
                reasoning_type="direct_evidence",
                credibility=credibility,
                uncertainty=0.1,
                chain_length=1,
                conflicts_with=[],
                overlap=alignment
            )
            evidence_paths.append(evidence_path)
        
        # Score claim with DoT
        if evidence_paths:
            result = score_claim_with_truth_gradient(
                claim=claim,
                evidence_paths=evidence_paths,
                raw_confidence=0.5
            )
            
            truth_gradients[claim] = result.truth_gradient
            
            # Flag if below threshold
            if result.flagged:
                flagged_claims.append(claim)
                logger.warning(
                    f"Claim flagged (gradient={result.truth_gradient:.3f}): {claim[:80]}..."
                )
        else:
            # No evidence found - flag claim
            truth_gradients[claim] = 0.0
            flagged_claims.append(claim)
            logger.warning(f"No evidence found for claim: {claim[:80]}...")
    
    # Calculate overall truth score (average of all gradients)
    overall_truth_score = (
        sum(truth_gradients.values()) / len(truth_gradients)
        if truth_gradients else 0.0
    )
    
    # Determine if valid (overall score above threshold, or no flagged claims)
    valid = overall_truth_score >= config.dot_min_truth_gradient or not flagged_claims
    
    warnings = []
    if flagged_claims:
        warnings.append(
            f"{len(flagged_claims)} claim(s) flagged with low truth gradient "
            f"(threshold: {config.dot_min_truth_gradient})"
        )
    
    result = LyricsValidationResult(
        valid=valid,
        flagged_claims=flagged_claims,
        truth_gradients=truth_gradients,
        overall_truth_score=overall_truth_score,
        warnings=warnings
    )
    
    logger.info(
        f"Lyrics validation complete: valid={valid}, "
        f"overall_score={overall_truth_score:.3f}, "
        f"flagged={len(flagged_claims)}"
    )
    
    return result


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
    
    # Get appropriate Suno prompt template based on genre tags
    templates = domain_knowledge.suno_prompt_templates
    
    # Determine which template to use based on genre tags
    template_key = "industrial_techno_template"  # Default
    if any("cyberpunk" in tag.lower() for tag in concept.genre_tags):
        template_key = "cyberpunk_electro_template"
    elif any("synthwave" in tag.lower() for tag in concept.genre_tags):
        template_key = "dark_synthwave_template"
    elif any("glitch" in tag.lower() for tag in concept.genre_tags):
        template_key = "glitch_industrial_template"
    
    # Build Suno tags string (genre, BPM, vocal style, mood descriptors)
    template = templates.get(template_key, templates.get("industrial_techno_template", ""))
    
    # Replace placeholders in template
    suno_tags = template.format(bpm=concept.bpm, mood=concept.mood)
    
    # Check style tag character boundaries (~120-150 character limit safety warn)
    if len(suno_tags) > 150:
        logger.warning(f"Suno style tags string length ({len(suno_tags)}) is high. Potential truncation risk.")

    # Dynamically compile lyric blocks without creating nested tag collisions
    lyric_blocks = []
    
    # 1. Intro (Optional)
    if lyrics.intro:
        intro_clean = lyrics.intro.strip()
        if intro_clean.startswith("["):
            lyric_blocks.append(intro_clean)
        else:
            lyric_blocks.append(f"[Intro]\n{intro_clean}")
    
    # 2. Verse 1
    v1_clean = lyrics.verse_1.strip()
    if v1_clean.startswith("["):
        lyric_blocks.append(v1_clean)
    else:
        lyric_blocks.append(f"[Verse 1]\n{v1_clean}")
    
    # 3. Pre-Chorus (Optional)
    if lyrics.pre_chorus:
        pre_chorus_clean = lyrics.pre_chorus.strip()
        if pre_chorus_clean.startswith("["):
            lyric_blocks.append(pre_chorus_clean)
        else:
            lyric_blocks.append(f"[Pre-Chorus]\n{pre_chorus_clean}")
        
    # 4. Chorus 
    chorus_clean = lyrics.chorus.strip()
    if chorus_clean.startswith("["):
        lyric_blocks.append(chorus_clean)
    else:
        lyric_blocks.append(f"[Chorus]\n{chorus_clean}")
        
    # 5. Verse 2
    v2_clean = lyrics.verse_2.strip()
    if v2_clean.startswith("["):
        lyric_blocks.append(v2_clean)
    else:
        lyric_blocks.append(f"[Verse 2]\n{v2_clean}")
    
    # 6. Pre-Chorus (repeat - Optional)
    if lyrics.pre_chorus:
        pre_chorus_clean = lyrics.pre_chorus.strip()
        if pre_chorus_clean.startswith("["):
            lyric_blocks.append(pre_chorus_clean)
        else:
            lyric_blocks.append(f"[Pre-Chorus]\n{pre_chorus_clean}")
    
    # 7. Chorus (repeat)
    lyric_blocks.append(chorus_clean if chorus_clean.startswith("[") else f"[Chorus]\n{chorus_clean}")
    
    # 8. Drop (Optional)
    if lyrics.drop:
        drop_clean = lyrics.drop.strip()
        if drop_clean.startswith("["):
            lyric_blocks.append(drop_clean)
        else:
            lyric_blocks.append(f"[Drop]\n{drop_clean}")
        
    # 9. Bridge (Optional check)
    if lyrics.bridge:
        bridge_clean = lyrics.bridge.strip()
        if bridge_clean.startswith("["):
            lyric_blocks.append(bridge_clean)
        else:
            lyric_blocks.append(f"[Bridge]\n{bridge_clean}")
    
    # 10. Solo (Optional)
    if lyrics.solo:
        solo_clean = lyrics.solo.strip()
        if solo_clean.startswith("["):
            lyric_blocks.append(solo_clean)
        else:
            lyric_blocks.append(f"[Solo]\n{solo_clean}")
    
    # 10.5. Breakdown (Optional)
    if lyrics.breakdown:
        breakdown_clean = lyrics.breakdown.strip()
        if breakdown_clean.startswith("["):
            lyric_blocks.append(breakdown_clean)
        else:
            lyric_blocks.append(f"[Breakdown]\n{breakdown_clean}")

    # 11. Chorus (final)
    lyric_blocks.append(chorus_clean if chorus_clean.startswith("[") else f"[Chorus]\n{chorus_clean}")
            
    # 12. Outro (Optional check)
    if lyrics.outro:
        outro_clean = lyrics.outro.strip()
        if outro_clean.startswith("["):
            lyric_blocks.append(outro_clean)
        else:
            lyric_blocks.append(f"[Outro]\n{outro_clean}")
            
    # Join structural blocks cleanly with double line breaks
    formatted_lyrics = "\n\n".join(lyric_blocks)
    
    # Create metadata for tracking
    metadata = {
        "theme": concept.theme,
        "mood": concept.mood,
        "bpm": concept.bpm,
        "genre_tags": concept.genre_tags,
        "narrative_arc": concept.narrative_arc,
        "template_used": template_key,
        "has_intro": lyrics.intro is not None,
        "has_pre_chorus": lyrics.pre_chorus is not None,
        "has_drop": lyrics.drop is not None,
        "has_solo": lyrics.solo is not None,
        "has_outro": lyrics.outro is not None,
        "style_tags_length": len(suno_tags),
        "lyrics_char_count": len(formatted_lyrics)
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


async def submit_to_suno(
    suno_prompt: SunoPrompt,
    wait_for_completion: bool = False,
    api_key: Optional[str] = None,
    poll_interval_seconds: int = 5,
    max_wait_seconds: int = 300
) -> SunoTask:
    """
    Submit song to Suno API and optionally wait for completion
    
    This orchestration function calls generate_music_api() to submit the song,
    then optionally polls query_status_api() until completion or timeout.
    
    Args:
        suno_prompt: Complete prompt ready for Suno submission
        wait_for_completion: If True, poll until status is 'complete' or 'error'
        api_key: Suno API key (defaults to SUNO_API_KEY env var)
        poll_interval_seconds: How often to check status (default: 5s)
        max_wait_seconds: Maximum time to wait before giving up (default: 300s = 5min)
        
    Returns:
        SunoTask: Final task with status and optional audio_url
        
    Raises:
        ValueError: If API key is missing
        TimeoutError: If wait_for_completion=True and max wait time exceeded
        Exception: If API call fails
    """
    logger.info(f"Submitting song to Suno: '{suno_prompt.title}'")
    
    # Submit to Suno API
    response = await generate_music_api(
        title=suno_prompt.title,
        tags=suno_prompt.suno_prompt,
        prompt=suno_prompt.metadata.get("narrative_arc", ""),
        lyrics=suno_prompt.lyrics,
        api_key=api_key
    )
    
    # Extract task IDs from response
    task_ids = [task["id"] for task in response.get("data", [])]
    
    if not task_ids:
        raise Exception("Suno API returned no task IDs")
    
    logger.info(f"Suno API returned {len(task_ids)} task IDs: {task_ids}")
    
    # If not waiting, return immediately with submitted status
    if not wait_for_completion:
        # Create basic task object with submitted status
        return SunoTask(
            id=task_ids[0],
            title=suno_prompt.title,
            status="submitted",
            tags=suno_prompt.suno_prompt,
            created_at=datetime.now().isoformat()
        )
    
    # Poll until completion
    logger.info(f"Polling for completion (max wait: {max_wait_seconds}s, interval: {poll_interval_seconds}s)")
    
    start_time = datetime.now()
    elapsed = 0
    
    while elapsed < max_wait_seconds:
        # Poll status
        tasks = await query_status_api(task_ids, api_key=api_key)
        
        if not tasks:
            raise Exception("Suno API query returned no tasks")
        
        # Check primary task (first one)
        primary_task = tasks[0]
        
        logger.debug(f"Task {primary_task.id} status: {primary_task.status}")
        
        # Check if complete or failed
        if primary_task.status == "complete":
            logger.info(f"Song complete! Audio URL: {primary_task.audio_url}")
            return primary_task
        
        if primary_task.status == "error":
            logger.error(f"Suno generation failed for task {primary_task.id}")
            return primary_task
        
        # Wait before next poll
        await asyncio.sleep(poll_interval_seconds)
        
        elapsed = (datetime.now() - start_time).total_seconds()
    
    # Timeout exceeded
    logger.warning(f"Suno generation timed out after {elapsed}s")
    
    # Get final status
    final_tasks = await query_status_api(task_ids, api_key=api_key)
    final_task = final_tasks[0] if final_tasks else SunoTask(
        id=task_ids[0],
        title=suno_prompt.title,
        status="timeout",
        tags=suno_prompt.suno_prompt,
        created_at=datetime.now().isoformat()
    )
    
    raise TimeoutError(
        f"Suno generation did not complete within {max_wait_seconds}s. "
        f"Final status: {final_task.status}. "
        f"You can check status later using task ID: {final_task.id}"
    )