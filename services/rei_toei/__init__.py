"""
Rei Toei Music Avatar Service Package

This package provides the core service for Rei Toei, the AI music avatar that transforms
curated technical knowledge into original music compositions via both Suno (vocal songs)
and Strudel (algorithmic patterns).

Author: Shawn Jackson Dyck
Version: alpha-v0.0.2.7
"""

# Re-export public API for backward compatibility with services.rei_toei_service

# Configuration
from services.rei_toei._config import ReiToeiConfig, MusicMode

# Data Models
from services.rei_toei._models import (
    ReiPersonaGraph,
    ReiDomainKnowledge,
    StrudelPatternTemplate,
    SunoGenerateRequest,
    SunoTask,
    StrudelPatternLibrary,
    Theme,
    SongConcept,
    Lyrics,
    LyricsValidationResult,
    SunoPrompt,
    StrudelPattern,
    ValidationResult,
    ExecutionResult,
)

# Loader Functions
from services.rei_toei._loaders import (
    load_rei_persona,
    load_rei_domain_knowledge,
    load_strudel_patterns,
)

# Suno HTTP Client Functions
from services.rei_toei._suno_client import (
    generate_music_api,
    query_status_api,
)

# Suno Pipeline Functions
from services.rei_toei._suno_pipeline import (
    extract_themes,
    generate_song_concept,
    compose_lyrics,
    validate_lyrics_with_dot,
    assemble_suno_prompt,
    submit_to_suno,
)

# Strudel Pipeline Functions
from services.rei_toei._strudel_pipeline import (
    map_concept_to_pattern,
    generate_strudel_code,
    validate_strudel_syntax,
    execute_strudel_pattern,
    save_pattern_to_library,
    load_pattern_from_library,
)

# Service Class and Singleton
from services.rei_toei.service import ReiToeiService, get_rei_service

# Define public API
__all__ = [
    # Configuration
    "ReiToeiConfig",
    "MusicMode",
    # Data Models
    "ReiPersonaGraph",
    "ReiDomainKnowledge",
    "StrudelPatternTemplate",
    "SunoGenerateRequest",
    "SunoTask",
    "StrudelPatternLibrary",
    "Theme",
    "SongConcept",
    "Lyrics",
    "LyricsValidationResult",
    "SunoPrompt",
    "StrudelPattern",
    "ValidationResult",
    "ExecutionResult",
    # Loader Functions
    "load_rei_persona",
    "load_rei_domain_knowledge",
    "load_strudel_patterns",
    # Suno HTTP Client
    "generate_music_api",
    "query_status_api",
    # Suno Pipeline
    "extract_themes",
    "generate_song_concept",
    "compose_lyrics",
    "validate_lyrics_with_dot",
    "assemble_suno_prompt",
    "submit_to_suno",
    # Strudel Pipeline
    "map_concept_to_pattern",
    "generate_strudel_code",
    "validate_strudel_syntax",
    "execute_strudel_pattern",
    "save_pattern_to_library",
    "load_pattern_from_library",
    # Service
    "ReiToeiService",
    "get_rei_service",
]