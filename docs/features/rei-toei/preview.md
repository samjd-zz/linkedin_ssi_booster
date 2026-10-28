# Rei CLI Preview Runtime Behavior

See the [feature overview](idea.md) for Rei's role and music-generation architecture.

```bash
# Explicit theme: --rei-theme requires a quoted value
bash run.sh --profile core run --rm app \
  python main.py --rei-generate --rei-preview --rei-theme "async programming"

# Automatic theme selection from extracted knowledge
bash run.sh --profile core run --rm app python main.py --rei-generate --rei-preview
```

Preview generates the song concept, full lyrics, and formatted Suno prompt using local Ollama. It does not save artifacts, submit to Suno, download media, or render FLUX images. It is not a fast placeholder or a generation-free dry run.

## Preparation

Rei-only CLI runs skip GitHub profile enrichment because it is not used by the music prompts. Concept and lyric generation share the existing CLI Ollama client (including the configured model and host); the Rei default remains `gemma4:e4b` if `OLLAMA_MODEL` is unset. Recent titles are read once and reused for automatic theme selection and title uniqueness. Explicit themes skip unused avatar-state loading, except that `--rei-explain` still loads extracted evidence for DoT validation. Strudel's explicit-theme path likewise avoids avatar loading and reuses the CLI client.

## Timings and Retries

INFO timing records distinguish `rei.preparation`, `rei.concept`, `rei.lyrics`, `rei.suno_formatting`, and optional `rei.dot_validation`; Strudel generation uses `rei.strudel`. Existing `ollama.chat` wall times and server timing metrics identify each underlying model request.

The lyric composer currently allows up to five attempts for Japanese/bilingual output and one for English, with up to 4,096 generated tokens per attempt. Structural, language-mix, script, and repetitiveness failures can trigger a complete regeneration. These checks and retry limits are unchanged by the startup optimization; warning logs give retry reasons. Formatting includes deterministic Japanese/Romaji normalization and does not make another LLM call. Use timings to distinguish retries from post-generation CPU work.

The launcher still performs its GPU passthrough probe and requests a cached Docker build for one-off app runs, preserving stale-image protection. Those steps occur before Python's stage logs.

See [regression coverage](../../testing-and-dev.md#rei-cli-preview-preparation-and-timing) for isolated CLI tests and current suite results.
