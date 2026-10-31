# Rei CLI Preview Runtime Behavior

See the [feature overview](idea.md) for Rei's role and music-generation architecture.

```bash
# Explicit theme: --rei-theme requires a quoted value
bash run.sh --profile core run --rm app \
  python main.py --rei-generate --rei-preview --rei-theme "async programming"

# Automatic theme selection from extracted knowledge
bash run.sh --profile core run --rm app python main.py --rei-generate --rei-preview

# Rebuild the app image before previewing local code changes
bash run.sh --profile core run --build --rm app python main.py --rei-generate --rei-preview
```

Preview generates the song concept, full lyrics, and formatted Suno prompt using local Ollama. It does not save artifacts, submit to Suno, download media, or render FLUX images. It is not a fast placeholder or a generation-free dry run.

## Preparation

Rei-only CLI runs skip GitHub profile enrichment because it is not used by the music prompts. Concept and lyric generation share the existing CLI Ollama client (including the configured model and host); the Rei default remains `gemma4:e4b` if `OLLAMA_MODEL` is unset. Recent titles are read once and reused for automatic theme selection and title uniqueness. Explicit themes skip unused avatar-state loading, except that `--rei-explain` still loads extracted evidence for DoT validation. Strudel's explicit-theme path likewise avoids avatar loading and reuses the CLI client.

## Timings and Retries

INFO timing records distinguish `rei.preparation`, `rei.concept`, `rei.lyrics`, `rei.suno_formatting`, and optional `rei.dot_validation`; Strudel generation uses `rei.strudel`. Existing `ollama.chat` wall times and server timing metrics identify each underlying model request.

The lyric composer currently allows up to five attempts for Japanese/bilingual output and one for English, with up to 4,096 generated tokens per attempt. Structural, language-mix, script, and repetitiveness failures can trigger a complete regeneration. These checks and retry limits are unchanged by the startup optimization; warning logs give retry reasons. Formatting includes deterministic Japanese/Romaji normalization and does not make another LLM call. Use timings to distinguish retries from post-generation CPU work.

The launcher performs its GPU passthrough probe before Python's stage logs. One-off runs reuse the existing app image unless `run --build` is supplied.

## Japanese Lyric Cues

For Japanese and bilingual songs, Rei checks inline, bracketed, parenthesized, and recognizable bare Romaji against their Japanese lyric lines. Every uncued Japanese line receives a generated Romaji cue, with auxiliary verbs and conjunctive particles joined to their verb (`segumentoka sareru`, `hikatte`). Existing cues that differ only by such splits, like `[segumentoka sa reru]`, are re-joined while keeping their macrons and capitalization. English translation lines remain sung. Recognized inline pronunciations count toward cue coverage; when only an English translation is present, backfilling uses the Japanese phrase without incorporating the translation. Explicit pronunciation/meaning pairs retain their English meaning; ambiguous English lyrics and sound cues are handled conservatively. Formatting also removes leaked quoted stage instructions and keeps technical acronyms such as `SQL` attached to Japanese phrases. The direct console fallback applies the same cleanup to recognizable section-marked songs; unstructured replies are unchanged.

Readings use SudachiPy's contextual tokenization and pykakasi's Hepburn conversion; both are already included by the core requirements. If Sudachi is unavailable, Rei warns and falls back to pykakasi alone. If a Japanese character cannot be read, Rei warns and leaves its existing cue unchanged rather than producing a partial reading. These checks do not guarantee correct Japanese, resolve every ambiguous reading, or verify English translations: review the preview before submitting. They do not add an LLM call.

See [regression coverage](../../testing-and-dev.md#rei-cli-preview-preparation-and-timing) for isolated CLI tests and current suite results.
