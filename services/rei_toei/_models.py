"""
Rei Toei Data Models

All dataclasses for Rei Toei service.

Author: Shawn Jackson Dyck
Version: alpha-v0.0.2.7
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
    intro: Optional[str]
    verse_1: str
    pre_chorus: str
    chorus: str
    verse_2: str
    drop: Optional[str]
    bridge: str
    solo: Optional[str]
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