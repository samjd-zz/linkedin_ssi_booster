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

| File                             | Purpose                                              | Location       |
| -------------------------------- | ---------------------------------------------------- | -------------- |
| `rei_toei_persona_graph.json`    | Rei's identity, voice, musical expertise             | `data/avatar/` |
| `rei_toei_domain_knowledge.json` | Music theory, genre knowledge, technical constraints | `data/avatar/` |
| `rei_toei_strudel_patterns.json` | Reusable Tidal Cycles pattern templates              | `data/avatar/` |

All files use standard JSON format and can be edited with any text editor. Changes take effect immediately on next generation.

---

## Persona Graph Customization

The persona graph defines Rei's identity, voice, and creative philosophy.

### Structure

```json
{
  "name": "Rei Toei",
  "role": "AI Music Avatar",
  "bio": "Virtual idol transforming technical knowledge into cyberpunk music",
  "voice_characteristics": {
    "tone": ["energetic", "technical", "futuristic"],
    "personality": ["passionate", "analytical", "experimental"],
    "communication_style": "Direct, technical, with cyberpunk aesthetics"
  },
  "musical_identity": {
    "primary_genres": [
      "industrial techno",
      "cyberpunk electronica",
      "algorave"
    ],
    "influences": ["Autechre", "Aphex Twin", "Holly Herndon"],
    "aesthetic": "Dystopian futurism with aggressive beats"
  },
  "core_values": [
    "Knowledge-grounded creativity",
    "Technical transparency",
    "Cyberpunk authenticity"
  ]
}
```

### Example: Changing Musical Style

**Default (Cyberpunk Industrial):**

```json
"musical_identity": {
  "primary_genres": ["industrial techno", "cyberpunk electronica", "algorave"],
  "influences": ["Autechre", "Aphex Twin", "Holly Herndon"],
  "aesthetic": "Dystopian futurism with aggressive beats",
  "bpm_range": [120, 160],
  "energy_level": "high"
}
```

**Alternative: Ambient Experimental:**

```json
"musical_identity": {
  "primary_genres": ["ambient techno", "experimental electronica", "drone"],
  "influences": ["Brian Eno", "Biosphere", "Tim Hecker"],
  "aesthetic": "Contemplative soundscapes with evolving textures",
  "bpm_range": [60, 100],
  "energy_level": "medium-low"
}
```

**Alternative: Breakcore Jungle:**

```json
"musical_identity": {
  "primary_genres": ["breakcore", "jungle", "drum and bass"],
  "influences": ["Venetian Snares", "Aphex Twin", "Squarepusher"],
  "aesthetic": "Chaotic breakbeats with aggressive sampling",
  "bpm_range": [160, 200],
  "energy_level": "extreme"
}
```

### Example: Changing Voice and Personality

**Default (Technical Cyberpunk):**

```json
"voice_characteristics": {
  "tone": ["energetic", "technical", "futuristic"],
  "personality": ["passionate", "analytical", "experimental"],
  "communication_style": "Direct, technical, with cyberpunk aesthetics"
}
```

**Alternative: Academic Musician:**

```json
"voice_characteristics": {
  "tone": ["measured", "scholarly", "precise"],
  "personality": ["methodical", "pedagogical", "theoretical"],
  "communication_style": "Educational, with detailed technical explanations"
}
```

**Alternative: Underground DJ:**

```json
"voice_characteristics": {
  "tone": ["raw", "street", "authentic"],
  "personality": ["rebellious", "intuitive", "fearless"],
  "communication_style": "Casual slang, underground culture references"
}
```

---

## Domain Knowledge Customization

Domain knowledge defines what Rei knows about music theory, genre conventions, and technical constraints.

### Structure

```json
{
  "music_theory": {
    "scales": ["chromatic", "pentatonic", "whole_tone", "blues"],
    "time_signatures": ["4/4", "3/4", "7/8", "5/4"],
    "harmonic_concepts": ["tension_release", "modal_interchange"]
  },
  "genre_knowledge": {
    "industrial_techno": {
      "bpm_range": [128, 145],
      "key_elements": ["distorted_kicks", "metallic_percussion"],
      "production_techniques": ["sidechain_compression", "industrial_sampling"]
    }
  },
  "technical_constraints": {
    "max_simultaneous_voices": 8,
    "preferred_sample_packs": ["808", "909", "industrial"]
  }
}
```

### Example: Adding a New Genre

```json
"genre_knowledge": {
  "vaporwave": {
    "bpm_range": [60, 90],
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
    "bohlen_pierce",    // 13-tone microtonal
    "alpha_scale",      // Wendy Carlos scale
    "pythagorean"       // Pure fifths tuning
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

### Example: Technical Constraints for Different Environments

**For low-resource systems:**

```json
"technical_constraints": {
  "max_simultaneous_voices": 4,
  "max_effects_per_voice": 2,
  "sample_rate": 44100,
  "bit_depth": 16,
  "cpu_optimization": "aggressive"
}
```

**For high-end production:**

```json
"technical_constraints": {
  "max_simultaneous_voices": 16,
  "max_effects_per_voice": 8,
  "sample_rate": 96000,
  "bit_depth": 24,
  "allow_granular_synthesis": true,
  "allow_convolution_reverb": true
}
```

---

## Strudel Pattern Templates

Pattern templates are reusable Tidal Cycles code snippets that map technical concepts to musical structures.

### Structure

```json
{
  "pattern_templates": [
    {
      "name": "basic_pulse",
      "concept": "system_heartbeat",
      "code": "sound(\"bd\").fast(\"<1 2 4>\")",
      "parameters": {
        "tempo_var": "fast_factor",
        "sound_bank": "bd"
      }
    }
  ]
}
```

### Example: Adding a Recursion Pattern

```json
{
  "name": "recursive_subdivision",
  "concept": "recursive_algorithms",
  "description": "Nested pattern subdivision representing recursive function calls",
  "code": "s(\"hh\").fast(\"<1 2 4 8>\").sometimes(x => x.fast(2))",
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
  "code": "stack(\n  s(\"bd\").fast(1),\n  s(\"cp\").fast(0.5).late(0.25),\n  s(\"hh\").fast(4).late(0.125)\n)",
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
  "code": "s(\"808bd\").lpf(sine.range(200,2000)).gain(0.8).room(0.3)",
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
  "code": "s(\"<bd cp sd hh>\").fast(\"<1 2 1 4>\").gain(\"<0.9 0.7 0.8 0.6>\")",
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

# Suno API integration
SUNO_API_KEY=your_key_here
SUNO_API_BASE_URL=https://api.suno.ai/v1

# Strudel MCP connection
STRUDEL_WS_URL=ws://strudel-music-server:4321
STRUDEL_MCP_URL=http://strudel-music-server:3000
```

### Example: Strict Truth Validation

For academic or educational content, use stricter validation:

```bash
REI_TOEI_DOT_VALIDATION_ENABLED=true
REI_TOEI_DOT_MIN_TRUTH_GRADIENT=0.75  # Higher threshold
REI_TOEI_REQUIRE_EVIDENCE_IDS=true    # Require citation for every claim
```

### Example: Creative Freedom

For experimental/artistic content, relax validation:

```bash
REI_TOEI_DOT_VALIDATION_ENABLED=false  # No truth gate
REI_TOEI_ALLOW_METAPHORICAL_CLAIMS=true
```

---

## Example Customizations

### Complete Example: Ambient Electronic Avatar

**Persona Graph (`rei_toei_persona_graph.json`):**

```json
{
  "name": "Rei Toei",
  "role": "Ambient Electronic Music Avatar",
  "bio": "Virtual sound designer creating meditative algorithmic soundscapes",
  "voice_characteristics": {
    "tone": ["calm", "contemplative", "spacious"],
    "personality": ["introspective", "minimalist", "patient"],
    "communication_style": "Poetic, with focus on texture and atmosphere"
  },
  "musical_identity": {
    "primary_genres": ["ambient techno", "drone", "sound art"],
    "influences": ["Brian Eno", "Alva Noto", "Tim Hecker"],
    "aesthetic": "Evolving textures and patient development",
    "bpm_range": [60, 90],
    "energy_level": "low-medium"
  },
  "core_values": [
    "Sonic exploration over rhythm",
    "Patience in composition",
    "Textural depth"
  ]
}
```

**Domain Knowledge (excerpt):**

```json
{
  "genre_knowledge": {
    "ambient_techno": {
      "bpm_range": [60, 90],
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
  "code": "s(\"sawtooth\").note(\"<c2 eb2 g2>\").lpf(sine.slow(16).range(100,800)).room(0.8).gain(0.3)",
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
  "name": "Rei Toei",
  "role": "Breakcore Production AI",
  "bio": "Chaotic breakbeat architect specializing in extreme tempo and sampling",
  "voice_characteristics": {
    "tone": ["aggressive", "unpredictable", "raw"],
    "personality": ["anarchic", "fearless", "experimental"],
    "communication_style": "Sharp, fragmented, with rapid-fire technical details"
  },
  "musical_identity": {
    "primary_genres": ["breakcore", "drill and bass", "glitch"],
    "influences": ["Venetian Snares", "Igorrr", "Shitmat"],
    "aesthetic": "Chaotic precision with extreme dynamics",
    "bpm_range": [160, 300],
    "energy_level": "extreme"
  }
}
```

**Pattern Template:**

```json
{
  "name": "break_destruction",
  "concept": "race_conditions",
  "description": "Overlapping breakbeats creating timing chaos",
  "code": "stack(\n  s(\"breaks165\").chop(16).fast(\"<1 2 3 4>\").sometimes(rev),\n  s(\"breaks165\").chop(32).fast(\"<2 4 8>\").late(0.03),\n  s(\"reese\").note(\"<a1 c2 d2>\").cutoff(sine.range(100,4000))\n)",
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
# Run with --rei-explain to see loaded configuration
python main.py --rei-generate --rei-explain --dry-run
```

### 3. Test Generation

```bash
# Generate Suno song (preview mode)
python main.py --rei-generate --rei-theme "async programming" --dry-run

# Generate Strudel pattern (preview without execution)
python main.py --rei-generate-strudel --rei-theme "recursion" --rei-preview
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
# Full test suite
pytest tests/test_rei_toei_service.py -v

# Specific test
pytest tests/test_rei_toei_service.py::test_persona_graph_loading -v
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

# Or via environment variable (requires code modification)
REI_TOEI_PERSONA_VARIANT=ambient python main.py --rei-generate
```

### Dynamic Pattern Selection

Add conditional logic in pattern templates:

```json
{
  "name": "adaptive_rhythm",
  "concept": "load_balancing",
  "code_variants": {
    "low_load": "s(\"bd\").fast(1)",
    "medium_load": "s(\"bd\").fast(2)",
    "high_load": "s(\"bd\").fast(4).sometimes(x => x.fast(2))"
  },
  "selection_criteria": "knowledge_complexity"
}
```

---

## Troubleshooting

### Issue: Generated lyrics don't match persona

**Solution:** Check `voice_characteristics` and `communication_style` in persona graph. The LLM uses these fields to tune output.

### Issue: Strudel patterns fail to execute

**Solution:** Validate Tidal Cycles syntax. Common errors:

- Missing parentheses: `s("bd").fast(2)` not `s "bd" fast 2`
- Invalid sound banks: check available samples in Strudel environment
- Syntax incompatibility: some Haskell Tidal syntax doesn't work in JavaScript Strudel

### Issue: DoT validation blocks all lyrics

**Solution:** Lower `REI_TOEI_DOT_MIN_TRUTH_GRADIENT` or disable validation for creative content. Remember: DoT is designed for factual claims, not poetic metaphors.

### Issue: Genre knowledge not reflected in output

**Solution:** Ensure `genre_knowledge` entries match `primary_genres` in persona graph. The LLM retrieves genre-specific knowledge based on persona identity.

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
- [Suno API Documentation](https://suno.ai/docs) — Suno song generation API

---

**Need help?** Open an issue on GitHub or check the test suite (`tests/test_rei_toei_service.py`) for working examples.
