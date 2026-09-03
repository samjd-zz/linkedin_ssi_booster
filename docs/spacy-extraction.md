# spaCy Extraction — What Is Learned and How It Is Tuned

This document covers the NLP half of the continual-learning pipeline: what spaCy does at each stage, what ends up in `data/avatar/extracted_knowledge.json`, how language routing picks a model, and every knob that changes the output.

For the surrounding pipeline — retrieval, truth gate, confidence scoring, routing — see [learning-pipeline.md](learning-pipeline.md).

---

## What spaCy Actually Extracts

spaCy is used at four distinct points. Each does a different job and is tuned separately.

### 1. Pre-filter summarization

`summarize_article()` compresses an article to its highest-signal sentences before extraction runs, so the fact extractor sees a dense summary rather than the full page.

Each sentence is scored:

| Signal               | Weight                                                                                                                                             |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Named entity count   | `+2.0` per entity                                                                                                                                  |
| Document position    | `+1.0 / (1 + rank)` — earlier sentences score higher                                                                                               |
| Sentence length      | `+1.0` for 10–25 tokens, `+0.5` for >5, `0` otherwise                                                                                              |
| Announcement markers | `+1.5` for `new`, `announce`, `launch`, `release`, `breakthrough`, `significant`, `important`, `key`, `major`, `発表`, `新`, `開発`, `公開`, `導入` |

Top-scoring sentences are re-sorted into original document order and joined.

**Tuning:** the extraction path calls this with `max_sentences=10` over a 5000-character window — deliberately wider than post generation (`max_sentences=5`) to preserve fact diversity. Summarization is skipped entirely if the article is under 800 characters, or if the resulting summary is under 200 characters (falls back to full text).

### 2. Theme extraction → `entities` and `tags`

`extract_themes()` produces the metadata stored on every `ExtractedFact`. It merges two sources:

- **Named entities** with labels `PERSON`, `ORG`, `GPE`, `PRODUCT`, `EVENT`, `WORK_OF_ART`, `LAW`, `LANGUAGE`, `NORP`, `FAC`, `LOC`, `DATE`, `TIME`
- **Noun chunks** kept when they are 2+ words, 5+ characters, or detected as Japanese

The combined set is lowercased, deduplicated, sorted, then split purely by token count:

| Field      | Rule                            | Cap |
| ---------- | ------------------------------- | --- |
| `entities` | themes with **>1** token        | 5   |
| `tags`     | themes with **exactly 1** token | 8   |

This is a mechanical word-count split, not a semantic one. A single-token organisation name lands in `tags`, and a multi-word noun chunk lands in `entities`.

**Fallback:** when spaCy is unavailable the extractor drops to regex — capitalized words become `entities`, 4+ character lowercase words become `tags`, and `extraction_method` is stamped `regex_fallback` instead of `spacy_nlp` so the two are distinguishable on disk.

### 3. Semantic near-duplicate suppression

Within a single article, each candidate sentence is compared against facts already collected from the same URL. Similarity `>= 0.93` marks it a near-paraphrase and it is dropped. This catches tense and wording variants that produce different content hashes but identical meaning.

This check uses the **primary** model (`SPACY_MODEL`), not the language-routed model — Japanese sentences are compared using English vectors, so the threshold is effectively much harder to reach on Japanese text.

### 4. Truth gate similarity floors

Layers 3 and 5 of the truth gate use `compute_similarity()` against the source article and the fact pool. See [Truth Gate layers](learning-pipeline.md#stage-3-truth-gate-5-layers).

---

## What Lands on Disk

Each surviving sentence is written to `data/avatar/extracted_knowledge.json` as an `ExtractedFact`:

| Field                         | Source                                                           |
| ----------------------------- | ---------------------------------------------------------------- |
| `id`                          | `ext-` + SHA-256[:12] of `source_url` + statement                |
| `statement`                   | The extracted sentence, verbatim after cleaning                  |
| `source_url` / `source_title` | Originating article                                              |
| `extracted_at`                | ISO-8601 UTC timestamp                                           |
| `entities`                    | Multi-word spaCy themes (max 5)                                  |
| `tags`                        | Single-token spaCy themes (max 8)                                |
| `confidence`                  | `high` \| `medium` \| `low` — caller-supplied, defaults `medium` |
| `extraction_method`           | `spacy_nlp` or `regex_fallback`                                  |
| `primary_category`            | Model2Vec category of the article (empty when disabled)          |
| `primary_ssi_component`       | SSI component mapped from the category                           |

Three dedup layers guard the write: exact `id` match, cross-URL statement-hash match (so shared boilerplate is stored once), and the 0.93 similarity check above.

---

## Language Routing

`detect_language()` is a character-set test, not a statistical classifier: if the text contains any Hiragana, Katakana, or Kanji it routes to `ja`, otherwise `en`. There is no confidence score and no third option — a single Japanese character in an English article routes the whole text to the Japanese pipeline.

The router then picks the first model in `SPACY_MODELS` whose name starts with the target language prefix. Models are lazy-loaded on first use.

```bash
SPACY_MODEL=en_core_web_md                      # primary — similarity, near-dup, fallback
SPACY_MODELS=en_core_web_md,ja_core_news_md     # routing pool
```

When a listed model is missing, the loader logs a warning and silently falls back to English. Japanese text tokenized by the English pipeline produces meaningless spans, so treat that warning as a hard failure — see [setup.md](setup.md#prerequisites).

### Japanese-language behaviour

Japanese extraction works, but three characteristics differ from the English path and are worth knowing before reading the output.

**Sentence splitting does not fire.** The fact extractor splits on `re.split(r"(?<=[.!?])\s+", text)`. Japanese terminates sentences with `。` and does not use spaces between them, so a Japanese article typically survives as a **single** very long statement rather than a set of discrete facts. The summarization step (which uses `doc.sents` and does handle `。`) is the only thing keeping statement length bounded.

**Noise filters do not apply.** Every filter in the [noise filtering table](learning-pipeline.md#noise-filtering-continual-learning) is an English regex. Japanese site chrome — navigation menus, share buttons, footer links, category lists — passes straight through and is stored inside the statement text alongside real content.

**Noun chunks are unavailable.** The `ja_core_news_md` pipeline does not implement `noun_chunks`; the extractor catches the `NotImplementedError` and continues. Japanese themes therefore come from NER only, which is why Japanese `tags` skew toward dates, times, and numeric tokens (`10月2日`, `2027年1月16日`, `18:00`) rather than concepts.

Net effect: Japanese facts are currently high-recall and low-precision. They are useful as retrieval evidence and for exercising the multi-language path, but they are noisier per-fact than English facts. Raising `min_sentence_len` does not help — the statements are long, not short.

---

## Tuning Reference

| Knob                       | Default  | Effect                                                                                                                        |
| -------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `min_sentence_len`         | `40`     | Function argument, not env. Sentences shorter than this are dropped before any NLP runs.                                      |
| `confidence`               | `medium` | Function argument. Stamped on every fact from the run.                                                                        |
| `EXTRACTED_EVIDENCE_COUNT` | `5`      | Max extracted facts fed into the HybridRetriever evidence pool per article. Raise to give learned facts more weight.          |
| `EXTRACTED_CONTEXT_LIMIT`  | `15`     | Max extracted facts injected as text into the Ollama prompt. Only facts whose tokens overlap the current article are included. |
| `TOPIC_SIGNAL_WINDOW`      | `100`    | How many recent facts build the adaptive topic signal that tilts SSI component selection.                                     |
| `CURATOR_MAX_PER_FEED`     | `10`     | Entries scanned per feed before keyword filtering — the upstream volume control.                                              |
| `MODEL2VEC_ENABLED`        | `true`   | When false, `primary_category` and `primary_ssi_component` are left empty on every fact.                                      |
| `AVATAR_LEARNING_ENABLED`  | `true`   | Master switch for narrative memory injection and moderation-event logging.                                                    |

`--learn` bypasses the `max_ideas` cap so every relevant article in the run is processed, not just the ones selected for posting.

---

## Reading the Run Log

```
🧠 12 new facts from 'imase、約1年の休止を経て活動再開を発表' (🗂️ pool=953)
🧠 0 new facts from 'This Week in Spring - September 1st, 2026'  (🗂️ pool=953)
```

`pool=N` is the total graph size after the article. `0 new facts` on a re-run is expected, not a failure — it means every candidate sentence hit one of the three dedup layers.

To see why individual sentences were rejected, enable debug logging. Every filter logs its own reason code:

```
extraction [too-short]: …
extraction [html-residue]: …
extraction [rss-boilerplate]: …
extraction [truncated-mid-word]: …
extraction [weak-entity]: …
extraction [spacy-verbless-blob]: …
```

---

## See Also

- [Learning, Grounding, and Explainability Pipeline](learning-pipeline.md) — the surrounding pipeline
- [Setup Guide](setup.md#prerequisites) — installing `spacy[ja]` and the language models
- [Docker Deployment](docker-deployment.md#spacy-language-models-in-the-image) — models baked into the container image
- [Environment Variables Reference](environment-variables.md#spacy_models--spacy_language_packs) — full env var reference
