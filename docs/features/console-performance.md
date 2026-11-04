# Console Runtime and Performance

```bash
bash run.sh --profile core run --rm -it app python main.py --console
```

Use `/rei` for Rei Toei, plain follow-ups to stay with Rei, and `/sam` to return
to Sam. The flag is `--console`, not `-console`.

## Reused Work

- **Sam's knowledge snapshot:** startup loads avatar files once for grounding,
  query-tag relationships, and knowledge-graph bootstrap. Normal query parsing
  no longer reloads avatar files on every turn.
- **Hybrid retrieval:** evidence tokenization uses one batch, with a reusable
  BM25 index keyed by text content rather than IDs alone. Editing a fact under
  the same ID rebuilds the index.
- **Semantic retrieval:** Model2Vec preserves results for batches larger than
  its 512-entry per-text cache. A bounded, model/content-aware corpus cache
  reuses candidate embeddings across different questions; queries are encoded
  separately. Restoring these scores can change rankings that previously
  silently lost their semantic signal.
- **External evidence:** skip the redundant local ranking whose results would
  all be discarded when at least two distinct internal facts fill its slots.
  Sparse-pool fallback and the explicit `/katzilla` route remain unchanged;
  this optimization does not newly enable external API calls.
- **Rei's knowledge:** persona/domain files are lazy-cached through the existing
  Rei service. Ordinary chat and songs do not require Strudel templates.
  Concept, lyric, and pattern generation reuse the active console Ollama client,
  including its model and host. Rei's history is capped at 24 turns.

`/reload` refreshes Sam's snapshot, tag relationships, and graph/retriever
together. It invalidates Rei's cached knowledge, which reloads on next use;
templates still load only if requested. This is useful after a separate
`--learn` job or edits to avatar files. `/reset` clears conversation history,
not the knowledge snapshot.

## INFO Timing Records

| Stage | What it measures |
| ----- | ---------------- |
| `console.preparation` | Sam's snapshot preparation and graph bootstrap, including `/reload` |
| `retrieval.hybrid` | BM25, semantic scoring, and graph reranking |
| `console.sam.chat` | Sam's direct chat request wall time |
| `console.rei.chat` | Rei's direct conversation request wall time |
| `console.rei.turn` | Rei dispatch, preparation, and generation, excluding voice playback |
| `console.rei.concept`, `console.rei.lyrics` | Song concept and lyric generation, including existing retries |
| `console.rei.suno_formatting` | Deterministic Suno output formatting |
| `console.rei.strudel` | Pattern generation |
| `console.voice` | Synchronous Piper synthesis and complete audio playback |
| `console.art` | Explicit/requested FLUX art handling, including prompt optimization |
| `console.verification` | Optional truth-gate/DoT/similarity verification |

Sam and Rei direct chat now also log Ollama server `load_s`, `prompt_eval_s`,
`generation_s`, `total_s`, and token counts. Song/pattern LLM calls retain
the shared `ollama.chat` metrics. Missing server values are `None`, not zero.
Stages overlap: do not sum nested durations.

## Expected Delays

First-use NLP/model loading still costs time. A cold Ollama model or switching
between Ollama and FLUX on a shared GPU can still require loading. Generation
limits, Japanese/bilingual lyric checks, and retries are unchanged.

Replies print before voice playback and Sam's optional art/verification work.
Piper intentionally blocks until audio completes; set `CONSOLE_USE_VOICE=false`
in `.env` before starting the process for text-only conversations. Verification
is off by default; `/verify`, `/avatar-explain`, `/dot-report`, and `/truth-gate` add work.
The truth gate filters the shown reply only when `/truth-gate` is on; the report
toggles score quietly and reuse the gate result when both are on.
Inline verification now prints one truth bar, not a duplicate report bar.

Sam's console replies pass through a garbled-output guard
(`services/llm_output_guard.py`) before display or the truth gate. Some local
runtimes, notably IPEX-LLM on Intel iGPUs, can decode long prefix-cached prompts
into token salad: Latin glued to Chinese characters, code identifiers, symbol
runs, and stray scripts. When a reply looks garbled, `chat_as_persona` unloads
the model to drop its KV/prefix cache and retries once; a second garbled reply
raises `GarbledOutputError`, the console prints a clear error, and the turn is
dropped from history. All compose files set `OLLAMA_NUM_PARALLEL=1` on the
Ollama server so one request owns the whole context and cache.

No background speech, reduced grounding checks, shorter generation limits, or
between-turn model unloads were introduced (the garbled-reply retry unloads
only after a token-salad reply). Operation-count regressions verify
the removed work; actual latency depends on the loaded models and hardware.

See [regression coverage](../testing-and-dev.md#console-performance-regressions)
and [Rei CLI preview](rei-toei/preview.md) for adjacent runtime behavior.
