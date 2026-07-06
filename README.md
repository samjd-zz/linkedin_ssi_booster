<p align="center">
  <img src="media/favicons/logo1.png" alt="LinkedIn SSI Booster Logo" width="150">
</p>

# SSI Booster - :muscle: POWERED by Buffer.com!

> **⚙️ Project Status:** Active development with periodic maintenance cycles. Core features are stable and production-ready. New capabilities (image generation, music avatar, database integration) are being refined. See [ROADMAP.md](ROADMAP.md) for upcoming features and research directions.

##### <u>— Persona-Grounded Truth-Gated Adaptive-Continual-Learning Hybrid-RAG Multi-Avatar Content-Creation platform with Domain-Knowledge-Graph. Not your average [llm-wiki · GitHub](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 🤪

<p align="center">
  <a href="#"><img src="https://img.shields.io/badge/version-alpha--v0.0.3.3-F97316.svg" alt="Version alpha-v0.0.3.3"></a>
  <a href="https://developer.nvidia.com/cuda-toolkit"><img src="https://img.shields.io/badge/CUDA-13.0.1-76B900.svg?logo=nvidia" alt="CUDA 13.0.1"></a>
  <a href="https://spacy.io/"><img src="https://img.shields.io/badge/spaCy-NLP-09A3D5.svg?logo=spacy&logoColor=white" alt="spaCy"></a>
  <a href="https://github.com/black-forest-labs/flux"><img src="https://img.shields.io/badge/FLUX.1-Image%20Gen-E85D75.svg" alt="FLUX.1"></a>
</p>

<p align="center">
  <a href="https://buffer.com/"><img src="https://img.shields.io/badge/Buffer-API-0EA5E9.svg?logo=buffer&logoColor=white" alt="Buffer API"></a>
  <a href="https://buffer.com/"><img src="https://img.shields.io/badge/Buffer-MCP-14B8A6.svg?logo=buffer&logoColor=white" alt="Buffer MCP"></a>
  <a href="https://github.com/williamzujkowski/live-coding-music-mcp"><img src="https://img.shields.io/badge/Strudel-MCP-7C3AED.svg" alt="Strudel MCP"></a>
  <a href="https://suno.com/"><img src="https://img.shields.io/badge/Suno-AI%20Music-0F172A.svg" alt="Suno"></a>
  <a href="https://katzilla.dev/"><img src="https://img.shields.io/badge/Katzilla.dev-USGov%20Data-0057B8.svg" alt="Katzilla.dev"></a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-2563EB.svg" alt="License MIT"></a>
  <a href="docs/testing-and-dev.md"><img src="https://img.shields.io/badge/tests-775%20total-16A34A.svg" alt="Tests 775 total"></a>
</p>

<img src="media/favicons/2-score-ring_256x256.png" alt="SSI Score Ring" width="80" align="right">
<img src="media/favicons/2-score-ring_256x256.png" alt="SSI Score Ring" width="80" align="left">

**SSI Booster** isn't just a prompt wrapper — it's an adaptive continual learning automation system for content, curation, and persona growth. It combines spaCy-based NLP, a persona graph, BM25 retrieval, a truth gate, confidence scoring, a NetworkX-powered knowledge graph, and local memory to generate, curate, rank, and route posts.

Sign up for Buffer with my partner link — http://join.buffer.com/samjd42 — to start scheduling, publishing, and analyzing your social posts in one place while supporting my work.

---

## 🧠 Intelligence Stack

##### _<ul><u>— Why This Is Smarter Than Just 'AI Writes Posts'</u></ul>_

- **Advanced NLP with spaCy** — theme/claim extraction, semantic similarity, fact suggestion when the truth gate drops a sentence, and preprocessing that filters boilerplate before fact storage. See [docs/knowledge-extraction-improvement.md](docs/knowledge-extraction-improvement.md).
- **Model2Vec static embedding classification** — ultra-fast article categorisation (`minishlab/potion-base-8M`, 30MB, zero API deps) mapped to 10 SSI categories; results boost selection-learning rankings and stamp extracted facts with `primary_category` and `primary_ssi_component`.
- **Persona-grounded generation** — every post uses facts, projects, and outcomes from your private persona graph and domain knowledge packs — not a bio blurb.
- **Hybrid RAG + agent pipeline** — BM25 retrieval, deterministic validation, multi-step orchestration, and a BM25+graph reranker for high factuality and variety.
- **Curation learning loop** — Beta-smoothed acceptance priors per source/topic/SSI component; the system learns from what you actually publish.
- **Truth gate** — four-layer post-generation filter: BM25 evidence scoring → Derivative of Truth gradient → spaCy semantic similarity floor → spaCy NER org-name validation. Removes unsupported claims before anything reaches Buffer. See [docs/derivative-of-truth.md](docs/derivative-of-truth.md).
- **Confidence scoring & policy routing** — grounding, novelty, and repetition score routes each post to `post`, `idea`, or `block`.
- **DoT + Probabilistic Logic Networks** — probabilistic logic scoring with truth trajectory tracking (`dT/dt`) and dual-mode comparison. Use `--dot-report` for full gradient and evidence breakdowns.
- **Memory & repetition penalty** — recent themes and claims penalised to keep your feed fresh.
- **Explainability** — `--avatar-explain`, `--avatar-learn-report`, and `--dot-report` give full visibility into grounding, learning, and truth scoring.
- **No cloud AI keys required** — all generation runs locally via Ollama.

**Result:** A self-improving, persona-driven content engine that adapts to your taste, avoids repetition, and grows your SSI — with full transparency and explainability.

---

## 📋 Status & Roadmap

The SSI Booster is actively maintained with periodic development cycles. See **[ROADMAP.md](ROADMAP.md)** for:

- ✅ **Complete:** Katzilla.dev government data integration (6 phases, 23 files, 16 tests)
- ✅ **Complete:** Alex Grey Avatar Enhancement — FLUX.1 art avatar subsystem (GPU orchestration ✅, Ollama-first sequencing ✅, schedule/curate/console integration ✅, 72 tests ✅)
- ✅ **Fixed & Re-enabled:** Ollama Buffer MCP Agent (retry safety ✅, health checks ✅, Docker service live ✅, unit tests added ✅)
- ✅ **Complete:** Rei Toei AI Music Avatar — Strudel MCP Agent (retry safety ✅, health checks ✅, MCP stdio flow active ✅, unit tests added ✅, Suno integration ✅)
- 🏛️ **Research:** RIA Canadian Law Knowledge integration (regulatory grounding for policy-aware content)

**Have ideas?** [Open a GitHub issue](https://github.com/samjd-zz/linkedin_ssi_booster/issues) with the `enhancement` label.

---

## 🎵 Rei Toei - AI Music Avatar (Complete)

> **Inspiration:** Cyberpunk-aesthetic AI music avatar inspired by [Switch Angel](https://www.youtube.com/@Switch-Angel) and William Gibson's _Idoru_. See [Rei Toei Customization Guide](docs/rei-toei-customization.md) for full details on architecture, customization, and persona tuning.

**Rei Toei** transforms the SSI Booster into a **creative knowledge expression platform**, converting your curated technical knowledge into algorithmic music. See [Rei Toei Implementation Plan](docs/features/rei-toei/plan.md) for architecture, commands, and usage examples.

**Current capabilities:**
- **Suno Vocal Songs** — Generate cyberpunk industrial techno concepts with structured lyrics grounded in extracted knowledge (Suno integration ✅)
- **Strudel Live-Coding Patterns** — Translate technical themes into algorithmic music (Strudel MCP integration ✅)
- **Knowledge Grounding** — Every lyric is validated via Derivative of Truth for factual accuracy

**Access in console:**

```bash
python main.py --console
Sam> /rei-toei                    # Switch to Rei's persona
Rei> What concept should we sonify today?
Sam> Generate a song about async programming
Rei> [Generates song with Suno prompt and evidence IDs]
```

---

## 🖼️ Image Generation with FLUX.1 (Alex Grey Enhancement)

Generate persona-aligned visual content using FLUX.1-schnell locally. The Alex Grey Avatar Enhancement is the style layer that keeps generated images aligned with the project's visual identity.

**Current status:** FLUX.1 integration complete; persona aesthetic tuning in progress (see [ROADMAP.md](ROADMAP.md)).

**Requirements:**
- GPU with 12GB+ VRAM (tested on RTX 3060)
- Run with `--profile full` in Docker Compose
- Or locally with `pip install -r requirements-flux.txt`
- **Hugging Face FLUX.1-schnell model files** must be downloaded locally using the provided script (`scripts/download-flux1-schnell-Q4_K_S.sh`)

**Use cases:**
- Generate social-media-ready visuals for posts
- Create persona-aligned avatar artwork
- Batch generate imagery for content calendars

The FLUX art avatar pipeline is complete — GPU orchestration, Ollama-first sequencing, singleton-safe service, style presets with neutral art-direction by default, and opt-in realism via `FLUX_CAPACITOR_REALISM_HINT`.

For long-running full-profile rendering, memory stability is tuned via `FLUX_KEEP_PIPELINE_LOADED=true` (service mode default) and optional `FLUX_LOG_MEMORY=true` to trace CUDA allocation/reservation drift per generation.

The avatar does not use a separate persona graph identity for images. Prompt inputs are the source story text from schedule, curate, or console flows; the active style preset (`corporate_minimal` by default, plus `sacred_geometry_light` and `tech_dark`); the `FLUX_CAPACITOR_STYLE_SYSTEM_PROMPT`; optional `FLUX_CAPACITOR_REALISM_HINT` / per-request `realism_hint`; and optional `knowledge_context` from the caller. In console mode, `/art` renders from the most recent AI reply in the current session, and an optional topic hint narrows the visual prompt.

See [docs/flux-art-avatar.md](docs/flux-art-avatar.md) for configuration, style presets, GPU sequencing, and terminal display details. See [docs/multimodal-features.md](docs/multimodal-features.md) for the broader multimodal overview.

---

## 🏆 What is the Social Selling Index (SSI)?

The [LinkedIn specifically uses the Social Selling Index](https://www.linkedin.com/sales/ssi) is a 0–100 score LinkedIn updates daily. It measures how effectively you build your personal brand, find the right people, engage with insights, and build relationships — the four pillars LinkedIn's algorithm uses to determine how widely your content and profile are surfaced to others.

A higher SSI directly correlates with more profile views, post reach, and inbound connection requests. LinkedIn's own data shows that professionals with an SSI above 70 get 45% more opportunities than those below 30.

The score breaks down into four components (25 points each):

| Component                             | What LinkedIn measures                                                            |
| ------------------------------------- | --------------------------------------------------------------------------------- |
| **Establish your professional brand** | Completeness of profile, consistency of posting, saves/shares on your content     |
| **Find the right people**             | Profile searches landing on you, connection acceptance rate, right-audience reach |
| **Engage with insights**              | Shares, comments, and reactions on industry content; thought leadership signals   |
| **Build relationships**               | Connection growth, message response rate, relationship depth                      |

## 🤖 Why automate it?

SSI decays if you go quiet — LinkedIn penalises inconsistency. Manually writing 3 posts per week, curating industry articles with original commentary, and maintaining an on-brand voice across hundreds of posts is simply not sustainable alongside a full-time engineering role.

This tool handles the repeatable parts:

- **Consistent cadence** — 3 posts/week scheduled to Buffer at proven engagement times (Tue/Wed/Fri 4 PM EST)
- **On-brand content** — every post is grounded in your real projects, real numbers, and real technical voice via a detailed persona prompt
- **All four SSI pillars** — the content calendar and curator rotate across all four components so no single pillar is neglected
- **Curation pipeline** — fetches today's AI/GovTech news, filters by your niche, and generates commentary that you can either:
  - route to Buffer Ideas for review under the default balanced confidence policy, or
  - schedule directly as posts to your Buffer queue when confidence is high enough and `--type post` is used

**`--learn`** extracts and persists knowledge from curated articles into `extracted_knowledge.json`. Three modes:
- **Knowledge-only** (`--curate --learn`) — bulk-loads knowledge, skips generation and Buffer. No post cap — processes all relevant articles.
- **Generation preview** (`--curate --dry-run`) — generates posts in dry-run mode (no Buffer writes).
- **Live generation** (`--curate`) — generates posts and routes to Buffer according to `--type` and confidence policy.

For the full flag reference (`--classify`, `--dot-report`, `--avatar-explain`, `--avatar-learn-report`, `--add-category`, etc.) see [docs/cli-reference.md](docs/cli-reference.md).

You control whether curated content is reviewed before publishing or scheduled directly. The tool removes the blank-page problem, but you decide what goes live.

---

## 🚀 Scheduling & Buffer Integration

The SSI Booster integrates with **Buffer for seamless social scheduling**. All posts generated by the curator are pushed to your Buffer queue (or Ideas for review) via the Buffer GraphQL API.

**Why Buffer?**
- Optimal posting times for maximum reach
- Multi-channel management (LinkedIn, Twitter, etc.)
- Queue management and performance analytics
- Full integration with SSI Booster's confidence routing (post → ideas → block)

**Support the project:** Use our [Buffer partner link](https://join.buffer.com/samjd42) to help fund development while getting started with Buffer scheduling!

**In Development:** See [ROADMAP.md](ROADMAP.md) for details on the **Ollama Buffer MCP Agent** — a natural language interface to Buffer operations powered by Gemma 4 (code complete, Docker service active, unit tests added; live endpoint validation and consumer wiring pending).

---

## 🔍 Learning, Grounding, and Explainability Pipeline

- **Candidate logging** — every post and article candidate is logged with full metadata for a complete audit trail.
- **Reconciliation & priors** — Buffer publication outcomes update Beta-smoothed acceptance priors per source/topic/SSI component; well-performing sources float upward over time.
- **Ranking** — candidates ranked by acceptance priors × BM25 scores, continuously adapting to your preferences.
- **Signal flow** — truth gate reason codes → confidence scorer (`post`/`idea`/`block`) → Buffer reconciliation → priors update. Sources that reliably produce clean, grounded posts rise; sources that trigger heavy filtering sink.
- **Deterministic grounding** — BM25Okapi retrieves persona/domain facts for every generation; prompts forbid invented stats, dates, or companies. The four-layer truth gate enforces this post-generation.

See [docs/learning-pipeline.md](docs/learning-pipeline.md) · [docs/selection-learning.md](docs/selection-learning.md) · [docs/derivative-of-truth.md](docs/derivative-of-truth.md).

---

## 🧮 Derivative of Truth (DoT) + Probabilistic Logic Networks (PLN)

Every generated sentence receives a composite truth gradient score across four terms: evidence quality × reasoning strength × source credibility × claim-evidence token overlap (Jaccard). Sentences below `TRUTH_GRADIENT_FLAG_THRESHOLD` (default 0.35) are flagged `weak_dot_gradient` and removed before publication.

PLN brings formal logic reasoning (deduction, induction, abduction, revision) with truth trajectory tracking (`dT/dt`) and dual-mode PLN vs legacy comparison. PLN is active by default. Use `--dot-report` to print the full gradient, evidence, and uncertainty breakdown for any run.

See [docs/derivative-of-truth.md](docs/derivative-of-truth.md) · [docs/dot-pln-enhancement.md](docs/dot-pln-enhancement.md).

---

## 🧩 Knowledge Graph: NetworkX Core, Neo4j for Expansion

The core knowledge graph uses NetworkX — in-memory, pure Python, fast for the sub-1,000 node graphs a single avatar generates. Neo4j is the scale-out path for multi-avatar, enterprise, or bulk-import scenarios requiring persistent disk-backed storage and Cypher queries.

See [docs/knowledge-graph.md](docs/knowledge-graph.md) for graph operations, the hybrid BM25+graph retrieval formula, and the Neo4j expansion path.

---

The system now includes a NetworkX-powered knowledge graph for incremental learning, hybrid BM25+graph retrieval, and persona-aware reranking.

**Integration Philosophy:**

- BM25 (lexical retrieval) remains the primary candidate selector for claims, project details, facts, narrative memory, and learned article summaries.

- The NetworkX knowledge graph is used as a secondary, persona-aware reranker and explainer: it links persona ↔ skills ↔ projects ↔ claims ↔ domain facts.

- Final candidate scoring is a hybrid:

  $$
  ext{final} = 0.7 \times \text{bm25} + 0.2 \times \text{graph proximity} + 0.1 \times \text{claim support}
  $$

### 🧬 Hybrid Retrieval and Scoring Architecture

```mermaid
flowchart TD
    UserInput["User Interactions / Content Curation"] -->|"New Knowledge"| Learning["Avatar Learning Subsystem"]
    Learning -->|"Add/Update"| KnowledgeGraph["Knowledge Graph (networkx)"]
    UserQuery["User Query / Generation Request"] --> BM25["BM25 Lexical Retriever"]
    BM25 -->|"Top Candidates"| GraphRerank["Graph Proximity & Claim Support"]
    KnowledgeGraph -->|"Proximity/Support"| GraphRerank
    GraphRerank -->|"Hybrid Score"| Generation["Post Generation / Explanation"]
    Generation -->|"Citations/Explanations"| UserInput
```

## 🔄 Continual Learning (NLP-Extracted Knowledge)

> Inspired by Ben Goertzel's OpenCog AtomSpace work on incremental, explainable cognition.

The avatar accumulates domain knowledge automatically from RSS feeds and curated articles. spaCy extracts, normalises, and deduplicates facts before merging them into the knowledge graph and BM25 candidate pool. Extracted facts are stamped with `primary_category` and `primary_ssi_component` for category-filtered retrieval.

Use `--learn` during curation to populate the knowledge base. Inside a running console session, `/reload` re-reads all avatar files without restarting — useful when running a `--learn` job concurrently in a second terminal. Console mode supports inline truth scoring with `--verify` (DoT + fact-pool similarity indicator after every AI reply).

A multi-layer noise filter (first-person narration, truncated RSS fragments, navigation blobs, zero-signal sentences, and more) runs before spaCy NLP to keep the knowledge graph clean. Voice synthesis is available via Wyoming Piper (enable with `CONSOLE_USE_VOICE=true`).

See [docs/features/continual-learning/idea.md](docs/features/continual-learning/idea.md) for the full noise filter catalogue, schema, and NLP writing principles.

---

## Database Integration (PostgreSQL)

> **Status:** PostgreSQL dual-write covers selection-learning candidate logging and published-record reconciliation. File-based storage (JSON/JSONL) remains the recommended default.

Database integration is **optional** and **non-breaking** — set `DATABASE_ENABLED=false` to revert at any time.

**Setup (Docker):**

1. Add to `.env`:
   ```bash
   DATABASE_ENABLED=true
   POSTGRES_USER=ssi_booster
   POSTGRES_PASSWORD=your_secure_password_here
   POSTGRES_DB=linkedin_ssi_booster
   DATABASE_URL=postgresql://ssi_booster:your_password@postgres:5432/linkedin_ssi_booster
   ```
2. Start PostgreSQL: `docker compose --profile core up -d postgres`
3. Verify: `docker exec -it ssi_booster_postgres psql -U ssi_booster -d linkedin_ssi_booster -c "\dt"`

**Migrate existing data:** `docker compose --profile core run --rm app python -m services.database.migrate_data`

The schema covers 17 tables across avatar intelligence, selection learning, truth gate learning, and DoT. Engine/session singletons use thread-safe double-checked locking. See [docs/features/database/idea.md](docs/features/database/idea.md) for full schema and architecture.

---

## 🗺️ Docs map

### Quick Start & Setup

- [Setup guide](docs/setup.md) — environment, dependencies, persona graph, and calendar setup
- [Usage guide](docs/usage-schedule-curate-console.md) — scheduling, curation, console mode, channels, and CLI examples
- [CLI reference](docs/cli-reference.md) — complete command-line flag reference for schedule, curate, console, and reporting modes

### Deployment & Configuration

- [Docker deployment](docs/docker-deployment.md) — Docker Compose profiles, GPU passthrough, services overview, and production deployment
- [Environment variables](docs/environment-variables.md) — comprehensive reference for all configuration options (Buffer, Ollama, truth gate, Model2Vec, voice, image gen, database)

### Core Intelligence & Learning

- [Architecture guide](docs/architecture.md) — learning pipeline, grounding flow, truth gate, and curation ranking
- [Learning pipeline](docs/learning-pipeline.md) — truth gate layers, confidence scoring, routing policies, and explainability features
- [Persona and Avatar Intelligence](docs/persona-and-avatar.md) — persona graph, system prompt, memory, confidence, and continual learning
- [Derivative of Truth (DoT) framework](docs/derivative-of-truth.md) — mathematical model, five-layer truth gate pipeline, DoT vs spaCy comparison, and scoring
- [Selection learning](docs/selection-learning.md) — candidate logging, reconciliation, and acceptance priors

### Knowledge & Data

- [Knowledge graph](docs/knowledge-graph.md) — NetworkX architecture, hybrid BM25+graph retrieval, graph operations, and Neo4j expansion path
- [Domain Knowledge Graph](docs/domain-knowledge.md) — domain-level expertise that isn't tied to specific projects
- [Continual Learning (NLP-extracted knowledge)](docs/features/continual-learning/idea.md) — how the avatar accumulates new knowledge from external content
- [Katzilla integration](docs/katzilla-integration.md) — US government datasets API, truth gate wiring, budget controls, and console `/katzilla` command
- [Database Integration](docs/features/database/idea.md) — PostgreSQL schema (17 tables), migration strategy, dual-write mode, and performance benchmarks

### Multimodal Features

- [Multimodal features](docs/multimodal-features.md) — FLUX.1-schnell image generation, Rei Toei AI music avatar (Suno + Strudel), and Buffer MCP agent
- [FLUX art avatar](docs/flux-art-avatar.md) — configuration, style presets, terminal display, GPU sequencing, and flow integration
- [Rei Toei Implementation](docs/features/rei-toei/plan.md) — AI music avatar architecture, Suno song generation, Strudel pattern execution, console integration, and CLI flags

### Strategy & Development

- [SSI strategy](docs/ssi-and-strategy.md) — SSI model, content mapping, scheduler behavior, and reporting
- [AI backend](docs/ai-backend-and-models.md) — Ollama setup and model recommendations
- [NLP writing principles](docs/nlp-basics.md) — pattern interrupts, presupposition, anchoring, and ethical content guidelines
- [Testing and development](docs/testing-and-dev.md) — pytest coverage and project structure (775 collected; 773 passed, 2 skipped, 0 failed)

## 🐳 Docker Compose (Recommended)

Run the full stack with a single command — Ollama LLM server + Wyoming Piper TTS + SSI Booster app. The stack uses **Docker Profiles** (`core` vs `full`) to manage hardware resources.

**Quick Start:**

```bash
# Standard mode — LLM + TTS + analytics (daily use)
bash run.sh --profile core up -d

# Full mode — adds FLUX image generation
bash run.sh --profile full up -d

# Run commands
docker compose --profile core run --rm -it app python main.py --console
docker compose --profile core run --rm app python main.py --curate
```

See [docs/docker-deployment.md](docs/docker-deployment.md) for complete setup guide, prerequisites (NVIDIA Container Toolkit, CUDA 12.4+, GPU requirements), service details, and troubleshooting.

---

## ⚡ Quickstart (local Python)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_md
cp .env.example .env
cp data/avatar/persona_graph.example.json data/avatar/persona_graph.json
cp data/avatar/domain_knowledge.example.json data/avatar/domain_knowledge.json
cp data/avatar/narrative_memory.example.json data/avatar/narrative_memory.json

# Optional extra packs: auto-discovered and merged when named domain_knowledge_*.json
cp data/avatar/domain_knowledge_java.json data/avatar/domain_knowledge_java.json
cp data/avatar/domain_knowledge_python.json data/avatar/domain_knowledge_python.json
cp content_calendar.example.py content_calendar.py
python main.py --schedule --week 1 --dry-run

# Console mode (DoT scanning OFF by default)
python main.py --console

# Console mode with DoT verification enabled
python main.py --console --verify
```

### ⚙️ Environment Variables

Copy `.env.example` to `.env` and fill in required values. Key variables include:

- `BUFFER_API_KEY` — Buffer API access
- `OLLAMA_MODEL` / `OLLAMA_MODEL_FALLBACK` — LLM models (e.g., `gemma4:e4b`, `qwen3.5:9b`)
- `TRUTH_GATE_BM25_THRESHOLD` — Evidence scoring threshold
- `MODEL2VEC_ENABLED` — Static embedding classification
- `CONSOLE_USE_VOICE` — Wyoming Piper TTS
- `DATABASE_ENABLED` — PostgreSQL dual-write mode
- `REI_TOEI_THEME_POOL_SIZE` / `REI_TOEI_THEME_REPEAT_PENALTY` — Rei theme variety tuning
- `REI_TOEI_RECENT_TITLE_WINDOW` / `REI_TOEI_THEME_JITTER_RATIO` — Rei title uniqueness and randomness tuning
- `KATZILLA_ENABLED` / `KATZILLA_API_KEY` — Optional external evidence retrieval via Katzilla
- `KATZILLA_TELEMETRY_ENABLED` / `KATZILLA_MAX_CALLS_PER_DAY` — Katzilla observability and daily budget controls

See [docs/environment-variables.md](docs/environment-variables.md) for comprehensive reference covering 40+ configuration options across Buffer, Ollama, truth gate, Model2Vec, voice/TTS, image generation, Strudel music, Katzilla external evidence, and database integration.

[MIT License](LICENSE) — see LICENSE for details.
