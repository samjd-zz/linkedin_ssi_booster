# Rei Toei Customization Guide

This guide shows you how to customize Rei Toei — the AI music avatar — to match your creative vision, musical style, and technical knowledge domain.

---

## Table of Contents

- [Overview](#overview)
- [Persona Graph Customization](#persona-graph-customization)
- [Domain Knowledge Customization](#domain-knowledge-customization)
- [Stage Cue Profiles and Genre Catalog](#stage-cue-profiles-and-genre-catalog)
- [Strudel Pattern Templates](#strudel-pattern-templates)
- [Configuration Options](#configuration-options)
- [Example Customizations](rei-toei-customization-workflows.md#example-customizations)
- [Testing Your Changes](rei-toei-customization-workflows.md#testing-your-changes)

---

## Overview

Rei Toei's behavior is controlled by three main JSON configuration files:

| File                             | Purpose                                                     | Location       |
| -------------------------------- | ----------------------------------------------------------- | -------------- |
| `rei_toei_persona_graph.json`    | Rei's identity, voice, musical expertise                    | `data/avatar/` |
| `rei_toei_domain_knowledge.json` | Music theory, genre production techniques, prompt templates, Suno best practices | `data/avatar/` |
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
    },
    "lyric_density_to_bpm": {
      "base_bpm": 145,
      "base_syllables": 9,
      "bpm_per_syllable": 6.25,
      "max_bpm": 175
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
  "production_notes": {},
  "suno_best_practices": {
    "target_model": "V6_MINI",
    "source_note": "Official v6-family facts are separated from proxy limits and empirical prompt conventions.",
    "sources": {"suno_v6_models_faq": "https://help.suno.com/en/articles/13924481"},
    "prompt_rules": ["Keep parentheses for the intro vocalization and rare non-word vocalizations such as (Oh oh oh); never add repeated-word echoes in parentheses after lyric lines."]
  }
}
```

### Suno Best Practices

`suno_best_practices` is scoped to the `V6_MINI` model selected by default through the SunoAPI.org proxy. Suno's official v6 FAQ explicitly includes v6-mini in the model family and says all three v6 models understand musical structure and other prompt concepts; Suno also documents the 8-minute generation limit across v6, v6-wild, and v6-mini. The API proxy documents the `V6_MINI` model identifier and its style, lyric, negative-tag, and title limits. Proxy limits are not official Suno help-center claims.

Bracket syntax, whether stage directions are sung, parentheses for vocalizations, and Japanese lyric behavior are not documented by Suno specifically for v6-mini. Those rules are clearly marked as community/empirical conventions, not guaranteed model behavior. Only `prompt_rules` reaches the lyric-writing model. Up to 8 rules are added to the structured prompt under "Suno v6-mini lyric-formatting practices"; rules mentioning Japanese, Romaji, kana, or kanji are sent only when that model writes Japanese or bilingual lyrics. English-first translate mode skips them. The rest of the section is reference material. Edit `prompt_rules` to change the instructions.

The app defaults to `V6_MINI`. An explicit `SUNO_MODEL` environment variable overrides that default, so set it to `V6_MINI` if you want to make the selection explicit.

### Stage Cue Profiles and Genre Catalog

Required sections, bracketed labels, instrumental directions, and the intro primer now live in `lyrical_structure.stage_cues` in `data/avatar/rei_toei_domain_knowledge.json`, rather than a hardcoded mandatory-section list.

Select `active_profile` explicitly: `cyberpop` preserves the previous defaults; `cyberpunk`, `acoustic`, `rock`, `psytrance`, `progressive_psytrance`, `jungle_dnb`, `psychedelic_rock`, `progressive_rock`, `hip_hop`, and `ambient` offer different arrangements. Song genre tags do not automatically select a profile. CLI runs reload the file; use `/reload` in the console.

See [Stage Cue Configuration and Genre Catalog](rei-toei-stage-cues.md) for the complete schema, required-versus-optional behavior, intro controls, and the exhaustive catalog of potential stage cues by genre. The catalog covers 93 genres across nine families (cyber/synth/industrial electronic, club and bass music, pop/R&B/soul, rock and metal, hip-hop, acoustic/folk/roots, jazz and classical, global/regional, and ambient/experimental), plus a cross-genre palette of section headings, dynamics, rhythm, voice, texture, and ending cues. Profile settings reach the lyric prompt, draft gate, retry feedback, final formatting, and saved metadata. Every language mode allows five lyric attempts; unusable drafts then fail without canned song or section replacements. Existing Suno best-practice rules remain additional guidance; they do not override the structural policy.

### Example: Adding a New Genre

Optional `psytrance`, `progressive_psytrance`, and `jungle_dnb` entries provide genre-specific production guidance and Suno tags; their cue layouts require explicitly selecting the matching `active_profile`.

`progressive_psytrance` favors 128-138 BPM, rolling offbeat bass and gradual layered builds, unlike the faster guitar-led psytrance profile. `psychedelic_rock` adds fuzz guitar and spacious arrangements; `progressive_rock` adds evolving motifs, meter changes and long-form sections. Each has a separate template and optional stage profile.

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

### Lyric-Fitted Tempo

The concept BPM is chosen before any lyric exists, so Suno assembly treats it as a starting point. After the lyrics are finished, Rei measures the median syllables per sung line (Japanese mora count at `japanese_mora_weight`, default 0.6; labels, Romaji cues, and parenthesized vocalizations are skipped). The tempo floor is `base_bpm` at `base_syllables`, plus `bpm_per_syllable` for each extra syllable, capped at `max_bpm`. The BPM is only ever raised. With the defaults, 13-syllable lines lift a 145 BPM concept to 170, while short hook lines keep it.

Line density also adds a vocal-delivery style tag right after the BPM tag: `rapid-fire syllabic vocaloid delivery` at `dense_syllables` (12) or more, `spacious punchy hook phrasing` at `sparse_syllables` (8) or fewer. Tempos of 165 BPM and up use `breakneck hyperspeed vocaloid energy`. The CLI, console, and saved metadata show the fitted BPM; metadata also keeps `concept_bpm`, `median_line_syllables`, and `vocal_delivery`.

Runtime constraints are primarily configured via environment variables (for example, `REI_TOEI_DEFAULT_BPM`, `REI_TOEI_DEFAULT_GENRE`, `REI_TOEI_STRUDEL_DEFAULT_BARS`) rather than a `technical_constraints` object in `rei_toei_domain_knowledge.json`.

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

See [environment settings](rei-toei-customization-workflows.md#configuration-options).

### Bilingual Lyric Mix

See [Bilingual Lyric Mix](rei-toei-customization-workflows.md#bilingual-lyric-mix).

### Verified Intel WSL2 Laptop Workflow

See the [verified laptop workflow](rei-toei-customization-workflows.md#verified-intel-wsl2-laptop-workflow).

## Example Customizations

See [ambient and breakcore examples](rei-toei-customization-workflows.md#example-customizations).

## Testing Your Changes

See [validation and preview commands](rei-toei-customization-workflows.md#testing-your-changes).

## Advanced Customization

See [multiple variants and pattern selection](rei-toei-customization-workflows.md#advanced-customization).

## Troubleshooting

See [troubleshooting](rei-toei-customization-workflows.md#troubleshooting) and the [stage-policy checks](rei-toei-stage-cues.md#validation-and-troubleshooting).

## Best Practices

See [customization best practices](rei-toei-customization-workflows.md#best-practices).

## Further Reading

See [further reading](rei-toei-customization-workflows.md#further-reading).
