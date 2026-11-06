# Rei Toei Configuration, Examples, and Workflows

[Back to the customization guide](rei-toei-customization.md)

## Configuration Options

Rei Toei's behavior can be tuned via environment variables in `.env`:

### Core Settings

```bash
# Enable/disable DoT validation for lyrics
REI_TOEI_DOT_VALIDATION_ENABLED=true

# Minimum truth gradient for lyrical claims (0.0 - 1.0)
REI_TOEI_DOT_MIN_TRUTH_GRADIENT=0.60

# Suno API integration (sunoapi.org — third-party proxy)
SUNO_API_KEY=your_key_here
SUNO_API_BASE_URL=https://api.sunoapi.org
SUNO_MODEL=V6_MINI

# Strudel MCP command (used by agents/strudel_mcp_agent.py)
STRUDEL_MCP_COMMAND="npx -y @williamzujkowski/live-coding-music-mcp"
```

### Bilingual Lyric Mix

Set the language policy and desired Japanese lyrical-content target for Suno vocal lyrics:

```bash
REI_LYRIC_LANGUAGE=bilingual
REI_JAPANESE_LYRIC_PROBABILITY=0.33
```

The value is the source of truth for the bilingual target; it is not hardcoded in the prompt. `0.33` asks for approximately 33% Japanese lyrical content, while `0.50` asks for approximately 50%. The target is flexible for musical phrasing rather than a rigid alternating-line pattern.

Rei's bilingual instructions require Japanese to carry emotional, narrative, or hook meaning in complete singable phrases. English provides contrast and momentum. Selected Japanese hooks may be followed by a concise English sung echo on the next line, but Rei must not translate every Japanese line.

Japanese-only mode follows the same language-quality rules: contemporary idiomatic Japanese, natural particles and verb forms, selective kanji, and mora-aware phrasing. Rei avoids literal technical translations, unnecessary katakana jargon, isolated English words inside Japanese grammar, and Chinese-only glyphs. Technical loanwords are used only when they sound natural in Japanese music.

For learning support, Rei targets square-bracket annotations on roughly one out of every four Japanese lyric lines, capped at six cues per song. Use this order:

```text
接続はまだ終わらない
[setsuzoku wa mada owaranai]
The connection is not over yet
```

Use standard Hepburn-style Romaji in the bracket, including `o` for を and macrons such as `ō`, `ū`, and `ā` when appropriate. Keep the Japanese lyric first, then put the cue on its own line. These annotations are selective enough to keep the result song-like, but dense enough for language learning. The bracketed Romaji is instructional and not sung; the English meaning follows on its own line and is sung. If the model writes `[romaji] [English meaning]` on one line, the formatter moves the meaning onto its own sung line (skipping it when the next line already sings it), while short production cues such as `[Synth sweep]` stay bracketed. Parentheses remain reserved for vocalizations and production cues such as `(Ahh ahh ahh)` or `(bass drop)`.

The final Suno formatter normalizes common model variations such as `Japanese (Romaji) [Meaning]`, `Japanese [Romaji] (Meaning)`, either form with an extra English sung echo, standalone parenthetical Romaji after a Japanese line, and `Romaji (Japanese)` into the Japanese-first learning format. Leading or trailing English text around an inline cue is preserved as its own sung line. The formatter also repairs known non-Japanese script contamination in Japanese lyric lines, such as `サーಜ್` becoming `サージ`, and removes leaked instructional placeholders such as `[actual pronunciation] [actual English meaning]` before saving or submitting lyrics.

Small local models can also echo the JSON field instructions into lyric text. The formatter removes bare character-cap notes such as `400 chars` or `600 chars`, prose such as `on its own line`, `Kanji:`/`English:` metadata parentheticals, and cue instructions such as `then '(bass drop)' on its own line` while preserving the actual `(bass drop)` cue. It also converts leaked JSON escapes such as literal `\n` and `\.` sequences into clean lyric lines and punctuation, and removes leaked quote/comma delimiters.

If an initial draft drifts materially from the configured target or becomes single-language, Rei retries with the same environment-derived target. Malformed repair output never bypasses this check: the last parseable draft is revalidated and another repair is attempted when available. A draft that still falls outside the configured tolerance is rejected before it is saved or submitted to Suno.

**Chinese-script leakage detection:** Kanji and Chinese hanzi share Unicode codepoints, so CJK character presence alone cannot confirm genuine Japanese. Some models (notably the Qwen family, which is heavily trained on Chinese text) can generate Simplified Chinese and label it as "Japanese" bilingual lyrics — recognizable by markers like the fullwidth comma `，`, the particle `的`, or long unbroken ideograph runs with no hiragana/katakana. Validation runs in this order for every attempt: (1) require kana or kanji present at all, (2) reject Chinese-script leakage, (3) check the bilingual JP/EN line-ratio target. A draft that fails any of these retries, then falls back to hand-authored Japanese-aware lyrics rather than submitting Chinese-mislabeled-as-Japanese or English-only content.

Use `--rei-preview` to inspect a generated song without saving it or calling Suno:

```bash
bash run.sh --profile core run --rm app python main.py --rei-generate --rei-preview
```

### Verified Intel WSL2 Laptop Workflow

For the Windows WSL2 Intel iGPU setup, rebuild the application image after
source changes, then run the preview through the core profile:

```bash
bash run.sh --profile core build app
bash run.sh --profile core run --rm app \
  python main.py --rei-generate --rei-preview \
  --rei-theme "intel laptop gpu activated"
```

This uses the local Ollama service with the configured `qwen2.5:3b` primary
model and `llama3.2:3b` fallback. Preview mode prints the generated Suno song
without saving it or submitting it to Suno. `run.sh` detects WSL2 through
`/dev/dxg` and applies the Intel Ollama runtime override automatically.

### Example: Strict Truth Validation

For academic or educational content, use stricter validation:

```bash
REI_TOEI_DOT_VALIDATION_ENABLED=true
REI_TOEI_DOT_MIN_TRUTH_GRADIENT=0.75
```

### Example: Creative Freedom

For experimental/artistic content, relax validation:

```bash
REI_TOEI_DOT_VALIDATION_ENABLED=false
```

Note: `REI_TOEI_REQUIRE_EVIDENCE_IDS` and `REI_TOEI_ALLOW_METAPHORICAL_CLAIMS` are not currently implemented in runtime code.

---

## Example Customizations

### Complete Example: Ambient Electronic Avatar

**Persona Graph (`rei_toei_persona_graph.json`):**

```json
{
  "schemaVersion": "1.0",
  "identity": {
    "name": "Rei Toei",
    "role": "Ambient Electronic Music Avatar",
    "aesthetic": "Evolving textures and patient development"
  },
  "personality_traits": ["calm", "contemplative", "minimalist"],
  "musical_expertise": {
    "genres": ["Ambient techno", "Drone", "Sound art"],
    "production_techniques": ["Granular synthesis", "Long reverb tails"]
  },
  "production_knowledge": {
    "bpm_theory": {
      "default_range": [60, 90]
    }
  },
  "communication_style": {
    "tone": "Poetic, texture-focused"
  },
  "knowledge_sources": {},
  "creative_process": {},
  "constraints": {},
  "comparison_to_sam": {}
}
```

**Domain Knowledge (excerpt):**

```json
{
  "genre_production_techniques": {
    "ambient_techno": {
      "tempo": "60-90 BPM",
      "key_elements": [
        "evolving_pads",
        "sparse_percussion",
        "field_recordings",
        "granular_textures"
      ],
      "production_techniques": [
        "granular_synthesis",
        "long_reverb_tails",
        "subtle_modulation",
        "sample_stretching"
      ]
    }
  }
}
```

**Pattern Template (excerpt):**

```json
{
  "name": "evolving_drone",
  "concept": "continuous_processes",
  "description": "Slowly evolving texture representing long-running background tasks",
  "code": "sound(\"sawtooth\").note(\"<c2 eb2 g2>\").lpf(sine.slow(16).range(100,800)).room(0.8).gain(0.3)",
  "use_cases": [
    "background_services",
    "daemon_processes",
    "continuous_monitoring"
  ]
}
```

### Complete Example: Breakcore Chaos Avatar

**Persona Graph:**

```json
{
  "schemaVersion": "1.0",
  "identity": {
    "name": "Rei Toei",
    "role": "Breakcore Production AI",
    "aesthetic": "Chaotic precision with extreme dynamics"
  },
  "personality_traits": ["aggressive", "anarchic", "fearless"],
  "musical_expertise": {
    "genres": ["Breakcore", "Drill and bass", "Glitch"],
    "production_techniques": ["Chaotic breakbeat chops", "Aggressive sampling"]
  },
  "production_knowledge": {
    "bpm_theory": {
      "default_range": [160, 300]
    }
  },
  "communication_style": {
    "tone": "Sharp, fragmented, rapid-fire"
  },
  "knowledge_sources": {},
  "creative_process": {},
  "constraints": {},
  "comparison_to_sam": {}
}
```

**Pattern Template:**

```json
{
  "name": "break_destruction",
  "concept": "race_conditions",
  "description": "Overlapping breakbeats creating timing chaos",
  "code": "stack(\n  sound(\"breaks165\").chop(16).fast(\"<1 2 3 4>\").sometimes(rev),\n  sound(\"breaks165\").chop(32).fast(\"<2 4 8>\").late(0.03),\n  sound(\"reese\").note(\"<a1 c2 d2>\").cutoff(sine.range(100,4000))\n)",
  "use_cases": ["thread_collision", "deadlock_scenarios", "timing_attacks"]
}
```

---

## Testing Your Changes

### 1. Validate JSON Syntax

```bash
# Test JSON is valid
python -c "import json; json.load(open('data/avatar/rei_toei_persona_graph.json'))"
python -c "import json; json.load(open('data/avatar/rei_toei_domain_knowledge.json'))"
python -c "import json; json.load(open('data/avatar/rei_toei_strudel_patterns.json'))"
```

### 2. Test Configuration Loading

```bash
# Run with --rei-explain and --rei-preview to inspect choices without saving/submitting
python main.py --rei-generate --rei-explain --rei-preview
```

### 3. Test Generation

```bash
# Generate Suno song (preview mode)
python main.py --rei-generate --rei-theme "async programming" --rei-preview

# Generate Strudel pattern (preview without execution)
python main.py --rei-generate-strudel --rei-theme "recursion" --rei-preview

# Generate + attempt execution (requires a compatible execution backend)
python main.py --rei-generate-strudel --rei-theme "recursion" --rei-execute
```

### 4. Test Console Integration

```bash
# Enter console mode and switch to Rei
python main.py --console

# Inside console:
Sam> /rei-toei
Rei> [Structured song on an auto-selected theme]
You> Generate a song about neural networks
```

### 5. Run Unit Tests

```bash
# Full test module
source .venv/bin/activate && python -m pytest -q tests/test_rei_toei_service.py

# Strudel MCP agent unit tests
source .venv/bin/activate && python -m pytest -q tests/test_strudel_mcp_agent.py

# Specific test
source .venv/bin/activate && python -m pytest -q tests/test_rei_toei_service.py::test_load_rei_persona_success
```

### 6. Strudel MCP Health Check

```bash
# Validate MCP toolchain (initialize + tools/list) in Docker
bash run.sh --profile core run --rm strudel-mcp-agent --health-check
```

---

## Advanced Customization

### Creating Multiple Rei Variants

You can maintain multiple configurations for different contexts:

```bash
data/avatar/
├── rei_toei_persona_graph.json           # Default
├── rei_toei_persona_graph_ambient.json   # Ambient variant
├── rei_toei_persona_graph_breakcore.json # Breakcore variant
```

Then swap via symlink or environment variable:

```bash
# Swap to ambient variant
ln -sf rei_toei_persona_graph_ambient.json rei_toei_persona_graph.json

# Environment-variable switching is not currently implemented.
# If desired, add support in services/rei_toei/_config.py and loaders.
```

### Dynamic Pattern Selection

Conditional pattern branching is not supported by the current loader/runtime schema (which expects a single `code_template` per template). Use this approach only if you also add code support in `services/rei_toei/_loaders.py` and generation pipelines.

Example target shape (requires code changes):

```json
{
  "name": "adaptive_rhythm",
  "concept": "load_balancing",
  "code_variants": {
    "low_load": "sound(\"bd\").fast(1)",
    "medium_load": "sound(\"bd\").fast(2)",
    "high_load": "sound(\"bd\").fast(4).sometimes(x => x.fast(2))"
  },
  "selection_criteria": "knowledge_complexity"
}
```

---

## Troubleshooting

### Strudel Implementation Notes

- Loader compatibility: `load_strudel_patterns()` supports both top-level `templates` and legacy `pattern_library`.
- Execution transport: `execute_strudel_pattern()` attempts WebSocket first, then falls back to stdio MCP execution.
- Domain key compatibility: Strudel prompt assembly accepts either `core_functions`/`transformations` or `basic_functions`/`pattern_transformations`.

### Issue: Generated lyrics don't match persona

**Solution:** Check `personality_traits`, `communication_style`, and `identity` in persona graph. The LLM uses these fields to tune output.

### Issue: Strudel patterns fail to execute

**Solution:** Validate Tidal Cycles syntax. Common errors:

- Missing parentheses: `sound("bd").fast(2)` not `sound "bd" fast 2`
- Invalid sound banks: check available samples in Strudel environment
- Syntax incompatibility: some Haskell Tidal syntax doesn't work in JavaScript Strudel

**Additional note:** `validate_strudel_syntax()` is heuristic (regex/structure checks), not a full parser. A "valid" result is a preflight signal, not a guarantee of live execution.

### Issue: DoT validation blocks all lyrics

**Solution:** Lower `REI_TOEI_DOT_MIN_TRUTH_GRADIENT` or disable validation for creative content. Remember: DoT is designed for factual claims, not poetic metaphors.

### Issue: Genre knowledge not reflected in output

**Solution:** Ensure `genre_production_techniques` entries align with `musical_expertise.genres` in persona graph. The LLM retrieves genre-specific knowledge from those sections.

---

## Best Practices

1. **Start with small changes** — modify one section at a time and test
2. **Keep backups** — copy original files before major customizations
3. **Maintain consistency** — ensure persona, domain knowledge, and patterns align
4. **Test incrementally** — validate JSON → test loading → test generation → test integration
5. **Document your changes** — add comments in JSON (if using JSONC) or maintain a separate changelog

---

## Further Reading

- [Rei Toei Implementation Plan](features/rei-toei/plan.md) — Complete architecture and design
- [Rei Toei Feature Idea](features/rei-toei/idea.md) — Original concept and motivation
- [CLI Reference](cli-reference.md) — All `--rei-*` command-line flags
- [Console Mode Guide](usage-schedule-curate-console.md#console-mode--welcome-screen-and-query-routing) — Interactive Rei usage
- [Strudel Documentation](https://strudel.cc/) — Official Tidal Cycles / Strudel reference
- [SunoAPI Documentation](https://docs.sunoapi.org/suno-api/generate-music) — SunoAPI.org generate endpoint used by this project

---

**Need help?** Open an issue on GitHub or check the test suite (`tests/test_rei_toei_service.py`) for working examples.
