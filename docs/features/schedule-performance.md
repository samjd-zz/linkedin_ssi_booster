# Schedule Runtime and Performance

```bash
python main.py --schedule --week 1
python main.py --schedule --week 1 --channel linkedin,x --dry-run
```

## Preparation and Grounding

Schedule-only runs skip GitHub profile enrichment: that context is not consumed
by the schedule prompts. Console and curation still load their GitHub context.

Avatar state and normalized persona/domain evidence are prepared once per run,
not per channel/topic. Extracted evidence is normalized and tokenized once only
when `--avatar-explain` is enabled. Each topic's retrieved grounding is cached
for this run and reused across channels, including any optional external
evidence returned by retrieval. Generated text, truth gating, formatting,
hashtags, footers, and artwork remain channel-specific.

## Posting Caps and Preview Behavior

When `SCHEDULER_POSTING_SLOTS` contains an explicit cap, live non-YouTube runs
apply the scheduler's existing SSI allocation/ordering to calendar topics before
generation. The scheduler and CLI share the same selection implementation.
Already-selected posts are queued without a second SSI allocation, preserving
the original order even when a pillar has overflowing candidates.
For five topics, two channels, and one slot per channel, this reduces ten post
generations and art attempts to two. The queued topic selection is unchanged.

With no cap, the entire week is generated as before. Invalid cap configuration
retains the existing warning/no-cap behavior. `--dry-run` and YouTube generate
the entire week even when a cap is configured. YouTube scripts remain local,
with no Buffer submission.

Dry-run prevents Buffer calls, not model generation or the existing optional
art pipeline. Enabled FLUX can still generate artifacts during dry-run.

## Generation-Time Reports

Schedule `--dot-report` describes generated content, **not appended hashtags or
configured footers**; the report labels this scope explicitly. Metadata is
captured before image-prompt optimization or footer/hashtag appending.

Matching generation-time DoT results are reused. Paragraph/whitespace-only
formatting differences do not trigger another score. Changed generated text,
missing metadata, or a missing DoT result triggers a fallback score for the
generated content. Avatar explanations likewise use matching generation
metadata or validate the generated content again if it is unavailable.

This does not certify the factual accuracy of manually configured footer text.
Posting text and its configured hashtags/footers remain unchanged.

## Stage Timings and Shutdown

INFO logs now distinguish:

| Stage | Work |
| ----- | ---- |
| `schedule.preparation` | Avatar loading, normalization, optional extracted-evidence tokenization |
| `schedule.retrieval` | Topic grounding preparation or cache lookup |
| `schedule.generation` | Channel generation including truth gating |
| `schedule.dot_report` | Optional generated-content score lookup/fallback and report assembly |
| `schedule.gc` | Existing periodic garbage collection between topics |
| `schedule.art` | Scheduled artwork request/rendering |
| `schedule.queue` | Channel discovery and Buffer queue submission |
| `cleanup.total` | Complete post-run resource cleanup |
| `cleanup.ollama` | Ollama eviction request and wait |
| `cleanup.flux_remote` | FLUX HTTP unload request, only after an actual generation request |
| `cleanup.flux_local` | Unload of an already-imported local image runtime |
| `cleanup.heap` | Final Python garbage collection |

These nest with existing `ollama.chat`, `truth_gate`, and `buffer.graphql`
records; do not sum overlapping stages. Ollama server timings separate model
loading, prompt evaluation, and generation.

The shared cleanup helper now contacts FLUX `/unload` only if this process
actually attempted a remote generation request. Disabled/minimal FLUX,
DNS failures before a request, and text-only runs do not cause an otherwise
unused unload request. Failed generation requests still mark the runtime as
possibly used, so cleanup attempts to release it; successful unload clears the
marker. Cleanup does not import an unused local image runtime.

Ollama eviction and used-runtime cleanup remain synchronous. Existing timeouts
and memory-release behavior are retained rather than hiding cleanup in the
background.

See [regression coverage](../testing-and-dev.md#schedule-performance-regressions)
for operation-count tests. No hardware latency threshold is claimed.
