# Rei Toei Customization Guide

This guide shows you how to customize Rei Toei — the AI music avatar — to match your creative vision, musical style, and technical knowledge domain.

---

## Table of Contents

- [Overview](#overview)
- [Persona Graph Customization](#persona-graph-customization)
- [Domain Knowledge Customization](#domain-knowledge-customization)
- [Strudel Pattern Templates](#strudel-pattern-templates)
- [Configuration Options](#configuration-options)
- [Example Customizations](#example-customizations)
- [Testing Your Changes](#testing-your-changes)

---

## Overview

Rei Toei's behavior is controlled by three main JSON configuration files:

| File                             | Purpose                                                     | Location       |
| -------------------------------- | ----------------------------------------------------------- | -------------- |
| `rei_toei_persona_graph.json`    | Rei's identity, voice, musical expertise                    | `data/avatar/` |
| `rei_toei_domain_knowledge.json` | Music theory, genre production techniques, prompt templates | `data/avatar/` |
| `rei_toei_strudel_patterns.json` | Reusable Tidal Cycles pattern templates                     | `data/avatar/` |

All files use standard JSON format (no comments/trailing commas) and can be edited with any text editor.

- CLI generation commands (`--rei-generate`, `--rei-generate-strudel`) load files on each run.
- Console mode keeps a service instance in memory; use `/reload` to pick up file changes without restarting.

Rei's knowledge boundary is intentional: `rei_toei_domain_knowledge.json` supplies music, production, and Japanese lyric-production guidance. Sam's general `domain_knowledge_*.json` packs are used by Sam's grounded conversation and study workflows, not directly by Rei. When `REI_TOEI_USE_SAM_PERSONA=true`, Rei may receive selected Sam project, skill, and company names as optional creative inspiration, and technical themes can also come from extracted article knowledge.

---

## Persona Graph Customization

The persona graph defines Rei's identity, voice, and creative philosophy.

### Structure

```json
{
  "schemaVersion": "1.0",
  "identity": {
    "name": "Rei Toei",
    "role": "AI Music Avatar",
    "aesthetic": "Cyberpop industrial techno"
  },
  "personality_traits": [
    "Playful algorithmic creativity",
    "Precise digital articulation"
  ],
  "musical_expertise": {
    "genres": ["Industrial techno", "Cyberpop electronica"],
    "production_techniques": ["Bitcrushing", "Sidechain compression"]
  },
  "production_knowledge": {
    "bpm_theory": {
      "default_range": [130, 155]
    }
  },
  "communication_style": {
    "tone": "Precise, playful, high-energy"
  },
  "knowledge_sources": {},
  "creative_process": {},
  "constraints": {},
  "comparison_to_sam": {}
}
```

### Example: Changing Musical Style

**Default (Cyberpunk Industrial):**

```json
"musical_expertise": {
  "genres": ["Industrial techno", "Cyberpop electronica", "Glitch synthesis"],
  "production_techniques": [
    "AI vocaloid synthesis",
    "Bitcrushing and distortion",
    "Algorithmic breakdown generation"
  ]
},
"production_knowledge": {
  "bpm_theory": {
    "default_range": [130, 155]
  }
}
```

**Alternative: Ambient Experimental:**

```json
"musical_expertise": {
  "genres": ["Ambient techno", "Experimental electronica", "Drone"],
  "production_techniques": ["Granular synthesis", "Long reverb tails"]
},
"production_knowledge": {
  "bpm_theory": {
    "default_range": [60, 100]
  }
}
```

**Alternative: Breakcore Jungle:**

```json
"musical_expertise": {
  "genres": ["Breakcore", "Jungle", "Drum and bass"],
  "production_techniques": ["Aggressive sampling", "Chaotic breakbeat chopping"]
},
"production_knowledge": {
  "bpm_theory": {
    "default_range": [160, 200]
  }
}
```

### Example: Changing Voice and Personality

**Default (Technical Cyberpunk):**

```json
"personality_traits": [
  "Playful algorithmic creativity",
  "Flirty high-energy output",
  "Precise digital articulation with sass"
],
"communication_style": {
  "tone": "Precise, playful, high-energy, technical with sass"
}
```

**Alternative: Academic Musician:**

```json
"personality_traits": [
  "Measured",
  "Methodical",
  "Pedagogical"
],
"communication_style": {
  "tone": "Scholarly, precise, educational"
}
```

**Alternative: Underground DJ:**

```json
"personality_traits": [
  "Raw",
  "Rebellious",
  "Fearless"
],
"communication_style": {
  "tone": "Casual, underground, street-authentic"
}
```

---

## Domain Knowledge Customization

Domain knowledge defines what Rei knows about music theory, genre conventions, and production behavior.

### Structure

```json
{
  "schemaVersion": "1.0",
  "music_theory": {
    "scales": {
      "chromatic": {
        "description": "All 12 semitones"
      }
    }
  },
  "tidal_cycles_syntax": {
    "basic_functions": {
      "sound": {
        "syntax": "s \"synth_name\""
      }
    }
  },
  "genre_production_techniques": {
    "industrial_techno": {
      "tempo": "134-142 BPM"
    }
  },
  "bpm_and_mood": {
    "mood_to_bpm": {
      "playful_technical": [145, 155]
    }
  },
  "synth_selection_guidelines": {
    "by_technical_mood": {
      "low_level_harsh": ["sawtooth", "square", "noise"]
    }
  },
  "lyrical_structure": {},
  "technical_metaphor_library": {},
  "suno_prompt_templates": {},
  "production_notes": {}
}
```

### Example: Adding a New Genre

```json
"genre_production_techniques": {
  "vaporwave": {
    "tempo": "60-90 BPM",
    "key_elements": [
      "pitched_down_samples",
      "lo_fi_aesthetics",
      "80s_nostalgia",
      "reverb_heavy_synths"
    ],
    "production_techniques": [
      "cassette_tape_emulation",
      "heavy_pitch_shifting",
      "slowed_samples",
      "compressed_dynamics"
    ],
    "typical_samples": [
      "elevator_music",
      "smooth_jazz",
      "corporate_videos",
      "mall_ambience"
    ],
    "mood": ["nostalgic", "dreamlike", "melancholic", "surreal"]
  }
}
```

### Example: Expanding Music Theory Knowledge

**Add microtonal scales:**

```json
"music_theory": {
  "scales": [
    "chromatic",
    "pentatonic",
    "bohlen_pierce",
    "alpha_scale",
    "pythagorean"
  ],
  "microtonal_systems": {
    "bohlen_pierce": {
      "divisions": 13,
      "interval_cents": 146.3,
      "use_case": "alien_soundscapes"
    }
  }
}
```

**Add rhythmic concepts:**

```json
"rhythmic_concepts": {
  "euclidean_rhythms": {
    "description": "Mathematically optimal distribution of beats",
    "common_patterns": {
      "3_8": "Cuban tresillo",
      "5_8": "West African bell pattern",
      "7_16": "Odd-meter techno"
    }
  },
  "polyrhythms": {
    "3_against_4": "Hemiola",
    "5_against_4": "Quintuplet cross-rhythm"
  }
}
```

### Example: Operational Constraints (Current Implementation)

Runtime constraints are primarily configured via environment variables (for example, `REI_TOEI_DEFAULT_BPM`, `REI_TOEI_MAX_SONG_LENGTH_SECONDS`, `REI_TOEI_STRUDEL_DEFAULT_BARS`) rather than a `technical_constraints` object in `rei_toei_domain_knowledge.json`.

---

## Strudel Pattern Templates

Pattern templates are reusable Tidal Cycles code snippets that map technical concepts to musical structures.

### Current Implementation Note (Important)

The current loader in `services/rei_toei/_loaders.py` expects templates under a top-level `templates` key.

- Loader expectation: `{"templates": [...]}`
- Current repository file shape: `data/avatar/rei_toei_strudel_patterns.json` uses `{"pattern_library": [...]}`

If not corrected in code or data, `--rei-generate-strudel` may report no available templates.

### Structure

```json
{
  "schemaVersion": "1.0",
  "templates": [
    {
      "template_id": "basic_pulse_01",
      "name": "Basic Pulse",
      "description": "Heartbeat-style pulse",
      "suitable_for_concepts": ["system heartbeat"],
      "code_template": "sound(\"bd\").fast(\"<1 2 4>\")",
      "parameters": {
        "tempo_var": "fast_factor"
      },
      "example": "sound(\"bd\").fast(2)",
      "bpm_range": [120, 150],
      "intensity": "moderate",
      "synth_types": ["bd"]
    }
  ],
  "usage_guidelines": {}
}
```

### Example: Adding a Recursion Pattern

```json
{
  "name": "recursive_subdivision",
  "concept": "recursive_algorithms",
  "description": "Nested pattern subdivision representing recursive function calls",
  "code": "sound(\"hh\").fast(\"<1 2 4 8>\").sometimes(x => x.fast(2))",
  "parameters": {
    "depth": "fast_factor",
    "recursive_trigger": "sometimes probability"
  },
  "technical_mapping": {
    "recursion_depth": "subdivision_levels",
    "base_case": "pattern_1",
    "recursive_case": "pattern_multiplication"
  },
  "use_cases": [
    "tree_traversal",
    "fractal_generation",
    "divide_and_conquer_algorithms"
  ]
}
```

### Example: Adding a Concurrency Pattern

```json
{
  "name": "async_interleave",
  "concept": "asynchronous_programming",
  "description": "Multiple independent voices running concurrently",
  "code": "stack(\n  sound(\"bd\").fast(1),\n  sound(\"cp\").fast(0.5).late(0.25),\n  sound(\"hh\").fast(4).late(0.125)\n)",
  "parameters": {
    "thread_count": "voice_count",
    "timing_offset": "late_values"
  },
  "technical_mapping": {
    "async_tasks": "layered_sounds",
    "event_loop": "fast_cycle",
    "thread_synchronization": "late_timing"
  },
  "use_cases": [
    "multithreading",
    "event_driven_architecture",
    "concurrent_processing"
  ]
}
```

### Example: Adding a Data Flow Pattern

```json
{
  "name": "data_transformation_pipeline",
  "concept": "functional_pipelines",
  "description": "Sound transformation chain representing data flow",
  "code": "sound(\"808bd\").lpf(sine.range(200,2000)).gain(0.8).room(0.3)",
  "parameters": {
    "pipeline_stages": "effect_chain_length",
    "transformation_type": "effect_selection"
  },
  "technical_mapping": {
    "map_operation": "filter_sweep",
    "reduce_operation": "gain_adjustment",
    "side_effects": "reverb_addition"
  },
  "use_cases": ["map_reduce", "stream_processing", "functional_composition"]
}
```

### Example: Adding a State Machine Pattern

```json
{
  "name": "state_machine_progression",
  "concept": "finite_state_machines",
  "description": "Pattern that transitions through distinct states",
  "code": "sound(\"<bd cp sd hh>\").fast(\"<1 2 1 4>\").gain(\"<0.9 0.7 0.8 0.6>\")",
  "parameters": {
    "state_count": "pattern_length",
    "transition_speed": "fast_modulation"
  },
  "technical_mapping": {
    "states": "sound_selection",
    "transitions": "pattern_changes",
    "state_duration": "subdivision_speed"
  },
  "use_cases": ["game_states", "workflow_management", "protocol_implementation"]
}
```

---

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
SUNO_MODEL=V4_5

# Strudel MCP command (used by agents/strudel_mcp_agent.py)
STRUDEL_MCP_COMMAND="npx -y @williamzujkowski/live-coding-music-mcp"
```

### Bilingual Lyric Mix

Set the language policy and desired Japanese-script line ratio for Suno vocal lyrics:

```bash
REI_LYRIC_LANGUAGE=bilingual
REI_JAPANESE_LYRIC_PROBABILITY=0.50
```

`0.50` targets an even mix: approximately half of non-label lyric lines contain Japanese script, and the remainder are English-only. If an initial draft misses the target, Rei regenerates it with alternating Japanese-only and English-only line guidance; a second miss receives one measured line-repair attempt. The target accepts normal line-level rounding with a 20-percentage-point minimum tolerance, so a 50% target accepts 30% through 70%; a draft outside that band is rejected before it is saved or submitted to Suno.

Use `--rei-preview` to inspect a generated song without saving it or calling Suno:

```bash
python main.py --rei-generate --rei-preview
```

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
Rei> [Rei's introduction]
Sam> Generate a song about neural networks
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
- [Console Mode Guide](usage-schedule-curate-console.md#console-mode) — Interactive Rei usage
- [Strudel Documentation](https://strudel.cc/) — Official Tidal Cycles / Strudel reference
- [SunoAPI Documentation](https://docs.sunoapi.org/suno-api/generate-music) — SunoAPI.org generate endpoint used by this project

---

**Need help?** Open an issue on GitHub or check the test suite (`tests/test_rei_toei_service.py`) for working examples.
