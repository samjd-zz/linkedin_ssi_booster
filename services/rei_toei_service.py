"""
Rei Toei Music Avatar Service (Compatibility Wrapper)

This module provides backward compatibility by re-exporting the refactored
rei_toei package API. The actual implementation has been split into:

- services/rei_toei/_config.py - Configuration and enums
- services/rei_toei/_models.py - Data models
- services/rei_toei/_loaders.py - Loader functions
- services/rei_toei/_suno_client.py - Suno HTTP client
- services/rei_toei/_suno_pipeline.py - Suno generation pipeline
- services/rei_toei/_suno_submission.py - Suno API submission orchestration
- services/rei_toei/_suno_validation.py - DoT lyric validation
- services/rei_toei/_strudel_pipeline.py - Strudel generation pipeline
- services/rei_toei/service.py - Main service class

All existing imports will continue to work:
    from services.rei_toei_service import get_rei_service, ReiToeiConfig, etc.

Author: Shawn Jackson Dyck
Version: alpha-v0.0.3.5
"""

# Re-export entire package API for backward compatibility
from services.rei_toei import *  # noqa: F401, F403

# Explicitly re-export commonly used items for clarity
from services.rei_toei import (
    # Configuration
    ReiToeiConfig,
    MusicMode,
    # Data Models
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
    # Loader Functions
    load_rei_persona,
    load_rei_domain_knowledge,
    load_strudel_patterns,
    # Suno HTTP Client
    generate_music_api,
    query_status_api,
    # Suno Pipeline
    extract_themes,
    choose_diverse_theme,
    load_recent_rei_titles,
    ensure_unique_rei_title,
    generate_song_concept,
    compose_lyrics,
    validate_lyrics_with_dot,
    assemble_suno_prompt,
    submit_to_suno,
    # Strudel Pipeline
    map_concept_to_pattern,
    generate_strudel_code,
    validate_strudel_syntax,
    execute_strudel_pattern,
    save_pattern_to_library,
    load_pattern_from_library,
    # Service
    ReiToeiService,
    get_rei_service,
)