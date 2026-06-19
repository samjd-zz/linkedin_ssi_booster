# Knowledge Extraction Quality Improvement

## Problem

The knowledge extraction pipeline in `services/avatar_intelligence/_extraction.py` was processing raw article text with 500+ regex-based filtering rules to remove boilerplate, marketing copy, and navigation chrome. This "garbage in, heavy filtering" approach had several issues:

1. **Brittle maintenance** — Required constant updates as new noise patterns emerged
2. **False negatives** — High-quality facts buried in noisy text were sometimes filtered out
3. **Inefficient** — Processing large amounts of irrelevant text before filtering
4. **Inconsistent** — Different preprocessing for post generation vs knowledge extraction

## Solution

**Add spaCy summarization as a preprocessing step before extraction** — the same intelligent filtering already used for post generation.

**Status: ✅ Enabled by default** — This feature is automatically active in all knowledge extraction operations. No configuration required.

### Architecture Change

```
BEFORE:
Article (3000 chars, noisy)
  → 500+ regex filters
  → Low-quality facts extracted

AFTER:
Article (3000 chars, noisy)
  → spaCy summarize (max_sentences=10, focus_entities=True)
  → Concise text (~800 chars, high signal)
  → Lighter regex filtering
  → High-quality facts extracted
```

### Implementation

1. **`services/avatar_intelligence/_extraction.py`**:
   - Added optional `spacy_nlp` parameter to `extract_and_append_knowledge()`
   - If provided and `len(article_text) > 800`, runs spaCy summarization first
   - Uses `max_sentences=10` (more than post generation's 5) to preserve fact coverage
   - Processes wider window (5000 chars vs 3000) for broader context

2. **`services/content_curator/curator.py`**:
   - Passes `self._spacy_nlp` to `extract_and_append_knowledge()` in both:
     - Fast-path `--learn` mode (line 477)
     - Standard curation with generation (line 520)
   - Ensures consistent preprocessing across all extraction workflows

### Benefits

1. **Higher precision** — spaCy's entity-focused summarization surfaces important content
2. **Better signal-to-noise** — Boilerplate filtered out before fact extraction
3. **Consistency** — Same preprocessing for both post generation and knowledge extraction
4. **Performance** — Smaller text means faster regex processing
5. **Maintainability** — Can simplify regex filters since spaCy handles structural quality

### Parameters

- **`max_sentences=10`** — More than post generation (5) to cast wider net for facts
- **`focus_entities=True`** — Prioritizes sentences with named entities
- **`article_text[:5000]`** — Wider window than post generation (3000) for broader coverage
- **Minimum summary length: 200 chars** — Falls back to full text if summary too short

### Logging

New debug log shows compression ratio:

```
extract_and_append_knowledge: spaCy pre-filter 3421 → 856 chars for 'Article Title'
```

## Testing

New test suite in `tests/test_extraction_with_summarization.py`:

- **Baseline test**: Extract from noisy article without summarization
- **Improvement test**: Extract from same article with summarization
- **Comparison test**: Verifies boilerplate reduction

Run with:

```bash
pytest tests/test_extraction_with_summarization.py -v
```

Expected outcome: Significantly fewer boilerplate facts with summarization enabled.

## Future Work

### Filter Simplification (Optional)

Now that spaCy handles structural quality, many content-based regex filters can be simplified or removed:

**Safe to simplify/remove** (spaCy's sentence scoring already handles these):

- Marketing/CTA filters (`Learn more`, `Sign up`, `Try it`)
- Newsletter preambles (`Welcome to`, `In this article`)
- Event marketing openers (`This year, we're`)
- Generic filler sentences (no concrete claims)

**Keep** (structural/technical filters):

- HTML residue detection
- Truncation/fragment detection
- Entity/signal requirements (lighter thresholds)
- spaCy structural filters (verbless blobs, multi-sentence concatenations)

### Monitoring

Track extraction quality metrics:

- Facts extracted per article (should remain stable or increase)
- Boilerplate detection rate (should decrease significantly)
- Extraction time (should decrease slightly due to smaller input)

## Configuration

**Default Behavior:**

The spaCy summarization preprocessing is **enabled by default** for all knowledge extraction operations. When `ContentCurator` is instantiated (during `--curate` or `--learn` operations), it automatically:

1. Initializes spaCy NLP engine via `get_spacy_nlp()`
2. Passes `self._spacy_nlp` to `extract_and_append_knowledge()` on every article
3. Applies summarization when article text exceeds 800 characters

**To Disable (Optional):**

If you need to disable spaCy summarization preprocessing:

- Set `enable_spacy_summarization=False` when creating `ContentCurator` instance in `main.py`
- Or pass `spacy_nlp=None` directly to `extract_and_append_knowledge()`

The change is backward compatible — extraction works with or without the `spacy_nlp` parameter.
