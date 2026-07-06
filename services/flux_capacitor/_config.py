"""
FLUX Capacitor Configuration

Feature flags, style clamps, GPU policy values, and queue thresholds for the
art-avatar rendering pipeline.  All values are environment-driven so no code
edits are required for routine style or policy changes.

Author: Shawn Jackson Dyck
Version: alpha-v0.0.2.7
"""

import os
from pathlib import Path


class FluxCapacitorConfig:
    """Runtime configuration loaded from environment variables.

    Raises ValueError at construction time if required values are out of range.
    """

    def __init__(self) -> None:
        # ------------------------------------------------------------------ #
        # Feature toggle
        # ------------------------------------------------------------------ #
        self.enabled: bool = (
            os.getenv("FLUX_CAPACITOR_ENABLED", "false").lower() == "true"
        )

        # ------------------------------------------------------------------ #
        # Style persona prompt (user-owned, overrides preset suffix)
        # ------------------------------------------------------------------ #
        self.style_system_prompt: str = os.getenv(
            "FLUX_CAPACITOR_STYLE_SYSTEM_PROMPT",
            (
                "Professional B2B marketing illustration style. "
                "Editorial-clean composition, clear focal hierarchy, premium lighting, "
                "brand-safe color discipline, conversion-oriented visual storytelling. "
                "No surreal motifs, no clutter, no gimmicky effects."
            ),
        )

        # ------------------------------------------------------------------ #
        # Active style preset name (resolves against STYLE_PRESETS dict)
        # ------------------------------------------------------------------ #
        self.style_preset: str = os.getenv(
            "FLUX_CAPACITOR_STYLE_PRESET", "marketing_editorial"
        )

        # ------------------------------------------------------------------ #
        # Style clamps (hard limits — cannot be overridden by callers)
        # ------------------------------------------------------------------ #
        self.saturation_cap: float = float(
            os.getenv("FLUX_CAPACITOR_SATURATION_CAP", "0.55")
        )
        self.geometry_density_cap: float = float(
            os.getenv("FLUX_CAPACITOR_GEOMETRY_DENSITY_CAP", "0.40")
        )
        self.surreal_intensity_cap: float = float(
            os.getenv("FLUX_CAPACITOR_SURREAL_INTENSITY_CAP", "0.30")
        )

        # ------------------------------------------------------------------ #
        # Minimal mode — skip FLUX render, return text-only path always
        # ------------------------------------------------------------------ #
        self.minimal_mode: bool = (
            os.getenv("FLUX_CAPACITOR_MINIMAL_MODE", "false").lower() == "true"
        )

        # ------------------------------------------------------------------ #
        # GPU policy
        # ------------------------------------------------------------------ #
        self.ollama_first: bool = (
            os.getenv("FLUX_CAPACITOR_OLLAMA_FIRST", "true").lower() == "true"
        )
        self.flux_after_ollama: bool = (
            os.getenv("FLUX_CAPACITOR_FLUX_AFTER_OLLAMA", "true").lower() == "true"
        )
        self.max_concurrent_gpu_jobs: int = int(
            os.getenv("FLUX_CAPACITOR_MAX_CONCURRENT_GPU_JOBS", "1")
        )
        self.queue_wait_timeout_seconds: int = int(
            os.getenv("FLUX_CAPACITOR_QUEUE_WAIT_TIMEOUT_SECONDS", "120")
        )

        # ------------------------------------------------------------------ #
        # Render dimensions / steps (RTX 3060 safe defaults)
        # ------------------------------------------------------------------ #
        self.render_width: int = int(os.getenv("FLUX_CAPACITOR_RENDER_WIDTH", "768"))
        self.render_height: int = int(
            os.getenv("FLUX_CAPACITOR_RENDER_HEIGHT", "768")
        )
        self.render_steps: int = int(os.getenv("FLUX_CAPACITOR_RENDER_STEPS", "4"))

        # ------------------------------------------------------------------ #
        # Artifact storage
        # ------------------------------------------------------------------ #
        self.flux_subdir: str = os.getenv(
            "FLUX_CAPACITOR_SUBDIR", "flux_capacitor"
        )
        self.stories_subdir: str = os.getenv(
            "FLUX_CAPACITOR_STORIES_SUBDIR", "stories"
        )

        self._validate()

    def _validate(self) -> None:
        if not (0.0 <= self.saturation_cap <= 1.0):
            raise ValueError(
                f"FLUX_CAPACITOR_SATURATION_CAP must be 0–1, got {self.saturation_cap}"
            )
        if not (0.0 <= self.geometry_density_cap <= 1.0):
            raise ValueError(
                f"FLUX_CAPACITOR_GEOMETRY_DENSITY_CAP must be 0–1, "
                f"got {self.geometry_density_cap}"
            )
        if not (0.0 <= self.surreal_intensity_cap <= 1.0):
            raise ValueError(
                f"FLUX_CAPACITOR_SURREAL_INTENSITY_CAP must be 0–1, "
                f"got {self.surreal_intensity_cap}"
            )
        if self.max_concurrent_gpu_jobs < 1:
            raise ValueError(
                f"FLUX_CAPACITOR_MAX_CONCURRENT_GPU_JOBS must be ≥ 1, "
                f"got {self.max_concurrent_gpu_jobs}"
            )
        if self.render_steps < 1:
            raise ValueError(
                f"FLUX_CAPACITOR_RENDER_STEPS must be ≥ 1, got {self.render_steps}"
            )
        if self.render_width < 256 or self.render_height < 256:
            raise ValueError(
                "FLUX_CAPACITOR_RENDER_WIDTH and RENDER_HEIGHT must be ≥ 256"
            )


# --------------------------------------------------------------------------- #
# Built-in style presets
# --------------------------------------------------------------------------- #

STYLE_PRESETS: dict[str, dict] = {
    "marketing_editorial": {
        "name": "marketing_editorial",
        "palette": "brand-safe navy, slate, cool neutrals, controlled accent cyan",
        "geometry_density": 0.15,
        "saturation_cap": 0.42,
        "surreal_intensity_cap": 0.10,
        "prompt_suffix": (
            "Professional campaign-ready composition, hero subject with clean negative space, "
            "editorial-grade lighting, modern business context, premium product-marketing polish, "
            "minimal distractions, strong visual hierarchy suitable for LinkedIn creatives."
        ),
    },
    "corporate_minimal": {
        "name": "corporate_minimal",
        "palette": "muted blues, greys, and warm whites",
        "geometry_density": 0.25,
        "saturation_cap": 0.45,
        "surreal_intensity_cap": 0.20,
        "prompt_suffix": (
            "Clean lines, restrained geometric accents, professional depth-of-field, "
            "soft gradient background, executive-facing corporate design language."
        ),
    },
    "sacred_geometry_light": {
        "name": "sacred_geometry_light",
        "palette": "cool indigo, silver, deep navy",
        "geometry_density": 0.40,
        "saturation_cap": 0.55,
        "surreal_intensity_cap": 0.30,
        "prompt_suffix": (
            "Subtle Flower-of-Life geometry, translucent overlays, "
            "restrained sacred-geometry motifs, polished digital art."
        ),
    },
    "tech_dark": {
        "name": "tech_dark",
        "palette": "near-black background, electric blue and white accents",
        "geometry_density": 0.30,
        "saturation_cap": 0.50,
        "surreal_intensity_cap": 0.20,
        "prompt_suffix": (
            "Dark technical aesthetic, circuit-board textures hinted at the margins, "
            "sharp typography composition feel, professional digital illustration."
        ),
    },
}

DEFAULT_STYLE_PRESET: str = "marketing_editorial"
