"""
Rei Toei Configuration and Enums

Author: Shawn Jackson Dyck
Version: alpha-v0.0.2.7
"""

import os
from enum import Enum
from pathlib import Path


class MusicMode(Enum):
    """Music generation mode"""
    SUNO = "suno"
    STRUDEL = "strudel"


class ReiToeiConfig:
    """Configuration for Rei Toei service from environment variables"""
    
    def __init__(self):
        self.enabled = os.getenv("REI_TOEI_ENABLED", "true").lower() == "true"
        self.default_bpm = int(os.getenv("REI_TOEI_DEFAULT_BPM", "142"))
        self.default_genre = os.getenv("REI_TOEI_DEFAULT_GENRE", "industrial techno cyberpop")
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

        # Lyric language policy. In bilingual mode, Rei mixes Japanese + English
        # within the same song, and the configured probability acts as target JP ratio.
        lyric_language = os.getenv("REI_LYRIC_LANGUAGE", "bilingual").strip().lower()
        if lyric_language not in {"english", "japanese", "bilingual"}:
            raise ValueError(
                "REI_LYRIC_LANGUAGE must be one of: english, japanese, bilingual"
            )
        self.lyric_language = lyric_language
        japanese_probability = float(
            os.getenv("REI_JAPANESE_LYRIC_PROBABILITY", "0.25")
        )
        if not 0.0 <= japanese_probability <= 1.0:
            raise ValueError("REI_JAPANESE_LYRIC_PROBABILITY must be between 0.0 and 1.0")
        self.japanese_lyric_probability = japanese_probability

        # Theme diversity and title uniqueness tuning
        self.theme_pool_size = max(1, int(os.getenv("REI_TOEI_THEME_POOL_SIZE", "20")))
        self.recent_title_window = max(1, int(os.getenv("REI_TOEI_RECENT_TITLE_WINDOW", "20")))

        repeat_penalty = float(os.getenv("REI_TOEI_THEME_REPEAT_PENALTY", "0.10"))
        # Clamp to [0.01, 1.0] where lower values penalize repeats more strongly.
        self.theme_repeat_penalty = max(0.01, min(1.0, repeat_penalty))

        jitter_ratio = float(os.getenv("REI_TOEI_THEME_JITTER_RATIO", "0.10"))
        # Clamp to [0.0, 0.5] to avoid unstable weight swings.
        self.theme_jitter_ratio = max(0.0, min(0.5, jitter_ratio))
        
        # File paths
        self.persona_path = Path("data/avatar/rei_toei_persona_graph.json")
        self.domain_knowledge_path = Path("data/avatar/rei_toei_domain_knowledge.json")
        self.strudel_patterns_path = Path("data/avatar/rei_toei_strudel_patterns.json")