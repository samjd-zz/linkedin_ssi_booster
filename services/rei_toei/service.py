"""
ReiToeiService Class and Singleton

This module provides the main service orchestrator for Rei Toei music generation,
coordinating between Suno and Strudel pipelines with lazy-loaded knowledge.

Author: Shawn Jackson Dyck
Version: alpha-v0.0.3.5
"""

import logging
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.avatar_intelligence._models import PersonaGraph

from ._config import ReiToeiConfig
from ._models import (
    ReiPersonaGraph,
    ReiDomainKnowledge,
    StrudelPatternLibrary,
    StrudelPatternTemplate
)
from ._loaders import (
    load_rei_persona,
    load_rei_domain_knowledge,
    load_strudel_patterns
)

logger = logging.getLogger(__name__)


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
# Singleton Instance
# ============================================================================

_rei_service_instance: Optional[ReiToeiService] = None


def get_rei_service() -> ReiToeiService:
    """
    Get singleton instance of ReiToeiService
    
    Returns:
        ReiToeiService: The singleton service instance
    """
    global _rei_service_instance
    if _rei_service_instance is None:
        _rei_service_instance = ReiToeiService()
    return _rei_service_instance