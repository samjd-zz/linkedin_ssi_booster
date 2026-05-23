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