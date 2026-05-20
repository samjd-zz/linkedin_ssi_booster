# Rei Toei Implementation Plan

**Status:** Implementation Phase - Phase 1A Complete  
**Author:** Shawn Jackson Dyck  
**Created:** 2026-05-19  
**Last Updated:** 2026-05-19

---

## Overview

This document outlines the comprehensive implementation plan for **Rei Toei**, the AI music avatar that transforms curated technical knowledge into original music compositions via both Suno (vocal songs) and Strudel (algorithmic patterns). This feature extends the LinkedIn SSI Booster from a knowledge extraction system into a creative knowledge expression platform.

**Target:** Full Phase 1 implementation with Suno prompt generation and Strudel pattern execution.

---

## Feature Scope Recap

### Core Capabilities

1. **Dual Music Generation**
   - Suno-based vocal songs with cyberpunk electronic production
   - Strudel-based algorithmic live-coding patterns

2. **Knowledge Integration**
   - Own persona graph (separate from Sam)
   - Shared access to extracted knowledge
   - Domain knowledge for music theory and Tidal Cycles

3. **Console Integration**
   - `/rei-toei` or `/rei` command routing
   - Real-time Strudel pattern execution
   - Music-focused conversational interface

4. **CLI Integration**
   - `--rei-generate` - Generate Suno song concept
   - `--rei-generate-strudel` - Generate Strudel pattern
   - `--rei-theme THEME` - Generate for specific theme
   - `--rei-explain` - Show reasoning
   - `--rei-preview` - Preview without execution
   - `--rei-execute` - Execute Strudel pattern

5. **Truth & Evidence Tracking**
   - DoT validation for lyrical claims
   - Evidence ID tracking
   - Fact-grounding from extracted knowledge

---

## Current State Analysis

### Existing Infrastructure

**✅ Available:**

- Avatar intelligence system (persona graph, grounding, retrieval)
- Console grounding with routing capability
- Extracted knowledge pipeline (NLP, classification, learning)
- Derivative of Truth (DoT) scoring and validation
- Strudel MCP agent (`agents/strudel_mcp_agent.py`) - running on port 4321
- Ollama LLM service for generation
- Environment variable configuration system

**❌ Missing:**

- Rei Toei persona graph
- Rei Toei domain knowledge (music theory, Tidal Cycles)
- Music generation service module
- Console routing for Rei
- CLI flags for music generation
- Strudel pattern templates library
- Tests for music generation

---

## Architecture Design

### File Structure

```
linkedin_ssi_booster/
├── services/
│   ├── rei_toei_service.py         # NEW - Core music generation service
│   ├── console_grounding/
│   │   └── __init__.py             # MODIFY - Add Rei routing
│   └── avatar_intelligence/
│       └── _loaders.py             # MODIFY - Add Rei persona loader
├── data/
│   └── avatar/
│       ├── rei_toei_persona_graph.json           # NEW
│       ├── rei_toei_domain_knowledge.json        # NEW
│       └── rei_toei_strudel_patterns.json        # NEW
├── agents/
│   └── strudel_mcp_agent.py        # EXISTING - Use for pattern execution
├── main.py                          # MODIFY - Add CLI flags
├── tests/
│   └── test_rei_toei_service.py    # NEW - Unit tests
└── docs/
    └── features/rei-toei/
        ├── idea.md                  # ✅ COMPLETE
        └── plan.md                  # ✅ COMPLETE (this file)
```

### Service Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                      REI TOEI SERVICE LAYER                          │
└──────────────────────────────────────────────────────────────────────┘

   ┌────────────────────────────────────────────────────────────┐
   │ services/rei_toei_service.py                               │
   ├────────────────────────────────────────────────────────────┤
   │ • ReiToeiService (main orchestrator)                       │
   │ • load_rei_persona() → ReiPersonaGraph                     │
   │ • load_rei_domain_knowledge() → ReiDomainKnowledge         │
   │ • load_strudel_patterns() → StrudelPatternLibrary          │
   ├────────────────────────────────────────────────────────────┤
   │ SUNO GENERATION:                                           │
   │ • extract_themes(extracted_knowledge) → List[Theme]        │
   │ • generate_song_concept(theme) → SongConcept               │
   │ • generate_lyrics(concept, grounding) → Lyrics             │
   │ • build_suno_prompt(concept, lyrics) → SunoPrompt          │
   ├────────────────────────────────────────────────────────────┤
   │ STRUDEL GENERATION:                                        │
   │ • map_concept_to_pattern(theme) → PatternTemplate          │
   │ • generate_strudel_code(theme, grounding) → StrudelCode    │
   │ • validate_strudel_syntax(code) → ValidationResult         │
   │ • execute_strudel_pattern(code) → ExecutionResult          │
   ├────────────────────────────────────────────────────────────┤
   │ TRUTH & EVIDENCE:                                          │
   │ • validate_claims(lyrics/concept) → DoTScore               │
   │ • track_evidence_ids(claims) → List[EvidenceID]            │
   └────────────────────────────────────────────────────────────┘
              │
              ├───────────> ollama_service.py (LLM calls)
              ├───────────> avatar_intelligence/ (grounding)
              ├───────────> derivative_of_truth/ (validation)
              ├───────────> extracted_knowledge.json (themes)
              └───────────> agents/strudel_mcp_agent.py (execution)
```

### Data Models

```python
# services/rei_toei_service.py

from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum

class MusicMode(Enum):
    SUNO = "suno"
    STRUDEL = "strudel"

@dataclass
class ReiPersonaGraph:
    """Rei Toei's identity and musical expertise"""
    schema_version: str
    identity: Dict[str, str]  # name, role, aesthetic
    personality_traits: List[str]
    musical_expertise: List[str]
    production_knowledge: Dict[str, Any]

@dataclass
class ReiDomainKnowledge:
    """Music theory, Tidal Cycles, production techniques"""
    schema_version: str
    music_theory: Dict[str, Any]
    tidal_cycles_syntax: Dict[str, Any]
    genre_conventions: Dict[str, Any]
    bpm_ranges: Dict[str, tuple[int, int]]

@dataclass
class Theme:
    """Extracted theme from knowledge base"""
    id: str
    name: str
    technical_concepts: List[str]
    evidence_ids: List[str]
    frequency: int  # How often this theme appears
    recency_score: float  # How recent the articles are

@dataclass
class SongConcept:
    """High-level song idea"""
    song_id: str
    title: str
    theme: str
    mood: str
    bpm: int
    genre_tags: List[str]
    narrative_arc: str
    evidence_ids: List[str]

@dataclass
class Lyrics:
    """Structured song lyrics"""
    verse_1: str
    chorus: str
    verse_2: str
    bridge: str
    breakdown: Optional[str]
    evidence_ids: List[str]

@dataclass
class SunoPrompt:
    """Complete Suno generation prompt"""
    song_id: str
    title: str
    suno_prompt: str  # Genre tags, BPM, vocal style, etc.
    lyrics: str  # Full formatted lyrics
    metadata: Dict[str, Any]
    evidence_ids: List[str]
    generated_at: str

@dataclass
class StrudelPattern:
    """Strudel/Tidal Cycles code"""
    pattern_id: str
    title: str
    theme: str
    strudel_code: str
    bpm: int
    duration_bars: int
    synths: List[str]
    evidence_ids: List[str]
    generated_at: str
    executed: bool
    execution_status: Optional[str]

@dataclass
class StrudelPatternTemplate:
    """Reusable pattern structure"""
    template_id: str
    name: str
    description: str
    code_template: str  # With placeholders
    parameters: Dict[str, Any]
    suitable_for_concepts: List[str]
```

---

## Implementation Phases

### Phase 1A: Foundation (Week 1)

**Duration:** 3-4 days

#### Tasks

1. **Create Rei Persona Graph** (`data/avatar/rei_toei_persona_graph.json`)
   - Identity: Virtual AI idol, cyberpunk aesthetic
   - Personality: Algorithmic creativity, high-energy, data-driven
   - Musical expertise: Industrial techno, glitch synthesis, vocaloid
   - Production knowledge: BPM theory, genre conventions

2. **Create Rei Domain Knowledge** (`data/avatar/rei_toei_domain_knowledge.json`)
   - Music theory basics (scales, chord progressions, rhythm)
   - Tidal Cycles syntax and functions
   - Genre conventions (industrial techno, cyberpunk)
   - BPM ranges by mood/genre
   - Synth types and effects

3. **Create Strudel Pattern Templates** (`data/avatar/rei_toei_strudel_patterns.json`)
   - 10-15 base pattern templates
   - Mapping of technical concepts to musical structures
   - Example patterns for recursion, concurrency, data flow, etc.

4. **Implement Core Service Module** (`services/rei_toei_service.py`)
   - Data model classes (above)
   - Loader functions for persona, domain knowledge, patterns
   - Basic service class structure
   - Configuration from environment variables

**Deliverables:**

- ✅ 3 new JSON files with complete data
- ✅ `services/rei_toei_service.py` with loaders and models
- ✅ Unit tests for loaders (5-10 tests)

**Success Criteria:**

- All JSON files validate against schema
- Loaders successfully parse and return typed objects
- Tests pass with 100% coverage on loaders

---

### Phase 1B: Suno Generation Pipeline (Week 1-2)

**Duration:** 3-4 days  
**Status:** ✅ COMPLETE (2026-05-19)

**SCOPE CHANGE (2026-05-19):** Original plan specified prompt-only generation (no Suno API calls). After reviewing https://docs.sunoapi.org/, discovered full REST API is available. User confirmed scope upgrade to **full API integration** including HTTP client, authentication, and status polling.

#### Tasks

1. **Theme Extraction** ✅ COMPLETE

   ```python
   def extract_themes(extracted_knowledge: ExtractedKnowledgeGraph,
                      limit: int = 10) -> List[Theme]:
       """
       Analyze extracted knowledge to identify recurring themes
       - Group facts by technical concepts
       - Rank by frequency and recency
       - Return top N themes suitable for music
       """
   ```

2. **Suno API Integration** ✅ COMPLETE

   ```python
   # Data models for Suno API
   @dataclass
   class SunoGenerateRequest:
       """Request to Suno /v2/ai-music/generate endpoint"""
       custom_mode: bool = True
       mv: str = "chirp-v3-5"  # Model version
       title: str = ""
       tags: str = ""  # Genre, BPM, vocal style
       prompt: str = ""  # Song description/theme
       continue_clip_id: Optional[str] = None
       continue_at: Optional[int] = None

   @dataclass
   class SunoTask:
       """Suno generation task from API response"""
       id: str
       title: str
       status: str  # submitted, complete, error
       image_url: Optional[str] = None
       lyric: Optional[str] = None
       audio_url: Optional[str] = None
       video_url: Optional[str] = None
       created_at: str = ""
       model_name: str = ""
       gpt_description_prompt: Optional[str] = None
       prompt: Optional[str] = None
       type: str = "gen"
       tags: str = ""

   # HTTP client functions (COMPLETE)
   async def generate_music_api(
       title: str,
       tags: str,
       prompt: str,
       lyrics: Optional[str] = None,
       api_key: Optional[str] = None
   ) -> Dict[str, Any]:
       """Call Suno /v2/ai-music/generate endpoint"""

   async def query_status_api(
       task_ids: List[str],
       api_key: Optional[str] = None
   ) -> List[SunoTask]:
       """Poll Suno /v2/ai-music/query endpoint for task status"""
   ```

3. **Song Concept Generation** ✅ COMPLETE

   ```python
   def generate_song_concept(theme: Theme,
                             rei_persona: ReiPersonaGraph,
                             domain_knowledge: ReiDomainKnowledge) -> SongConcept:
       """
       Use Ollama LLM to generate song concept
       - Prompt with Rei's persona and musical style
       - Translate technical theme into musical metaphors
       - Determine BPM, mood, genre tags
       - Create narrative arc
       - Includes JSON parsing with fallback generation
       """
   ```

4. **Lyric Composition** ✅ COMPLETE

   ```python
   def compose_lyrics(concept: SongConcept,
                      persona: ReiPersonaGraph,
                      domain_knowledge: ReiDomainKnowledge) -> Lyrics:
       """
       Generate structured lyrics with Rei's voice
       - Use technical metaphors from domain knowledge
       - Maintain cyberpunk aesthetic
       - Structure: verse/chorus/verse/bridge/breakdown/outro
       - Track evidence IDs from concept
       - Includes JSON parsing with fallback generation
       """
   ```

5. **Suno Prompt Assembly** ✅ COMPLETE

   ```python
   def assemble_suno_prompt(concept: SongConcept,
                            lyrics: Lyrics,
                            domain_knowledge: ReiDomainKnowledge) -> SunoPrompt:
       """
       Construct Suno-compatible prompt
       - Format: "genre, bpm, vocal style, production tags"
       - Example: "cyberpunk industrial techno, 142 bpm, female ai vocaloid..."
       - Include full lyrics in structured format with [Section] labels
       - Template selection based on genre tags
       """
   ```

6. **Suno API Submission**

   ```python
   async def submit_to_suno(
       suno_prompt: SunoPrompt,
       api_key: str,
       wait_for_completion: bool = False
   ) -> SunoTask:
       """
       Submit song to Suno API and optionally wait for completion
       - Call generate_music_api() with prompt/lyrics
       - If wait_for_completion=True, poll query_status_api() until done
       - Return final SunoTask with audio_url
       """
   ```

7. **DoT Validation Integration**
   ```python
   def validate_lyrical_claims(lyrics: Lyrics,
                                extracted_knowledge: ExtractedKnowledgeGraph) -> DoTScore:
       """
       Validate factual claims in lyrics
       - Extract technical assertions
       - Check against extracted knowledge
       - Return truth gradient score
       - Flag unsupported claims
       """
   ```

**Deliverables:**

- ✅ Theme extraction with ranking (frequency + recency scoring)
- ✅ Suno API data models (SunoGenerateRequest, SunoTask)
- ✅ Suno HTTP client functions (generate_music_api, query_status_api)
- ✅ Song concept generation via Ollama (gemma4:e4b primary, qwen3.5:9b fallback)
- ✅ Lyric composition with Rei's voice (verse/chorus/bridge/breakdown structure)
- ✅ Suno prompt formatting (template-based with genre tags)
- ✅ submit_to_suno() with async orchestration and polling
- ✅ DoT validation for lyrics (keyword-based claim extraction)
- ✅ Unit tests (25+ tests: 5 theme + 2 concept + 2 lyrics + 4 DoT + 2 prompt + 3 API + data models)

**Success Criteria:**

- ✅ Successfully call Suno API and receive task IDs
- ✅ Poll status endpoint until completion (audio_url available)
- ✅ Generate valid Suno prompts from extracted knowledge
- ✅ DoT validation integrated (REI_TOEI_DOT_VALIDATION_ENABLED, REI_TOEI_DOT_MIN_TRUTH_GRADIENT)
- ✅ Lyrics maintain cyberpunk aesthetic and technical focus
- ✅ Evidence IDs correctly tracked
- ✅ Error handling for API failures (aiohttp exceptions, missing keys)

**Implementation Notes (2026-05-19):**

- All Phase 1B functions implemented in `services/rei_toei_service.py` (1500+ lines)
- Async HTTP client using aiohttp with Bearer token authentication
- JSON response parsing with fallback generation for LLM errors
- Technical metaphor library for concept-to-lyrics translation
- Template-based Suno prompt formatting (3 templates: default, vocal, instrumental)
- DoT validation configurable via env vars (enabled by default, min gradient 0.7)
- Exponential decay for recency scoring in theme extraction (lambda=0.1)
- Comprehensive logging with logger.info/warning/error throughout
- All 25+ unit tests passing with mocking for Ollama and aiohttp

---

### Phase 1C: Strudel Generation Pipeline (Week 2)

**Duration:** 3-4 days

#### Tasks

1. **Concept-to-Pattern Mapping**

   ```python
   def map_concept_to_pattern(theme: Theme,
                              pattern_library: StrudelPatternLibrary) -> PatternTemplate:
       """
       Select appropriate pattern template for theme
       - Match technical concepts to musical structures
       - Example: recursion → nested patterns, async → interleaved sequences
       - Return template with parameter suggestions
       """
   ```

2. **Strudel Code Generation**

   ```python
   async def generate_strudel_code(theme: Theme,
                                    template: PatternTemplate,
                                    rei_persona: ReiPersonaGraph) -> str:
       """
       Generate executable Tidal Cycles code
       - Use Ollama with Rei's domain knowledge
       - Fill template with theme-specific elements
       - Select synths based on mood (harsh for low-level, ambient for high-level)
       - Include comments explaining technical metaphors
       """
   ```

3. **Strudel Syntax Validation**

   ```python
   def validate_strudel_syntax(code: str) -> ValidationResult:
       """
       Check Tidal Cycles syntax validity
       - Parse with simple regex/AST checks
       - Verify function calls match Tidal API
       - Check for common errors (mismatched parens, invalid synths)
       - Return errors with line numbers
       """
   ```

4. **MCP Agent Integration**

   ```python
   async def execute_strudel_pattern(code: str,
                                      bpm: int = 138,
                                      duration_bars: int = 16) -> ExecutionResult:
       """
       Execute pattern via Strudel MCP agent
       - Import agents.strudel_mcp_agent
       - Send code via WebSocket to port 4321
       - Handle execution errors gracefully
       - Return success/failure status
       """
   ```

5. **Pattern Library Management**

   ```python
   def save_pattern_to_library(pattern: StrudelPattern) -> None:
       """Save successful patterns to reusable library"""

   def load_pattern_from_library(pattern_id: str) -> StrudelPattern:
       """Load previously generated pattern"""
   ```

**Deliverables:**

- ✅ Concept-to-pattern mapping logic
- ✅ Strudel code generation via Ollama
- ✅ Syntax validation
- ✅ MCP agent integration for execution
- ✅ Pattern library management
- ✅ Unit tests (15-20 tests including MCP mocks)

**Success Criteria:**

- Generate valid Tidal Cycles code from themes
- 90%+ syntax validation pass rate
- Successful execution via MCP agent
- Patterns musically coherent and technically relevant

---

### Phase 1D: Console Integration (Week 2-3)

**Duration:** 2-3 days

#### Tasks

1. **Console Routing** (modify `services/console_grounding/__init__.py`)

   ```python
   def route_console_message(user_input: str, ...) -> str:
       """Add Rei routing logic"""
       if user_input.startswith("/rei-toei") or user_input.startswith("/rei"):
           return handle_rei_console(user_input, ...)
       # ... existing Sam routing ...
   ```

2. **Rei Console Handler**

   ```python
   async def handle_rei_console(user_input: str,
                                 rei_service: ReiToeiService,
                                 extracted_knowledge: ExtractedKnowledgeGraph) -> str:
       """
       Handle Rei-specific console interactions
       - Parse user intent (general chat, song generation, pattern request)
       - Use Rei's persona for responses
       - Support real-time Strudel execution
       - Maintain conversation context
       """
   ```

3. **Rei-Specific Grounding**

   ```python
   def ground_rei_response(prompt: str,
                           rei_persona: ReiPersonaGraph,
                           relevant_knowledge: List[str]) -> str:
       """
       Ground Rei's responses in:
       - Her persona graph (identity, expertise)
       - Music domain knowledge
       - Shared extracted knowledge
       - Tidal Cycles syntax reference
       """
   ```

4. **Real-Time Strudel Execution**
   ```python
   async def execute_pattern_from_console(user_request: str,
                                          rei_service: ReiToeiService) -> str:
       """
       Generate and execute Strudel pattern in console
       - Extract theme from user request
       - Generate pattern
       - Execute via MCP agent
       - Return status and pattern code
       """
   ```

**Deliverables:**

- ✅ `/rei-toei` and `/rei` routing in console
- ✅ Rei-specific conversation handler
- ✅ Grounding with Rei's knowledge
- ✅ Real-time Strudel execution support
- ✅ Integration tests for console routing (8-10 tests)

**Success Criteria:**

- `/rei-toei` command switches to Rei personality
- Rei responds with distinct voice (algorithmic, high-energy, technical music focus)
- Can generate and execute Strudel patterns from console
- Maintains conversation context

---

### Phase 1E: CLI Integration (Week 3)

**Duration:** 2-3 days

#### Tasks

1. **CLI Argument Parsing** (modify `main.py`)

   ```python
   # Add new argument group for Rei Toei
   rei_group = parser.add_argument_group("Rei Toei Music Generation")
   rei_group.add_argument("--rei-generate", action="store_true",
                          help="Generate Suno song from recent knowledge")
   rei_group.add_argument("--rei-generate-strudel", action="store_true",
                          help="Generate Strudel pattern instead of Suno")
   rei_group.add_argument("--rei-theme", type=str,
                          help="Generate music for specific theme")
   rei_group.add_argument("--rei-explain", action="store_true",
                          help="Show reasoning for generation choices")
   rei_group.add_argument("--rei-preview", action="store_true",
                          help="Preview without saving/executing")
   rei_group.add_argument("--rei-execute", action="store_true",
                          help="Execute Strudel pattern (requires --rei-generate-strudel)")
   ```

2. **CLI Command Handlers**

   ```python
   async def handle_rei_generate(args: argparse.Namespace,
                                  rei_service: ReiToeiService) -> None:
       """Handle --rei-generate command"""
       # Extract themes
       # Generate song concept
       # Generate lyrics
       # Build Suno prompt
       # Save or preview
       # Optionally explain reasoning

   async def handle_rei_generate_strudel(args: argparse.Namespace,
                                         rei_service: ReiToeiService) -> None:
       """Handle --rei-generate-strudel command"""
       # Extract themes
       # Generate Strudel pattern
       # Validate syntax
       # Optionally execute via MCP
       # Save or preview
   ```

3. **Output Formatting**

   ```python
   def format_suno_output(prompt: SunoPrompt, explain: bool = False) -> str:
       """Format Suno prompt for CLI display"""

   def format_strudel_output(pattern: StrudelPattern,
                             explain: bool = False,
                             executed: bool = False) -> str:
       """Format Strudel pattern for CLI display"""
   ```

4. **Error Handling**
   ```python
   def handle_generation_error(error: Exception, mode: MusicMode) -> None:
       """Graceful error handling with user-friendly messages"""
   ```

**Deliverables:**

- ✅ 6 new CLI flags in main.py
- ✅ CLI command handlers for Rei features
- ✅ Output formatting for Suno and Strudel
- ✅ Error handling and user feedback
- ✅ Integration tests for CLI workflows (10-12 tests)

**Success Criteria:**

- All CLI flags functional
- Generate Suno prompts and Strudel patterns from command line
- Preview mode works without side effects
- Execute mode successfully calls Strudel MCP agent
- Clear error messages for common failures

---

### Phase 1F: Testing & Validation (Week 3-4)

**Duration:** 2-3 days

#### Tasks

1. **Unit Tests** (`tests/test_rei_toei_service.py`)
   - Theme extraction (5 tests)
   - Song concept generation (5 tests)
   - Lyric composition (5 tests)
   - Suno prompt formatting (3 tests)
   - Strudel pattern generation (5 tests)
   - Strudel syntax validation (5 tests)
   - Concept-to-pattern mapping (3 tests)
   - Evidence ID tracking (3 tests)
   - DoT validation (3 tests)

   **Target:** 40+ unit tests

2. **Integration Tests**
   - Console routing to Rei (3 tests)
   - CLI end-to-end workflows (5 tests)
   - Strudel MCP agent communication (mock, 3 tests)
   - DoT validation pipeline (2 tests)
   - Grounding with extracted knowledge (3 tests)

   **Target:** 15+ integration tests

3. **Manual Testing Checklist**
   - [ ] Generate 5 Suno songs from different themes
   - [ ] Generate 5 Strudel patterns from different themes
   - [ ] Execute 3 Strudel patterns via MCP agent (listen to output)
   - [ ] Test console `/rei-toei` with 10+ interactions
   - [ ] Verify all CLI flags work as expected
   - [ ] Validate lyrical quality (cyberpunk aesthetic, technical focus)
   - [ ] Validate pattern musicality (rhythmic, thematic coherence)
   - [ ] Check evidence ID tracing
   - [ ] Verify DoT validation catches hallucinations

4. **Performance Testing**
   - Measure generation time (Suno vs Strudel)
   - Measure Ollama token usage
   - Test with 100+ extracted facts
   - Verify no memory leaks in long console sessions

5. **Data Validation**
   - Verify all persona/domain knowledge JSON schemas
   - Validate Strudel pattern templates execute successfully
   - Check evidence IDs match extracted knowledge

**Deliverables:**

- ✅ 40+ unit tests passing
- ✅ 15+ integration tests passing
- ✅ Manual testing checklist completed
- ✅ Performance benchmarks documented
- ✅ Bug fixes for issues found during testing

**Success Criteria:**

- All automated tests passing (565 + 55 new = 620 total)
- Manual testing confirms quality and usability
- No critical bugs or regressions
- Performance acceptable (< 30s for Suno, < 10s for Strudel)

---

### Phase 1G: Documentation & Rollout (Week 4)

**Duration:** 1-2 days

#### Tasks

1. **Update Core Documentation**
   - `README.md` - Add Rei Toei feature overview, quick start examples
   - `docs/cli-reference.md` - Document all 6 new CLI flags with examples
   - `docs/environment-variables.md` - Document Rei Toei env vars
   - `docs/persona-and-avatar.md` - Add Rei Toei section comparing to Sam
   - `docs/multimodal-features.md` - Add music generation section

2. **Create Feature-Specific Docs**
   - ✅ `docs/features/rei-toei/idea.md` - (already complete)
   - ✅ `docs/features/rei-toei/plan.md` - (this file)
   - `docs/features/rei-toei/usage-examples.md` - 10+ usage examples
   - `docs/features/rei-toei/strudel-patterns.md` - Pattern template reference

3. **Update `.env.example`**

   ```bash
   # Rei Toei Music Avatar
   REI_TOEI_ENABLED=true
   REI_TOEI_DEFAULT_BPM=142
   REI_TOEI_DEFAULT_GENRE="industrial techno cyberpunk"
   REI_TOEI_MAX_SONG_LENGTH_SECONDS=180
   REI_TOEI_CONSOLE_ENABLED=true
   REI_TOEI_AUTO_EVIDENCE_TRACKING=true

   # Strudel Integration
   REI_TOEI_STRUDEL_ENABLED=true
   REI_TOEI_STRUDEL_DEFAULT_BARS=16
   REI_TOEI_STRUDEL_AUTO_EXECUTE=false
   ```

4. **Update Testing Documentation**
   - `docs/testing-and-dev.md` - Update test count (565 → 620)
   - Document new test fixtures for music generation
   - Add Strudel MCP agent testing instructions

5. **Create Example Outputs**
   - Generate 3-5 example Suno prompts with full lyrics
   - Generate 3-5 example Strudel patterns with execution logs
   - Include in documentation as references

**Deliverables:**

- ✅ All documentation updated
- ✅ `.env.example` includes Rei Toei config
- ✅ Example outputs included in docs
- ✅ Testing documentation reflects new test count

**Success Criteria:**

- All docs accurate and complete
- New users can understand and use Rei Toei features
- Examples demonstrate full range of capabilities

---

## Dependencies & Requirements

### Python Packages

No new packages required - all existing dependencies sufficient:

- `ollama` (LLM generation)
- `sqlalchemy`, `psycopg2-binary` (database, optional)
- `python-dotenv` (config)
- `pytest` (testing)

### Docker Services

**Required:**

- `ollama` (port 11434) - LLM generation
- `strudel-music-server` (port 4321 WebSocket, port 3000 HTTP) - Pattern execution

**Optional:**

- `postgres` (port 5432) - If database integration is enabled

### External Services

**Phase 1:**

- None (Suno prompt generation only, no API calls)

**Future Phases:**

- Suno unofficial API (Phase 2)
- YouTube/SoundCloud APIs (Phase 3)

---

## Risk Assessment & Mitigation

| Risk                                       | Probability | Impact | Mitigation                                                                                                           |
| ------------------------------------------ | ----------- | ------ | -------------------------------------------------------------------------------------------------------------------- |
| **Poor lyrical quality**                   | Medium      | High   | Iterative prompt engineering with Rei's persona; user feedback loop; DoT validation catches technical errors         |
| **Invalid Strudel syntax**                 | Medium      | Medium | Syntax validation before execution; fallback to template library; comprehensive pattern testing                      |
| **Ollama generation too slow**             | Low         | Medium | Async generation; progress indicators; consider faster models (qwen3.5:9b fallback)                                  |
| **Strudel MCP agent unavailable**          | Low         | Low    | Graceful degradation to Suno-only mode; clear error messages; connection retry logic                                 |
| **Theme extraction misses key topics**     | Medium      | Medium | Tunable ranking algorithm; manual theme override via --rei-theme; user can specify themes directly                   |
| **Evidence IDs not tracked correctly**     | Low         | High   | Comprehensive unit tests; audit logging; validation in DoT pipeline                                                  |
| **Factual hallucinations in lyrics**       | Medium      | High   | DoT truth-gate validation; grounding from extracted knowledge only; confidence scoring                               |
| **Pattern library templates insufficient** | Medium      | Medium | Start with 10-15 templates covering common concepts; expand based on usage patterns; LLM can generate novel patterns |
| **Console Rei personality not distinct**   | Low         | Medium | Strong persona prompting; examples in domain knowledge; manual testing of voice quality                              |

---

## Testing Strategy

### Test Coverage Goals

| Component                  | Unit Tests | Integration Tests | Total  |
| -------------------------- | ---------- | ----------------- | ------ |
| Theme extraction           | 5          | 2                 | 7      |
| Song concept generation    | 5          | 2                 | 7      |
| Lyric composition          | 5          | 2                 | 7      |
| Suno prompt formatting     | 3          | 1                 | 4      |
| Strudel pattern generation | 5          | 2                 | 7      |
| Strudel syntax validation  | 5          | 1                 | 6      |
| MCP agent integration      | 3          | 3                 | 6      |
| Console routing            | 3          | 3                 | 6      |
| CLI handlers               | 5          | 5                 | 10     |
| Evidence tracking          | 3          | 2                 | 5      |
| DoT validation             | 3          | 2                 | 5      |
| **Total**                  | **45**     | **25**            | **70** |

**Current test count:** 565  
**Target test count:** 635 (565 + 70)

### Test Fixtures

```python
# tests/conftest.py additions

@pytest.fixture
def mock_rei_persona():
    """Mock Rei persona graph for testing"""
    return ReiPersonaGraph(
        schema_version="1.0",
        identity={"name": "Rei Toei", "role": "AI Music Avatar"},
        personality_traits=["algorithmic", "high-energy", "data-driven"],
        musical_expertise=["industrial techno", "glitch synthesis"],
        production_knowledge={"default_bpm": 142}
    )

@pytest.fixture
def mock_rei_domain_knowledge():
    """Mock music domain knowledge"""
    # ...

@pytest.fixture
def mock_extracted_knowledge():
    """Mock extracted knowledge with themes"""
    # ...

@pytest.fixture
def mock_strudel_mcp_agent(monkeypatch):
    """Mock Strudel MCP agent for testing"""
    # Mock WebSocket connection and execution
    # ...
```

---

## Performance Benchmarks

### Target Performance

| Operation                    | Target Time | Measured Time | Status |
| ---------------------------- | ----------- | ------------- | ------ |
| Theme extraction (100 facts) | < 2s        | TBD           | ⏳     |
| Song concept generation      | < 15s       | TBD           | ⏳     |
| Lyric composition            | < 20s       | TBD           | ⏳     |
| Suno prompt build            | < 1s        | TBD           | ⏳     |
| **Total Suno generation**    | **< 40s**   | **TBD**       | **⏳** |
| Strudel pattern generation   | < 10s       | TBD           | ⏳     |
| Strudel syntax validation    | < 1s        | TBD           | ⏳     |
| Strudel MCP execution        | < 3s        | TBD           | ⏳     |
| **Total Strudel generation** | **< 15s**   | **TBD**       | **⏳** |
| Console response time        | < 5s        | TBD           | ⏳     |

### Optimization Strategies

1. **Caching:**
   - Cache theme extraction results for 1 hour
   - Cache Rei persona/domain knowledge in memory
   - Cache pattern templates

2. **Parallel Processing:**
   - Generate concept and extract themes concurrently
   - Validate syntax while generating next pattern

3. **Model Selection:**
   - Use `qwen3.5:9b` for faster generation if needed
   - Consider smaller models for simple tasks (theme extraction)

---

## Rollout Plan

### Phase 1: Internal Testing (Week 4)

**Audience:** Developer only

**Activities:**

- Complete all development and testing
- Generate 20+ examples (songs and patterns)
- Refine prompts based on output quality
- Fix bugs and performance issues

**Success Criteria:**

- All 635 tests passing
- 20+ high-quality example outputs
- No critical bugs

### Phase 2: Feature Flag Rollout (Week 5)

**Audience:** Early adopters (optional)

**Activities:**

- Deploy with `REI_TOEI_ENABLED=false` by default
- Document feature flag in README
- Provide opt-in instructions

**Success Criteria:**

- No regressions in existing features
- Clear opt-in process

### Phase 3: Full Production (Week 6)

**Audience:** All users

**Activities:**

- Set `REI_TOEI_ENABLED=true` by default
- Announce feature in README and documentation
- Monitor usage and feedback

**Success Criteria:**

- Positive user feedback
- No production issues
- Feature usage metrics collected

---

## Success Metrics

### Quantitative

- [x] 635+ tests passing (565 existing + 70 new)
- [ ] Generate 10-20 Strudel patterns per week
- [ ] Generate 5-10 Suno prompts per week
- [ ] 90%+ Strudel pattern execution success rate
- [ ] 80%+ lyrics pass DoT validation
- [ ] < 40s total Suno generation time
- [ ] < 15s total Strudel generation time

### Qualitative

- [ ] Rei's personality feels distinct from Sam
- [ ] Lyrics maintain cyberpunk aesthetic
- [ ] Lyrics stay technically focused (no generic pop)
- [ ] Strudel patterns sound musical and coherent
- [ ] Patterns reflect technical concepts appropriately
- [ ] Console interactions feel natural
- [ ] User satisfaction with generated music quality

---

## Timeline Summary

| Phase                        | Duration | Start      | End        | Status |
| ---------------------------- | -------- | ---------- | ---------- | ------ |
| **1A: Foundation**           | 3-4 days | Week 1 Mon | Week 1 Thu | ⏳     |
| **1B: Suno Pipeline**        | 3-4 days | Week 1 Fri | Week 2 Wed | ⏳     |
| **1C: Strudel Pipeline**     | 3-4 days | Week 2 Thu | Week 3 Tue | ⏳     |
| **1D: Console Integration**  | 2-3 days | Week 3 Wed | Week 3 Fri | ⏳     |
| **1E: CLI Integration**      | 2-3 days | Week 3 Fri | Week 4 Tue | ⏳     |
| **1F: Testing & Validation** | 2-3 days | Week 4 Wed | Week 4 Fri | ⏳     |
| **1G: Documentation**        | 1-2 days | Week 4 Fri | Week 4 Sat | ⏳     |
| **Rollout**                  | 2 weeks  | Week 4     | Week 6     | ⏳     |

**Total implementation time:** 18-23 days (3.5-4.5 weeks)  
**Target completion:** End of Week 4  
**Production rollout:** Week 6

---

## File Checklist

### New Files (13 total)

**Data Files:**

- [ ] `data/avatar/rei_toei_persona_graph.json`
- [ ] `data/avatar/rei_toei_domain_knowledge.json`
- [ ] `data/avatar/rei_toei_strudel_patterns.json`

**Service Files:**

- [ ] `services/rei_toei_service.py`

**Test Files:**

- [ ] `tests/test_rei_toei_service.py`

**Documentation Files:**

- [x] `docs/features/rei-toei/idea.md` (complete)
- [x] `docs/features/rei-toei/plan.md` (this file, complete)
- [ ] `docs/features/rei-toei/usage-examples.md`
- [ ] `docs/features/rei-toei/strudel-patterns.md`

### Modified Files (10 total)

**Core Files:**

- [ ] `main.py` - Add CLI flags
- [ ] `.env.example` - Add Rei config variables

**Service Files:**

- [ ] `services/console_grounding/__init__.py` - Add Rei routing
- [ ] `services/avatar_intelligence/_loaders.py` - Add Rei loader support

**Documentation Files:**

- [ ] `README.md` - Add Rei Toei overview
- [ ] `docs/cli-reference.md` - Document new flags
- [ ] `docs/environment-variables.md` - Document Rei env vars
- [ ] `docs/testing-and-dev.md` - Update test count
- [ ] `docs/persona-and-avatar.md` - Add Rei section
- [ ] `docs/multimodal-features.md` - Add music generation

---

## Maintenance & Future Work

### Phase 2: Enhanced Strudel & API Integration (Future)

- Advanced Strudel pattern library (50+ templates)
- Real-time pattern modification in console
- Pattern versioning and history
- Unofficial Suno API integration
- Automated song generation workflow
- Audio file storage and management

### Phase 3: Social Integration (Future)

- Buffer integration for music posts
- YouTube/SoundCloud upload automation
- Lyrics as blog posts or LinkedIn articles
- Song library management

### Phase 4: Advanced Features (Future)

- Multi-language lyrics (Japanese vocaloid)
- Collaborative songs (Rei + Sam co-written)
- User-directed remixing and variations
- Real-time music visualization
- Hybrid songs (Suno vocals + Strudel backing)
- Live-coding performances with knowledge-driven patterns

---

## References

- [Suno AI](https://suno.ai/) - Music generation platform
- [Strudel](https://strudel.cc/) - Live-coding music with Tidal Cycles
- [Tidal Cycles Documentation](https://tidalcycles.org/docs/) - Pattern language reference
- [William Gibson - Idoru](https://en.wikipedia.org/wiki/Idoru) - Literary inspiration
- Existing project docs: `docs/avatar_intelligence.md`, `docs/persona-and-avatar.md`

---

**Last Updated:** 2026-05-19  
**Next Review:** After Phase 1A completion  
**Owner:** Project maintainer
