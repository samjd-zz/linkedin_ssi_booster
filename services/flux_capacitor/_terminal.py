"""Terminal rendering helpers for FLUX art-avatar output."""

from __future__ import annotations

import importlib
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _display_art_in_terminal(image_path: str | None, width: int | None = None) -> None:
    """Render a FLUX-generated image inline in the terminal using term-image.

    ``width`` is the number of terminal columns to occupy. ``None`` lets
    term-image auto-fit to the full terminal width. ``FLUX_DISPLAY_WIDTH`` can
    cap the width when needed.

    Skips missing files and unavailable inline renderers.
    """
    if not image_path:
        return

    if not Path(image_path).is_file():
        return

    env_width_raw = os.getenv("FLUX_DISPLAY_WIDTH", "").strip()
    env_width = int(env_width_raw) if env_width_raw.isdigit() else None
    requested_width = width if width is not None else env_width

    import shutil

    terminal_columns = shutil.get_terminal_size(fallback=(120, 40)).columns
    render_width = requested_width
    if render_width is not None:
        render_width = max(10, min(render_width, max(10, terminal_columns - 2)))

    render_image_path = image_path
    temp_upsampled_path: str | None = None
    upsample_factor_raw = os.getenv("FLUX_DISPLAY_UPSCALE_FACTOR", "1").strip()
    upsample_factor = int(upsample_factor_raw) if upsample_factor_raw.isdigit() else 1
    upsample_factor = max(1, min(upsample_factor, 6))

    if upsample_factor > 1:
        try:
            pil_image_mod = importlib.import_module("PIL.Image")
            import tempfile

            resampling = getattr(pil_image_mod, "Resampling", pil_image_mod)
            image_filter = getattr(
                resampling,
                "LANCZOS",
                getattr(resampling, "BICUBIC", None),
            )

            with pil_image_mod.open(image_path) as source_image:
                upsampled_image = source_image.resize(
                    (
                        source_image.width * upsample_factor,
                        source_image.height * upsample_factor,
                    ),
                    image_filter,
                )

                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    prefix="flux-term-upsample-",
                    suffix=".png",
                    delete=False,
                ) as temp_file:
                    temp_upsampled_path = temp_file.name

                upsampled_image.save(temp_upsampled_path, format="PNG")
                render_image_path = temp_upsampled_path
        except Exception as exc:  # noqa: BLE001
            logger.warning("terminal upsampling skipped: %s", exc)

    try:
        term_image_mod = importlib.import_module("term_image.image")
        term_image_from_file = getattr(term_image_mod, "from_file")
        image = term_image_from_file(render_image_path, width=render_width)
        image.draw()
    except Exception as exc:  # noqa: BLE001
        if render_width is not None:
            try:
                term_image_mod = importlib.import_module("term_image.image")
                term_image_from_file = getattr(term_image_mod, "from_file")
                image = term_image_from_file(render_image_path, width=None)
                image.draw()
                logger.warning(
                    "term-image fixed-width render failed (requested=%s, clamped=%s, cols=%s); fell back to auto-fit: %s",
                    requested_width,
                    render_width,
                    terminal_columns,
                    exc,
                )
                return
            except Exception as fallback_exc:  # noqa: BLE001
                logger.warning(
                    "term-image display skipped after fixed-width and auto-fit failures: %s",
                    fallback_exc,
                )
                return

        logger.warning("term-image display skipped: %s", exc)
    finally:
        if temp_upsampled_path:
            try:
                Path(temp_upsampled_path).unlink(missing_ok=True)
            except OSError:
                pass
