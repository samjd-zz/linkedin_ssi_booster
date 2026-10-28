# Cache-First Docker Launcher

`run.sh` passes Compose arguments through unchanged. It no longer forces a build
for one-off app commands. Existing images are reused, making everyday launches
faster and avoiding build-time package/model downloads.

```bash
# Default: reuse the existing app image.
bash run.sh --profile core run --rm app python main.py --rei-generate --rei-preview

# Opt in to rebuilding, using Docker's normal layer cache.
bash run.sh --profile core run --build --rm app python main.py --rei-generate --rei-preview
bash run.sh --profile core up --build -d

# Or rebuild only the app before the next run.
bash run.sh --profile core build app
```

Source is copied into the image, so **source/dependency changes require an explicit
rebuild**. `--build` does not mean `--no-cache`; unchanged build layers remain reusable.
Compose may build/pull when required images are missing. The default is cache-first,
not an enforced network-isolation mode.

## Cached / Disconnected Core Preview

While online, build the app and cache the selected profile's service images and
configured primary/fallback Ollama models. Keep the same Compose project name so
the existing images and named volumes are reused. The app image includes spaCy
models; runtime embedding models must also already exist in its Hugging Face cache.

```bash
# Use cached images only; fail rather than build/pull missing service images.
bash run.sh --profile core up -d --no-build --pull never postgres ollama

# With those services already running, preview without starting dependencies.
bash run.sh --profile core run --rm --no-deps --pull never app \
  python main.py --rei-generate --rei-preview
```

On NVIDIA hosts, the GPU probe now uses `docker run --pull=never`; it never
downloads its CUDA image. Cache it once while online:

```bash
docker pull nvidia/cuda:12.4.1-base-ubuntu22.04
```

If that image is absent or passthrough fails, the launcher warns and falls back
to CPU. Existing Intel/WSL device detection is unchanged.

`ollama-init` now checks each configured model using `ollama show`. Cached models
skip registry requests on CPU, NVIDIA, Intel, and Intel WSL profiles. Missing
models are pulled; pull failures stop initialization rather than printing success.
To update a cached model, explicitly run `ollama pull` inside the Ollama service
(the Intel images expose the binary at `/llm/ollama/ollama`).

These settings **do not create a network air gap**. Missing runtime assets may
still need downloads, and RSS curation, Buffer publishing/reconciliation, GitHub
enrichment, and remote integrations require network access. The full profile also
has additional voice/FLUX/Playwright assets to cache. Use local-only features and
external network controls when actual isolation is required.
