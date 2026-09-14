# AI Backend and Models

All generation in the project uses Ollama through Docker, which means no cloud AI keys are required for the main writing workflow. Use `bash run.sh` as the normal launcher so GPU detection, service wiring, and audio runtime variables stay consistent across Linux and Windows WSL2 laptops.

## Run Ollama in Docker

```bash
bash run.sh --profile core up -d ollama
bash run.sh --profile core run --rm ollama-init
```

The compose stack already wires `OLLAMA_BASE_URL` to `http://ollama:11434`, so there is no need to run `ollama serve` manually. Use the `ollama` service inside Docker for pulls, stops, and model management.

## Freeing Memory

When you’re done with a model and want to release VRAM, stop it explicitly from the Ollama container:

```bash
bash run.sh --profile core exec ollama ollama stop "$OLLAMA_MODEL"
```

Use the same command with whichever model name you loaded in your Ollama instance.

## Recommended models

The README recommends `gemma4:26b` for best post quality, and lists `qwen2.5:14b`, `llama3.2`, and `mistral-nemo` as smaller or faster alternatives. It also characterizes `qwen2.5:14b` as a strong fallback when VRAM is constrained and `llama3.2` as the fastest but lower-quality option.

| Model          | Positioning                                                                                                                                                                  |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `gemma4:26b`   | Recommended for best quality and stronger long-prompt behavior.                                                                                                              |
| `qwen2.5:14b`  | Strong fallback with lower memory requirements.                                                                                                                              |
| `qwen2.5:7b`   | Stronger multilingual instruction-following; ~2x slower than `qwen2.5:3b` on an Intel iGPU.                                                                                  |
| `qwen2.5:3b`   | Good speed/quality fit for Intel iGPU laptops running bilingual JP/EN Rei Toei lyric generation — noticeably stronger at real Japanese than `llama3.2:3b` at a similar size. |
| `llama3.2`     | Fastest option with lower output quality; weak at generating real Japanese script.                                                                                           |
| `mistral-nemo` | Additional supported alternative.                                                                                                                                            |

**Do not use `qwen2.5-coder`** for creative/ghostwriting or Rei Toei lyric generation — it is code-specialized and a poor fit for that workload. Use a base `qwen2.5` model instead.

**Qwen-family Chinese-script leakage risk:** Qwen models are heavily trained on Chinese text and can leak Simplified Chinese script into "Japanese" bilingual lyric output (e.g. via the fullwidth comma `，` or the particle `的`) instead of genuine Japanese kana/kanji. `services/rei_toei/_suno_pipeline.py` detects this (`_has_chinese_leakage`) and retries or falls back to hand-authored Japanese lyrics rather than submitting Chinese-mislabeled-as-Japanese content. See [rei-toei-customization.md](rei-toei-customization.md#bilingual-lyric-mix) for details.

## Fallback model for YouTube Short scripts

If the main Ollama model fails to generate a YouTube Short script (e.g., due to model limitations, VRAM exhaustion, or empty output), the system will automatically retry with a fallback model specified in the `.env` file:

```dotenv
# Laptop-sized fallback for the qwen2.5:3b Rei Toei setup
OLLAMA_MODEL_FALLBACK=llama3.2:3b
```

For the Intel iGPU laptop profile, keep both `qwen2.5:3b` and `llama3.2:3b` pulled in the Ollama container. The fallback is used for empty responses or API errors; Rei Toei also has its own bounded lyric validation and Japanese-aware fallback when the model emits unusable JSON or language/script artifacts.

**Tip:** You can use any supported Ollama model as a fallback, but choose one that fits your hardware and quality needs.

## Context sizing

The README recommends `OLLAMA_NUM_CTX=16384` as the baseline for persona-heavy grounded prompts, with `8192` suggested when memory or latency is tight and `32768` suggested only when logs show truncation or degraded long-context behavior. This guidance is tied directly to the large prompt footprint created by persona, grounding, and curation context.

## One-off override

The active model can also be overridden for a single run by prefixing the command with an `OLLAMA_MODEL` environment override. In Docker, pass the override to the app container so the compose stack stays consistent. This is useful when comparing speed or quality without editing `.env`.

```bash
bash run.sh --profile core run --rm -e OLLAMA_MODEL=llama3.2 app python main.py --curate --dry-run
```

## Other useful commands:

```bash
docker exec -it ssi_booster_ollama ollama list
docker exec -it ssi_booster_ollama ollama rm <unused-model>
```
