# FLUX Art Avatar

Local GPU image generation for persona-aligned visual content, built on FLUX.1-schnell (GGUF quantised). The README refers to this as the Alex Grey Avatar Enhancement: a style-and-aesthetic layer that guides the image prompt without introducing a separate visual persona. The `services/flux_capacitor/` package integrates image rendering into all three main flows — schedule, curate, and console — with a single shared GPU orchestrator that enforces Ollama-first sequencing on the RTX 3060.

---

## Architecture

```
FluxCapacitorService (singleton, get_flux_service())
├── GPUOrchestrator  — threading.Lock gate, Ollama-first priority queue
├── make_request()   — builds ArtAvatarRequest from post text + style config
└── render()         — runs run_art_avatar() → image + story + metadata artifacts
```

The singleton is process-wide — all schedule/curate/console flows share one GPU orchestrator so Ollama's VRAM occupancy is always visible before a FLUX render begins. `get_flux_service()` uses double-checked locking; `notify_ollama_start()` / `notify_ollama_done()` must be called from any code path that drives LLM generation to keep GPU sequencing correct.

---

## Style Presets

Three built-in presets, selected via `FLUX_CAPACITOR_STYLE_PRESET`:

| Preset | Description |
|---|---|
| `corporate_minimal` (default) | Muted palette, subtle sacred geometry, professional |
| `sacred_geometry` | Geometric overlays, spiritual-tech aesthetic |
| `tech_dark` | Dark background, high-contrast technical motifs |

Style clamp variables cap parameter values to prevent over-rendering:

| Variable | Default |
|---|---|
| `FLUX_CAPACITOR_SATURATION_CAP` | `0.55` |
| `FLUX_CAPACITOR_GEOMETRY_DENSITY_CAP` | `0.40` |
| `FLUX_CAPACITOR_SURREAL_INTENSITY_CAP` | `0.30` |

An optional per-request system prompt override (`FLUX_CAPACITOR_STYLE_SYSTEM_PROMPT`) lets you inject custom style language at the prompt level.

---

## Realism Control

Hard-coded photorealistic wording was removed in v0.0.3.3. Art direction defaults to neutral compositional guidance. Opt-in realism via:

- **Env var:** `FLUX_CAPACITOR_REALISM_HINT=photorealistic, studio lighting, high detail`
- **Per-request:** `style_overrides={"realism_hint": "..."}` in `make_request()`

Leave unset for preset-driven art direction — mixing photographic terms with corporate-minimal or sacred-geometry presets produces incoherent prompts.

## Prompt Inputs

The art avatar does not pull a separate visual persona from the persona graph. The prompt is assembled from:

- The source story text passed in from schedule, curate, or console flows
- The active style preset selected by `FLUX_CAPACITOR_STYLE_PRESET`
- The optional `FLUX_CAPACITOR_STYLE_SYSTEM_PROMPT` style persona override
- The optional `FLUX_CAPACITOR_REALISM_HINT` or per-request `realism_hint`
- The optional `knowledge_context` provided by the caller, such as a console topic hint

For console `/art`, the source story is the most recent assistant reply in the current session. The topic hint becomes both the visual theme and the short knowledge context passed into the optimizer.

---

## Terminal Display

Art renders are displayed inline using `term-image`. By default the image auto-fits to the full terminal width (maximum resolution for your renderer protocol). Override:

```bash
FLUX_DISPLAY_WIDTH=80   # cap to 80 columns
```

For true pixel-level rendering, use a kitty-compatible terminal (Kitty, WezTerm) which supports the kitty graphics protocol. Sixel and unicode-block fallbacks are lower quality.

---

## Requirements

- GPU with 12GB+ VRAM (tested on RTX 3060)
- Docker: `--profile full` profile
- Local: `pip install -r requirements-flux.txt`
- GGUF model: run `scripts/download-flux1-schnell-Q4_K_S.sh` to download

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `FLUX_CAPACITOR_ENABLED` | `false` | Enable image generation (default off) |
| `FLUX_CAPACITOR_STYLE_PRESET` | `corporate_minimal` | Active style preset |
| `FLUX_CAPACITOR_STYLE_SYSTEM_PROMPT` | _(unset)_ | Optional style language override |
| `FLUX_CAPACITOR_REALISM_HINT` | _(unset)_ | Optional photographic quality hint |
| `FLUX_CAPACITOR_SATURATION_CAP` | `0.55` | Saturation clamp (0.0–1.0) |
| `FLUX_CAPACITOR_GEOMETRY_DENSITY_CAP` | `0.40` | Geometry density clamp |
| `FLUX_CAPACITOR_SURREAL_INTENSITY_CAP` | `0.30` | Surreal intensity clamp |
| `FLUX_CAPACITOR_RENDER_WIDTH` | `768` | Render width in pixels |
| `FLUX_CAPACITOR_RENDER_HEIGHT` | `768` | Render height in pixels |
| `FLUX_CAPACITOR_RENDER_STEPS` | `4` | Inference steps (FLUX.1-schnell optimised) |
| `FLUX_CAPACITOR_OLLAMA_FIRST` | `true` | Hold FLUX until Ollama GPU drains |
| `FLUX_CAPACITOR_FLUX_AFTER_OLLAMA` | `true` | FLUX waits for Ollama completion signal |
| `FLUX_CAPACITOR_MAX_CONCURRENT_GPU_JOBS` | `1` | Max simultaneous GPU jobs |
| `FLUX_CAPACITOR_QUEUE_WAIT_TIMEOUT_SECONDS` | `120` | Seconds before deferring a render |
| `FLUX_CAPACITOR_SUBDIR` | `flux_capacitor` | Artifact subdirectory under `GENERATED_CONTENT_DIR` |
| `FLUX_CAPACITOR_STORIES_SUBDIR` | `stories` | Story artifact subdirectory |
| `FLUX_CAPACITOR_MINIMAL_MODE` | `false` | Skip story generation, render image only |
| `FLUX_DISPLAY_WIDTH` | _(unset)_ | Terminal display column cap |

See [docs/environment-variables.md](environment-variables.md) for the full reference.

---

## Flow Integration

Renders trigger automatically after post generation when `FLUX_CAPACITOR_ENABLED=true`:

| Flow | Function in `main.py` |
|---|---|
| Schedule | `_render_schedule_art_avatar()` |
| Curate | `_render_curate_art_avatar()` |
| Console | `_render_console_art_avatar()` |

Results merge into the idea/post record as metadata keys:

```python
{
    "art_avatar_status": "rendered",        # rendered | deferred | failed | text_only
    "art_avatar_image_path": "/path/img.png",
    "art_avatar_story_path": "/path/story.txt",
    "art_avatar_story_save_status": "saved",
    "art_avatar_defer_reason": None,
    "art_avatar_render_error": None,
    "art_avatar_wait_seconds": 0.0,
}
```

---

## Testing

- `tests/test_flux_capacitor_pipeline.py` — config validation, model contracts, style preset clamping, prompt assembly, GPU orchestrator state machine, pipeline disabled/deferred/failed paths, story artifact persistence
- `tests/test_gpu_orchestration_policy.py` — Ollama-first queue ordering, TEXT_ONLY timeout fallback, slot acquire/release lifecycle, concurrency safety
- `tests/test_flux_service_singleton.py` — concurrent `get_flux_service()` access (8 threads, verifies single construction)
- `tests/test_flux_capacitor_schedule_integration.py` / `test_flux_capacitor_curate_console_integration.py` — end-to-end flow wiring tests
