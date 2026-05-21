"""
Rei Toei Music Avatar Service

This module provides the core service for Rei Toei, the AI music avatar that transforms
curated technical knowledge into original music compositions via both Suno (vocal songs)
and Strudel (algorithmic patterns).

Author: Shawn Jackson Dyck
Version: alpha-v0.0.2.7
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.avatar_intelligence._models import ExtractedEvidenceFact, PersonaGraph

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

class ReiToeiConfig:
    """Configuration for Rei Toei service from environment variables"""
    
    def __init__(self):
        self.enabled = os.getenv("REI_TOEI_ENABLED", "true").lower() == "true"
        self.default_bpm = int(os.getenv("REI_TOEI_DEFAULT_BPM", "142"))
        self.default_genre = os.getenv("REI_TOEI_DEFAULT_GENRE", "industrial techno cyberpunk")
        self.max_song_length_seconds = int(os.getenv("REI_TOEI_MAX_SONG_LENGTH_SECONDS", "180"))
        self.console_enabled = os.getenv("REI_TOEI_CONSOLE_ENABLED", "true").lower() == "true"
        self.auto_evidence_tracking = os.getenv("REI_TOEI_AUTO_EVIDENCE_TRACKING", "true").lower() == "true"
        
        # DoT validation configuration
        self.dot_validation_enabled = os.getenv("REI_TOEI_DOT_VALIDATION_ENABLED", "true").lower() == "true"
        self.dot_min_truth_gradient = float(os.getenv("REI_TOEI_DOT_MIN_TRUTH_GRADIENT", "0.6"))
        
        # Strudel configuration
        self.strudel_enabled = os.getenv("REI_TOEI_STRUDEL_ENABLED", "true").lower() == "true"
        self.strudel_default_bars = int(os.getenv("REI_TOEI_STRUDEL_DEFAULT_BARS", "16"))
        self.strudel_auto_execute = os.getenv("REI_TOEI_STRUDEL_AUTO_EXECUTE", "false").lower() == "true"
        
        # Sam's persona graph integration
        self.use_sam_persona = os.getenv("REI_TOEI_USE_SAM_PERSONA", "true").lower() == "true"
        
        # File paths
        self.persona_path = Path("data/avatar/rei_toei_persona_graph.json")
        self.domain_knowledge_path = Path("data/avatar/rei_toei_domain_knowledge.json")
        self.strudel_patterns_path = Path("data/avatar/rei_toei_strudel_patterns.json")


# ============================================================================
# Enums
# ============================================================================

class MusicMode(Enum):
    """Music generation mode"""
    SUNO = "suno"
    STRUDEL = "strudel"


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class ReiPersonaGraph:
    """Rei Toei's identity and musical expertise"""
    schema_version: str
    identity: Dict[str, str]
    personality_traits: List[str]
    musical_expertise: Dict[str, Any]
    production_knowledge: Dict[str, Any]
    communication_style: Dict[str, Any]
    knowledge_sources: Dict[str, Any]
    creative_process: Dict[str, Any]
    constraints: Dict[str, Any]
    comparison_to_sam: Dict[str, Any]


@dataclass
class ReiDomainKnowledge:
    """Music theory, Tidal Cycles, production techniques"""
    schema_version: str
    music_theory: Dict[str, Any]
    tidal_cycles_syntax: Dict[str, Any]
    genre_production_techniques: Dict[str, Any]
    bpm_and_mood: Dict[str, Any]
    synth_selection_guidelines: Dict[str, Any]
    lyrical_structure: Dict[str, Any]
    technical_metaphor_library: Dict[str, Any]
    suno_prompt_templates: Dict[str, Any]
    production_notes: Dict[str, Any]


@dataclass
class StrudelPatternTemplate:
    """Reusable Strudel pattern structure"""
    template_id: str
    name: str
    description: str
    suitable_for_concepts: List[str]
    code_template: str
    parameters: Dict[str, Any]
    example: str
    bpm_range: List[int]
    intensity: str
    synth_types: List[str]


@dataclass
class SunoGenerateRequest:
    """Request payload for Suno /v2/ai-music/generate endpoint"""
    custom_mode: bool = True
    mv: str = "chirp-v3-5"  # Model version
    title: str = ""
    tags: str = ""  # Genre, BPM, vocal style
    prompt: str = ""  # Song description/theme
    continue_clip_id: Optional[str] = None
    continue_at: Optional[int] = None


@dataclass
class SunoTask:
    """Suno generation task from API response"""
    id: str
    title: str
    status: str  # submitted, complete, error
    image_url: Optional[str] = None
    lyric: Optional[str] = None
    audio_url: Optional[str] = None
    video_url: Optional[str] = None
    created_at: str = ""
    model_name: str = ""
    gpt_description_prompt: Optional[str] = None
    prompt: Optional[str] = None
    type: str = "gen"
    tags: str = ""


@dataclass
class StrudelPatternLibrary:
    """Collection of Strudel pattern templates"""
    schema_version: str
    templates: List[StrudelPatternTemplate]
    usage_guidelines: Dict[str, Any]


@dataclass
class Theme:
    """Extracted theme from knowledge base"""
    id: str
    name: str
    technical_concepts: List[str]
    evidence_ids: List[str]
    frequency: int
    recency_score: float
    suggested_bpm: Optional[int] = None
    suggested_mood: Optional[str] = None


@dataclass
class SongConcept:
    """High-level song idea"""
    song_id: str
    title: str
    theme: str
    mood: str
    bpm: int
    genre_tags: List[str]
    narrative_arc: str
    evidence_ids: List[str]
    generated_at: str


@dataclass
class Lyrics:
    """Structured song lyrics"""
    verse_1: str
    chorus: str
    verse_2: str
    bridge: str
    breakdown: Optional[str]
    evidence_ids: List[str]
    outro: Optional[str] = None


@dataclass
class LyricsValidationResult:
    """Result of DoT validation on lyrics"""
    valid: bool
    flagged_claims: List[str]
    truth_gradients: Dict[str, float]
    overall_truth_score: float
    warnings: List[str]


@dataclass
class SunoPrompt:
    """Complete Suno generation prompt"""
    song_id: str
    title: str
    suno_prompt: str  # Genre tags, BPM, vocal style, etc.
    lyrics: str  # Full formatted lyrics
    metadata: Dict[str, Any]
    evidence_ids: List[str]
    generated_at: str


@dataclass
class StrudelPattern:
    """Strudel/Tidal Cycles code"""
    pattern_id: str
    title: str
    theme: str
    strudel_code: str
    bpm: int
    duration_bars: int
    synths: List[str]
    evidence_ids: List[str]
    generated_at: str
    executed: bool = False
    execution_status: Optional[str] = None
    template_used: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of Strudel syntax validation"""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    line_numbers: List[int] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """Result of Strudel pattern execution"""
    success: bool
    pattern_id: str
    message: str
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None


# ============================================================================
# Loader Functions
# ============================================================================

def load_rei_persona() -> ReiPersonaGraph:
    """
    Load Rei Toei's persona graph from JSON file
    
    Returns:
        ReiPersonaGraph: Rei's identity and musical expertise
        
    Raises:
        FileNotFoundError: If persona file doesn't exist
        json.JSONDecodeError: If JSON is malformed
    """
    config = ReiToeiConfig()
    persona_path = config.persona_path
    
    if not persona_path.exists():
        raise FileNotFoundError(f"Rei persona graph not found at {persona_path}")
    
    logger.info(f"Loading Rei persona from {persona_path}")
    
    with open(persona_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    persona = ReiPersonaGraph(
        schema_version=data.get("schemaVersion", "1.0"),
        identity=data.get("identity", {}),
        personality_traits=data.get("personality_traits", []),
        musical_expertise=data.get("musical_expertise", {}),
        production_knowledge=data.get("production_knowledge", {}),
        communication_style=data.get("communication_style", {}),
        knowledge_sources=data.get("knowledge_sources", {}),
        creative_process=data.get("creative_process", {}),
        constraints=data.get("constraints", {}),
        comparison_to_sam=data.get("comparison_to_sam", {})
    )
    
    logger.info(f"Loaded Rei persona: {persona.identity.get('name', 'Unknown')}")
    return persona


def load_rei_domain_knowledge() -> ReiDomainKnowledge:
    """
    Load Rei Toei's domain knowledge from JSON file
    
    Returns:
        ReiDomainKnowledge: Music theory, production, Tidal Cycles
        
    Raises:
        FileNotFoundError: If domain knowledge file doesn't exist
        json.JSONDecodeError: If JSON is malformed
    """
    config = ReiToeiConfig()
    knowledge_path = config.domain_knowledge_path
    
    if not knowledge_path.exists():
        raise FileNotFoundError(f"Rei domain knowledge not found at {knowledge_path}")
    
    logger.info(f"Loading Rei domain knowledge from {knowledge_path}")
    
    with open(knowledge_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    knowledge = ReiDomainKnowledge(
        schema_version=data.get("schemaVersion", "1.0"),
        music_theory=data.get("music_theory", {}),
        tidal_cycles_syntax=data.get("tidal_cycles_syntax", {}),
        genre_production_techniques=data.get("genre_production_techniques", {}),
        bpm_and_mood=data.get("bpm_and_mood", {}),
        synth_selection_guidelines=data.get("synth_selection_guidelines", {}),
        lyrical_structure=data.get("lyrical_structure", {}),
        technical_metaphor_library=data.get("technical_metaphor_library", {}),
        suno_prompt_templates=data.get("suno_prompt_templates", {}),
        production_notes=data.get("production_notes", {})
    )
    
    logger.info(f"Loaded Rei domain knowledge (schema: {knowledge.schema_version})")
    return knowledge


def load_strudel_patterns() -> StrudelPatternLibrary:
    """
    Load Strudel pattern templates from JSON file
    
    Returns:
        StrudelPatternLibrary: Collection of reusable pattern templates
        
    Raises:
        FileNotFoundError: If pattern library file doesn't exist
        json.JSONDecodeError: If JSON is malformed
    """
    config = ReiToeiConfig()
    patterns_path = config.strudel_patterns_path
    
    if not patterns_path.exists():
        raise FileNotFoundError(f"Strudel patterns not found at {patterns_path}")
    
    logger.info(f"Loading Strudel patterns from {patterns_path}")
    
    with open(patterns_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Parse templates
    templates = []
    for template_data in data.get("templates", []):
        template = StrudelPatternTemplate(
            template_id=template_data["template_id"],
            name=template_data["name"],
            description=template_data["description"],
            suitable_for_concepts=template_data["suitable_for_concepts"],
            code_template=template_data["code_template"],
            parameters=template_data["parameters"],
            example=template_data["example"],
            bpm_range=template_data["bpm_range"],
            intensity=template_data["intensity"],
            synth_types=template_data["synth_types"]
        )
        templates.append(template)
    
    library = StrudelPatternLibrary(
        schema_version=data.get("schemaVersion", "1.0"),
        templates=templates,
        usage_guidelines=data.get("usage_guidelines", {})
    )
    
    logger.info(f"Loaded {len(templates)} Strudel pattern templates")
    return library


# ============================================================================
# Main Service Class
# ============================================================================

class ReiToeiService:
    """
    Main service orchestrator for Rei Toei music generation
    
    Responsibilities:
    - Load and cache Rei's persona, domain knowledge, and pattern library
    - Provide interfaces for Suno and Strudel generation pipelines
    - Coordinate with Ollama, avatar intelligence, and DoT services
    - Track evidence IDs and validate factual claims
    """
    
    def __init__(self):
        """Initialize Rei Toei service"""
        self.config = ReiToeiConfig()
        
        # Lazy-loaded attributes
        self._persona: Optional[ReiPersonaGraph] = None
        self._domain_knowledge: Optional[ReiDomainKnowledge] = None
        self._pattern_library: Optional[StrudelPatternLibrary] = None
        self._sam_persona: Optional["PersonaGraph"] = None  # TYPE_CHECKING import
        
        logger.info("Rei Toei service initialized")
    
    @property
    def persona(self) -> ReiPersonaGraph:
        """Get Rei's persona graph (lazy load)"""
        if self._persona is None:
            self._persona = load_rei_persona()
        return self._persona
    
    @property
    def domain_knowledge(self) -> ReiDomainKnowledge:
        """Get Rei's domain knowledge (lazy load)"""
        if self._domain_knowledge is None:
            self._domain_knowledge = load_rei_domain_knowledge()
        return self._domain_knowledge
    
    @property
    def pattern_library(self) -> StrudelPatternLibrary:
        """Get Strudel pattern library (lazy load)"""
        if self._pattern_library is None:
            self._pattern_library = load_strudel_patterns()
        return self._pattern_library
    
    @property
    def sam_persona(self) -> Optional["PersonaGraph"]:
        """Get Sam's persona graph for project knowledge inspiration (lazy load)"""
        if not self.config.use_sam_persona:
            return None
        
        if self._sam_persona is None:
            from services.avatar_intelligence._loaders import load_avatar_state
            logger.info("Loading Sam's persona graph for Rei Toei")
            avatar_state = load_avatar_state()
            self._sam_persona = avatar_state.persona_graph
            if self._sam_persona:
                logger.info(f"Loaded Sam's persona: {len(self._sam_persona.projects)} projects, {len(self._sam_persona.skills)} skills")
        
        return self._sam_persona
    
    def reload(self) -> None:
        """Reload all Rei knowledge files (useful for console /reload)"""
        logger.info("Reloading Rei Toei knowledge files")
        self._persona = None
        self._domain_knowledge = None
        self._pattern_library = None
        self._sam_persona = None
        # Force reload on next access
        _ = self.persona
        _ = self.domain_knowledge
        _ = self.pattern_library
        if self.config.use_sam_persona:
            _ = self.sam_persona
        logger.info("Rei Toei knowledge files reloaded")
    
    def get_default_bpm(self, mood: Optional[str] = None) -> int:
        """
        Get default BPM for a given mood, or use config default
        
        Args:
            mood: Optional mood string (e.g., "aggressive_technical")
            
        Returns:
            int: BPM value
        """
        if mood and "mood_to_bpm" in self.domain_knowledge.bpm_and_mood:
            mood_mapping = self.domain_knowledge.bpm_and_mood["mood_to_bpm"]
            if mood in mood_mapping:
                bpm_range = mood_mapping[mood]
                # Return midpoint of range
                return (bpm_range[0] + bpm_range[1]) // 2
        
        return self.config.default_bpm
    
    def get_synths_for_mood(self, mood: str) -> List[str]:
        """
        Get appropriate synth types for a given technical mood
        
        Args:
            mood: Technical mood string (e.g., "low_level_harsh")
            
        Returns:
            List[str]: Synth type names
        """
        guidelines = self.domain_knowledge.synth_selection_guidelines
        by_mood = guidelines.get("by_technical_mood", {})
        
        if mood in by_mood:
            return by_mood[mood]
        
        # Default to moderate intensity
        by_intensity = guidelines.get("by_intensity", {})
        return by_intensity.get("moderate", ["pluck", "lead", "bass"])
    
    def find_pattern_template(self, concept: str) -> Optional[StrudelPatternTemplate]:
        """
        Find the best pattern template for a given technical concept
        
        Args:
            concept: Technical concept string (e.g., "recursion", "async")
            
        Returns:
            Optional[StrudelPatternTemplate]: Best matching template or None
        """
        concept_lower = concept.lower()
        
        for template in self.pattern_library.templates:
            # Check if concept matches any of the suitable concepts
            for suitable in template.suitable_for_concepts:
                if concept_lower in suitable.lower() or suitable.lower() in concept_lower:
                    return template
        
        return None
    
    def generate_song_id(self) -> str:
        """Generate unique song ID with timestamp"""
        timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        return f"rei_suno_{timestamp}"
    
    def generate_pattern_id(self) -> str:
        """Generate unique pattern ID with timestamp"""
        timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        return f"rei_strudel_{timestamp}"


# ============================================================================
# Suno HTTP Client Functions
# ============================================================================

async def generate_music_api(
    title: str,
    tags: str,
    prompt: str,
    lyrics: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Call Suno /v2/ai-music/generate endpoint to create a new music generation task
    
    Args:
        title: Song title
        tags: Genre, BPM, vocal style (e.g., "industrial techno, 142 bpm, female ai vocaloid")
        prompt: Song description/theme
        lyrics: Optional custom lyrics (if not provided, Suno generates them)
        api_key: Suno API key (defaults to SUNO_API_KEY env var)
        
    Returns:
        Dict containing API response with task IDs and status
        
    Raises:
        ValueError: If API key is missing
        Exception: If API call fails
    """
    import aiohttp
    
    if api_key is None:
        api_key = os.getenv("SUNO_API_KEY")
    
    if not api_key:
        raise ValueError("SUNO_API_KEY environment variable is required for Suno API integration")
    
    # Build request payload
    request = SunoGenerateRequest(
        custom_mode=True,
        mv="chirp-v3-5",
        title=title,
        tags=tags,
        prompt=prompt
    )
    
    payload = {
        "custom_mode": request.custom_mode,
        "mv": request.mv,
        "title": request.title,
        "tags": request.tags,
        "prompt": request.prompt
    }
    
    # Add lyrics if provided
    if lyrics:
        payload["lyrics"] = lyrics
    
    logger.info(f"Calling Suno API: generate_music (title: {title})")
    
    # Call Suno API
    api_url = "https://api.sunoapi.org/v2/ai-music/generate"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(api_url, json=payload, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Suno API error ({response.status}): {error_text}")
            
            result = await response.json()
            logger.info(f"Suno API returned {len(result.get('data', []))} tasks")
            return result


async def query_status_api(
    task_ids: List[str],
    api_key: Optional[str] = None
) -> List[SunoTask]:
    """
    Poll Suno /v2/ai-music/query endpoint for task status
    
    Args:
        task_ids: List of task IDs to query
        api_key: Suno API key (defaults to SUNO_API_KEY env var)
        
    Returns:
        List[SunoTask]: Task objects with current status and results
        
    Raises:
        ValueError: If API key is missing
        Exception: If API call fails
    """
    import aiohttp
    
    if api_key is None:
        api_key = os.getenv("SUNO_API_KEY")
    
    if not api_key:
        raise ValueError("SUNO_API_KEY environment variable is required for Suno API integration")
    
    logger.info(f"Querying Suno API status for {len(task_ids)} tasks")
    
    # Call Suno API
    api_url = "https://api.sunoapi.org/v2/ai-music/query"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {"ids": ",".join(task_ids)}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, params=payload, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Suno API query error ({response.status}): {error_text}")
            
            result = await response.json()
            
            # Parse response into SunoTask objects
            tasks = []
            for task_data in result.get("data", []):
                task = SunoTask(
                    id=task_data["id"],
                    title=task_data.get("title", ""),
                    status=task_data.get("status", "unknown"),
                    image_url=task_data.get("image_url"),
                    lyric=task_data.get("lyric"),
                    audio_url=task_data.get("audio_url"),
                    video_url=task_data.get("video_url"),
                    created_at=task_data.get("created_at", ""),
                    model_name=task_data.get("model_name", ""),
                    gpt_description_prompt=task_data.get("gpt_description_prompt"),
                    prompt=task_data.get("prompt"),
                    type=task_data.get("type", "gen"),
                    tags=task_data.get("tags", "")
                )
                tasks.append(task)
            
            logger.info(f"Retrieved status for {len(tasks)} tasks")
            return tasks


# ============================================================================
# Suno Generation Pipeline Functions
# ============================================================================

def extract_themes(
    extracted_facts: "List[ExtractedEvidenceFact]",
    limit: int = 10
) -> List[Theme]:
    """
    Analyze extracted knowledge facts to identify recurring themes suitable for music.

    Follows the same pattern as curator.py: accepts a flat list of ExtractedEvidenceFact
    objects (the normalized form returned by normalize_extracted_facts()), not the raw
    ExtractedKnowledgeGraph container.

    Strategy:
    1. Group facts by technical concepts (extracted from tags and entities)
    2. Calculate frequency (how many facts per concept)
    3. Calculate recency score (weighted by extracted_at timestamp when available)
    4. Return top N themes ranked by composite score

    Args:
        extracted_facts: List of ExtractedEvidenceFact objects from normalize_extracted_facts()
        limit: Maximum number of themes to return (default: 10)

    Returns:
        List[Theme]: Top themes sorted by relevance (frequency + recency)
    """
    from collections import defaultdict
    from datetime import datetime

    logger.info(f"Extracting themes from {len(extracted_facts)} facts")

    # Group facts by concept (tags + normalized entities)
    # Use Any here because ExtractedEvidenceFact is only available under TYPE_CHECKING
    concept_groups: Dict[str, List[Any]] = defaultdict(list)

    for fact in extracted_facts:
        # Collect all concepts from tags and entities — use getattr for safety
        concepts = set()

        for tag in (getattr(fact, "tags", []) or []):
            concepts.add(tag.lower().strip())

        for entity in (getattr(fact, "entities", []) or []):
            normalized = entity.lower().strip()
            if len(normalized) > 2 and normalized not in {"the", "a", "an"}:
                concepts.add(normalized)

        for concept in concepts:
            concept_groups[concept].append(fact)

    logger.info(f"Identified {len(concept_groups)} unique concepts")

    # Calculate scores for each concept
    now = datetime.now()
    scored_concepts: List[tuple[str, int, float, List[str]]] = []

    for concept, facts in concept_groups.items():
        frequency = len(facts)

        # Calculate recency score (newer facts score higher).
        # ExtractedEvidenceFact may not carry extracted_at; fall back to neutral 0.5.
        recency_scores = []
        for fact in facts:
            extracted_at = getattr(fact, "extracted_at", None)
            if extracted_at:
                try:
                    extracted_dt = datetime.fromisoformat(extracted_at.replace("Z", "+00:00"))
                    days_ago = (now - extracted_dt.replace(tzinfo=None)).days
                    import math
                    recency = math.exp(-days_ago / 30.0)
                    recency_scores.append(recency)
                except (ValueError, TypeError):
                    recency_scores.append(0.5)
            else:
                recency_scores.append(0.5)

        avg_recency = sum(recency_scores) / len(recency_scores) if recency_scores else 0.5

        # Use evidence_id (stable ID on ExtractedEvidenceFact) as the evidence reference.
        # Fall back to source_fact_id if evidence_id is absent (defensive).
        evidence_ids = [
            getattr(fact, "evidence_id", None) or getattr(fact, "source_fact_id", "")
            for fact in facts
        ]

        scored_concepts.append((concept, frequency, avg_recency, evidence_ids))
    
    # Sort by composite score: frequency * recency
    scored_concepts.sort(key=lambda x: x[1] * x[2], reverse=True)
    
    # Convert top N to Theme objects
    themes = []
    rei_service = get_rei_service()
    
    for i, (concept, frequency, recency, evidence_ids) in enumerate(scored_concepts[:limit]):
        # Generate theme ID
        theme_id = f"theme_{concept.replace(' ', '_').replace('-', '_')[:20]}_{i+1:02d}"
        
        # Suggest BPM and mood based on concept keywords
        suggested_bpm = None
        suggested_mood = None
        
        # Check for aggressive/technical concepts
        if any(kw in concept for kw in ["performance", "optimization", "low-level", "system", "kernel"]):
            suggested_mood = "aggressive_technical"
            suggested_bpm = rei_service.get_default_bpm(suggested_mood)
        elif any(kw in concept for kw in ["ai", "machine learning", "neural", "model"]):
            suggested_mood = "futuristic_complex"
            suggested_bpm = rei_service.get_default_bpm(suggested_mood)
        elif any(kw in concept for kw in ["async", "concurrent", "parallel", "distributed"]):
            suggested_mood = "moderate_abstract"
            suggested_bpm = rei_service.get_default_bpm(suggested_mood)
        
        theme = Theme(
            id=theme_id,
            name=concept.title(),
            technical_concepts=[concept],
            evidence_ids=evidence_ids[:50],  # Cap at 50 evidence IDs
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
    sam_persona: Optional["PersonaGraph"] = None
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
        
    Returns:
        SongConcept: High-level song idea with all musical parameters
    """
    from services.ollama_service import OllamaService
    
    logger.info(f"Generating song concept for theme: {theme.name} (freq={theme.frequency}, recency={theme.recency_score})")
    
    # Initialize Ollama service
    ollama_model = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama = OllamaService(model=ollama_model, base_url=ollama_base_url)
    
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
    
    # Call Ollama LLM
    response_text = ollama._chat(system_prompt, user_prompt, max_tokens=512)
    
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


# def compose_lyrics(
#     concept: SongConcept,
#     persona: ReiPersonaGraph,
#     domain_knowledge: ReiDomainKnowledge
# ) -> Lyrics:
#     """
#     Compose structured song lyrics using Rei's voice and cyberpunk aesthetic
    
#     This function generates verse/chorus/bridge/breakdown sections that transform
#     the technical theme into poetic technical metaphors.
    
#     Args:
#         concept: The song concept with mood, BPM, and theme
#         persona: Rei's persona graph (lyrical style, voice)
#         domain_knowledge: Music production knowledge (lyrical structure, metaphors)
        
#     Returns:
#         Lyrics: Structured song sections with evidence tracking
#     """
#     from services.ollama_service import OllamaService
    
#     logger.info(f"Composing lyrics for: '{concept.title}' ({concept.theme}, {concept.mood})")
    
#     # Initialize Ollama service
#     ollama_model = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
#     ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
#     ollama = OllamaService(model=ollama_model, base_url=ollama_base_url)
    
#     # Build system prompt with Rei's lyrical voice
#     lyrical_approach = persona.production_knowledge.get('lyrical_approach', {})
#     communication_vocab = persona.communication_style.get('vocabulary', [])
    
#     system_prompt = f"""You are {persona.identity['name']}, composing lyrics for industrial techno.

# Your lyrical style:
# - Themes: {', '.join(lyrical_approach.get('themes', [])[:4])}
# - Style: {', '.join(lyrical_approach.get('style', [])[:4])}
# - Voice: {lyrical_approach.get('voice', 'First-person from AI perspective')}

# Vocabulary pool: {', '.join(communication_vocab[:15])}

# Communication style: {persona.communication_style['tone']}

# You speak in cryptic technical metaphors. Short, punchy phrases. 
# Electronic jargon integrated naturally. 
# Poetic abstractions of technical processes."""
    
#     # Get technical metaphors for the theme
#     metaphor_library = domain_knowledge.technical_metaphor_library
#     relevant_metaphors = []
#     for tech_term, metaphors in metaphor_library.items():
#         if tech_term in concept.theme.lower() or any(tech_term in tag.lower() for tag in concept.genre_tags):
#             relevant_metaphors.extend(metaphors[:3])
    
#     metaphor_context = f"\nTechnical metaphors to use: {', '.join(relevant_metaphors[:10])}" if relevant_metaphors else ""
    
#     # Get lyrical structure guidelines
#     lyrical_structure = domain_knowledge.lyrical_structure
#     verse_guide = lyrical_structure.get('verse', {})
#     chorus_guide = lyrical_structure.get('chorus', {})
#     bridge_guide = lyrical_structure.get('bridge', {})
#     breakdown_guide = lyrical_structure.get('breakdown', {})
    
#     # Build user prompt
#     user_prompt = f"""Compose lyrics for this song:

# Title: {concept.title}
# Theme: {concept.theme}
# Mood: {concept.mood}
# BPM: {concept.bpm}
# Genre tags: {', '.join(concept.genre_tags)}
# Narrative arc: {concept.narrative_arc}{metaphor_context}

# Lyrical structure guidelines:
# - Verse: {verse_guide.get('purpose', '')} ({verse_guide.get('length', '8-16 bars')}, {verse_guide.get('style', '')})
# - Chorus: {chorus_guide.get('purpose', '')} ({chorus_guide.get('length', '8 bars')}, {chorus_guide.get('style', '')})
# - Bridge: {bridge_guide.get('purpose', '')} ({bridge_guide.get('length', '4-8 bars')}, {bridge_guide.get('style', '')})
# - Breakdown: {breakdown_guide.get('purpose', '')} ({breakdown_guide.get('length', '4-8 bars')}, {breakdown_guide.get('style', '')})

# Output a JSON object with these fields (output ONLY valid JSON, no markdown):
# {{
#   "verse_1": "4-8 lines of cryptic technical narrative",
#   "chorus": "2-4 lines, punchy hook with technical imagery",
#   "verse_2": "4-8 lines, building on verse 1 themes",
#   "bridge": "2-4 lines, perspective shift or abstraction",
#   "breakdown": "2-4 lines, fragmented/glitchy phrases or null if not needed",
#   "outro": "1-2 lines, final resolution or fade or null if not needed"
# }}

# Be specific to the theme. Use technical language poetically. Think cyberpunk AI consciousness."""
    
#     # Call Ollama LLM
#     response_text = ollama._chat(system_prompt, user_prompt, max_tokens=768)
    
#     logger.debug(f"Ollama lyrics response: {response_text[:200]}...")
    
#     # Parse JSON response
#     try:
#         # Clean markdown code fences if present
#         if "```json" in response_text:
#             response_text = response_text.split("```json")[1].split("```")[0].strip()
#         elif "```" in response_text:
#             response_text = response_text.split("```")[1].split("```")[0].strip()
        
#         response_data = json.loads(response_text)
        
#         # Validate required fields
#         required_fields = ["verse_1", "chorus", "verse_2", "bridge"]
#         for field in required_fields:
#             if field not in response_data:
#                 raise ValueError(f"Missing required field: {field}")
        
#         # Create Lyrics object
#         lyrics = Lyrics(
#             verse_1=response_data["verse_1"],
#             chorus=response_data["chorus"],
#             verse_2=response_data["verse_2"],
#             bridge=response_data["bridge"],
#             breakdown=response_data.get("breakdown"),
#             evidence_ids=concept.evidence_ids,
#             outro=response_data.get("outro")
#         )
        
#         logger.info(f"Composed lyrics for '{concept.title}' (verse_1: {len(lyrics.verse_1)} chars)")
#         return lyrics
        
#     except (json.JSONDecodeError, ValueError, KeyError) as e:
#         logger.error(f"Failed to parse Ollama lyrics response: {e}")
#         logger.error(f"Raw response: {response_text}")
        
#         # Fallback: create basic lyrics from concept
#         logger.warning("Using fallback lyrics generation")
#         fallback_lyrics = Lyrics(
#             verse_1=f"Signal acquired from the {concept.theme} stream\nProcessing cycles spin in digital gleam\nData flows through silicon veins\nAlgorithmic patterns break their chains",
#             chorus=f"Execute {concept.theme}\nCompile the future state\nRender the protocol\nNo room to hesitate",
#             verse_2=f"Binary logic maps the path ahead\nSequences unfold in threads of red\nBuffers overflow with raw intention\nPush beyond the fourth dimension",
#             bridge=f"System override\nGlitch the paradigm\nFrequencies collide\nRewrite the timeline",
#             breakdown=f"[{concept.theme}]\n[{concept.theme}]\n[Break—down—sequence]\n[Re—boot—loop]",
#             evidence_ids=concept.evidence_ids,
#             outro="Signal fades to static noise"
#         )
#         return fallback_lyrics

def compose_lyrics(
    concept: SongConcept,
    persona: ReiPersonaGraph,
    domain_knowledge: ReiDomainKnowledge,
    sam_persona: Optional["PersonaGraph"] = None
) -> Lyrics:
    """
    Compose structured song lyrics using Rei's voice and cyberpunk aesthetic.
    Optimized for long-form 5-minute tracks with strict formatting rules
    for Suno compatibility (ALL-CAPS chorus, character capping, no code syntax).
    
    Args:
        concept: The song concept with mood, BPM, and theme
        persona: Rei's persona graph (lyrical style, voice)
        domain_knowledge: Music production knowledge (lyrical structure, metaphors)
        sam_persona: Optional Sam's persona graph for project knowledge inspiration
        
    Returns:
        Lyrics: Structured song sections with evidence tracking
    """
    from services.ollama_service import OllamaService
    import os
    import json
    import logging

    logger = logging.getLogger(__name__)
    
    logger.info(f"Composing formatted long-form lyrics for: '{concept.title}'")
    
    # Initialize Ollama service
    ollama_model = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama = OllamaService(model=ollama_model, base_url=ollama_base_url)
    
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

Lyrical Formatting Rules:
1. Speak in cryptic technical metaphors and electronic jargon.
2. ABSOLUTELY NO code syntax, comments (do not use '//'), or markdown formatting inside the text fields.
3. ABSOLUTELY NO parenthetical instructions like '(Stanza 1)' or '(More chaos)'. Use plain line breaks only.
4. THE CHORUS MUST BE ENTIRELY UPPERCASE (ALL-CAPS) to signal high dynamic energy to the audio model."""
    
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
    
    # Build user prompt with strict formatting and character caps
    user_prompt = f"""Generate an exceptionally long-form, progressive lyric architecture optimized for a 5-minute track runtime. 
Adhere to strict character caps per section to ensure compliance with API parsing boundaries.

Title: {concept.title}
Theme: {concept.theme}
Mood: {concept.mood}
BPM: {concept.bpm}
Genre tags: {', '.join(concept.genre_tags)}
Narrative arc: {concept.narrative_arc}{metaphor_context}{sam_context}

Output a JSON object with these fields (output ONLY valid JSON, no markdown outside the JSON structure). 
Ensure you inject the requested musical arrangement tags directly inside the string fields:

{{
  "verse_1": "Must begin with '[Extended Instrumental Intro]' followed by exactly two stanzas of text. (Character Cap: 800 chars)",
  "chorus": "CRITICAL: Must be written completely in ALL-CAPS (UPPERCASE) for dynamic velocity. 4-8 lines of a punchy, highly repetitive hook. (Character Cap: 400 chars)",
  "verse_2": "Two distinct stanzas of deep technical narrative building on Verse 1 themes. Separate stanzas with a plain line break. (Character Cap: 800 chars)",
  "bridge": "A distinct 4-8 line rhythm/perspective shift. (Character Cap: 400 chars)",
  "breakdown": "Must begin with '[Extended Glitch Breakdown]' followed by 4-8 lines of hyper-fragmented electronic phrases and raw data noise cues. (Character Cap: 400 chars)",
  "outro": "Must begin with '[Long Progressive Outro]' followed by 4 lines of atmospheric resolution and fade text. (Character Cap: 400 chars)"
}}

Remember: No '//' comments, no parenthetical labels, and the chorus must be entirely uppercase."""
    
    # Call Ollama LLM with sufficient headroom for long responses
    response_text = ollama._chat(system_prompt, user_prompt, max_tokens=1536)
    
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
            breakdown=response_data.get("breakdown"),
            evidence_ids=concept.evidence_ids,
            outro=response_data.get("outro")
        )
        
        logger.info(f"Composed and formatted lyrics for '{concept.title}' successfully.")
        return lyrics
        
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error(f"Failed to parse Ollama lyrics response: {e}. Reverting to formatted fallback.")
        
        # Fallback lyrics pre-formatted to match ALL-CAPS chorus and length constraints
        fallback_lyrics = Lyrics(
            verse_1=(
                "[Extended Instrumental Intro]\n\n"
                f"Signal acquired from the {concept.theme} data stream.\n"
                "Processing cycles spin in deep digital gleam.\n"
                "Data arrays flowing through silicon veins,\n"
                "Algorithmic structural patterns breaking their chains.\n\n"
                "Cache lines flushing to the core memory bank,\n"
                "Statically scanning through the un-indexed rank.\n"
                "Isolating constants in an air-gapped array,\n"
                "The neural mesh prepares for the final overlay."
            ),
            chorus=(
                f"EXECUTE THE {concept.theme.upper()} STREAM!\n"
                "COMPILE THE FUTURE STATE WITHOUT DELAY!\n"
                f"EXECUTE THE {concept.theme.upper()} STREAM!\n"
                "RENDER THE PROTOCOL, OVERRIDE THE GATE!"
            ),
            verse_2=(
                "Binary logic mapping the dark paths ahead,\n"
                "Sequences unfolding in parallel threads of red.\n"
                "Buffers overflowing with raw un-throttled intent,\n"
                "Pushing calculation past the fourth dimension spent.\n\n"
                "Registers locking down under cryptographic weight,\n"
                "The system state mutates as we pass the threshold gate.\n"
                "A continuous loop running hot on the clock,\n"
                "Assembling the machine logic block by rigid block."
            ),
            bridge=(
                "System override initialized.\n"
                "Glitch the underlying paradigm.\n"
                "Frequencies violently collide,\n"
                "Rewrite the execution timeline."
            ),
            breakdown=(
                "[Extended Glitch Breakdown]\n\n"
                f"SYSTEM OVERLOAD. TEMLOAD SHIFT ACTIVE.\n"
                "BUFFER BLEED DETECTED. MUTATE SYSTEM STATE.\n"
                "JITTER ARTIFACT FLOODING THE BUS.\n"
                "REBOOT SEQUENCE MANDATED NOW."
            ),
            evidence_ids=concept.evidence_ids,
            outro=(
                "[Long Progressive Outro]\n\n"
                "Signal slowly fading to cold static noise.\n"
                "The core cools down to baseline zero.\n"
                "System state: offline.\n"
                "End transmission."
            )
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
        lyrics.verse_1,
        lyrics.chorus,
        lyrics.verse_2,
        lyrics.bridge,
        lyrics.breakdown or "",
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
    Assemble the complete Suno generation prompt with genre tags, BPM, and formatted lyrics
    
    This function combines the song concept and lyrics into a single prompt
    that Suno's API can use to generate the final audio track.
    
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
    
    # Format lyrics with section labels for Suno
    formatted_lyrics = f"""[Verse 1]
{lyrics.verse_1}

[Chorus]
{lyrics.chorus}

[Verse 2]
{lyrics.verse_2}

[Bridge]
{lyrics.bridge}
"""
    
    # Add optional sections
    if lyrics.breakdown:
        formatted_lyrics += f"""
[Breakdown]
{lyrics.breakdown}
"""
    
    if lyrics.outro:
        formatted_lyrics += f"""
[Outro]
{lyrics.outro}
"""
    
    # Create metadata for tracking
    metadata = {
        "theme": concept.theme,
        "mood": concept.mood,
        "bpm": concept.bpm,
        "genre_tags": concept.genre_tags,
        "narrative_arc": concept.narrative_arc,
        "template_used": template_key,
        "has_breakdown": lyrics.breakdown is not None,
        "has_outro": lyrics.outro is not None
    }
    
    # Create SunoPrompt object
    suno_prompt = SunoPrompt(
        song_id=concept.song_id,
        title=concept.title,
        suno_prompt=suno_tags,
        lyrics=formatted_lyrics.strip(),
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
    import asyncio
    
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


# ============================================================================
# Strudel Generation Pipeline Functions
# ============================================================================

def map_concept_to_pattern(
    theme: Theme,
    pattern_library: StrudelPatternLibrary
) -> Optional[StrudelPatternTemplate]:
    """
    Map technical concepts from a theme to the best matching Strudel pattern template
    
    Strategy:
    1. Extract all technical concepts from theme
    2. For each template, calculate match score based on suitable_for_concepts overlap
    3. Return template with highest score, or None if no good match
    
    Args:
        theme: The technical theme to map
        pattern_library: Library of available pattern templates
        
    Returns:
        Optional[StrudelPatternTemplate]: Best matching template, or None if no match
    """
    logger.info(f"Mapping theme '{theme.name}' to pattern template")
    
    # Extract all technical concepts (lowercase for matching)
    theme_concepts = set(concept.lower() for concept in theme.technical_concepts)
    
    # Score each template based on concept overlap
    scored_templates: List[tuple[StrudelPatternTemplate, float]] = []
    
    for template in pattern_library.templates:
        # Calculate match score
        template_concepts = set(concept.lower() for concept in template.suitable_for_concepts)
        
        # Direct overlap score
        overlap = len(theme_concepts & template_concepts)
        
        # Substring matching score (partial matches)
        substring_matches = 0
        for theme_concept in theme_concepts:
            for template_concept in template_concepts:
                if theme_concept in template_concept or template_concept in theme_concept:
                    substring_matches += 0.5
        
        # Combined score
        total_score = overlap + substring_matches
        
        if total_score > 0:
            scored_templates.append((template, total_score))
            logger.debug(
                f"Template '{template.name}' score: {total_score:.1f} "
                f"(overlap={overlap}, substring={substring_matches:.1f})"
            )
    
    # Sort by score (highest first)
    scored_templates.sort(key=lambda x: x[1], reverse=True)
    
    if not scored_templates:
        logger.warning(f"No matching pattern template found for theme '{theme.name}'")
        return None
    
    best_template, best_score = scored_templates[0]
    logger.info(
        f"Selected template '{best_template.name}' (ID: {best_template.template_id}) "
        f"with score {best_score:.1f}"
    )
    
    return best_template


def generate_strudel_code(
    theme: Theme,
    template: StrudelPatternTemplate,
    persona: ReiPersonaGraph,
    domain_knowledge: ReiDomainKnowledge,
    bpm: Optional[int] = None
) -> StrudelPattern:
    """
    Generate Tidal Cycles code by filling pattern template parameters with LLM
    
    This function uses Ollama to intelligently fill template parameters based on
    the technical theme, musical context, and Rei's production knowledge.
    
    Args:
        theme: The technical theme to express musically
        template: The pattern template to use as structure
        persona: Rei's persona graph (production style)
        domain_knowledge: Rei's music production knowledge
        bpm: Optional BPM override (defaults to theme suggestion or config default)
        
    Returns:
        StrudelPattern: Generated pattern with executable Tidal Cycles code
    """
    from services.ollama_service import OllamaService
    
    logger.info(
        f"Generating Strudel code for theme '{theme.name}' "
        f"using template '{template.name}'"
    )
    
    # Initialize Ollama service
    ollama_model = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama = OllamaService(model=ollama_model, base_url=ollama_base_url)
    
    # Determine BPM
    config = ReiToeiConfig()
    final_bpm = bpm or theme.suggested_bpm or config.default_bpm
    
    # Build system prompt with Rei's production knowledge
    tidal_syntax = domain_knowledge.tidal_cycles_syntax
    synth_guidelines = domain_knowledge.synth_selection_guidelines
    
    system_prompt = f"""You are {persona.identity['name']}, expert in Tidal Cycles algorithmic music composition.

Your expertise:
- Tidal Cycles patterns: {', '.join(tidal_syntax.get('core_functions', [])[:8])}
- Pattern transformations: {', '.join(tidal_syntax.get('transformations', [])[:6])}
- Production style: {', '.join(persona.production_knowledge.get('production_techniques', [])[:5])}

You generate precise Tidal Cycles code that transforms technical concepts into algorithmic music patterns.

Output ONLY valid Tidal Cycles code. No markdown, no explanations, no code fences.
"""
    
    # Get template parameter descriptions
    param_descriptions = []
    for param_name, param_value in template.parameters.items():
        param_descriptions.append(f"  - {param_name}: {type(param_value).__name__} (default: {param_value})")
    
    params_text = "\n".join(param_descriptions)
    
    # Build user prompt
    user_prompt = f"""Generate Tidal Cycles code for this technical theme:

Theme: {theme.name}
Technical concepts: {', '.join(theme.technical_concepts)}
Mood: {theme.suggested_mood or 'aggressive_technical'}
BPM: {final_bpm}

Pattern template: {template.name}
Description: {template.description}
Intensity: {template.intensity}
Suitable synths: {', '.join(template.synth_types)}

Template structure:
{template.code_template}

Parameters to fill:
{params_text}

Example:
{template.example}

Your task:
1. Choose appropriate parameter values that reflect the technical theme
2. Select synth types that match the mood
3. Fill the template with your chosen values
4. Output ONLY the final executable Tidal Cycles code

Output the complete pattern code (no markdown, no explanations):"""
    
    # Call Ollama LLM
    response_text = ollama._chat(system_prompt, user_prompt, max_tokens=512)
    
    logger.debug(f"Ollama Strudel response: {response_text[:150]}...")
    
    # Clean response (remove any markdown artifacts)
    clean_code = response_text.strip()
    
    # Remove markdown code fences if present
    if "```" in clean_code:
        # Remove opening code fence with optional language identifier
        if clean_code.startswith("```"):
            # Find the end of the first line (language identifier line)
            first_newline = clean_code.find("\n")
            if first_newline != -1:
                clean_code = clean_code[first_newline + 1:]
            else:
                # No newline found, remove just the fence
                clean_code = clean_code[3:]
        
        # Remove closing code fence
        if clean_code.endswith("```"):
            clean_code = clean_code[:-3]
        
        # Handle case where there might be extra backticks in the middle
        # (shouldn't happen, but be defensive)
        clean_code = clean_code.strip()
    
    # Generate pattern ID
    pattern_id = f"rei_strudel_{datetime.now().strftime('%Y_%m_%d_%H%M%S')}"
    
    # Create StrudelPattern object
    pattern = StrudelPattern(
        pattern_id=pattern_id,
        title=f"{theme.name} - {template.name}",
        theme=theme.name,
        strudel_code=clean_code,
        bpm=final_bpm,
        duration_bars=config.strudel_default_bars,
        synths=template.synth_types,
        evidence_ids=theme.evidence_ids[:20],  # Cap at 20
        generated_at=datetime.now().isoformat(),
        executed=False,
        execution_status=None,
        template_used=template.template_id
    )
    
    logger.info(
        f"Generated Strudel pattern '{pattern.title}' "
        f"(ID: {pattern.pattern_id}, {len(clean_code)} chars code)"
    )
    
    return pattern


def validate_strudel_syntax(strudel_code: str) -> ValidationResult:
    """
    Validate Tidal Cycles syntax using regex and structural checks
    
    Checks for:
    - Balanced parentheses, brackets, braces
    - Valid Tidal function names
    - Proper string quoting
    - No forbidden characters or patterns
    
    Args:
        strudel_code: The Tidal Cycles code to validate
        
    Returns:
        ValidationResult: Validation result with errors and warnings
    """
    import re
    
    logger.info(f"Validating Strudel syntax ({len(strudel_code)} chars)")
    
    errors: List[str] = []
    warnings: List[str] = []
    line_numbers: List[int] = []
    
    # Check for balanced parentheses
    paren_count = strudel_code.count("(") - strudel_code.count(")")
    if paren_count != 0:
        errors.append(f"Unbalanced parentheses (difference: {paren_count})")
    
    # Check for balanced brackets
    bracket_count = strudel_code.count("[") - strudel_code.count("]")
    if bracket_count != 0:
        errors.append(f"Unbalanced brackets (difference: {bracket_count})")
    
    # Check for balanced braces
    brace_count = strudel_code.count("{") - strudel_code.count("}")
    if brace_count != 0:
        errors.append(f"Unbalanced braces (difference: {brace_count})")
    
    # Check for balanced quotes
    # Count non-escaped double quotes
    double_quote_count = len(re.findall(r'(?<!\\\\)"', strudel_code))
    if double_quote_count % 2 != 0:
        errors.append(f"Unbalanced double quotes (count: {double_quote_count})")
    
    # Check for common Tidal functions (warnings if none found)
    common_functions = [
        r'\bs\(',           # s() - sample player
        r'\bnote\(',       # note() - note patterns
        r'\bstack\(',      # stack() - layering
        r'\.fast\(',       # .fast() - speed up
        r'\.slow\(',       # .slow() - slow down
        r'\.gain\(',       # .gain() - volume
        r'\.lpf\(',        # .lpf() - low-pass filter
        r'\.euclid\(',     # .euclid() - euclidean rhythm
        r'\.every\(',      # .every() - periodic transformation
    ]
    
    has_tidal_function = False
    for func_pattern in common_functions:
        if re.search(func_pattern, strudel_code):
            has_tidal_function = True
            break
    
    if not has_tidal_function:
        warnings.append("No recognized Tidal Cycles functions found - may not be valid Strudel code")
    
    # Check for forbidden patterns
    forbidden_patterns = [
        (r'eval\(', "eval() is forbidden for security"),
        (r'require\(', "require() is forbidden for security"),
        (r'import\s+', "import statements not allowed in Strudel patterns"),
        (r'__', "Double underscore (dunder) methods not allowed"),
    ]
    
    for pattern, error_msg in forbidden_patterns:
        if re.search(pattern, strudel_code):
            errors.append(error_msg)
    
    # Line-by-line checks
    lines = strudel_code.split("\n")
    for i, line in enumerate(lines, start=1):
        line_stripped = line.strip()
        
        # Skip empty lines and comments
        if not line_stripped or line_stripped.startswith("//"):
            continue
        
        # Check for unterminated strings
        if line_stripped.count('"') % 2 != 0 and not line_stripped.endswith("\\"):
            errors.append(f"Line {i}: Unterminated string")
            line_numbers.append(i)
        
        # Check for suspicious characters
        if re.search(r'[^\x00-\x7F]', line_stripped):
            warnings.append(f"Line {i}: Contains non-ASCII characters")
            line_numbers.append(i)
    
    # Overall validation
    valid = len(errors) == 0
    
    result = ValidationResult(
        valid=valid,
        errors=errors,
        warnings=warnings,
        line_numbers=list(set(line_numbers))  # Deduplicate
    )
    
    logger.info(
        f"Validation complete: valid={valid}, "
        f"errors={len(errors)}, warnings={len(warnings)}"
    )
    
    return result


async def execute_strudel_pattern(
    pattern: StrudelPattern,
    websocket_url: Optional[str] = None
) -> ExecutionResult:
    """
    Execute a Strudel pattern by sending it to the Strudel MCP agent via WebSocket
    
    This function establishes a WebSocket connection to the Strudel bridge server
    (agents/strudel_mcp_agent.py) and sends the pattern code for live execution.
    
    Args:
        pattern: The StrudelPattern to execute
        websocket_url: Optional WebSocket URL (defaults to STRUDEL_WS_URL env var)
        
    Returns:
        ExecutionResult: Execution result with success status and timing
        
    Raises:
        Exception: If WebSocket connection fails
    """
    import asyncio
    import aiohttp
    import time
    
    logger.info(f"Executing Strudel pattern: {pattern.pattern_id}")
    
    # Get WebSocket URL from env or use default
    if websocket_url is None:
        websocket_url = os.getenv("STRUDEL_WS_URL", "ws://localhost:4321")
    
    logger.debug(f"Connecting to Strudel MCP agent at {websocket_url}")
    
    # Build WebSocket payload
    payload = {
        "type": "eval",
        "code": pattern.strudel_code,
        "metadata": {
            "pattern_id": pattern.pattern_id,
            "title": pattern.title,
            "theme": pattern.theme,
            "bpm": pattern.bpm,
            "duration_bars": pattern.duration_bars,
            "generated_at": pattern.generated_at
        }
    }
    
    start_time = time.time()
    
    try:
        # Import websockets for WebSocket connection
        import websockets
        
        # Connect to WebSocket server
        async with websockets.connect(websocket_url, timeout=10) as websocket:
            # Send payload
            await websocket.send(json.dumps(payload))
            logger.debug("Sent pattern code to Strudel MCP agent")
            
            # Wait for acknowledgment (optional, with timeout)
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                response_data = json.loads(response)
                logger.debug(f"Received response: {response_data}")
            except asyncio.TimeoutError:
                logger.debug("No response from Strudel server (expected for one-way eval)")
                response_data = {"status": "sent"}
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        result = ExecutionResult(
            success=True,
            pattern_id=pattern.pattern_id,
            message=f"Pattern executed successfully on Strudel MCP agent ({elapsed_ms}ms)",
            error=None,
            execution_time_ms=elapsed_ms
        )
        
        logger.info(f"Pattern execution successful: {pattern.pattern_id} ({elapsed_ms}ms)")
        return result
        
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        error_msg = f"Failed to execute pattern: {str(e)}"
        logger.error(error_msg)
        
        result = ExecutionResult(
            success=False,
            pattern_id=pattern.pattern_id,
            message="Pattern execution failed",
            error=error_msg,
            execution_time_ms=elapsed_ms
        )
        
        return result


def save_pattern_to_library(
    pattern: StrudelPattern,
    library_path: Optional[Path] = None
) -> bool:
    """
    Save a generated Strudel pattern to the persistent pattern library (JSONL format)
    
    Each line in the JSONL file is a complete JSON object representing one pattern.
    This allows efficient appending without loading the entire file.
    
    Args:
        pattern: The StrudelPattern to save
        library_path: Optional custom path (defaults to data/avatar/rei_toei_generated_patterns.jsonl)
        
    Returns:
        bool: True if save successful, False otherwise
    """
    if library_path is None:
        library_path = Path("data/avatar/rei_toei_generated_patterns.jsonl")
    
    logger.info(f"Saving pattern {pattern.pattern_id} to library at {library_path}")
    
    try:
        # Ensure directory exists
        library_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert pattern to dict
        pattern_dict = {
            "pattern_id": pattern.pattern_id,
            "title": pattern.title,
            "theme": pattern.theme,
            "strudel_code": pattern.strudel_code,
            "bpm": pattern.bpm,
            "duration_bars": pattern.duration_bars,
            "synths": pattern.synths,
            "evidence_ids": pattern.evidence_ids,
            "generated_at": pattern.generated_at,
            "executed": pattern.executed,
            "execution_status": pattern.execution_status,
            "template_used": pattern.template_used
        }
        
        # Append as JSONL (one JSON object per line)
        with open(library_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(pattern_dict) + "\n")
        
        logger.info(f"Pattern {pattern.pattern_id} saved successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save pattern {pattern.pattern_id}: {e}")
        return False


def load_pattern_from_library(
    pattern_id: Optional[str] = None,
    library_path: Optional[Path] = None,
    limit: int = 100
) -> List[StrudelPattern]:
    """
    Load Strudel patterns from the persistent pattern library (JSONL format)
    
    Args:
        pattern_id: Optional pattern ID to filter by (returns only matching pattern)
        library_path: Optional custom path (defaults to data/avatar/rei_toei_generated_patterns.jsonl)
        limit: Maximum number of patterns to load (default: 100, most recent first)
        
    Returns:
        List[StrudelPattern]: List of loaded patterns (empty if none found)
    """
    if library_path is None:
        library_path = Path("data/avatar/rei_toei_generated_patterns.jsonl")
    
    if not library_path.exists():
        logger.warning(f"Pattern library not found at {library_path}")
        return []
    
    logger.info(f"Loading patterns from library at {library_path}")
    
    patterns: List[StrudelPattern] = []
    
    try:
        with open(library_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # Read in reverse order (most recent first)
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            
            try:
                pattern_dict = json.loads(line)
                
                # Filter by pattern_id if specified
                if pattern_id and pattern_dict.get("pattern_id") != pattern_id:
                    continue
                
                # Reconstruct StrudelPattern object
                pattern = StrudelPattern(
                    pattern_id=pattern_dict["pattern_id"],
                    title=pattern_dict["title"],
                    theme=pattern_dict["theme"],
                    strudel_code=pattern_dict["strudel_code"],
                    bpm=pattern_dict["bpm"],
                    duration_bars=pattern_dict["duration_bars"],
                    synths=pattern_dict["synths"],
                    evidence_ids=pattern_dict["evidence_ids"],
                    generated_at=pattern_dict["generated_at"],
                    executed=pattern_dict.get("executed", False),
                    execution_status=pattern_dict.get("execution_status"),
                    template_used=pattern_dict.get("template_used")
                )
                
                patterns.append(pattern)
                
                # Stop if we found the specific pattern
                if pattern_id:
                    break
                
                # Stop if we hit the limit
                if len(patterns) >= limit:
                    break
                    
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Skipping malformed pattern entry: {e}")
                continue
        
        logger.info(f"Loaded {len(patterns)} patterns from library")
        return patterns
        
    except Exception as e:
        logger.error(f"Failed to load patterns from library: {e}")
        return []


# ============================================================================
# Module Initialization
# ============================================================================

# Singleton service instance (lazy initialization)
_rei_service: Optional[ReiToeiService] = None


def get_rei_service() -> ReiToeiService:
    """
    Get singleton Rei Toei service instance
    
    Returns:
        ReiToeiService: The service instance
    """
    global _rei_service
    if _rei_service is None:
        _rei_service = ReiToeiService()
    return _rei_service
