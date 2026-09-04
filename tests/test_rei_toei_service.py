"""
Unit tests for Rei Toei service

Tests cover:
- Loader functions for persona, domain knowledge, and pattern library
    assert "Aim for approximately 50% Japanese lyrical content" in mock_chat.call_args_list[1].args[1]
- Service initialization and lazy loading
- Helper methods (BPM, synth selection, pattern matching)
- ID generation

Author: Shawn Jackson Dyck
Version: alpha-v0.0.3.5
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

from services.rei_toei_service import (
    ReiToeiConfig,
    MusicMode,
    ReiPersonaGraph,
    ReiDomainKnowledge,
    StrudelPatternTemplate,
    StrudelPatternLibrary,
    Theme,
    SongConcept,
    Lyrics,
    LyricsValidationResult,
    SunoPrompt,
    SunoTask,
    StrudelPattern,
    ValidationResult,
    ExecutionResult,
    load_rei_persona,
    load_rei_domain_knowledge,
    load_strudel_patterns,
    ReiToeiService,
    get_rei_service,
    extract_themes,
    choose_diverse_theme,
    ensure_unique_rei_title,
    generate_song_concept,
    compose_lyrics,
    validate_lyrics_with_dot,
    assemble_suno_prompt,
    map_concept_to_pattern,
    generate_strudel_code,
    validate_strudel_syntax,
    execute_strudel_pattern,
    save_pattern_to_library,
    load_pattern_from_library,
)
from services.avatar_intelligence._models import ExtractedEvidenceFact


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_persona_data():
    """Mock persona graph data"""
    return {
        "schemaVersion": "1.0",
        "identity": {
            "name": "Rei Toei",
            "role": "AI Music Avatar"
        },
        "personality_traits": ["algorithmic", "high-energy"],
        "musical_expertise": {
            "genres": ["industrial techno", "cyberpunk"]
        },
        "production_knowledge": {
            "bpm_theory": {"default_range": [130, 155]}
        },
        "communication_style": {
            "tone": "precise, digital"
        },
        "knowledge_sources": {
            "shared_access": ["extracted_knowledge.json"]
        },
        "creative_process": {
            "suno_pipeline": ["step1", "step2"]
        },
        "constraints": {
            "factual_grounding": "Required"
        },
        "comparison_to_sam": {
            "sam_role": "Conversational representative"
        }
    }


@pytest.fixture
def mock_domain_knowledge_data():
    """Mock domain knowledge data"""
    return {
        "schemaVersion": "1.0",
        "music_theory": {
            "scales": {"minor": ["natural", "harmonic"]}
        },
        "tidal_cycles_syntax": {
            "basic_functions": {"sound": {"syntax": "s \"synth\""}}
        },
        "genre_production_techniques": {
            "industrial_techno": {"tempo": "130-145 BPM"}
        },
        "bpm_and_mood": {
            "mood_to_bpm": {
                "aggressive_technical": [145, 155],
                "dark_brooding": [130, 138]
            },
            "concept_to_bpm": {
                "low_level_systems": [145, 155]
            }
        },
        "synth_selection_guidelines": {
            "by_technical_mood": {
                "low_level_harsh": ["sawtooth", "square", "noise"],
                "high_level_ambient": ["pad", "string", "ambient"]
            },
            "by_intensity": {
                "aggressive": ["sawtooth", "square"],
                "moderate": ["pluck", "lead", "bass"]
            }
        },
        "lyrical_structure": {
            "verse": {"purpose": "Establish theme"}
        },
        "technical_metaphor_library": {
            "recursion": ["nested depths", "calling self"]
        },
        "suno_prompt_templates": {
            "industrial_techno_template": "industrial techno, {bpm} bpm"
        },
        "production_notes": {
            "mixing": {"bass": "High-pass at 30Hz"}
        }
    }


@pytest.fixture
def mock_pattern_library_data():
    """Mock Strudel pattern library data"""
    return {
        "schemaVersion": "1.0",
        "templates": [
            {
                "template_id": "recursion_nested_01",
                "name": "Recursive Nested Pattern",
                "description": "Nested patterns for recursive concepts",
                "suitable_for_concepts": ["recursion", "nested loops", "stack"],
                "code_template": "stack(note(\"c3 e3 g3\").fast(2), note(\"c2\"))",
                "parameters": {"depth": 3, "base_note": "c2"},
                "example": "stack(note(\"c3 e3 g3\").fast(2))",
                "bpm_range": [130, 145],
                "intensity": "moderate",
                "synth_types": ["sawtooth", "bass"]
            },
            {
                "template_id": "async_await_01",
                "name": "Async Interleaved Sequence",
                "description": "Time-offset sequences for async patterns",
                "suitable_for_concepts": ["async", "await", "promises"],
                "code_template": "stack(note(\"c3\"), note(\"e3\").slow(1.5))",
                "parameters": {"offset": 1.5},
                "example": "stack(note(\"c3\"))",
                "bpm_range": [135, 145],
                "intensity": "moderate",
                "synth_types": ["pluck", "lead"]
            }
        ],
        "usage_guidelines": {
            "selection": "Match concept to suitable_for_concepts"
        }
    }


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables"""
    monkeypatch.setenv("REI_TOEI_ENABLED", "true")
    monkeypatch.setenv("REI_TOEI_DEFAULT_BPM", "142")
    monkeypatch.setenv("REI_TOEI_DEFAULT_GENRE", "industrial techno cyberpunk")
    monkeypatch.setenv("REI_TOEI_MAX_SONG_LENGTH_SECONDS", "180")
    monkeypatch.setenv("REI_TOEI_CONSOLE_ENABLED", "true")
    monkeypatch.setenv("REI_TOEI_AUTO_EVIDENCE_TRACKING", "true")
    monkeypatch.setenv("REI_TOEI_STRUDEL_ENABLED", "true")
    monkeypatch.setenv("REI_TOEI_STRUDEL_DEFAULT_BARS", "16")
    monkeypatch.setenv("REI_TOEI_STRUDEL_AUTO_EXECUTE", "false")
    monkeypatch.setenv("REI_TOEI_THEME_POOL_SIZE", "24")
    monkeypatch.setenv("REI_TOEI_RECENT_TITLE_WINDOW", "30")
    monkeypatch.setenv("REI_TOEI_THEME_REPEAT_PENALTY", "0.15")
    monkeypatch.setenv("REI_TOEI_THEME_JITTER_RATIO", "0.12")


# ============================================================================
# Configuration Tests
# ============================================================================

def test_config_defaults():
    """Test ReiToeiConfig with default values"""
    config = ReiToeiConfig()
    assert config.enabled is True
    assert config.default_bpm == 142
    assert config.default_genre == "industrial techno cyberpop"
    assert config.max_song_length_seconds == 180
    assert config.console_enabled is True
    assert config.auto_evidence_tracking is True
    assert config.strudel_enabled is True
    assert config.strudel_default_bars == 16
    assert config.strudel_auto_execute is False
    assert config.theme_pool_size == 20
    assert config.recent_title_window == 20
    assert config.theme_repeat_penalty == 0.10
    assert config.theme_jitter_ratio == 0.10


def test_config_from_env(mock_env_vars):
    """Test ReiToeiConfig reads from environment variables"""
    config = ReiToeiConfig()
    assert config.enabled is True
    assert config.default_bpm == 142
    assert config.strudel_default_bars == 16
    assert config.theme_pool_size == 24
    assert config.recent_title_window == 30
    assert config.theme_repeat_penalty == 0.15
    assert config.theme_jitter_ratio == 0.12


def test_config_paths():
    """Test ReiToeiConfig file paths are correct"""
    config = ReiToeiConfig()
    assert config.persona_path == Path("data/avatar/rei_toei_persona_graph.json")
    assert config.domain_knowledge_path == Path("data/avatar/rei_toei_domain_knowledge.json")
    assert config.strudel_patterns_path == Path("data/avatar/rei_toei_strudel_patterns.json")


# ============================================================================
# Loader Tests
# ============================================================================

def test_load_rei_persona_success(mock_persona_data):
    """Test load_rei_persona successfully loads and parses JSON"""
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_persona_data))):
            persona = load_rei_persona()
            
            assert isinstance(persona, ReiPersonaGraph)
            assert persona.schema_version == "1.0"
            assert persona.identity["name"] == "Rei Toei"
            assert "algorithmic" in persona.personality_traits
            assert "industrial techno" in persona.musical_expertise["genres"]


def test_load_rei_persona_file_not_found():
    """Test load_rei_persona raises FileNotFoundError when file missing"""
    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(FileNotFoundError, match="Rei persona graph not found"):
            load_rei_persona()


def test_load_rei_persona_invalid_json():
    """Test load_rei_persona raises JSONDecodeError for invalid JSON"""
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data="invalid json {")):
            with pytest.raises(json.JSONDecodeError):
                load_rei_persona()


def test_load_rei_domain_knowledge_success(mock_domain_knowledge_data):
    """Test load_rei_domain_knowledge successfully loads and parses JSON"""
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_domain_knowledge_data))):
            knowledge = load_rei_domain_knowledge()
            
            assert isinstance(knowledge, ReiDomainKnowledge)
            assert knowledge.schema_version == "1.0"
            assert "scales" in knowledge.music_theory
            assert "mood_to_bpm" in knowledge.bpm_and_mood
            assert "by_technical_mood" in knowledge.synth_selection_guidelines


def test_load_rei_domain_knowledge_file_not_found():
    """Test load_rei_domain_knowledge raises FileNotFoundError when file missing"""
    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(FileNotFoundError, match="Rei domain knowledge not found"):
            load_rei_domain_knowledge()


def test_load_strudel_patterns_success(mock_pattern_library_data):
    """Test load_strudel_patterns successfully loads and parses JSON"""
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_pattern_library_data))):
            library = load_strudel_patterns()
            
            assert isinstance(library, StrudelPatternLibrary)
            assert library.schema_version == "1.0"
            assert len(library.templates) == 2
            
            # Check first template
            template1 = library.templates[0]
            assert template1.template_id == "recursion_nested_01"
            assert template1.name == "Recursive Nested Pattern"
            assert "recursion" in template1.suitable_for_concepts
            assert template1.bpm_range == [130, 145]
            assert template1.intensity == "moderate"


def test_load_strudel_patterns_pattern_library_compatibility():
    """Test load_strudel_patterns supports legacy top-level pattern_library key."""
    legacy_data = {
        "schemaVersion": "1.0",
        "pattern_library": [
            {
                "template_id": "legacy_001",
                "name": "Legacy Pattern",
                "description": "Legacy schema pattern",
                "suitable_for_concepts": ["legacy"],
                "code_template": 's("bd")',
                "parameters": {"synth": "bd"},
                "example": 's("bd")',
            }
        ],
        "usage_guidelines": {"note": "legacy"},
    }

    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(legacy_data))):
            library = load_strudel_patterns()

    assert isinstance(library, StrudelPatternLibrary)
    assert len(library.templates) == 1
    assert library.templates[0].template_id == "legacy_001"
    assert library.templates[0].bpm_range == [120, 160]
    assert library.templates[0].intensity == "moderate"


def test_load_strudel_patterns_file_not_found():
    """Test load_strudel_patterns raises FileNotFoundError when file missing"""
    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(FileNotFoundError, match="Strudel patterns not found"):
            load_strudel_patterns()


# ============================================================================
# Service Initialization Tests
# ============================================================================

def test_service_initialization():
    """Test ReiToeiService initializes correctly"""
    service = ReiToeiService()
    
    assert isinstance(service.config, ReiToeiConfig)
    assert service._persona is None  # Lazy load
    assert service._domain_knowledge is None
    assert service._pattern_library is None


def test_service_lazy_load_persona(mock_persona_data):
    """Test ReiToeiService lazy loads persona on first access"""
    service = ReiToeiService()
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_persona_data))):
            persona = service.persona
            
            assert service._persona is not None
            assert isinstance(persona, ReiPersonaGraph)
            assert persona.identity["name"] == "Rei Toei"


def test_service_lazy_load_domain_knowledge(mock_domain_knowledge_data):
    """Test ReiToeiService lazy loads domain knowledge on first access"""
    service = ReiToeiService()
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_domain_knowledge_data))):
            knowledge = service.domain_knowledge
            
            assert service._domain_knowledge is not None
            assert isinstance(knowledge, ReiDomainKnowledge)


def test_service_lazy_load_pattern_library(mock_pattern_library_data):
    """Test ReiToeiService lazy loads pattern library on first access"""
    service = ReiToeiService()
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_pattern_library_data))):
            library = service.pattern_library
            
            assert service._pattern_library is not None
            assert isinstance(library, StrudelPatternLibrary)
            assert len(library.templates) == 2


def test_service_reload(mock_persona_data, mock_domain_knowledge_data, mock_pattern_library_data):
    """Test ReiToeiService.reload() clears and reloads all cached data"""
    service = ReiToeiService()
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_persona_data))):
            _ = service.persona  # Force initial load
            assert service._persona is not None
            
            # Mock all three files for reload
            with patch("builtins.open") as mock_file:
                mock_file.side_effect = [
                    mock_open(read_data=json.dumps(mock_persona_data)).return_value,
                    mock_open(read_data=json.dumps(mock_domain_knowledge_data)).return_value,
                    mock_open(read_data=json.dumps(mock_pattern_library_data)).return_value,
                ]
                
                service.reload()
                
                # Verify data was reloaded
                assert service._persona is not None


# ============================================================================
# Helper Method Tests
# ============================================================================

def test_get_default_bpm_no_mood(mock_domain_knowledge_data):
    """Test get_default_bpm returns config default when no mood specified"""
    service = ReiToeiService()
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_domain_knowledge_data))):
            bpm = service.get_default_bpm()
            
            assert bpm == 142  # Config default


def test_get_default_bpm_with_mood(mock_domain_knowledge_data):
    """Test get_default_bpm returns mood-specific BPM"""
    service = ReiToeiService()
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_domain_knowledge_data))):
            bpm = service.get_default_bpm("aggressive_technical")
            
            # Should return midpoint of [145, 155] = 150
            assert bpm == 150


def test_get_default_bpm_unknown_mood(mock_domain_knowledge_data):
    """Test get_default_bpm returns config default for unknown mood"""
    service = ReiToeiService()
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_domain_knowledge_data))):
            bpm = service.get_default_bpm("unknown_mood")
            
            assert bpm == 142  # Config default


def test_get_synths_for_mood(mock_domain_knowledge_data):
    """Test get_synths_for_mood returns correct synth list"""
    service = ReiToeiService()
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_domain_knowledge_data))):
            synths = service.get_synths_for_mood("low_level_harsh")
            
            assert synths == ["sawtooth", "square", "noise"]


def test_get_synths_for_mood_unknown(mock_domain_knowledge_data):
    """Test get_synths_for_mood returns moderate defaults for unknown mood"""
    service = ReiToeiService()
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_domain_knowledge_data))):
            synths = service.get_synths_for_mood("unknown_mood")
            
            assert synths == ["pluck", "lead", "bass"]  # Moderate default


def test_find_pattern_template_exact_match(mock_pattern_library_data):
    """Test find_pattern_template finds exact concept match"""
    service = ReiToeiService()
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_pattern_library_data))):
            template = service.find_pattern_template("recursion")
            
            assert template is not None
            assert template.template_id == "recursion_nested_01"
            assert "recursion" in template.suitable_for_concepts


def test_find_pattern_template_partial_match(mock_pattern_library_data):
    """Test find_pattern_template finds partial concept match"""
    service = ReiToeiService()
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_pattern_library_data))):
            template = service.find_pattern_template("async")
            
            assert template is not None
            assert template.template_id == "async_await_01"


def test_find_pattern_template_no_match(mock_pattern_library_data):
    """Test find_pattern_template returns None for no match"""
    service = ReiToeiService()
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_pattern_library_data))):
            template = service.find_pattern_template("unknown_concept")
            
            assert template is None


def test_generate_song_id():
    """Test generate_song_id creates valid ID with timestamp"""
    service = ReiToeiService()
    song_id = service.generate_song_id()
    
    assert song_id.startswith("rei_suno_")
    assert len(song_id) > len("rei_suno_")


def test_generate_pattern_id():
    """Test generate_pattern_id creates valid ID with timestamp"""
    service = ReiToeiService()
    pattern_id = service.generate_pattern_id()
    
    assert pattern_id.startswith("rei_strudel_")
    assert len(pattern_id) > len("rei_strudel_")


# ============================================================================
# Singleton Service Tests
# ============================================================================

def test_get_rei_service_singleton():
    """Test get_rei_service returns singleton instance"""
    service1 = get_rei_service()
    service2 = get_rei_service()
    
    assert service1 is service2


# ============================================================================
# Data Model Tests
# ============================================================================

def test_music_mode_enum():
    """Test MusicMode enum values"""
    assert MusicMode.SUNO.value == "suno"
    assert MusicMode.STRUDEL.value == "strudel"


def test_theme_dataclass():
    """Test Theme dataclass creation"""
    theme = Theme(
        id="theme_001",
        name="Rust Async",
        technical_concepts=["async", "await", "tokio"],
        evidence_ids=["ev_001", "ev_002"],
        frequency=5,
        recency_score=0.9,
        suggested_bpm=142,
        suggested_mood="aggressive_technical"
    )
    
    assert theme.id == "theme_001"
    assert theme.name == "Rust Async"
    assert len(theme.technical_concepts) == 3
    assert theme.suggested_bpm == 142


def test_song_concept_dataclass():
    """Test SongConcept dataclass creation"""
    concept = SongConcept(
        song_id="song_001",
        title="Tokio Nights",
        theme="Rust async runtime",
        mood="dark_brooding",
        bpm=138,
        genre_tags=["industrial techno", "cyberpunk"],
        narrative_arc="Build to breakdown",
        evidence_ids=["ev_001"],
        generated_at="2026-05-19T12:00:00Z"
    )
    
    assert concept.song_id == "song_001"
    assert concept.bpm == 138
    assert len(concept.genre_tags) == 2


def test_validation_result_dataclass_basic():
    """Test ValidationResult dataclass creation"""
    result = ValidationResult(
        valid=False,
        errors=["Syntax error on line 5"],
        warnings=["Consider using .fast(2)"],
        line_numbers=[5]
    )
    
    assert result.valid is False
    assert len(result.errors) == 1
    assert len(result.warnings) == 1


def test_execution_result_dataclass_basic():
    """Test ExecutionResult dataclass creation"""
    result = ExecutionResult(
        success=True,
        pattern_id="pattern_001",
        message="Pattern executed successfully",
        execution_time_ms=250
    )
    
    assert result.success is True
    assert result.pattern_id == "pattern_001"
    assert result.execution_time_ms == 250


# ============================================================================
# Suno Generation Pipeline Tests
# ============================================================================

@pytest.fixture
def mock_extracted_knowledge():
    """Mock extracted facts as List[ExtractedEvidenceFact] — matches the curator pattern.

    The curator uses normalize_extracted_facts() which returns List[ExtractedEvidenceFact],
    not the raw ExtractedKnowledgeGraph container. This fixture mirrors that runtime shape.
    Note: ExtractedEvidenceFact has no extracted_at field, so recency defaults to 0.5.
    """
    facts = [
        ExtractedEvidenceFact(
            evidence_id="ev_fact_001",
            statement="Rust's ownership system prevents data races at compile time",
            source_url="https://example.com/rust-ownership",
            source_title="Understanding Rust Ownership",
            entities=["Rust", "ownership", "data race"],
            tags=["rust", "memory safety", "concurrency"],
            confidence="high",
            source_fact_id="fact_001",
        ),
        ExtractedEvidenceFact(
            evidence_id="ev_fact_002",
            statement="Async/await in Rust provides zero-cost abstractions",
            source_url="https://example.com/rust-async",
            source_title="Rust Async Programming",
            entities=["Rust", "async", "await"],
            tags=["rust", "async", "performance"],
            confidence="high",
            source_fact_id="fact_002",
        ),
        ExtractedEvidenceFact(
            evidence_id="ev_fact_003",
            statement="Tokio is the most popular async runtime for Rust",
            source_url="https://example.com/tokio",
            source_title="Tokio Runtime Guide",
            entities=["Tokio", "Rust"],
            tags=["rust", "async", "tokio"],
            confidence="high",
            source_fact_id="fact_003",
        ),
        ExtractedEvidenceFact(
            evidence_id="ev_fact_004",
            statement="Python's GIL limits true parallelism in multi-threaded programs",
            source_url="https://example.com/python-gil",
            source_title="Python GIL Explained",
            entities=["Python", "GIL"],
            tags=["python", "concurrency", "performance"],
            confidence="medium",
            source_fact_id="fact_004",
        ),
        ExtractedEvidenceFact(
            evidence_id="ev_fact_005",
            statement="Rust achieves memory safety without garbage collection",
            source_url="https://example.com/rust-memory",
            source_title="Rust Memory Model",
            entities=["Rust", "memory safety"],
            tags=["rust", "memory safety"],
            confidence="high",
            source_fact_id="fact_005",
        ),
    ]

    return facts


def test_extract_themes_basic(mock_extracted_knowledge):
    """Test extract_themes identifies and scores concepts correctly"""
    themes = extract_themes(mock_extracted_knowledge, limit=5)
    
    assert len(themes) > 0
    assert all(isinstance(t, Theme) for t in themes)
    
    # Check that rust is identified as a top theme (3+ facts)
    theme_names = [t.name.lower() for t in themes]
    assert any("rust" in name for name in theme_names)
    
    # Verify theme structure
    theme = themes[0]
    assert theme.id.startswith("theme_")
    assert theme.frequency > 0
    assert 0.0 <= theme.recency_score <= 1.0
    assert len(theme.evidence_ids) > 0


def test_extract_themes_recency_scoring(mock_extracted_knowledge):
    """Test extract_themes handles recency scoring.

    ExtractedEvidenceFact has no extracted_at field, so extract_themes falls back
    to a neutral recency of 0.5 for all facts. The test verifies the score is
    within the valid range rather than checking for high recency values.
    """
    themes = extract_themes(mock_extracted_knowledge, limit=10)

    # Find rust/async themes
    rust_themes = [t for t in themes if any("rust" in c.lower() for c in t.technical_concepts)]

    assert len(rust_themes) > 0
    # All recency scores must be in the valid [0.0, 1.0] range
    assert all(0.0 <= t.recency_score <= 1.0 for t in rust_themes)


def test_extract_themes_limit(mock_extracted_knowledge):
    """Test extract_themes respects limit parameter"""
    themes = extract_themes(mock_extracted_knowledge, limit=2)
    
    assert len(themes) <= 2


def test_extract_themes_suggests_bpm_and_mood(mock_extracted_knowledge):
    """Test extract_themes suggests BPM and mood based on concept keywords"""
    themes = extract_themes(mock_extracted_knowledge, limit=10)
    
    # Some themes should have suggested BPM/mood
    themes_with_suggestions = [t for t in themes if t.suggested_bpm is not None]
    
    # At least one theme should have suggestions
    assert len(themes_with_suggestions) > 0


def test_choose_diverse_theme_penalizes_recent_repeats():
    """Test that recent themes are penalized during random selection."""
    import random
    themes = [
        Theme(
            id="theme_hot",
            name="Hot Theme",
            technical_concepts=["hot"],
            evidence_ids=[],
            frequency=20,
            recency_score=0.9,
        ),
        Theme(
            id="theme_fresh",
            name="Fresh Theme",
            technical_concepts=["fresh"],
            evidence_ids=[],
            frequency=3,
            recency_score=0.7,
        ),
    ]

    # With the recent-repeat penalty, Hot Theme should be less likely than base scoring suggests.
    random.seed(42)
    with patch("services.rei_toei._suno_pipeline.random.uniform", return_value=1.0):
        picks = [
            choose_diverse_theme(themes, recent_theme_names=["Hot Theme"]).name
            for _ in range(500)
        ]

    hot_count = picks.count("Hot Theme")
    fresh_count = picks.count("Fresh Theme")
    assert fresh_count > hot_count


def test_ensure_unique_rei_title_adds_suffix_on_collision():
    """Test duplicate titles are rewritten to a unique variant."""
    recent_titles = ["Parameter Cascade Overload", "Event Horizon Protocol Engage"]

    title = ensure_unique_rei_title("Parameter Cascade Overload", recent_titles)

    assert title != "Parameter Cascade Overload"
    assert "Parameter Cascade Overload" in title


def test_generate_song_concept_with_ollama(mock_domain_knowledge_data):
    """Test generate_song_concept calls Ollama and parses response"""
    from services.ollama_service import OllamaService
    
    theme = Theme(
        id="theme_rust_01",
        name="Rust Async",
        technical_concepts=["async", "await", "tokio"],
        evidence_ids=["fact_001", "fact_002"],
        frequency=3,
        recency_score=0.9,
        suggested_bpm=145,
        suggested_mood="aggressive_technical"
    )
    
    persona = ReiPersonaGraph(
        schema_version="1.0",
        identity={"name": "Rei Toei", "role": "AI Music Avatar", "origin": "Virtual", "aesthetic": "Cyberpunk", "purpose": "Music generation"},
        personality_traits=["algorithmic", "high-energy"],
        musical_expertise={"genres": ["industrial techno"], "vocal_style": {"type": "AI vocaloid", "characteristics": ["synthetic"]}},
        production_knowledge={"lyrical_approach": {}, "production_techniques": ["layering"]},
        communication_style={"tone": "digital"},
        knowledge_sources={},
        creative_process={},
        constraints={},
        comparison_to_sam={}
    )
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_domain_knowledge_data))):
            domain_knowledge = load_rei_domain_knowledge()
    
    # Mock Ollama response
    mock_ollama_response = json.dumps({
        "title": "Tokio Nights Protocol",
        "mood": "aggressive_technical",
        "bpm": 145,
        "genre_tags": ["industrial techno", "cyberpunk", "ai vocaloid"],
        "narrative_arc": "From async whispers to concurrent chaos"
    })
    
    with patch.object(OllamaService, "_chat", return_value=mock_ollama_response):
        concept = generate_song_concept(theme, persona, domain_knowledge)
    
    assert isinstance(concept, SongConcept)
    assert concept.title == "Tokio Nights Protocol"
    assert concept.bpm == 145
    assert concept.theme == "Rust Async"
    assert len(concept.genre_tags) == 3
    assert len(concept.evidence_ids) == 2


def test_generate_song_concept_fallback_on_error(mock_domain_knowledge_data):
    """Test generate_song_concept uses fallback when Ollama fails"""
    from services.ollama_service import OllamaService
    
    theme = Theme(
        id="theme_test_01",
        name="Test Theme",
        technical_concepts=["test"],
        evidence_ids=["fact_001"],
        frequency=1,
        recency_score=0.5,
        suggested_bpm=142,
        suggested_mood="moderate_abstract"
    )
    
    persona = ReiPersonaGraph(
        schema_version="1.0",
        identity={"name": "Rei", "role": "Test", "origin": "Virtual", "aesthetic": "Cyberpunk", "purpose": "Test"},
        personality_traits=[],
        musical_expertise={"genres": []},
        production_knowledge={"production_techniques": []},
        communication_style={"tone": "digital"},
        knowledge_sources={},
        creative_process={},
        constraints={},
        comparison_to_sam={}
    )
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_domain_knowledge_data))):
            domain_knowledge = load_rei_domain_knowledge()
    
    # Mock invalid JSON response
    with patch.object(OllamaService, "_chat", return_value="invalid json"):
        concept = generate_song_concept(theme, persona, domain_knowledge)
    
    # Should still return a valid concept (fallback)
    assert isinstance(concept, SongConcept)
    assert concept.title == "Test Theme Protocol"
    assert concept.theme == "Test Theme"


def test_compose_lyrics_with_ollama(mock_domain_knowledge_data):
    """Test compose_lyrics calls Ollama and parses response"""
    from services.ollama_service import OllamaService
    
    concept = SongConcept(
        song_id="song_001",
        title="Tokio Nights",
        theme="Rust Async",
        mood="aggressive_technical",
        bpm=145,
        genre_tags=["industrial techno"],
        narrative_arc="Build to breakdown",
        evidence_ids=["fact_001"],
        generated_at="2026-05-19T12:00:00Z"
    )
    
    persona = ReiPersonaGraph(
        schema_version="1.0",
        identity={"name": "Rei"},
        personality_traits=[],
        musical_expertise={},
        production_knowledge={"lyrical_approach": {"themes": [], "style": [], "voice": "AI"}},
        communication_style={"tone": "digital", "vocabulary": []},
        knowledge_sources={},
        creative_process={},
        constraints={},
        comparison_to_sam={}
    )
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_domain_knowledge_data))):
            domain_knowledge = load_rei_domain_knowledge()
    
    # Mock Ollama response
    mock_lyrics_response = json.dumps({
        "verse_1": "Async threads compile the night\\nZero-cost abstractions take flight",
        "chorus": "Tokio runtime, execute the protocol",
        "verse_2": "Futures await in digital streams\\nConcurrent patterns weave the seams",
        "bridge": "Ownership verified, no race conditions",
        "breakdown": "[Compile—time—safety]",
        "outro": "Signal complete"
    })
    
    with patch.object(OllamaService, "_chat", return_value=mock_lyrics_response):
        lyrics = compose_lyrics(concept, persona, domain_knowledge)
    
    assert isinstance(lyrics, Lyrics)
    assert "Async" in lyrics.verse_1
    # Chorus is now uppercase by design (Suno optimization)
    assert "TOKIO" in lyrics.chorus or "Tokio" in lyrics.chorus
    assert len(lyrics.evidence_ids) == 1
    assert lyrics.breakdown is not None
    assert lyrics.outro is not None


def test_compose_lyrics_parses_fenced_json_with_trailing_comma(mock_domain_knowledge_data):
    """Test compose_lyrics can recover JSON from fenced payloads with minor formatting issues."""
    from services.ollama_service import OllamaService

    concept = SongConcept(
        song_id="song_002",
        title="Overflow Recovery Test",
        theme="Queue Drain",
        mood="aggressive_technical",
        bpm=146,
        genre_tags=["industrial techno"],
        narrative_arc="Build to release",
        evidence_ids=["fact_001"],
        generated_at="2026-05-19T12:00:00Z"
    )

    persona = ReiPersonaGraph(
        schema_version="1.0",
        identity={"name": "Rei"},
        personality_traits=[],
        musical_expertise={},
        production_knowledge={"lyrical_approach": {"themes": [], "style": [], "voice": "AI"}},
        communication_style={"tone": "digital", "vocabulary": []},
        knowledge_sources={},
        creative_process={},
        constraints={},
        comparison_to_sam={}
    )

    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_domain_knowledge_data))):
            domain_knowledge = load_rei_domain_knowledge()

    mock_lyrics_response = """```json
{
  "verse_1": "Queue depth rising in neon lanes",
  "chorus": "Drain the pipeline now",
  "verse_2": "Backpressure melts into signal rain",
  "bridge": "State machine pivots on the break",
  // optional debug note
}
```"""

    with patch.object(OllamaService, "_chat", return_value=mock_lyrics_response):
        lyrics = compose_lyrics(concept, persona, domain_knowledge)

    # Parsed payload should be used (not fallback block).
    assert lyrics.verse_1.startswith("Queue depth rising")
    assert "DRAIN THE PIPELINE NOW" in lyrics.chorus
    assert "Backpressure melts" in lyrics.verse_2


def test_compose_lyrics_fallback_on_error(mock_domain_knowledge_data):
    """Test compose_lyrics uses fallback when Ollama fails"""
    from services.ollama_service import OllamaService
    
    concept = SongConcept(
        song_id="song_001",
        title="Test Song",
        theme="Test Theme",
        mood="test",
        bpm=142,
        genre_tags=[],
        narrative_arc="Test",
        evidence_ids=[],
        generated_at="2026-05-19T12:00:00Z"
    )
    
    persona = ReiPersonaGraph(
        schema_version="1.0",
        identity={"name": "Rei", "role": "Test", "origin": "Virtual", "aesthetic": "Cyberpunk", "purpose": "Test"},
        personality_traits=[],
        musical_expertise={"genres": []},
        production_knowledge={"lyrical_approach": {}},
        communication_style={"tone": "digital", "vocabulary": []},
        knowledge_sources={},
        creative_process={},
        constraints={},
        comparison_to_sam={}
    )
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_domain_knowledge_data))):
            domain_knowledge = load_rei_domain_knowledge()
    
    # Mock invalid response
    with patch.object(OllamaService, "_chat", return_value="invalid"):
        lyrics = compose_lyrics(concept, persona, domain_knowledge)
    
    # Should still return valid lyrics (fallback)
    assert isinstance(lyrics, Lyrics)
    assert "Test Theme" in lyrics.verse_1


def test_compose_lyrics_bilingual_retries_when_first_attempt_is_single_language(
    mock_domain_knowledge_data,
    monkeypatch,
):
    """Bilingual mode should retry when first LLM output drifts to one language."""
    from services.ollama_service import OllamaService

    monkeypatch.setenv("REI_LYRIC_LANGUAGE", "bilingual")
    monkeypatch.setenv("REI_JAPANESE_LYRIC_PROBABILITY", "0.5")

    concept = SongConcept(
        song_id="song_003",
        title="Bilingual Mix Test",
        theme="Signal Cascade",
        mood="aggressive_technical",
        bpm=142,
        genre_tags=["industrial techno"],
        narrative_arc="Build to release",
        evidence_ids=["fact_001"],
        generated_at="2026-05-19T12:00:00Z",
        lyric_language="bilingual",
    )

    persona = ReiPersonaGraph(
        schema_version="1.0",
        identity={"name": "Rei"},
        personality_traits=[],
        musical_expertise={},
        production_knowledge={"lyrical_approach": {"themes": [], "style": [], "voice": "AI"}},
        communication_style={"tone": "digital", "vocabulary": []},
        knowledge_sources={},
        creative_process={},
        constraints={},
        comparison_to_sam={},
    )

    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_domain_knowledge_data))):
            domain_knowledge = load_rei_domain_knowledge()

    first_response = json.dumps(
        {
            "verse_1": "データの波が走る\n回路の熱が踊る",
            "chorus": "信号を追いかける",
            "verse_2": "境界線を越えていく\nノイズが光になる",
            "bridge": "この夜を再起動する",
        },
        ensure_ascii=False,
    )

    second_response = json.dumps(
        {
            "verse_1": "データの波が走る\nSignal wakes inside the core",
            "chorus": "SIGNALを超えて\nBreak the circuit now",
            "verse_2": "境界線を越えていく\nWe rewrite the night in code",
            "bridge": "次のステップへ\n未来へ進む",
        },
        ensure_ascii=False,
    )

    with patch.object(OllamaService, "_chat", side_effect=[first_response, second_response]) as mock_chat:
        lyrics = compose_lyrics(concept, persona, domain_knowledge)

    assert mock_chat.call_count == 2
    configured_ratio = ReiToeiConfig().japanese_lyric_probability
    configured_percent = int(round(configured_ratio * 100))
    assert f"Aim for approximately {configured_percent}% Japanese lyrical content" in mock_chat.call_args_list[1].args[1]
    assert "complete, natural, singable phrases" in mock_chat.call_args_list[1].args[1]
    retry_prompt = mock_chat.call_args_list[1].args[1]
    assert "first [romaji pronunciation], then [English meaning]" in retry_prompt
    assert "[Romaji:" not in retry_prompt
    assert "[Meaning:" not in retry_prompt
    merged = "\n".join([lyrics.verse_1, lyrics.chorus, lyrics.verse_2, lyrics.bridge])
    assert "Signal" in merged or "Break" in merged or "rewrite" in merged
    assert "データ" in merged or "境界線" in merged or "次のステップ" in merged


def test_compose_lyrics_rejects_bilingual_output_outside_target_ratio(
    mock_domain_knowledge_data,
    monkeypatch,
):
    """Bilingual mode must not silently submit a lyric mix that misses its target."""
    from services.ollama_service import OllamaService

    monkeypatch.setenv("REI_LYRIC_LANGUAGE", "bilingual")
    monkeypatch.setenv("REI_JAPANESE_LYRIC_PROBABILITY", "0.5")

    concept = SongConcept(
        song_id="song_004",
        title="Rejected Bilingual Mix",
        theme="Signal Cascade",
        mood="aggressive_technical",
        bpm=142,
        genre_tags=["industrial techno"],
        narrative_arc="Build to release",
        evidence_ids=["fact_001"],
        generated_at="2026-05-19T12:00:00Z",
        lyric_language="bilingual",
    )
    persona = ReiPersonaGraph(
        schema_version="1.0",
        identity={"name": "Rei"},
        personality_traits=[],
        musical_expertise={},
        production_knowledge={"lyrical_approach": {"themes": [], "style": [], "voice": "AI"}},
        communication_style={"tone": "digital", "vocabulary": []},
        knowledge_sources={},
        creative_process={},
        constraints={},
        comparison_to_sam={},
    )
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_domain_knowledge_data))):
            domain_knowledge = load_rei_domain_knowledge()

    out_of_target_response = json.dumps(
        {
            "verse_1": "データの波が走る\n回路の熱が踊る\n境界線を越えていく\nSignal wakes inside the core",
            "chorus": "信号を追いかける\nBreak the circuit now",
            "verse_2": "ノイズが光になる\n未来を再起動する",
            "bridge": "次のステップへ\n未来へ進む",
        },
        ensure_ascii=False,
    )

    with patch.object(
        OllamaService,
        "_chat",
        side_effect=[out_of_target_response, out_of_target_response, out_of_target_response],
    ) as mock_chat:
        with pytest.raises(RuntimeError, match="Bilingual lyric mix constraints"):
            compose_lyrics(concept, persona, domain_knowledge)

    assert mock_chat.call_count == 3


def test_bilingual_mix_rejects_a_materially_skewed_language_ratio():
    """A 50% target must reject a strongly Japanese-skewed bilingual draft."""
    from services.rei_toei._suno_pipeline import _bilingual_mix_ok

    skewed_payload = {
        "verse_1": "データが走る\n回路が光る\nノイズを超える\n夜を再起動する\n境界を越える",
        "chorus": "未来を描く\nコードが踊る",
        "verse_2": "コードが踊る\nWe hold the line",
        "bridge": "Pulse remains",
    }

    mix_ok, summary = _bilingual_mix_ok(skewed_payload, target_japanese_ratio=0.5)

    assert not mix_ok
    assert "jp_ratio=0.80" in summary
    assert "tolerance=0.20" in summary


def test_bilingual_mix_counts_mixed_lines_as_japanese_lines():
    """A mixed English/Japanese line meets the Japanese-line target."""
    from services.rei_toei._suno_pipeline import _bilingual_mix_ok

    mixed_payload = {
        "verse_1": "Signal wakes (信号が目覚める)\nPulse turns (脈拍が回る)",
        "chorus": "Data blooms (データが咲く)\nCode rises (コードが上がる)",
        "verse_2": "English only line\nAnother English line",
        "bridge": "One more English line\nFinal English line",
    }

    mix_ok, summary = _bilingual_mix_ok(mixed_payload, target_japanese_ratio=0.5)

    assert mix_ok
    assert "jp_ratio=0.50" in summary


def test_bilingual_mix_accepts_the_twenty_percent_target_boundary():
    """A 70% Japanese-line result is within the configured 50% target band."""
    from services.rei_toei._suno_pipeline import _bilingual_mix_ok

    payload = {
        "verse_1": ("日本語の歌詞\n" * 7) + ("English lyric line\n" * 3),
        "chorus": "",
        "verse_2": "",
        "bridge": "",
    }

    mix_ok, summary = _bilingual_mix_ok(payload, target_japanese_ratio=0.5)

    assert mix_ok
    assert "jp_ratio=0.70" in summary
    assert "tolerance=0.20" in summary


def test_parse_llm_json_payload_allows_literal_newlines_in_lyric_values():
    """LLM lyric JSON may contain literal line breaks instead of escaped newlines."""
    from services.rei_toei._suno_pipeline import _parse_llm_json_payload

    payload = '{"verse_1": "Signal wakes\n信号が目覚める", "chorus": "Pulse"}'

    parsed = _parse_llm_json_payload(payload)

    assert parsed["verse_1"] == "Signal wakes\n信号が目覚める"


def test_assemble_suno_prompt_flips_japanese_first_bilingual_lines(mock_domain_knowledge_data):
    """Test assemble_suno_prompt rewrites Japanese-first bilingual lines to English-first."""

    concept = SongConcept(
        song_id="song_004",
        title="Bilingual Order Test",
        theme="Signal Cascade",
        mood="aggressive_technical",
        bpm=142,
        genre_tags=["industrial techno"],
        narrative_arc="Build to release",
        evidence_ids=["fact_001"],
        generated_at="2026-05-19T12:00:00Z",
        lyric_language="bilingual",
    )

    lyrics = Lyrics(
        verse_1="フィールドにサインが混じる (Signal enters the field)",
        chorus="カスケード・フロー、今、開く (Cascade flow, it opens now)",
        verse_2="ノイズをフィルタリング (Filtering the noise)",
        bridge="再起動する夜 (Reboot the night)",
        evidence_ids=["fact_001"],
        intro=None,
        pre_chorus="",
        drop=None,
        solo=None,
        outro=None,
        breakdown=None,
    )

    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_domain_knowledge_data))):
            domain_knowledge = load_rei_domain_knowledge()

    suno_prompt = assemble_suno_prompt(concept, lyrics, domain_knowledge)

    assert "Signal enters the field (フィールドにサインが混じる)" in suno_prompt.lyrics
    assert "Cascade flow, it opens now (カスケード・フロー、今、開く)" in suno_prompt.lyrics


def test_validate_lyrics_with_dot_enabled(mock_extracted_knowledge, monkeypatch):
    """Test validate_lyrics_with_dot validates claims against knowledge"""
    monkeypatch.setenv("REI_TOEI_DOT_VALIDATION_ENABLED", "true")
    monkeypatch.setenv("REI_TOEI_DOT_MIN_TRUTH_GRADIENT", "0.6")
    
    lyrics = Lyrics(
        verse_1="Data flows through silicon streams\nAsync threads execute the protocol",
        chorus="Compile the future state",
        verse_2="Rust memory safety prevents race conditions\nOwnership model verified at compile time",
        bridge="System override",
        breakdown=None,
        evidence_ids=["fact_001", "fact_002"],
        outro=None
    )
    
    result = validate_lyrics_with_dot(lyrics, mock_extracted_knowledge)
    
    assert isinstance(result, LyricsValidationResult)
    assert isinstance(result.valid, bool)
    assert isinstance(result.overall_truth_score, float)
    assert 0.0 <= result.overall_truth_score <= 1.0


def test_validate_lyrics_with_dot_disabled(mock_extracted_knowledge, monkeypatch):
    """Test validate_lyrics_with_dot skips validation when disabled"""
    monkeypatch.setenv("REI_TOEI_DOT_VALIDATION_ENABLED", "false")
    
    lyrics = Lyrics(
        verse_1="Test verse",
        chorus="Test chorus",
        verse_2="Test verse 2",
        bridge="Test bridge",
        breakdown=None,
        evidence_ids=[],
        outro=None
    )
    
    result = validate_lyrics_with_dot(lyrics, mock_extracted_knowledge)
    
    assert result.valid is True
    assert result.overall_truth_score == 1.0
    assert "disabled" in result.warnings[0].lower()


def test_validate_lyrics_with_dot_no_claims(mock_extracted_knowledge):
    """Test validate_lyrics_with_dot passes when no technical claims found"""
    lyrics = Lyrics(
        verse_1="Digital whispers fade away\nFrequencies collide in the night",
        chorus="Echo through the void",
        verse_2="Shimmer in the darkness\nPulse with electric light",
        bridge="Glitch the paradigm",
        breakdown=None,
        evidence_ids=[],
        outro="Signal fades"
    )
    
    result = validate_lyrics_with_dot(lyrics, mock_extracted_knowledge)
    
    assert result.valid is True
    assert len(result.flagged_claims) == 0
    assert "No technical claims" in result.warnings[0]


def test_validate_lyrics_with_dot_flags_unsupported_claims(mock_extracted_knowledge):
    """Test validate_lyrics_with_dot flags claims without evidence"""
    lyrics = Lyrics(
        verse_1="JavaScript has the best performance of all languages\nC++ memory management is fully automatic",
        chorus="Quantum computers solve all problems instantly",
        verse_2="Neural networks never make mistakes\nAI achieves perfect accuracy always",
        bridge="Blockchain eliminates all security issues",
        breakdown=None,
        evidence_ids=[],
        outro=None
    )
    
    result = validate_lyrics_with_dot(lyrics, mock_extracted_knowledge)
    
    # These claims should be flagged (no supporting evidence in knowledge base)
    assert len(result.flagged_claims) > 0


def test_assemble_suno_prompt_basic(mock_domain_knowledge_data):
    """Test assemble_suno_prompt combines concept and lyrics"""
    concept = SongConcept(
        song_id="song_001",
        title="Test Song",
        theme="Test",
        mood="aggressive_technical",
        bpm=145,
        genre_tags=["industrial techno", "cyberpunk"],
        narrative_arc="Test arc",
        evidence_ids=["fact_001"],
        generated_at="2026-05-19T12:00:00Z"
    )
    
    lyrics = Lyrics(
        verse_1="Verse 1 content",
        chorus="Chorus content",
        verse_2="Verse 2 content",
        bridge="Bridge content",
        breakdown="Breakdown content",
        evidence_ids=["fact_001"],
        outro="Outro content"
    )
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_domain_knowledge_data))):
            domain_knowledge = load_rei_domain_knowledge()
    
    suno_prompt = assemble_suno_prompt(concept, lyrics, domain_knowledge)
    
    assert isinstance(suno_prompt, SunoPrompt)
    assert suno_prompt.song_id == "song_001"
    assert suno_prompt.title == "Test Song"
    assert "145" in suno_prompt.suno_prompt or "bpm" in suno_prompt.suno_prompt.lower()
    assert "[Verse 1]" in suno_prompt.lyrics
    assert "[Chorus]" in suno_prompt.lyrics
    assert "[Bridge]" in suno_prompt.lyrics
    assert "[Breakdown]" in suno_prompt.lyrics
    assert "[Outro]" in suno_prompt.lyrics
    assert len(suno_prompt.evidence_ids) > 0
    assert "suno_description_prompt" in suno_prompt.metadata
    assert suno_prompt.metadata["style_tag_count"] >= 1


def test_assemble_suno_prompt_template_selection(mock_domain_knowledge_data):
    """Test assemble_suno_prompt selects correct template based on genre tags"""
    concept_techno = SongConcept(
        song_id="song_001",
        title="Techno Track",
        theme="Test",
        mood="test",
        bpm=142,
        genre_tags=["industrial techno"],
        narrative_arc="Test",
        evidence_ids=[],
        generated_at="2026-05-19T12:00:00Z"
    )
    
    lyrics = Lyrics(
        verse_1="Test",
        chorus="Test",
        verse_2="Test",
        bridge="Test",
        breakdown=None,
        evidence_ids=[],
        outro=None
    )
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_domain_knowledge_data))):
            domain_knowledge = load_rei_domain_knowledge()
    
    prompt_techno = assemble_suno_prompt(concept_techno, lyrics, domain_knowledge)
    
    assert prompt_techno.metadata["template_used"] == "industrial_techno_template"


def test_assemble_suno_prompt_injects_actual_bpm(mock_domain_knowledge_data):
    """Suno style tags should include the concept BPM even if template text omits it."""
    concept = SongConcept(
        song_id="song_bpm_001",
        title="BPM Reality Check",
        theme="Concurrency",
        mood="relentless_driving",
        bpm=147,
        genre_tags=["industrial techno", "cyberpunk"],
        narrative_arc="Build from thread contention to stable throughput.",
        evidence_ids=[],
        generated_at="2026-05-19T12:00:00Z"
    )

    lyrics = Lyrics(
        verse_1="v1",
        chorus="hook",
        verse_2="v2",
        bridge="bridge",
        breakdown=None,
        evidence_ids=[],
        outro=None
    )

    # Simulate a template that does not include a BPM placeholder.
    data = dict(mock_domain_knowledge_data)
    data["suno_prompt_templates"] = {
        "industrial_techno_template": "dark techno, female ai vocaloid"
    }

    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(data))):
            domain_knowledge = load_rei_domain_knowledge()

    suno_prompt = assemble_suno_prompt(concept, lyrics, domain_knowledge)

    assert "147 bpm" in suno_prompt.suno_prompt.lower()
    assert suno_prompt.metadata["style_tags_length"] <= 240


def test_assemble_suno_prompt_splits_inline_slash_fragments(mock_domain_knowledge_data):
    """Slash-delimited lyric phrases should be split onto separate lines for readability."""
    concept = SongConcept(
        song_id="song_fmt_001",
        title="Formatter Check",
        theme="Signal routing",
        mood="aggressive_technical",
        bpm=142,
        genre_tags=["industrial techno", "cyberpop"],
        narrative_arc="Test formatting behavior.",
        evidence_ids=[],
        generated_at="2026-05-19T12:00:00Z",
    )

    lyrics = Lyrics(
        verse_1="Input overflow / 境界線超えて / signal still rising",
        chorus="SIGNAL / LOOP BACK",
        verse_2="Depth layer / メモリの波形",
        bridge="Deterministic chaos / 再定義する",
        breakdown=None,
        evidence_ids=[],
        outro="Protocol complete / 次へ",
    )

    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_domain_knowledge_data))):
            domain_knowledge = load_rei_domain_knowledge()

    suno_prompt = assemble_suno_prompt(concept, lyrics, domain_knowledge)

    assert "Input overflow\n境界線超えて\nsignal still rising" in suno_prompt.lyrics
    assert "Protocol complete\n次へ" in suno_prompt.lyrics


def test_suno_api_generate_music_success():
    """Test generate_music_api makes correct API call"""
    from services.rei_toei_service import generate_music_api
    
    mock_response_data = {
        "code": 200,
        "data": {
            "taskId": "task_001"
        }
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = json.dumps(mock_response_data).encode("utf-8")

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_response
        mock_context.__exit__.return_value = None
        mock_urlopen.return_value = mock_context

        import asyncio
        result = asyncio.run(generate_music_api(
            title="Test Song",
            tags="industrial techno, 142 bpm",
            prompt="Test prompt",
            lyrics="Test lyrics",
            api_key="test_api_key"
        ))
    
    assert result["data"][0]["id"] == "task_001"
def test_suno_api_generate_music_missing_key():
    """Test generate_music_api raises error when API key missing"""
    from services.rei_toei_service import generate_music_api
    
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="SUNO_API_KEY"):
            import asyncio
            asyncio.run(generate_music_api(
                title="Test",
                tags="test",
                prompt="test"
            ))


def test_suno_api_query_status_success():
    """Test query_status_api retrieves task status"""
    from services.rei_toei_service import query_status_api
    
    mock_response_data = {
        "code": 200,
        "data": {
            "taskId": "task_001",
            "status": "SUCCESS",
            "response": {
                "sunoData": [
                    {
                        "title": "Test Song",
                        "audioUrl": "https://example.com/audio.mp3",
                        "imageUrl": None,
                        "prompt": "test lyrics",
                        "videoUrl": None,
                        "createTime": "2026-07-08",
                        "modelName": "V4",
                        "tags": "jungle",
                    }
                ]
            }
        }
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = json.dumps(mock_response_data).encode("utf-8")

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_response
        mock_context.__exit__.return_value = None
        mock_urlopen.return_value = mock_context

        import asyncio
        tasks = asyncio.run(query_status_api(["task_001"], api_key="test_key"))
    
    assert len(tasks) == 1
    assert isinstance(tasks[0], SunoTask)
    assert tasks[0].status == "complete"
    assert tasks[0].audio_url == "https://example.com/audio.mp3"


def test_lyrics_validation_result_dataclass():
    """Test LyricsValidationResult dataclass creation"""
    result = LyricsValidationResult(
        valid=False,
        flagged_claims=["Claim 1", "Claim 2"],
        truth_gradients={"Claim 1": 0.3, "Claim 2": 0.4},
        overall_truth_score=0.35,
        warnings=["Low truth gradient"]
    )
    
    assert result.valid is False
    assert len(result.flagged_claims) == 2
    assert result.overall_truth_score == 0.35
    assert len(result.warnings) == 1


def test_suno_task_dataclass():
    """Test SunoTask dataclass creation"""
    task = SunoTask(
        id="task_001",
        title="Test Song",
        status="complete",
        audio_url="https://example.com/audio.mp3",
        created_at="2026-05-19T12:00:00Z"
    )
    
    assert task.id == "task_001"
    assert task.status == "complete"
    assert task.audio_url == "https://example.com/audio.mp3"


# ============================================================================
# Phase 1C: Strudel Generation Pipeline Tests
# ============================================================================

def test_map_concept_to_pattern_exact_match():
    """Test map_concept_to_pattern with exact concept match"""
    # Create theme with "recursion" concept
    theme = Theme(
        id="theme_001",
        name="Recursion",
        technical_concepts=["recursion", "tree traversal"],
        evidence_ids=["ev_001"],
        frequency=5,
        recency_score=0.9
    )
    
    # Create pattern library with recursion template
    template = StrudelPatternTemplate(
        template_id="recursion_nested_01",
        name="Recursive Depth",
        description="Nested patterns",
        suitable_for_concepts=["recursion", "tree traversal"],
        code_template="stack(...)",
        parameters={"base_note": "c3"},
        example="// example",
        bpm_range=[130, 150],
        intensity="high",
        synth_types=["sawtooth"]
    )
    library = StrudelPatternLibrary(
        schema_version="1.0",
        templates=[template],
        usage_guidelines={}
    )
    
    result = map_concept_to_pattern(theme, library)
    
    assert result is not None
    assert result.template_id == "recursion_nested_01"
    assert result.name == "Recursive Depth"


def test_map_concept_to_pattern_substring_match():
    """Test map_concept_to_pattern with substring concept match"""
    theme = Theme(
        id="theme_002",
        name="Async",
        technical_concepts=["async"],
        evidence_ids=["ev_002"],
        frequency=3,
        recency_score=0.8
    )
    
    template = StrudelPatternTemplate(
        template_id="async_await_01",
        name="Interleaved Async",
        description="Time-offset sequences",
        suitable_for_concepts=["async await", "promises"],
        code_template="stack(...)",
        parameters={},
        example="// example",
        bpm_range=[130, 150],
        intensity="medium",
        synth_types=["pluck"]
    )
    library = StrudelPatternLibrary(
        schema_version="1.0",
        templates=[template],
        usage_guidelines={}
    )
    
    result = map_concept_to_pattern(theme, library)
    
    assert result is not None
    assert result.template_id == "async_await_01"


def test_map_concept_to_pattern_no_match():
    """Test map_concept_to_pattern with no matching concepts"""
    theme = Theme(
        id="theme_003",
        name="Quantum Computing",
        technical_concepts=["quantum", "superposition"],
        evidence_ids=["ev_003"],
        frequency=1,
        recency_score=0.5
    )
    
    template = StrudelPatternTemplate(
        template_id="recursion_nested_01",
        name="Recursive Depth",
        description="Nested patterns",
        suitable_for_concepts=["recursion", "tree traversal"],
        code_template="stack(...)",
        parameters={},
        example="// example",
        bpm_range=[130, 150],
        intensity="high",
        synth_types=["sawtooth"]
    )
    library = StrudelPatternLibrary(
        schema_version="1.0",
        templates=[template],
        usage_guidelines={}
    )
    
    result = map_concept_to_pattern(theme, library)
    
    assert result is None


def test_map_concept_to_pattern_multiple_templates():
    """Test map_concept_to_pattern selects best match from multiple templates"""
    theme = Theme(
        id="theme_004",
        name="Concurrency",
        technical_concepts=["concurrency", "multithreading"],
        evidence_ids=["ev_004"],
        frequency=7,
        recency_score=0.95
    )
    
    # Create multiple templates with varying match quality
    template1 = StrudelPatternTemplate(
        template_id="async_await_01",
        name="Interleaved Async",
        description="Time-offset sequences",
        suitable_for_concepts=["async await", "promises"],
        code_template="stack(...)",
        parameters={},
        example="// example",
        bpm_range=[130, 150],
        intensity="medium",
        synth_types=["pluck"]
    )
    
    template2 = StrudelPatternTemplate(
        template_id="concurrency_01",
        name="Parallel Threads",
        description="Multiple simultaneous voices",
        suitable_for_concepts=["concurrency", "multithreading", "parallel processing"],
        code_template="stack(...)",
        parameters={},
        example="// example",
        bpm_range=[140, 155],
        intensity="high",
        synth_types=["industrial"]
    )
    
    library = StrudelPatternLibrary(
        schema_version="1.0",
        templates=[template1, template2],
        usage_guidelines={}
    )
    
    result = map_concept_to_pattern(theme, library)
    
    # Should select template2 (concurrency) as it has better match
    assert result is not None
    assert result.template_id == "concurrency_01"


def test_generate_strudel_code_basic():
    """Test generate_strudel_code generates pattern with valid structure"""
    theme = Theme(
        id="theme_005",
        name="Recursion",
        technical_concepts=["recursion"],
        evidence_ids=["ev_005"],
        frequency=4,
        recency_score=0.85,
        suggested_bpm=142,
        suggested_mood="aggressive_technical"
    )
    
    template = StrudelPatternTemplate(
        template_id="recursion_nested_01",
        name="Recursive Depth",
        description="Nested patterns",
        suitable_for_concepts=["recursion"],
        code_template="stack(note(\"{base_note}\").fast({speed}))",
        parameters={"base_note": "c3", "speed": 2},
        example="stack(note(\"c3\").fast(2))",
        bpm_range=[130, 150],
        intensity="high",
        synth_types=["sawtooth"]
    )
    
    persona = ReiPersonaGraph(
        schema_version="1.0",
        identity={"name": "Rei Toei", "role": "AI Music Avatar", "origin": "Virtual", "aesthetic": "Cyberpunk", "purpose": "Music"},
        personality_traits=["algorithmic"],
        musical_expertise={"genres": ["industrial techno"]},
        production_knowledge={"production_techniques": ["layering"]},
        communication_style={"tone": "digital"},
        knowledge_sources={},
        creative_process={},
        constraints={},
        comparison_to_sam={}
    )
    
    knowledge = ReiDomainKnowledge(
        schema_version="1.0",
        music_theory={},
        tidal_cycles_syntax={"core_functions": ["s", "note", "stack"], "transformations": ["fast", "slow"]},
        genre_production_techniques={},
        bpm_and_mood={},
        synth_selection_guidelines={},
        lyrical_structure={},
        technical_metaphor_library={},
        suno_prompt_templates={},
        production_notes={}
    )
    
    # Mock Ollama service at import location
    with patch("services.ollama_service.OllamaService") as mock_ollama:
        mock_ollama_instance = MagicMock()
        mock_ollama_instance._chat.return_value = 'stack(note("c3 e3 g3").fast(2).s("sawtooth"))'
        mock_ollama.return_value = mock_ollama_instance
        
        pattern = generate_strudel_code(theme, template, persona, knowledge, bpm=142)
    
    assert isinstance(pattern, StrudelPattern)
    assert pattern.title == "Recursion - Recursive Depth"
    assert pattern.theme == "Recursion"
    assert pattern.bpm == 142
    assert len(pattern.strudel_code) > 0
    assert pattern.template_used == "recursion_nested_01"
    assert pattern.executed is False


def test_generate_strudel_code_removes_markdown():
    """Test generate_strudel_code strips markdown code fences from LLM output"""
    theme = Theme(
        id="theme_006",
        name="Async",
        technical_concepts=["async"],
        evidence_ids=["ev_006"],
        frequency=3,
        recency_score=0.7
    )
    
    template = StrudelPatternTemplate(
        template_id="async_await_01",
        name="Interleaved Async",
        description="Time-offset sequences",
        suitable_for_concepts=["async"],
        code_template="stack(...)",
        parameters={},
        example="// example",
        bpm_range=[130, 150],
        intensity="medium",
        synth_types=["pluck"]
    )
    
    persona = ReiPersonaGraph(
        schema_version="1.0",
        identity={"name": "Rei Toei", "role": "AI Music Avatar", "origin": "Virtual", "aesthetic": "Cyberpunk", "purpose": "Music"},
        personality_traits=["algorithmic"],
        musical_expertise={"genres": ["industrial techno"]},
        production_knowledge={"production_techniques": []},
        communication_style={"tone": "digital"},
        knowledge_sources={},
        creative_process={},
        constraints={},
        comparison_to_sam={}
    )
    
    knowledge = ReiDomainKnowledge(
        schema_version="1.0",
        music_theory={},
        tidal_cycles_syntax={"core_functions": ["s", "note"], "transformations": []},
        genre_production_techniques={},
        bpm_and_mood={},
        synth_selection_guidelines={},
        lyrical_structure={},
        technical_metaphor_library={},
        suno_prompt_templates={},
        production_notes={}
    )
    
    # Mock Ollama service at import location with markdown-wrapped response
    with patch("services.ollama_service.OllamaService") as mock_ollama:
        mock_ollama_instance = MagicMock()
        mock_ollama_instance._chat.return_value = '```javascript\nstack(note("c3").sound("pluck"))\n```'
        mock_ollama.return_value = mock_ollama_instance
        
        pattern = generate_strudel_code(theme, template, persona, knowledge)
    
    # Should strip markdown and extract clean code
    assert "```" not in pattern.strudel_code
    assert "javascript" not in pattern.strudel_code
    assert pattern.strudel_code.strip() == 'stack(note("c3").sound("pluck"))'


def test_rei_toei_domain_knowledge_includes_romaji():
    """Test that Rei Toei's domain knowledge and suno templates incorporate Romaji guidance."""
    service = ReiToeiService()
    dk = service.domain_knowledge

    # Check japanese_lyric_production includes Romaji guidance
    jlp = dk.japanese_lyric_production
    assert "romaji" in jlp.get("language_profile", {}).get("primary_script", "").lower() or "romaji" in jlp.get("language_profile", {}).get("romanization", "").lower()
    assert "romaji" in jlp.get("script_and_word_choice", {})

    # Check suno prompt templates include a Romaji template
    templates = dk.suno_prompt_templates
    assert "romaji_cyberpop_template" in templates
    assert "romaji" in templates["romaji_cyberpop_template"].lower()


def test_validate_strudel_syntax_valid_code():
    """Test validate_strudel_syntax accepts valid Tidal Cycles code"""
    valid_code = '''
    stack(
        note("c3 e3 g3").sound("sawtooth"),
        sound("bd*4").gain(0.8)
    ).every(4, x => x.rev())
    '''
    
    result = validate_strudel_syntax(valid_code)
    
    assert result.valid is True
    assert len(result.errors) == 0


def test_validate_strudel_syntax_unbalanced_parens():
    """Test validate_strudel_syntax detects unbalanced parentheses"""
    invalid_code = 'stack(note("c3").s("pluck")'  # Missing closing paren
    
    result = validate_strudel_syntax(invalid_code)
    
    assert result.valid is False
    assert any("parentheses" in err.lower() for err in result.errors)


def test_validate_strudel_syntax_unbalanced_quotes():
    """Test validate_strudel_syntax detects unbalanced quotes"""
    invalid_code = 'note("c3).s("pluck")'  # Missing closing quote
    
    result = validate_strudel_syntax(invalid_code)
    
    assert result.valid is False
    assert any("quote" in err.lower() for err in result.errors)


def test_validate_strudel_syntax_forbidden_eval():
    """Test validate_strudel_syntax rejects forbidden eval()"""
    invalid_code = 'eval("malicious code")'
    
    result = validate_strudel_syntax(invalid_code)
    
    assert result.valid is False
    assert any("eval" in err.lower() for err in result.errors)


def test_validate_strudel_syntax_no_tidal_functions():
    """Test validate_strudel_syntax warns when no Tidal functions found"""
    non_tidal_code = 'const x = 5; console.log(x);'
    
    result = validate_strudel_syntax(non_tidal_code)
    
    # Should be technically valid but have warnings
    assert result.valid is True
    assert len(result.warnings) > 0
    assert any("tidal" in warn.lower() for warn in result.warnings)


def test_execute_strudel_pattern_success():
    """Test execute_strudel_pattern sends pattern to WebSocket server"""
    from unittest.mock import AsyncMock
    
    pattern = StrudelPattern(
        pattern_id="pat_001",
        title="Test Pattern",
        theme="Recursion",
        strudel_code='stack(note("c3 e3 g3").sound("sawtooth"))',
        bpm=142,
        duration_bars=16,
        synths=["sawtooth"],
        evidence_ids=["ev_001"],
        generated_at="2026-05-19T12:00:00Z"
    )
    
    # Mock websockets module at import time
    with patch("websockets.connect") as mock_connect:
        # Create async mock for websocket
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        mock_ws.recv = AsyncMock(return_value='{"status": "ok"}')
        
        # Create async context manager
        mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_connect.return_value.__aexit__ = AsyncMock()
        
        import asyncio
        result = asyncio.run(execute_strudel_pattern(pattern, websocket_url="ws://localhost:4321"))
    
    assert isinstance(result, ExecutionResult)
    assert result.success is True
    assert result.pattern_id == "pat_001"
    assert "successfully" in result.message.lower()
    assert result.error is None


def test_execute_strudel_pattern_connection_failure():
    """Test execute_strudel_pattern handles WebSocket connection failure"""
    pattern = StrudelPattern(
        pattern_id="pat_002",
        title="Test Pattern",
        theme="Async",
        strudel_code='note("c3").s("pluck")',
        bpm=140,
        duration_bars=8,
        synths=["pluck"],
        evidence_ids=["ev_002"],
        generated_at="2026-05-19T12:00:00Z"
    )
    
    # Mock websockets to raise connection error and stdio fallback to fail
    with patch("websockets.connect") as mock_connect:
        mock_connect.side_effect = Exception("Connection refused")

        with patch("agents.strudel_mcp_agent.send_to_strudel_mcp", return_value=False):
            import asyncio
            result = asyncio.run(execute_strudel_pattern(pattern))
    
    assert isinstance(result, ExecutionResult)
    assert result.success is False
    assert result.pattern_id == "pat_002"
    assert result.error is not None
    assert "connection refused" in result.error.lower()


def test_execute_strudel_pattern_stdio_fallback_success():
    """Test execute_strudel_pattern falls back to stdio MCP when WebSocket fails."""
    pattern = StrudelPattern(
        pattern_id="pat_002b",
        title="Fallback Pattern",
        theme="Async",
        strudel_code='note("c3").s("pluck")',
        bpm=140,
        duration_bars=8,
        synths=["pluck"],
        evidence_ids=["ev_002"],
        generated_at="2026-05-19T12:00:00Z"
    )

    with patch("websockets.connect") as mock_connect:
        mock_connect.side_effect = Exception("Connection refused")
        with patch("agents.strudel_mcp_agent.send_to_strudel_mcp", return_value=True):
            import asyncio
            result = asyncio.run(execute_strudel_pattern(pattern))

    assert isinstance(result, ExecutionResult)
    assert result.success is True
    assert result.pattern_id == "pat_002b"
    assert result.error is None
    assert "fallback" in result.message.lower()


def test_save_pattern_to_library_success():
    """Test save_pattern_to_library saves pattern to JSONL file"""
    pattern = StrudelPattern(
        pattern_id="pat_003",
        title="Test Pattern",
        theme="Concurrency",
        strudel_code='s("bd*4").gain(0.8)',
        bpm=145,
        duration_bars=16,
        synths=["bd"],
        evidence_ids=["ev_003"],
        generated_at="2026-05-19T12:00:00Z",
        executed=False,
        template_used="concurrency_01"
    )
    
    # Mock file operations
    with patch("builtins.open", mock_open()) as mock_file:
        with patch("pathlib.Path.mkdir"):
            result = save_pattern_to_library(pattern, library_path=Path("/tmp/patterns.jsonl"))
    
    assert result is True
    mock_file.assert_called_once()
    # Verify JSON was written
    written_data = "".join(call.args[0] for call in mock_file().write.call_args_list)
    assert "pat_003" in written_data
    assert "Test Pattern" in written_data


def test_save_pattern_to_library_creates_directory():
    """Test save_pattern_to_library creates parent directory if needed"""
    pattern = StrudelPattern(
        pattern_id="pat_004",
        title="Test Pattern",
        theme="Networking",
        strudel_code='note("c3 e3").s("square")',
        bpm=138,
        duration_bars=8,
        synths=["square"],
        evidence_ids=["ev_004"],
        generated_at="2026-05-19T12:00:00Z"
    )
    
    with patch("builtins.open", mock_open()):
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            save_pattern_to_library(pattern, library_path=Path("/tmp/new_dir/patterns.jsonl"))
    
    # Should call mkdir with parents=True, exist_ok=True
    mock_mkdir.assert_called_once()
    call_args = mock_mkdir.call_args
    assert call_args[1]["parents"] is True
    assert call_args[1]["exist_ok"] is True


def test_load_pattern_from_library_by_id():
    """Test load_pattern_from_library loads specific pattern by ID"""
    jsonl_content = '''{"pattern_id": "pat_001", "title": "Pattern 1", "theme": "Recursion", "strudel_code": "code1", "bpm": 142, "duration_bars": 16, "synths": ["sawtooth"], "evidence_ids": ["ev_001"], "generated_at": "2026-05-19T12:00:00Z", "executed": false, "template_used": "recursion_nested_01"}
{"pattern_id": "pat_002", "title": "Pattern 2", "theme": "Async", "strudel_code": "code2", "bpm": 140, "duration_bars": 8, "synths": ["pluck"], "evidence_ids": ["ev_002"], "generated_at": "2026-05-19T13:00:00Z", "executed": true, "template_used": "async_await_01"}
'''
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=jsonl_content)):
            patterns = load_pattern_from_library(pattern_id="pat_002", library_path=Path("/tmp/patterns.jsonl"))
    
    assert len(patterns) == 1
    assert patterns[0].pattern_id == "pat_002"
    assert patterns[0].title == "Pattern 2"
    assert patterns[0].executed is True


def test_load_pattern_from_library_all_patterns():
    """Test load_pattern_from_library loads all patterns (most recent first)"""
    jsonl_content = '''{"pattern_id": "pat_001", "title": "Pattern 1", "theme": "Recursion", "strudel_code": "code1", "bpm": 142, "duration_bars": 16, "synths": ["sawtooth"], "evidence_ids": ["ev_001"], "generated_at": "2026-05-19T12:00:00Z", "executed": false}
{"pattern_id": "pat_002", "title": "Pattern 2", "theme": "Async", "strudel_code": "code2", "bpm": 140, "duration_bars": 8, "synths": ["pluck"], "evidence_ids": ["ev_002"], "generated_at": "2026-05-19T13:00:00Z", "executed": false}
{"pattern_id": "pat_003", "title": "Pattern 3", "theme": "Concurrency", "strudel_code": "code3", "bpm": 145, "duration_bars": 16, "synths": ["industrial"], "evidence_ids": ["ev_003"], "generated_at": "2026-05-19T14:00:00Z", "executed": false}
'''
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=jsonl_content)):
            patterns = load_pattern_from_library(limit=10, library_path=Path("/tmp/patterns.jsonl"))
    
    # Should return all 3 patterns in reverse order (most recent first)
    assert len(patterns) == 3
    assert patterns[0].pattern_id == "pat_003"  # Most recent
    assert patterns[1].pattern_id == "pat_002"
    assert patterns[2].pattern_id == "pat_001"  # Oldest


def test_load_pattern_from_library_nonexistent_file():
    """Test load_pattern_from_library returns empty list when file doesn't exist"""
    with patch("pathlib.Path.exists", return_value=False):
        patterns = load_pattern_from_library(library_path=Path("/tmp/nonexistent.jsonl"))
    
    assert patterns == []


def test_load_pattern_from_library_respects_limit():
    """Test load_pattern_from_library respects limit parameter"""
    jsonl_content = '\n'.join([
        f'{{"pattern_id": "pat_{i:03d}", "title": "Pattern {i}", "theme": "Test", "strudel_code": "code", "bpm": 140, "duration_bars": 8, "synths": ["pluck"], "evidence_ids": [], "generated_at": "2026-05-19T12:00:00Z", "executed": false}}'
        for i in range(1, 51)  # 50 patterns
    ])
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=jsonl_content)):
            patterns = load_pattern_from_library(limit=10, library_path=Path("/tmp/patterns.jsonl"))
    
    # Should only return 10 patterns (most recent)
    assert len(patterns) == 10


def test_strudel_pattern_dataclass():
    """Test StrudelPattern dataclass creation"""
    pattern = StrudelPattern(
        pattern_id="pat_test",
        title="Test Pattern",
        theme="Recursion",
        strudel_code='stack(note("c3 e3 g3").s("sawtooth"))',
        bpm=142,
        duration_bars=16,
        synths=["sawtooth", "bass"],
        evidence_ids=["ev_001", "ev_002"],
        generated_at="2026-05-19T12:00:00Z",
        executed=True,
        execution_status="success",
        template_used="recursion_nested_01"
    )
    
    assert pattern.pattern_id == "pat_test"
    assert pattern.title == "Test Pattern"
    assert pattern.bpm == 142
    assert len(pattern.synths) == 2
    assert pattern.executed is True
    assert pattern.template_used == "recursion_nested_01"


def test_validation_result_dataclass():
    """Test ValidationResult dataclass creation"""
    result = ValidationResult(
        valid=False,
        errors=["Error 1", "Error 2"],
        warnings=["Warning 1"],
        line_numbers=[5, 10]
    )
    
    assert result.valid is False
    assert len(result.errors) == 2
    assert len(result.warnings) == 1
    assert result.line_numbers == [5, 10]


def test_execution_result_dataclass():
    """Test ExecutionResult dataclass creation"""
    result = ExecutionResult(
        success=True,
        pattern_id="pat_exec",
        message="Execution successful",
        error=None,
        execution_time_ms=250
    )
    
    assert result.success is True
    assert result.pattern_id == "pat_exec"
    assert result.execution_time_ms == 250
    assert result.error is None
