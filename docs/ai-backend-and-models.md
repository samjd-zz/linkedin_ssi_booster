# AI Backend and Models

All generation in the project uses Ollama through Docker Compose, which means no cloud AI keys are required for the main writing workflow. The README presents Ollama as the foundation for local post generation and recommends tuning model choice and context window based on quality and available memory.

## Run Ollama in Docker

```bash
docker compose --profile core up -d ollama
docker compose --profile core exec ollama ollama pull gemma4:26b
```

The compose stack already wires `OLLAMA_BASE_URL` to `http://ollama:11434`, so there is no need to run `ollama serve` manually. Use the `ollama` service inside Docker for pulls, stops, and model management.

## Freeing Memory

When you’re done with a model and want to release VRAM, stop it explicitly from the Ollama container:

```bash
docker compose --profile core exec ollama ollama stop "$OLLAMA_MODEL"
```

Use the same command with whichever model name you loaded in your Ollama instance.

## Recommended models

The README recommends `gemma4:26b` for best post quality, and lists `qwen2.5:14b`, `llama3.2`, and `mistral-nemo` as smaller or faster alternatives. It also characterizes `qwen2.5:14b` as a strong fallback when VRAM is constrained and `llama3.2` as the fastest but lower-quality option.

| Model          | Positioning                                                     |
| -------------- | --------------------------------------------------------------- |
| `gemma4:26b`   | Recommended for best quality and stronger long-prompt behavior. |
| `qwen2.5:14b`  | Strong fallback with lower memory requirements.                 |
| `llama3.2`     | Fastest option with lower output quality.                       |
| `mistral-nemo` | Additional supported alternative.                               |

## Fallback model for YouTube Short scripts

If the main Ollama model fails to generate a YouTube Short script (e.g., due to model limitations, VRAM exhaustion, or empty output), the system will automatically retry with a fallback model specified in the `.env` file:

```dotenv
# Fallback model to use if the main model fails to generate a YouTube Short script (optional)
OLLAMA_MODEL_FALLBACK=qwen2.5:14b
```

This variable is optional, but recommended if your primary model is large (e.g., `gemma4:26b`) and you want a reliable backup for time-sensitive or resource-constrained runs. The fallback model should be pre-pulled and available in your Ollama instance. If unset, the fallback defaults to `qwen2.5:14b`.

**Tip:** You can use any supported Ollama model as a fallback, but choose one that fits your hardware and quality needs.

## Context sizing

The README recommends `OLLAMA_NUM_CTX=16384` as the baseline for persona-heavy grounded prompts, with `8192` suggested when memory or latency is tight and `32768` suggested only when logs show truncation or degraded long-context behavior. This guidance is tied directly to the large prompt footprint created by persona, grounding, and curation context.

## One-off override

The active model can also be overridden for a single run by prefixing the command with an `OLLAMA_MODEL` environment override. In Docker, pass the override to the app container so the compose stack stays consistent. This is useful when comparing speed or quality without editing `.env`.

```bash
docker compose --profile core run --rm -e OLLAMA_MODEL=llama3.2 app python main.py --curate --dry-run
```
