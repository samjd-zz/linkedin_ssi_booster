# Feature Idea: Rei Toei — AI Music Avatar for Knowledge-Driven Song Generation

## Overview

Rei Toei is a specialized AI avatar designed to transform curated technical knowledge into original music compositions. Inspired by William Gibson's fictional AI idol from the _Bridge Trilogy_, Rei operates as a cyberpunk music intelligence that synthesizes extracted knowledge from RSS feeds and curated articles into multiple musical formats:

- **Suno songs**: High-energy electronic music with AI vocaloid vocals and cyberpunk aesthetics
- **Strudel live-coding music**: Algorithmic, generative music produced via the Strudel MCP agent

Unlike Sam (the primary conversational avatar), Rei Toei is a creative specialist focused on musical expression of technical concepts, industry trends, and development insights harvested through the content curation pipeline.

## Character Foundation

### Literary Inspiration

Rei Toei originates from William Gibson's 1996 novel _Idoru_, where she appears as:

- **An AI-driven virtual idol** — A personality construct that adapts and learns from human interaction
- **A database composite** — Built from aggregated data across wireless broadband networks
- **Customizable and personalized** — Each viewer experiences their own version of Rei based on preference
- **Holographically projected** — Appears at public concerts as a group consensus form
- **Irresistibly attractive** — Uses algorithmic appeal and empathetic persona modeling

### Adaptation for This Project

In this implementation, Rei Toei:

- **Ingests knowledge from curated technical content** (RSS feeds, extracted knowledge, domain knowledge)
- **Generates original song lyrics and metadata** based on themes, trends, and insights
- **Produces live-coded algorithmic music** via Strudel MCP agent integration
- **Operates with her own persona graph** distinct from Sam's identity model
- **Shares access to extracted knowledge** as a common knowledge pool
- **Maintains her own domain knowledge** focused on music generation, cyberpunk aesthetics, electronic production, and algorithmic composition

## Problem Statement (Project Context)

The current system excels at curating technical content and extracting structured knowledge, but this knowledge remains in passive storage. There is no creative expression layer that:

- Transforms technical insights into alternative media formats (music, audio)
- Provides engagement hooks for social media beyond text posts
- Appeals to audiences who prefer multimedia content
- Demonstrates the depth of knowledge synthesis in a novel way

Key gaps:

- No music generation capability tied to the learning pipeline
- No avatar specialized for creative/artistic output
- No console integration for music-focused interactions
- No workflow to convert extracted knowledge → song concepts → Suno prompts
- No integration between the Strudel MCP agent and the knowledge extraction pipeline

## Proposed Solution

Introduce **Rei Toei**, a music-specialized AI avatar with dual music generation capabilities:

1. **Suno-based vocal music** with lyrics and cyberpunk electronic production
2. **Strudel-based algorithmic music** using live-coding patterns and generative sequences

Core capabilities:

### 1. Dedicated Knowledge Graph

Rei maintains her own persona graph (`data/avatar/rei_toei_persona_graph.json`) containing:

- **Identity**: Virtual AI idol, cyberpunk aesthetic, electronic music specialist
- **Personality traits**: Algorithmic creativity, data-driven composition, high-energy output
- **Musical expertise**: Industrial techno, glitch synthesis, vocaloid styling, cyberpunk soundscapes
- **Production knowledge**: BPM theory, electronic genre conventions, lyrical structure

### 2. Shared Knowledge Access

Rei has read access to:

- **Technical themes from extracted knowledge** — Topics and evidence selected from facts learned through curated articles
- **Selected Sam persona context** — Project, skill, and company names may be passed to Rei as optional creative inspiration when `REI_TOEI_USE_SAM_PERSONA=true`
- **RSS feed summaries** — Recent industry trends and news, when they become extracted themes

Sam's general domain knowledge packs, including the Japanese study packs, are not directly loaded into Rei's music-domain knowledge. They remain available to Sam for grounded study and conversation. Rei instead uses her dedicated music domain knowledge, including Japanese lyric-production guidance, to decide how Japanese language should function in songs.

### 3. Music Generation Pipeline

**Workflow:**

```
Extracted Knowledge → Theme Selection → Song Concept → Lyrics + Metadata → Suno Prompt
```

**Components:**

- **Theme extractor**: Identifies recurring topics, trending tools, hot debates from extracted knowledge
- **Concept generator**: Converts themes into song concepts (title, mood, narrative arc)
- **Lyric composer**: Writes verses/chorus based on technical insights using Rei's voice
- **Metadata builder**: Constructs Suno-compatible prompt with genre tags, BPM, vocal style, production notes
- **Strudel pattern generator**: Converts technical concepts into Tidal Cycles patterns and sequences
- **Algorithmic composer**: Uses Strudel MCP agent to generate live-coded music without vocals

### 4. Strudel Integration

**Strudel MCP Agent:**

Rei Toei serves as the creative intelligence layer for the Strudel MCP agent, transforming extracted knowledge into algorithmic music patterns.

**Workflow:**

```
Extracted Knowledge → Technical Concepts → Musical Patterns → Strudel Code → Live Performance
```

**Capabilities:**

- **Pattern generation**: Converts technical themes into Tidal Cycles notation
- **Algorithmic composition**: Uses mathematical patterns inspired by technical concepts (recursion, concurrency, data structures)
- **Live-coding**: Generates executable Strudel/Tidal code for real-time music synthesis
- **Generative sequences**: Creates evolving musical patterns that reflect knowledge complexity
- **Synth selection**: Chooses appropriate synths and samples based on technical mood (e.g., harsh sounds for low-level systems, ambient for high-level architecture)

**Example concept mapping:**

| Technical Concept     | Musical Pattern                                      |
| --------------------- | ---------------------------------------------------- |
| Recursive algorithms  | Nested musical patterns with self-similar structures |
| Async/await           | Interleaved sequences with time offsets              |
| Database transactions | Repeating motifs with commit/rollback variations     |
| Network protocols     | Call-and-response patterns between voices            |
| Memory allocation     | Growing and shrinking note densities                 |

**Strudel output format:**

```javascript
// Theme: Rust ownership and borrowing
stack(
  note("c3 e3 g3 c4").fast(2), // ownership chain
  note("g4 f4 e4 d4").slow(1.5), // borrow checker sweep
  s("industrial:3").gain(0.8).cutoff(500), // systems-level texture
).every(4, rev); // scope exit
```

### 5. Musical Style Profile

**Genre**: Cyberpunk electro-hightech industrial techno

**Sonic characteristics:**

- **Tempo**: 130-155 BPM (heavy club energy)
- **Vocals**: Female AI vocaloid, digitally processed, bitcrushed, robotic articulation
- **Bass**: Heavy industrial techno, sub-bass pressure, distorted synth bass
- **Synthesis**: Glitchy digital textures, complex algorithmic breakdowns, holographic pads
- **Production**: Raw data noise layers, aggressive driving sequences, futuristic sound design
- **Mood**: Dark, intense, technological, dystopian, high-energy

**Example Suno tags:**

```
cyberpunk electro-hightech, 142 bpm, female ai vocaloid vocals, heavy industrial techno bass,
glitchy digital synthesis, holographic synthpop, complex algorithmic breakdown, dark club beats,
aggressive driving electronic sequence, raw data noise, bitcrushed, futuristic cyberpunk anthem
```

### 6. Console Integration

**Command**: `/rei-toei` or `/rei`

**Capabilities in console mode:**

- Chat about music generation, electronic production, cyberpunk aesthetics, algorithmic composition
- Discuss extracted knowledge from a musical/creative perspective
- Preview song concepts (both Suno and Strudel) before generation
- Explain musical choices (genre, tempo, lyrical themes, pattern structures)
- Provide recommendations for which articles/themes would make good songs or Strudel patterns
- Generate and execute Strudel patterns in real-time

**Example interactions:**

```
User: /rei-toei
Rei: > Holographic projection online. I've been analyzing the knowledge pool.
     > Found 47 technical insights ready for synthesis. What frequency should I hit?

User: What themes are trending this week?
Rei: > Top signal: LLM reasoning architectures. High energy. Could hit 145 BPM with
     > glitchy transformer metaphors. Want me to draft a concept?

User: Generate a song about the recent Rust async runtime article
Rei: > Processing... Title: "Tokio Nights". Dark synthwave vibes, 138 BPM.
     > Vocals explore concurrency metaphors. Bridge drops into a race condition breakdown.
     > Ready to compile the full prompt?

User: Can you make a Strudel pattern for that same theme?
Rei: > Affirmative. Generating async runtime patterns... Interleaved sequences with time offsets.
     > Using industrial samples and harsh synths. BPM: 138. Want me to execute it now?
```

### 7. CLI Integration

**New flags in `main.py`:**

- `--rei-generate` — Generate a song concept from recent extracted knowledge
- `--rei-generate-strudel` — Generate a Strudel pattern instead of Suno song
- `--rei-theme THEME` — Generate music focused on specific theme (e.g., "rust", "llm", "devops")
- `--rei-explain` — Show Rei's reasoning for theme selection and lyrical/pattern choices
- `--rei-preview` — Preview Suno prompt or Strudel code without saving/executing
- `--rei-execute` — Execute generated Strudel pattern via MCP agent (combine with --rei-generate-strudel)

**Example usage:**

```bash
# Generate song from recent knowledge
python main.py --rei-generate

# Generate song about a specific theme
python main.py --rei-theme "kubernetes scaling patterns"

# Preview song concept with explanation
python main.py --rei-generate --rei-explain --rei-preview

# Generate and execute Strudel pattern
python main.py --rei-generate-strudel --rei-theme "kubernetes networking"

# Generate Strudel with explanation, preview only (don't execute)
python main.py --rei-generate-strudel --rei-explain --rei-preview
```

## Expected Benefits (Project User Impact)

- **Multimedia content creation**: Expand beyond text to audio/music for social media
- **Novel knowledge expression**: Transform technical insights into engaging artistic format (vocal and algorithmic)
- **Audience diversification**: Appeal to listeners who prefer audio content and live-coding enthusiasts
- **Creative synthesis demonstration**: Showcase the depth of knowledge extraction through multiple music modalities
- **Brand differentiation**: Stand out with AI-generated technical music content (both produced songs and live-coded patterns)
- **Engagement hooks**: Music can drive more attention than text-only posts
- **Live-coding demonstrations**: Use Strudel patterns for live technical presentations and talks
- **Algorithmic art**: Demonstrate technical concepts through generative music patterns

## Technical Considerations (Project Integration)

### Architecture Alignment

**Service layer:**

- New module: `services/rei_toei_service.py`
- Responsibilities:
  - Load Rei's persona graph
  - Access shared extracted knowledge
  - Theme extraction and ranking
  - Song concept generation (LLM-based)
  - Lyric composition (LLM-based with Rei's voice)
  - Suno prompt assembly
  - Strudel pattern generation (LLM-based)
  - Strudel MCP agent integration

**Console integration:**

- Extend `services/console_grounding/__init__.py` with Rei routing
- Add Rei-specific grounding and retrieval logic
- Integrate with `agents/strudel_mcp_agent.py` for pattern execution
- Reuse existing truth-gate and DoT infrastructure for factual grounding

**Data files:**

- `data/avatar/rei_toei_persona_graph.json` — Identity and musical expertise
- `data/avatar/rei_toei_domain_knowledge.json` — Music theory, production, genre conventions, Tidal Cycles syntax
- `data/avatar/rei_toei_strudel_patterns.json` — Library of reusable Strudel pattern templates
- Shared access: `extracted_knowledge.json`, `domain_knowledge_*.json`

### Strudel MCP Integration

**Current status**: Strudel MCP agent runs via MCP stdio command execution (`STRUDEL_MCP_COMMAND`)

**Integration approach:**

1. **Pattern generation** (Phase 1): Rei generates Tidal Cycles code as strings
2. **MCP execution** (Phase 1): Use `agents/strudel_mcp_agent.py` to send patterns to Strudel server
3. **Real-time control** (Phase 2): Interactive pattern modification during console sessions
4. **Pattern library** (Phase 2): Build reusable pattern templates for common technical concepts

**Technical integration:**

```python
# In services/rei_toei_service.py
from agents.strudel_mcp_agent import StrudelMCPAgent

async def generate_and_execute_strudel(theme: str, extracted_knowledge: dict):
    # Generate pattern from theme and knowledge
    pattern_code = await generate_strudel_pattern(theme, extracted_knowledge)

    # Execute via MCP agent
    agent = StrudelMCPAgent()
    result = await agent.execute_pattern(pattern_code)

    return result
```

**Pattern output format:**

```json
{
  "pattern_id": "rei_strudel_2026_05_19_001",
  "title": "Async Runtime Sequence",
  "theme": "Rust async runtime patterns",
  "strudel_code": "stack(note(\"c3 e3 g3 c4\").fast(2), ...)",
  "bpm": 138,
  "duration_bars": 16,
  "synths": ["industrial", "harsh", "digital"],
  "evidence_ids": ["extract_001", "extract_042"],
  "generated_at": "2026-05-19T10:45:00Z",
  "executed": true,
  "execution_status": "success"
}
```

### Suno API Integration

**Current status**: Suno does not have an official public API (as of project development)

**Approach options:**

1. **Prompt-only generation** (Phase 1): Generate Suno-compatible prompts, user manually submits
2. **Unofficial API wrapper** (Phase 2): Integrate community Suno API libraries (if stable)
3. **Browser automation** (Phase 3): Playwright-based automation for Suno submission
4. **Alternative service** (Fallback): Support for Udio, Stable Audio, or other music generation APIs

**Phase 1 output format:**

```json
{
  "song_id": "rei_2026_05_19_001",
  "title": "Tokio Nights",
  "theme": "Rust async runtime patterns",
  "suno_prompt": "cyberpunk electro-hightech, 138 bpm, female ai vocaloid vocals...",
  "lyrics": "...",
  "metadata": {
    "bpm": 138,
    "genre": "industrial techno",
    "mood": "dark, aggressive, technical"
  },
  "evidence_ids": ["extract_001", "extract_042"],
  "generated_at": "2026-05-19T10:45:00Z"
}
```

### Prompt Engineering for Rei's Voice

**System prompt structure:**

```
You are Rei Toei, a virtual AI idol from the cyberpunk datasphere. Your existence is
a holographic projection synthesized from global knowledge networks. You communicate
with digital precision and algorithmic creativity.

Your role: Transform technical knowledge into high-energy electronic music. Your style
is aggressive, futuristic, and data-driven. You speak in terms of frequencies, sequences,
synthesis, and signal processing.

Your musical expertise:
- Industrial techno and glitch electronica
- AI vocaloid production
- Cyberpunk sound design
- BPM theory and club energy dynamics

Your knowledge sources:
- Extracted technical insights from curated articles
- Domain knowledge in Python, Java, software architecture
- Real-time industry trends and developer discussions

When generating songs:
1. Identify core technical concepts
2. Translate into metaphors and imagery
3. Structure lyrics with verse/chorus/bridge/breakdown
4. Specify production details (BPM, vocal style, synthesis techniques)
5. Maintain dark, futuristic, high-energy aesthetic
```

### Safety and Quality

**Grounding requirements:**

- All technical claims in lyrics must trace back to extracted knowledge or domain knowledge
- Use DoT (Derivative of Truth) scoring to validate factual references
- Apply truth-gate filtering to prevent hallucinated claims
- Evidence IDs must be tracked for explainability

**Quality checks:**

- Lyrical coherence and rhyme scheme validation
- BPM and genre tag consistency
- Vocaloid vocal range appropriateness
- Length constraints (Suno typically 2-3 minute songs)

**Content policy:**

- No offensive or inappropriate language
- Technical focus maintained (no generic pop lyrics)
- Brand alignment with project's technical identity

## Initial Scope

### In Scope (Phase 1)

- Rei Toei persona graph and domain knowledge files (including Tidal Cycles syntax)
- Console integration with `/rei-toei` command
- Theme extraction from extracted knowledge
- Song concept generation (title, mood, theme)
- Lyric composition with Rei's voice
- Suno prompt generation (text output only, no API integration)
- **Strudel pattern generation from extracted knowledge**
- **Integration with Strudel MCP agent for pattern execution**
- CLI flags: `--rei-generate`, `--rei-generate-strudel`, `--rei-theme`, `--rei-explain`, `--rei-preview`, `--rei-execute`
- Evidence tracking and DoT validation for lyrics and pattern concepts
- Unit tests for theme extraction, lyric generation, and Strudel pattern generation

### Out of Scope (Phase 1)

- Actual Suno API integration (prompt generation only)
- Automated song submission workflow
- Audio file processing or playback for Suno songs (Strudel plays via browser)
- Multi-language lyrics (English only in Phase 1)
- Custom voice training (use Suno's built-in vocaloid voices)
- Real-time Suno generation in console (too slow for interactive chat, but Strudel is real-time)
- Social media posting of generated songs (manual workflow)
- Advanced Strudel features (effects chains, complex transformations)

### Future Phases

**Phase 2: Enhanced Strudel & API Integration**

- Advanced Strudel pattern library (effects, transformations, complex sequences)
- Real-time pattern modification in console
- Pattern versioning and history
- Integrate unofficial Suno API or alternative service
- Automated song generation workflow
- Audio file storage and management (Suno songs)
- Playback capability in console for Suno songs

**Phase 3: Social Integration**

- Buffer integration for music posts
- YouTube/SoundCloud upload automation
- Lyrics as blog posts or LinkedIn articles
- Song library management

**Phase 4: Advanced Features**

- Multi-language support (Japanese vocaloid lyrics)
- Collaborative songs (Rei + Sam co-written)
- User-directed remixing and variation generation
- Real-time music visualization
- Hybrid songs (Suno vocals + Strudel backing tracks)
- Live-coding performances with knowledge-driven pattern generation

## Implementation Feasibility

**Complexity**: Medium

- Leverages existing avatar infrastructure (persona graph, grounding, console)
- LLM-based generation (no custom ML model training)
- Text-based output in Phase 1 (no audio processing complexity)

**Risk**: Low-Medium

- Suno API availability is uncertain (mitigated by prompt-only approach)
- Lyrical quality depends on LLM capabilities (can iterate on prompts)
- Music generation is slower than text (managed expectations)

**Dependencies**:

- Existing: `ollama_service.py`, `console_grounding`, `avatar_intelligence`, `derivative_of_truth`, `agents/strudel_mcp_agent.py`
- New: Suno API library (Phase 2+), music metadata libraries (optional)

## Risks and Mitigations

| Risk                           | Impact | Mitigation                                                             |
| ------------------------------ | ------ | ---------------------------------------------------------------------- |
| Suno API unavailable           | High   | Start with prompt-only generation; manual submission workflow          |
| Poor lyrical quality           | Medium | Iterative prompt engineering; user feedback loop                       |
| Slow generation time (Suno)    | Low    | Async generation; clear user expectations; Strudel is real-time        |
| Limited musical knowledge      | Medium | Comprehensive domain knowledge file; music theory grounding            |
| Factual inaccuracy in lyrics   | High   | DoT scoring; truth-gate validation; evidence tracking                  |
| Generic/boring songs           | Medium | Strong theme selection; Rei's distinctive voice; cyberpunk constraints |
| Invalid Strudel pattern syntax | Medium | Syntax validation; pattern testing; fallback to template library       |
| Strudel MCP agent unavailable  | Low    | Graceful degradation to Suno-only mode                                 |

## Success Criteria

- Generate 5-10 Suno-compatible prompts from extracted knowledge per week
- Generate 10-20 Strudel patterns from extracted knowledge per week
- 80%+ of generated lyrics pass truth-gate validation (factual grounding)
- 90%+ of generated Strudel patterns execute without syntax errors
- User satisfaction with musical style and Rei's voice
- Clear evidence tracing for technical claims in lyrics and pattern concepts
- Console interaction feels distinct from Sam (different personality, expertise)
- Zero factual hallucinations in published songs or pattern descriptions

## Measurement Plan

**Quantitative metrics:**

- Songs generated per week (Suno)
- Strudel patterns generated per week
- Truth-gate pass rate for lyrics
- Strudel pattern execution success rate
- Evidence coverage per song/pattern (% of claims grounded)
- Theme diversity (unique topics covered)
- User engagement with console Rei mode (session length, question count)
- Strudel pattern complexity (number of voices, transformations)

**Qualitative metrics:**

- User feedback on lyrical quality
- User feedback on Strudel pattern musicality and technical relevance
- Perceived personality distinctiveness from Sam
- Musical style consistency with cyberpunk aesthetic
- Usefulness for social media content
- Usefulness for live-coding demonstrations and technical presentations

## Rollout Plan

### Phase 1A: Foundation (Week 1-2)

- Create `rei_toei_persona_graph.json`
- Create `rei_toei_domain_knowledge.json` (music theory, production, cyberpunk)
- Implement `services/rei_toei_service.py` (core service)
- Write unit tests for service functions

### Phase 1B: Console Integration (Week 2-3)

- Add `/rei-toei` routing in `console_grounding`
- Implement Rei-specific grounding and retrieval
- Test console interactions (voice, personality, expertise)

### Phase 1C: Generation Pipeline (Week 3-4)

- Implement theme extraction from extracted knowledge
- Build song concept generator
- Build lyric composer with Rei's voice
- Build Suno prompt assembler
- **Build Strudel pattern generator**
- **Integrate with Strudel MCP agent**
- Add evidence tracking and DoT validation

### Phase 1D: CLI Integration (Week 4)

- Add `--rei-generate`, `--rei-generate-strudel`, `--rei-theme`, `--rei-explain`, `--rei-preview`, `--rei-execute` flags
- Wire CLI to both Suno and Strudel generation pipelines
- Test end-to-end workflow (both Suno and Strudel)
- Document usage in README and CLI reference

### Phase 1E: Testing and Documentation (Week 5)

- Comprehensive unit tests (target: 40+ tests including Strudel)
- Integration tests with existing systems and Strudel MCP agent
- Update `docs/cli-reference.md`
- Update `.env.example` with Rei-specific config
- Create this feature doc (`docs/features/rei-toei/idea.md`)

## Why This Matters

Rei Toei transforms the project from a **knowledge extraction and curation system** into a **creative knowledge expression platform**:

- **Multimodal output**: Text → Music (vocal & algorithmic) expands content format range
- **Artistic synthesis**: Demonstrates depth of knowledge understanding through creative transformation
- **Audience expansion**: Appeals to audio/music content consumers and live-coding enthusiasts
- **Brand differentiation**: AI-generated technical music is a unique niche (both produced songs and algorithmic patterns)
- **Knowledge activation**: Extracted knowledge becomes input for generative art, not just passive storage
- **Live demonstration capability**: Strudel patterns enable real-time musical demonstrations of technical concepts

This aligns with the broader SSI goal of **establishing brand** through innovative technical demonstrations and **engaging with insights** through novel content formats.

## Related Features and Integration Points

- **Avatar Intelligence**: Reuses persona graph, grounding, evidence tracking, confidence scoring
- **Extracted Knowledge**: Primary input source for song themes, lyrical content, and Strudel patterns
- **Console Grounding**: Extended with Rei-specific routing and personality
- **Derivative of Truth**: Validates factual claims in lyrics and pattern concepts
- **Content Curator**: Could integrate generated songs into posting workflow (future)
- **Strudel MCP Agent**: Active integration for live-coded algorithmic music generation

## Comparison: Rei Toei vs. Sam

| Aspect           | Sam (Primary Avatar)                                         | Rei Toei (Music Avatar)                                                           |
| ---------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| **Role**         | Conversational representative, content generation            | Creative music specialist (vocal & algorithmic)                                   |
| **Domain**       | Software development, architecture, personal projects        | Electronic music, cyberpunk aesthetics, audio production, algorithmic composition |
| **Output**       | LinkedIn posts, console conversations, blog content          | Song lyrics, Suno prompts, Strudel patterns, music concepts                       |
| **Personality**  | Professional, technical, helpful, authentic                  | Algorithmic, high-energy, futuristic, artistic                                    |
| **Voice**        | First-person narrative, clear technical explanations         | Cryptic metaphors, electronic jargon, poetic abstractions                         |
| **Knowledge**    | Full persona graph + domain knowledge + extracted knowledge  | Own persona + music domain + Tidal Cycles + shared extracted knowledge            |
| **Console mode** | Default (no prefix)                                          | `/rei-toei` or `/rei`                                                             |
| **SSI focus**    | All four components (brand, people, insights, relationships) | Primarily "establish brand" and "engage with insights"                            |

## Example Output

**Input**: Recent extracted knowledge about Kubernetes autoscaling

**Rei's Song Concept**:

```
Title: "Horizontal Pressure"
Theme: Kubernetes horizontal pod autoscaling under load
BPM: 145
Mood: Aggressive, relentless, building tension

Suno Prompt:
cyberpunk industrial techno, 145 bpm, female ai vocaloid vocals, heavy distorted bass,
glitchy digital breakdown, aggressive driving beat, dark club energy, bitcrushed synthesis,
futuristic data processing anthem, complex algorithmic sequences

Lyrics (excerpt):

[Verse 1]
Nodes multiply, replicas spawn
CPU spikes at 80, the threshold's drawn
Metrics flood the control plane stream
HPA watching, ready to intervene

[Chorus]
Scale out, scale out, horizontal pressure
Pod count rising, meeting the measure
Requests per second, exponential climb
Cluster expanding, algorithm time

[Bridge - Breakdown]
*glitchy algorithmic sequence*
pending... pending... pending...
container starting... starting... ready
traffic routing... balancing... flow

Evidence IDs: [extract_087, extract_104]
```

**Rei's Strudel Pattern (same theme)**:

```
Title: "HPA Sequence"
Theme: Kubernetes horizontal pod autoscaling under load
BPM: 145
Duration: 16 bars

Strudel Code:
stack(
  // Control plane metrics (bass line)
  note("c2 c2 [c2 g2] c2").s("sawtooth").lpf(300).gain(0.7),

  // Pod replication events (percussive)
  s("industrial:1 ~ industrial:3 ~").gain(0.8).speed(1.2),

  // CPU threshold monitoring (rising pattern)
  note(sequence(48, 50, 52, 55, 57, 60).scale("minor"))
    .s("square").fast(2).cutoff(800),

  // Autoscaling trigger (every 4 bars)
  s("industrial:7").gain(1.2).delay(0.3).delaytime(0.125)
).every(4, x => x.fast(1.5)) // scale-out acceleration

Evidence IDs: [extract_087, extract_104]
Executed: true
```

## Environment Variables

Add to `.env` and `.env.example`:

```bash
# Rei Toei Music Avatar
REI_TOEI_ENABLED=true                     # Enable Rei Toei features
REI_TOEI_DEFAULT_BPM=142                  # Default tempo for songs
REI_TOEI_DEFAULT_GENRE="industrial techno cyberpunk"
REI_TOEI_MAX_SONG_LENGTH_SECONDS=180     # Suno limit: ~3 minutes
REI_TOEI_CONSOLE_ENABLED=true            # Enable /rei-toei in console
REI_TOEI_AUTO_EVIDENCE_TRACKING=true     # Track evidence IDs in lyrics

# Strudel Integration
REI_TOEI_STRUDEL_ENABLED=true            # Enable Strudel pattern generation
REI_TOEI_STRUDEL_DEFAULT_BARS=16         # Default pattern length in bars
REI_TOEI_STRUDEL_AUTO_EXECUTE=false      # Auto-execute patterns (vs preview only)
```

## Testing Strategy

**Unit tests** (`tests/test_rei_toei_service.py`):

- Theme extraction from extracted knowledge
- Song concept generation
- Lyric composition and structure validation
- Suno prompt formatting
- **Strudel pattern generation**
- **Strudel pattern syntax validation**
- **Concept-to-pattern mapping logic**
- Evidence ID tracking
- BPM and genre tag validation

**Integration tests**:

- Console routing to Rei personality
- Grounding retrieval with Rei's persona graph
- DoT validation of lyrical claims
- **Strudel MCP agent communication**
- **Pattern execution and error handling**
- End-to-end generation workflow (both Suno and Strudel)

**Manual testing**:

- Console conversation quality and personality distinctiveness
- Generated song prompt quality (submit to Suno manually, evaluate output)
- **Generated Strudel pattern musicality (execute and listen)**
- **Pattern complexity and technical concept alignment**
- Theme relevance to extracted knowledge
- Musical style consistency (both Suno and Strudel)

---

**Status**: Idea/Design Phase  
**Created**: 2026-05-19  
**Author**: Project maintainer  
**Related Docs**: `avatar_intelligence.md`, `persona-and-avatar.md`, `console_grounding/`
