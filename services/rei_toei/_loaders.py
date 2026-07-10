"""
Rei Toei Loader Functions

Functions to load Rei's persona, domain knowledge, and pattern library from JSON files.

Author: Shawn Jackson Dyck
Version: alpha-v0.0.2.7
"""

import json
import logging
from typing import TYPE_CHECKING

from services.rei_toei._config import ReiToeiConfig
from services.rei_toei._models import (
    ReiPersonaGraph,
    ReiDomainKnowledge,
    StrudelPatternLibrary,
    StrudelPatternTemplate,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


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
    
    logger.debug(f"Loading Rei persona from {persona_path}")
    
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
    
    logger.debug(f"Loaded Rei persona: {persona.identity.get('name', 'Unknown')}")
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
    
    logger.debug(f"Loading Rei domain knowledge from {knowledge_path}")
    
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
    
    logger.debug(f"Loaded Rei domain knowledge (schema: {knowledge.schema_version})")
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
    
    logger.debug(f"Loading Strudel patterns from {patterns_path}")
    
    with open(patterns_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Parse templates.
    # Backward compatibility: older files use "pattern_library" instead of "templates".
    raw_templates = data.get("templates")
    if raw_templates is None:
        raw_templates = data.get("pattern_library", [])

    templates = []
    for idx, template_data in enumerate(raw_templates):
        template_id = template_data.get("template_id") or f"template_{idx + 1:03d}"
        name = template_data.get("name", template_id)
        description = template_data.get("description", "")

        suitable_for_concepts = template_data.get("suitable_for_concepts")
        if not isinstance(suitable_for_concepts, list):
            concept = template_data.get("concept")
            suitable_for_concepts = [concept] if concept else []

        code_template = template_data.get("code_template") or template_data.get("code", "")
        if not code_template:
            logger.warning("Skipping template '%s' with no code_template/code", template_id)
            continue

        parameters = template_data.get("parameters", {})
        example = template_data.get("example", code_template)

        bpm_range = template_data.get("bpm_range", [120, 160])
        if not isinstance(bpm_range, list) or len(bpm_range) != 2:
            bpm_range = [120, 160]

        intensity = template_data.get("intensity", "moderate")
        synth_types = template_data.get("synth_types", [])
        if not isinstance(synth_types, list):
            synth_types = []
        if not synth_types and isinstance(parameters, dict):
            inferred = [
                str(v)
                for k, v in parameters.items()
                if k.startswith("synth") and isinstance(v, str)
            ]
            synth_types = inferred or ["sawtooth"]

        template = StrudelPatternTemplate(
            template_id=template_id,
            name=name,
            description=description,
            suitable_for_concepts=suitable_for_concepts,
            code_template=code_template,
            parameters=parameters,
            example=example,
            bpm_range=bpm_range,
            intensity=intensity,
            synth_types=synth_types,
        )
        templates.append(template)
    
    library = StrudelPatternLibrary(
        schema_version=data.get("schemaVersion", "1.0"),
        templates=templates,
        usage_guidelines=data.get("usage_guidelines", {})
    )
    
    logger.debug(f"Loaded {len(templates)} Strudel pattern templates")
    return library