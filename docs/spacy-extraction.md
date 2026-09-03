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

The combined set is lowercased and deduplicated, then split **by source** — named entities go to `entities`, noun chunks go to `concepts` (stored as `tags`):

| Field      | Source                             | Cap |
| ---------- | ---------------------------------- | --- |
| `entities` | spaCy NER spans (labels above)     | 5   |
| `tags`     | noun chunks not already an entity  | 8   |

Splitting by source is language-agnostic. The previous rule split on `str.split()` token count, which silently filed **every** Japanese theme as a tag — Japanese is written without spaces, so `entities` only ever caught strings containing an ASCII space, which in practice meant scraper fragments like `'04 00:00 imase'`.

Within each group, themes are ranked **longest-first** so that truncation keeps the most specific ones, and `DATE`/`TIME` entities are ranked last. Both matter: the old code sorted alphabetically before truncating, which let digit-leading strings win the cap, and plain longest-first is not enough either because Japanese dates (`2027年1月16日`) are longer than most concept themes.

**Fallback:** when spaCy is unavailable the extractor drops to regex — capitalized words become `entities`, 4+ character lowercase words become `tags`, and `extraction_method` is stamped `regex_fallback` instead of `spacy_nlp` so the two are distinguishable on disk.

### 3. Semantic near-duplicate suppression

Within a single article, each candidate sentence is compared against facts already collected from the same URL. Similarity `>= 0.93` marks it a near-paraphrase and it is dropped. This catches tense and wording variants that produce different content hashes but identical meaning.

This check routes through the same language-matched model as the rest of the pipeline, so Japanese sentences are compared with Japanese vectors.

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

Japanese extraction works. One characteristic still differs from the English path and is worth knowing before reading the output.

**Noise filters do not apply.** Every filter in the [noise filtering table](learning-pipeline.md#noise-filtering-continual-learning) is an English regex. Japanese site chrome — navigation menus, share buttons, footer links, category lists — passes straight through and is stored inside the statement text alongside real content. Japanese facts are therefore higher-recall and lower-precision than English ones: useful as retrieval evidence, noisier per fact.

#### Previously documented as limitations, now fixed

Three claims that appeared in earlier versions of this document were wrong or have since been corrected:

- **`noun_chunks` is implemented.** Verified on spaCy 3.8.16: `spacy/lang/ja/syntax_iterators.py` ships a `noun_chunks` iterator, and `ja_core_news_md` returns chunks normally. No `ja-ginza` dependency is required.
- **Sentence splitting fires.** The splitter is now `(?<=[。！？])\s*|(?<=[.!?])\s+` — the zero-width branch handles Japanese, which uses no space after `。`, while the ASCII branch keeps its whitespace requirement so decimals like `3.5` are not split.
- **Themes are no longer whitespace-classified.** See the entities/tags table above.

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
