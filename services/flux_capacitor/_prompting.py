"""
FLUX Capacitor Prompt Assembly and Style Clamping

Builds the final FLUX prompt from post/concept text, style presets, knowledge
context, and optional caller overrides.  Style constraints are treated as hard
limits and cannot be relaxed by callers.

Prompt precedence (highest → lowest):
  1. Hard safety/style clamps from config
  2. Explicit caller overrides (prompt_overrides, style_overrides)
  3. FLUX_CAPACITOR_STYLE_SYSTEM_PROMPT env value
  4. Style preset defaults
  5. Post/concept/topic context

Author: Shawn Jackson Dyck
Version: alpha-v0.0.2.7
"""

import logging
from typing import Any, Dict, Optional

from services.flux_capacitor._config import (
    STYLE_PRESETS,
    DEFAULT_STYLE_PRESET,
    FluxCapacitorConfig,
)
from services.flux_capacitor._models import ArtAvatarRequest, StylePreset

logger = logging.getLogger(__name__)

# Negative prompt shared by all presets
_NEGATIVE_PROMPT: str = (
    "nsfw, violence, gore, disturbing imagery, over-saturated colors, "
    "psychedelic excess, chaotic composition, illegible text, watermark, "
    "signature, blurry, low quality, overexposed, distorted faces"
)


def resolve_style_preset(
    preset_name: str,
    config: FluxCapacitorConfig,
) -> StylePreset:
    """Return a StylePreset for *preset_name*, clamped to config hard limits.

    Falls back to DEFAULT_STYLE_PRESET if *preset_name* is unknown.
    """
    raw = STYLE_PRESETS.get(preset_name) or STYLE_PRESETS.get(DEFAULT_STYLE_PRESET)
    if raw is None:
        raise ValueError(f"No style preset found for '{preset_name}'.")

    preset = StylePreset(
        name=raw["name"],
        palette=raw["palette"],
        geometry_density=min(raw["geometry_density"], config.geometry_density_cap),
        saturation_cap=min(raw["saturation_cap"], config.saturation_cap),
        surreal_intensity_cap=min(
            raw["surreal_intensity_cap"], config.surreal_intensity_cap
        ),
        prompt_suffix=raw["prompt_suffix"],
    )
    return preset


def apply_style_overrides(
    preset: StylePreset,
    style_overrides: Dict[str, Any],
    config: FluxCapacitorConfig,
) -> StylePreset:
    """Apply caller-supplied style overrides, enforcing hard config clamps."""
    if not style_overrides:
        return preset
    return StylePreset(
        name=preset.name,
        palette=style_overrides.get("palette", preset.palette),
        geometry_density=min(
            float(style_overrides.get("geometry_density", preset.geometry_density)),
            config.geometry_density_cap,
        ),
        saturation_cap=min(
            float(style_overrides.get("saturation_cap", preset.saturation_cap)),
            config.saturation_cap,
        ),
        surreal_intensity_cap=min(
            float(
                style_overrides.get(
                    "surreal_intensity_cap", preset.surreal_intensity_cap
                )
            ),
            config.surreal_intensity_cap,
        ),
        prompt_suffix=style_overrides.get("prompt_suffix", preset.prompt_suffix),
    )


def build_prompt(
    request: ArtAvatarRequest,
    config: FluxCapacitorConfig,
) -> str:
    """Assemble the final positive FLUX prompt for *request*.

    Returns a single prompt string ready to pass to the FLUX pipeline.
    """
    # 1. Resolve base content
    content_text: str = (request.post_text or request.concept_text or "").strip()
    if not content_text:
        raise ValueError("ArtAvatarRequest has no usable content text for prompt.")

    # Truncate very long posts to keep the prompt focused
    if len(content_text) > 400:
        content_text = content_text[:397] + "..."

    # 2. Resolve and clamp preset
    preset = resolve_style_preset(request.style_profile, config)

    # 3. Apply caller overrides (hard clamps still enforced)
    preset = apply_style_overrides(preset, request.style_overrides, config)

    # 4. Apply prompt_overrides (caller may inject a subject override)
    subject_override: Optional[str] = request.prompt_overrides.get("subject")
    subject_text: str = subject_override if subject_override else content_text

    # 5. Build theme / channel cue
    theme_cue: str = ""
    if request.theme:
        theme_cue = f" Theme: {request.theme}."
    if request.channels:
        channel_label = ", ".join(request.channels[:2])
        theme_cue += f" Channel context: {channel_label}."

    # 6. Knowledge context snippet (truncated)
    knowledge_snippet: str = ""
    if request.knowledge_context:
        kc = request.knowledge_context.strip()[:200]
        knowledge_snippet = f" Context: {kc}."

    # 7. Assemble style block
    style_block = (
        f"Palette: {preset.palette}. "
        f"Geometry density: {preset.geometry_density:.0%}. "
        f"{preset.prompt_suffix}"
    )

    # 8. Include FLUX_CAPACITOR_STYLE_SYSTEM_PROMPT when set
    style_persona = ""
    if config.style_system_prompt:
        style_persona = f" Style persona: {config.style_system_prompt.strip()}"

    # 9. Combine
    prompt = (
        f"Create an ultra realistic image of this input story: {subject_text}."
        f"{theme_cue}{knowledge_snippet} "
        "Photorealistic, lifelike, highly detailed, natural lighting, realistic textures. "
        f"{style_block}{style_persona}"
    ).strip()

    logger.debug("FLUX prompt assembled (len=%d): %.80s…", len(prompt), prompt)
    return prompt


def build_negative_prompt() -> str:
    """Return the shared negative prompt string."""
    return _NEGATIVE_PROMPT
