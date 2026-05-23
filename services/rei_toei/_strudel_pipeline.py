"""
Rei Toei Strudel Generation Pipeline

This module contains all functions for generating and executing Strudel/Tidal Cycles
algorithmic music patterns from technical themes.

Author: Shawn Jackson Dyck
Version: alpha-v0.0.2.7
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.avatar_intelligence._models import ExtractedEvidenceFact
    from services.rei_toei._models import (
        Theme, StrudelPatternLibrary, StrudelPatternTemplate,
        ReiPersonaGraph, ReiDomainKnowledge, StrudelPattern,
        ValidationResult, ExecutionResult
    )

logger = logging.getLogger(__name__)


def map_concept_to_pattern(
    theme: "Theme",
    pattern_library: "StrudelPatternLibrary"
) -> Optional["StrudelPatternTemplate"]:
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
    from services.rei_toei._models import StrudelPatternTemplate
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
    theme: "Theme",
    template: "StrudelPatternTemplate",
    persona: "ReiPersonaGraph",
    domain_knowledge: "ReiDomainKnowledge",
    bpm: Optional[int] = None
) -> "StrudelPattern":
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
    from services.rei_toei._config import ReiToeiConfig
    from services.rei_toei._models import StrudelPattern
    
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


def validate_strudel_syntax(strudel_code: str) -> "ValidationResult":
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
    from services.rei_toei._models import ValidationResult
    
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
    double_quote_count = len(re.findall(r'(?<!\\)"', strudel_code))
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
    pattern: "StrudelPattern",
    websocket_url: Optional[str] = None
) -> "ExecutionResult":
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
    from services.rei_toei._models import ExecutionResult
    
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
    pattern: "StrudelPattern",
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
) -> List["StrudelPattern"]:
    """
    Load Strudel patterns from the persistent pattern library (JSONL format)
    
    Args:
        pattern_id: Optional pattern ID to filter by (returns only matching pattern)
        library_path: Optional custom path (defaults to data/avatar/rei_toei_generated_patterns.jsonl)
        limit: Maximum number of patterns to load (default: 100, most recent first)
        
    Returns:
        List[StrudelPattern]: List of loaded patterns (empty if none found)
    """
    from services.rei_toei._models import StrudelPattern
    
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
