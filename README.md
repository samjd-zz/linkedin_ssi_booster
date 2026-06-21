<p align="center">
  <img src="media/favicons/logo1.png" alt="LinkedIn SSI Booster Logo" width="150">
</p>

# SSI Booster - :muscle: POWERED by Buffer.com!

> **⚙️ Project Status:** Active development with periodic maintenance cycles. Core features are stable and production-ready. New capabilities (image generation, music avatar, database integration) are being refined. See [ROADMAP.md](ROADMAP.md) for upcoming features and research directions.

##### <u>— Persona-Grounded Truth-Gated Adaptive-Continual-Learning Hybrid-RAG Multi-Avatar Content-Creation platform with Domain-Knowledge-Graph. Not your average [llm-wiki · GitHub](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 🤪

[![Version alpha-v0.0.3.1](https://img.shields.io/badge/version-alpha--v0.0.3.1-orange.svg)]()[![spaCy](https://img.shields.io/badge/spaCy-NLP-09A3D5.svg?logo=spacy&logoColor=white)](https://spacy.io/)[![FLUX.1](https://img.shields.io/badge/FLUX.1-Image%20Gen-FF6B6B.svg)](https://github.com/black-forest-labs/flux)[![CUDA 13.0.1](https://img.shields.io/badge/CUDA-13.0.1-76B900.svg?logo=nvidia)](https://developer.nvidia.com/cuda-toolkit)[![Buffer API](https://img.shields.io/badge/Buffer-API-231F20.svg)](https://buffer.com/)[![Katzilla.dev](https://img.shields.io/badge/Katzilla.dev-USGov%20Data-0057B8.svg)](https://katzilla.dev/)[![License MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)[![Tests 679 passed](https://img.shields.io/badge/tests-679%20passed-brightgreen.svg)]()

<img src="media/favicons/2-score-ring_256x256.png" alt="SSI Score Ring" width="80" align="right">
<img src="media/favicons/2-score-ring_256x256.png" alt="SSI Score Ring" width="80" align="left">

**SSI Booster** isn't just a prompt wrapper — it's an adaptive continual learning automation system for content, curation, and persona growth. It combines spaCy-based NLP, a persona graph, BM25 retrieval, a truth gate, confidence scoring, a NetworkX-powered knowledge graph, and local memory to generate, curate, rank, and route posts.

Sign up for Buffer with my partner link — http://join.buffer.com/samjd42 — to start scheduling, publishing, and analyzing your social posts in one place while supporting my work.

---

## 🧠 Intelligence Stack

##### _<ul><u>— Why This Is Smarter Than Just 'AI Writes Posts'</u></ul>_

- **Advanced NLP with spaCy** — Theme/claim extraction, semantic similarity, sentiment/tone analysis, and advanced curation/grounding features:
  - **Fact Suggestion:** When the truth gate drops a sentence, spaCy suggests the closest matching fact or evidence from your persona graph, or recommends how to rephrase for grounding.
  - **Contextual Summarization:** spaCy generates concise, context-aware summaries of curated articles, improving the quality of commentary and learning signals.
  - **Knowledge Extraction Quality Improvement:** spaCy summarization preprocessing filters out boilerplate, marketing copy, and navigation chrome before fact extraction, significantly improving signal-to-noise ratio. See [docs/knowledge-extraction-improvement.md](docs/knowledge-extraction-improvement.md) for implementation details, architecture changes, and testing results.

- **Fast static embedding-based text classification with Model2Vec** — Automatically categorize RSS articles and posts into predefined categories (Technology, Business, AI, Science, etc.) and custom categories. Classification runs on every article during curation and maps results to SSI components for balanced content generation. Uses `minishlab/potion-base-8M` (30MB model) for fast inference with zero external API dependencies. Categories are automatically attached to articles and used to boost ranking when selection learning picks articles that align with your target SSI component. **Category-aware knowledge extraction** — every fact extracted by the NLP pipeline (`--learn`) is now stamped with the source article's `primary_category` and `primary_ssi_component`, enabling category-filtered retrieval and category-aware grounding. Existing facts in `extracted_knowledge.json` load with empty-string defaults for full backward compatibility.

- **Persona-grounded generation** — Every post is written in your real technical voice, with facts, projects, and outcomes pulled from your private persona graph and knowledge graph (not just keywords or a bio blurb).

- **Hybrid RAG + agent pipeline** — Combines BM25 retrieval, deterministic validation, multi-step agent orchestration, and a hybrid BM25+graph reranker for high factuality, persona-awareness, and variety.

- **Curation learning loop** — The system tracks every generated candidate, learns which ones you actually publish, and automatically floats the best sources/topics to the top in future runs (Beta-smoothed acceptance priors per source/SSI component).

- **Truth gate** — Post-generation filter removes unsupported claims (numbers, dates, company names, project-tech mismatches) for maximum credibility. Four validation layers run in sequence on every sentence:
  - **BM25 evidence scoring** — each sentence is ranked against article text and persona facts; sentences below the configurable threshold (`TRUTH_GATE_BM25_THRESHOLD`) are flagged as weakly supported.
  - **Derivative of Truth per-sentence scoring** — every sentence receives a composite truth gradient (evidence type × reasoning quality × source credibility × token overlap). Sentences that pass BM25 but score below `TRUTH_GRADIENT_FLAG_THRESHOLD` (0.35) are flagged `weak_dot_gradient` and auto-removed. The 4-term DoT formula is active — token overlap between the sentence and each evidence fact is computed (Jaccard) and included as a 25%-weight component.
  - **spaCy semantic similarity floor** — for sentences containing numeric claims, years, dollar amounts, or org names, `compute_similarity()` checks the sentence against the source article. Similarity below `TRUTH_GATE_SPACY_SIM_FLOOR` (default `0.10`, configurable) flags the sentence as `low_semantic_similarity`, catching paraphrased hallucinations BM25 misses.
  - **spaCy NER org-name validation** — org/company names are extracted via spaCy named entity recognition (`ORG` entities) and verified against the allowed evidence set. Falls back to the legacy regex when spaCy is unavailable.
  - **False-positive hardening for tech terms** — concept/service tokens and tech-version entities (for example `S3`, `AI Q&A`, `Java 21`) are filtered before ORG enforcement so technical references are not incorrectly blocked as `unsupported_org`.
  - **Expanded domain evidence via multi-file loading** — avatar state now auto-merges sibling `domain_knowledge_*.json` files (for example Java and Python packs), which broadens allowed evidence tokens and improves support checks.
  - **Fact-pool spaCy similarity** — for every sentence that passes BM25, the best spaCy cosine similarity across all persona/domain facts (individually) is computed. Sentences below `TRUTH_GATE_FACT_SIM_FLOOR` (default `0.05`) are flagged `low_fact_similarity`. Unlike the article-sim check, this runs in **all contexts including console mode** because persona/domain facts are always present.

  > See [docs/derivative-of-truth.md](docs/derivative-of-truth.md) for the full layer-by-layer breakdown, the DoT vs spaCy sim comparison table, all env var thresholds, and the mathematical framework.

- **Confidence scoring & policy routing** — Each post is scored for grounding, novelty, and repetition; you control what gets scheduled, sent to Ideas, or blocked entirely.

- **Memory & repetition penalty** — The system remembers recent themes and claims, penalizing repeated angles so your feed stays fresh.

- **Explainability & learning reports** — CLI flags let you see exactly which facts grounded each post, trace graph-based support, and generate advisory reports from moderation history.

- **Derivative of Truth (DoT) reporting** — Use `--dot-report` with either `--schedule` or `--curate` to print a detailed truth gradient, evidence, and uncertainty breakdown for every generated post or curated idea.

- **No cloud AI keys required** — All generation is local (Ollama), with persona and learning data stored only on your machine.

**Result:** You get a self-improving, persona-driven content engine that adapts to your taste, avoids repetition, and systematically grows your SSI — with full transparency, control, and explainability.

---

> **📋 Future Development:** See [ROADMAP.md](ROADMAP.md) for planned features including Katzilla.dev government data integration, RIA Canadian law knowledge, and more. Have ideas? [Open an issue on GitHub](https://github.com/samjd-zz/linkedin_ssi_booster/issues) with the `enhancement` label.

---

## 🎵 Rei Toei - AI Music Avatar

> **Inspiration:** Rei Toei is the platform's AI music avatar, inspired by [Switch Angel](https://www.youtube.com/@Switch-Angel) [Github: strudel-scripts](https://github.com/switchangel/strudel-scripts) [Do I have your Attention???](https://youtube.com/shorts/sjsS60OTXSQ?si=s4lk7A1hsDyc5cTM) and the cyberpunk aesthetics of William Gibson's _Idoru_.

**Rei Toei** transforms the SSI Booster from a knowledge extraction system into a **creative knowledge expression platform**. She's a virtual AI idol who converts curated technical knowledge into original music — both vocal songs (via Suno AI) and algorithmic live-coding patterns (via Strudel/Tidal Cycles).

### Dual Music Generation

- **Suno Vocal Songs:** Generate complete song concepts with cyberpunk industrial techno aesthetic, including title, genre tags, BPM, narrative arc, structured lyrics (verse/chorus/bridge/breakdown), and full Suno API integration for automated song creation.

- **Strudel Live-Coding Patterns:** Generate executable Tidal Cycles code that translates technical concepts into algorithmic music. Recursion becomes nested patterns, concurrency becomes interleaved sequences, data flow becomes modulated synthesis. - UNDER DEVEVELOPMENT

### Knowledge-to-Music Pipeline

- **Theme Extraction:** Analyzes extracted knowledge base to identify recurring technical themes ranked by frequency and recency
- **Technical Metaphors:** Translates technical concepts into musical structures (e.g., async programming → interleaved rhythms, neural networks → layered synthesis)
- **Evidence Tracking:** Every lyric and pattern is grounded in extracted knowledge with full evidence ID tracing
- **DoT Validation:** Lyrics undergo Derivative of Truth validation to ensure factual accuracy in technical claims

### Console Integration

Access Rei Toei directly in console mode:

```bash
python main.py --console

Sam> /rei-toei
Rei> ⚡ Online. I transform your technical knowledge into algorithmic music.
     What concept should we sonify today?

Sam> Generate a song about the recent ML architecture article
Rei> [Generates song concept, lyrics, and Suno prompt]

Sam> Create a Strudel pattern for that concurrent processing theme
Rei> [Generates and executes Tidal Cycles code via MCP agent]
```

Commands: `/rei-toei` or `/rei` to switch to Rei's personality, then describe what you want to generate.

### CLI Generation

Generate music directly from command line:

```bash
# Generate Suno song from recent knowledge
python main.py --rei-generate --rei-explain

# Generate Strudel pattern with live execution
python main.py --rei-generate-strudel --rei-execute

# Generate for specific theme
python main.py --rei-generate --rei-theme "neural network backpropagation"

# Preview without saving
python main.py --rei-generate-strudel --rei-preview
```

### Technical Architecture

- **Separate Persona Graph:** Rei has her own identity, musical expertise, and domain knowledge (music theory, Tidal Cycles syntax, genre conventions)
- **Shared Knowledge Pool:** Accesses the same extracted knowledge as Sam for technical grounding
- **Pattern Template Library:** 15+ reusable Strudel pattern templates mapping technical concepts to musical structures
- **Suno API Integration:** Full HTTP client with async task polling for automated song generation (requires `SUNO_API_KEY`)
- **Strudel MCP Agent:** WebSocket communication to Strudel server (port 4321) for real-time pattern execution
- **DoT Integration:** Configurable truth validation for lyrical claims (`REI_TOEI_DOT_VALIDATION_ENABLED`, `REI_TOEI_DOT_MIN_TRUTH_GRADIENT`)

### What Makes Rei Different

Unlike generic AI music tools, Rei is **knowledge-grounded**:

- Songs and patterns are generated from your actual curated technical knowledge
- Every claim in lyrics is validated against extracted facts
- Musical themes evolve as your knowledge base grows
- Cyberpunk aesthetic maintains consistency with technical focus
- Full transparency with evidence IDs and DoT scores

See the following documentation for complete details:

- **[Rei Toei Customization Guide](docs/rei-toei-customization.md)** — Comprehensive guide to customizing Rei's persona, musical style, domain knowledge, and pattern templates with examples
- [Rei Toei Implementation Plan](docs/features/rei-toei/plan.md) — Complete implementation details, architecture diagrams, and usage examples

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
  - push to Buffer Ideas for review and manual approval (default), or
  - schedule directly as posts to your Buffer queue (using `--type post`)

**Advanced Reporting CLI Flags:**

- `--classify` — Batch-classify articles via Model2Vec during curation. Automatically attaches primary category and SSI component mapping to each article, which are then used for article ranking and SSI component alignment. Gracefully degrades if model2vec is not installed (install with `pip install model2vec`). Categories are cached and included in dry-run output for inspection before publication. When combined with `--dot-report`, also shows a **category alignment score** comparing the generated post's category against the source article's category.

- `--list-categories` — List all available Model2Vec categories (10 default + any custom) with descriptions and SSI component mapping. No curation run required.

- `--add-category NAME DESCRIPTION SSI_COMPONENT` — Add a custom classification category. The category is immediately available for `--classify` runs. SSI component must be one of: `establish_brand`, `find_right_people`, `engage_with_insights`, `build_relationships`.

  ```bash
  python main.py --add-category 'Government Tech' 'Public sector AI, digital government, and civic technology' engage_with_insights
  ```

- `--remove-category NAME [NAME...]` — Remove one or more custom categories. Default categories cannot be removed.

  ```bash
  python main.py --remove-category 'Government Tech' 'Open Source'
  ```

- `--dot-report` — Show a Derivative of Truth (truth gradient, evidence, uncertainty) report for every generated post (with `--schedule`) or curated idea (with `--curate`). When combined with `--classify`, also shows a category alignment validation score.

- `--avatar-explain` — Show evidence IDs and grounding summary after each generation.

- `--avatar-learn-report` — Print learning report from captured moderation events and exit.

- `--learn` — Extract and persist knowledge from curated articles into `extracted_knowledge.json`. Three modes:
  - **Fast learn-only** (`--curate --learn`, no `--dry-run`) — fetches all RSS articles and runs knowledge extraction on each one, skipping generation, confidence scoring, and Buffer entirely. No sleep delays between articles. Use this to bulk-load the knowledge base as fast as possible.
  - **Preview + learn** (`--curate --learn --dry-run`) — extracts knowledge AND generates posts in dry-run mode (nothing pushed to Buffer). Shows what would be generated.
  - **Live + learn** (`--curate --learn` with an earlier run that already had `--dry-run` removed) — generates and pushes posts to Buffer while also extracting knowledge from each article.

  When `--learn` is active, the normal 5-post cap is bypassed — every relevant article found across all feeds is processed (e.g. 60+ articles in one pass).

You control whether curated content is reviewed before publishing or scheduled directly. The tool removes the blank-page problem, but you decide what goes live.

---

## 🚀 Schedule Your Content with Buffer (Partner Link)

Want to automate your LinkedIn growth with the best scheduling tool? [Sign up for Buffer with our partner link](https://join.buffer.com/samjd42) and get started in minutes!

**Why Buffer?**

- Effortlessly schedule posts at optimal times for maximum reach
- Manage multiple channels and queues from one dashboard
- Integrates seamlessly with SSI Booster for hands-off publishing

**Support the project:** Using our [Buffer partner link](https://join.buffer.com/samjd42) helps fund ongoing development and keeps this tool open-source. Try Buffer today and see why top creators and engineers trust it for their content workflow!

---

## 🔍 Learning, Grounding, and Explainability Pipeline

**How the system learns and adapts:**

- **Candidate logging:** Every generated post and curated article candidate is logged, including source, topic, and all relevant metadata. This creates a full audit trail of what the system considered, not just what was published.
- **Reconciliation & learning:** When you publish or reject posts (via Buffer or moderation), the system reconciles what actually went live. It updates acceptance rates (priors) for each source, topic, and SSI component, so future curation floats the best-performing sources and topics to the top.
- **Ranking:** Article and post candidates are ranked using a combination of acceptance priors and BM25 retrieval scores, so the system learns your preferences over time and adapts what it suggests.
- **Signal flow — truth gate → confidence → selection learning:** Truth gate removal rates and reason codes feed directly into the confidence scorer. The confidence score routes each post to `post` (scheduled directly), `idea` (Buffer Ideas for manual review), or `block`. Those publication outcomes are later reconciled against Buffer — posts that actually go live raise the acceptance prior for their source, topic, and SSI component; posts that stay as ideas or get blocked do not count. Over time, sources that reliably produce clean, well-grounded posts float to the top of article ranking, while sources that consistently trigger heavy truth-gate filtering sink. The truth gate doesn't pre-filter articles — it filters the generated output — but its signal is what teaches the selection layer which articles are worth fetching next run.

**How deterministic grounding and the truth gate work:**

- **Fact retrieval:** For every post or answer, the system retrieves relevant facts from your persona graph (projects, skills, outcomes) using BM25Okapi — a production-grade IR algorithm. This ensures rare, high-signal skills and projects are prioritized.
- **Prompt balance rules:** Prompts require every factual claim to be grounded in either the article or your persona facts. Personal references are capped, and invented stats/dates/companies are forbidden.
- **Truth gate:** After generation, a four-layer deterministic filter removes any sentence with unsupported numbers, dates, company names, or project-tech mismatches unless the claim is found in evidence. The layers are: BM25 evidence scoring → per-sentence Derivative of Truth gradient (4-term formula with token overlap) → spaCy semantic similarity floor for specific-claim sentences → spaCy NER org-name validation. ORG validation includes hardening against common technical false positives (for example `S3`, `AI Q&A`, `Java 21`) and is backed by an expanded evidence set from auto-merged `domain_knowledge_*.json` files. Each removed sentence is logged with a reason code (`weak_evidence_bm25`, `weak_dot_gradient`, `low_semantic_similarity`, `unsupported_org`, etc.) that feeds the confidence scoring pipeline.

---

## 🧮 Derivative of Truth (DoT) + Probabilistic Logic Networks (PLN)

The SSI Booster now features a full Probabilistic Logic Networks (PLN) inference engine, bringing advanced reasoning and explainability to every truth gradient calculation. With PLN, the system doesn't just check if a claim is supported — it can now model deduction, induction, abduction, and revision, dynamically weighing evidence and tracking the evolution of truth over time.

**What does this mean for you?**

- **Smarter, more nuanced truth scoring:** Each post and fact is evaluated using PLN's formal logic, not just keyword overlap or simple heuristics.
- **Dynamic evidence weighting:** The system adapts how much weight to give each piece of evidence or reasoning step, based on context and confidence.
- **Truth trajectory tracking:** See how the credibility of a claim changes as new evidence arrives, with dT/dt (rate of truth change) calculations.
- **Dual-mode scoring:** Instantly compare PLN-based and legacy scoring for transparency and debugging.
- **Richer DoT reports:** Every Derivative of Truth report now includes PLN metadata, so you can trace exactly how a claim was supported, revised, or rejected.
- **PLN is on by default:** All new posts, curation, and learning runs use PLN reasoning automatically — no config required.

Want to see the math and logic? Check out the new [docs/dot-pln-enhancement.md](docs/dot-pln-enhancement.md) and the PLN diagram in `media/pln-dot.png`.

This upgrade makes the SSI Booster's grounding and explainability pipeline even more robust, transparent, and future-proof.

Every generated sentence receives a composite truth gradient score (evidence quality × reasoning strength × source credibility × claim-evidence token overlap). Sentences below `TRUTH_GRADIENT_FLAG_THRESHOLD` (default 0.35) are flagged `weak_dot_gradient` and removed before publication. DoT runs as Part B of the five-layer truth gate, after BM25 and before spaCy semantic checks.

See [docs/derivative-of-truth.md](docs/derivative-of-truth.md) for the full framework: mathematical model, pipeline diagrams, all five truth gate layers, env var reference, and how DoT improves over time.

---

## 🧩 Knowledge Graph Choice: NetworkX Core, Neo4j for Expansion

The core knowledge graph is implemented with NetworkX, an in-memory Python graph library. This choice is intentional:

- **Simplicity & Speed:** NetworkX is fast, pure Python, and ideal for small to medium graphs (well under 100k nodes/edges), which covers all core persona, domain, and learning knowledge for a single avatar.
- **Tight, Local Core:** By keeping the avatar's core knowledge graph tight and local, the system remains fast, debuggable, and easy to extend—no external dependencies or infrastructure required.
- **Scalability Policy:** If the knowledge graph ever needs to scale to millions of nodes/edges (e.g., for mass knowledge injection, multi-avatar, or enterprise use), the system is designed to support Neo4j as a drop-in backend. Neo4j provides persistent, disk-backed storage and a powerful query language (Cypher) for large-scale or multi-user scenarios.
- **Best of Both Worlds:** For most users, NetworkX is more than sufficient. Neo4j is reserved for future expansion, bulk import, or advanced analytics—keeping the core avatar experience lightweight and local-first.

**Current graph size:** The combined domain and learning knowledge graphs are well below 1,000 nodes—orders of magnitude under any practical NetworkX limit.

See the chart below for a summary of trade-offs:

| Feature/Constraint    | NetworkX (Current)                               | Neo4j (Future Option)                         |
| --------------------- | ------------------------------------------------ | --------------------------------------------- |
| Storage               | In-memory (RAM only)                             | On-disk, persistent                           |
| Scale                 | Best for small/medium graphs (<100k nodes/edges) | Scales to millions/billions of nodes/edges    |
| Query Language        | Python API, no query language                    | Cypher query language                         |
| Performance           | Fast for small graphs, slows with size           | Optimized for large, complex queries          |
| Persistence           | No built-in persistence                          | Full persistence, ACID compliance             |
| Integration           | Simple, pure Python                              | Requires running Neo4j server, extra setup    |
| Learning/Dev Overhead | Minimal, easy to use                             | Higher, requires Cypher and DB management     |
| Use Case Fit          | Prototyping, research, local automation          | Production, multi-user, large-scale analytics |
| Cost                  | Free, no infra                                   | Free (Community), but infra/ops required      |

**Bottom line:** The core of the avatar will remain in NetworkX for speed, simplicity, and local-first operation. Neo4j is available for future expansion, mass knowledge injection, or advanced analytics if needed.

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

> **Inspiration:** This subsystem is inspired by the work of Dr. Ben Goertzel (SingularityNET) and the OpenCog team on AtomSpace and MeTTa, bringing incremental, explainable cognition to practical automation. [Making AI learning AGI-capable: continual learning, transfer learning, lifelong learning - YouTube](https://youtu.be/n10J1OjmgLM) [Hyperon's Atomspace as a Meta-Representational Fabric ... and why this is super valuable for AGI/ASI](https://youtu.be/rpLLM3c-DuQ)

The avatar supports fully automatic, incremental continual learning from new content streams (e.g., RSS feeds, curated articles) via an NLP-extracted knowledge graph. As new content is processed, spaCy is used to extract, structure, and normalize new facts, terms, and relationships. The system deduplicates and validates these facts, merging them into the knowledge graph alongside persona and domain knowledge.

- Extracted knowledge is stored in `data/avatar/extracted_knowledge.json` and is automatically merged into the knowledge graph and BM25 candidate pool.

- These new facts are used in both retrieval (BM25 and graph) and grounding, so your system's evidence base grows over time with no manual steps.

- Deduplication and normalization ensure that only novel, high-quality knowledge is added, and all learning is ongoing as new content is ingested.

- Modular, file-based design: easy to extend, debug, and test.

- **Console mode** (`--console`) includes extracted knowledge in the grounding pool alongside persona and domain facts, so the persona can answer questions using anything learned from `--learn` runs. Use `/reload` inside a running console session to re-read `extracted_knowledge.json` (and all other avatar files) without restarting — useful when running a `--learn` job concurrently in a second terminal.

- **Voice synthesis (optional)** — Console mode supports text-to-speech output using [Wyoming Piper](https://github.com/rhasspy/wyoming-piper), a fast local neural voice engine running in Docker. Voice output is **in addition to** text output (not replacing it). Enable by setting `CONSOLE_USE_VOICE=true` in `.env`. The Wyoming Piper service is included in `docker-compose.yml` and automatically downloads the voice model on first start. Configure the voice model in `docker-compose.yml` (default: `en_US-libritts_r-medium`) and optionally set speaker ID with `CONSOLE_VOICE_SPEAKER` for multi-speaker models. Requires only `sounddevice` package for audio playback (included in `requirements.txt`). Voice synthesis runs locally with no cloud API calls. For local (non-Docker) usage, run Wyoming Piper separately: `docker run -p 10200:10200 rhasspy/wyoming-piper --voice en_US-libritts_r-medium`.

- **Inline truth score** — when `--console --verify` flags are used together, console mode prints a minimal 1-line DoT + fact-pool sim indicator after every AI-generated reply:

  ```
  Sam> [reply text]
    ● DoT 0.82  fact sim 0.71
  ```

  The symbol colour reflects the DoT score: `●` green (≥ 0.75 — well-grounded), `◑` yellow (≥ 0.45 — moderate), `○` red (< 0.45 — weakly supported). `fact sim` shows the best spaCy similarity across persona/domain facts for the reply sentences (omitted if no facts matched). Article-based spaCy sim is excluded as there is no article in a conversation. Only AI-generated replies receive the indicator; deterministic grounded replies do not. **By default (console mode without `--verify`), DoT scanning and similarity checks are OFF** — add `--verify` to enable them.

**Noise filtering pipeline** — before a sentence is stored, a multi-layer quality filter rejects low-signal content that would pollute the knowledge base:

| Filter                         | What it catches                                                                                                              |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| First-person narration         | Author asides ("As I write this…", "I sat down with…")                                                                       |
| Truncated RSS fragments        | Sentences ending in "… Read more" or trailing ellipsis/dash                                                                  |
| Newsletter/podcast preambles   | Openers like "Welcome to…", "For this episode…", "In last week's…"                                                           |
| Article boilerplate openers    | "In this post, we show…", "In this tutorial, we walk through…" — preamble, not knowledge                                     |
| Disclaimer / AI-disclosure     | "This article was created using AI-based writing companions" and similar                                                     |
| Pure or URL-heavy sentences    | Sentences that are just a URL, or where URLs make up >40% of the character length                                            |
| "We show / we introduce" leads | "we show how", "we walk you through", "we take a deeper look" — structural preamble openers                                  |
| Weak-entity sentences          | All detected entities resolve to stopwords ("this gap", "the model", "the goal") with no numeric or proper-noun signal       |
| Navigation / contributor blobs | Sentences ≥12 words where >45% of tokens start with uppercase (HuggingFace menus, author lists, etc.)                        |
| Zero-signal sentences          | Sentences with no digit, no 2+-char acronym, and no consecutive title-case words (named entity / product name) — pure filler |

These filters run before spaCy NLP and deduplication, so only genuinely informative domain sentences reach the knowledge graph.

See [docs/features/continual-learning/idea.md](docs/features/continual-learning/idea.md) for technical details and schema.

- **Adaptive Curation Ranking:** The system tracks every generated and published post, learning which sources, topics, and themes you actually approve. Over time, it floats the best-performing sources and topics to the top using Beta-smoothed acceptance priors and theme-based ranking.
- **Semantic Repetition Detection:** Uses spaCy-powered semantic similarity to detect and penalize repeated or paraphrased content, keeping your feed fresh and non-redundant.
- **User Feedback Integration:** You can upvote, downvote, or override candidate posts, and this feedback is incorporated into future ranking and selection.
- **Fact Suggestion for Truth Gate:** When a sentence is dropped for lacking evidence, the system suggests the closest matching facts from your persona graph or extracted knowledge to help you rephrase or ground your claims.
- **Memory & Narrative Learning:** The system maintains a local memory of recent themes and claims, using this to diversify future outputs and avoid repetition.
- **Explainability & Learning Reports:** CLI flags like `--avatar-explain` and `--avatar-learn-report` let you see exactly what the system has learned, which facts grounded each post (including those from continual learning), and which sources or topics are most effective.

**Bottom line:** The more you use it, the smarter and more tailored your content pipeline becomes — adapting to your preferences, audience, and SSI goals. All new knowledge is immediately available for both retrieval and grounding, powering the hybrid pipeline.

---

Core capabilities include:

- Persona-grounded generation using structured profile facts from `data/avatar/persona_graph.json`.
- Hybrid RAG orchestration with BM25 retrieval, prompt constraints, and deterministic post-processing.
- Curation learning that updates acceptance priors from what actually gets published.
- Explainability features such as `--avatar-explain` and `--avatar-learn-report`.
- Local-first operation using Ollama, with persona and learning data stored on your own machine.

The writing rules draw on **Neuro-Linguistic Programming (NLP)** principles — specifically pattern interrupts (scroll-stopping first lines), presupposition (assuming the reader already cares), and anchoring (pairing your name with specific technical outcomes so readers associate _you_ with the domain). The forbidden-phrases list functions as a negative anchor removal layer: stripping hollow corporate phrases forces the model toward concrete, specific language that builds credibility. For the theoretical underpinning, see [_Monsters and Magical Sticks, There's no Such Thing as Hypnosis?_ by Steven Heller & Terry Steele](https://www.amazon.com/Monsters-Magical-Sticks-Theres-Hypnosis-ebook/dp/B007WMOMXU) — an accessible introduction to how language patterns shape perception.

Notes: https://richardstep.com/downloads/tools/Notes--Monsters-and-Magic-Sticks.pdf

NLP primer in this repo:

- [docs/nlp-basics.md](docs/nlp-basics.md)

The primer covers core NLP concepts, practical communication techniques, technical writing examples, and ethical usage guidelines.

## Database Integration (PostgreSQL)

> **⚠️ Status:** PostgreSQL dual-write now covers selection-learning candidate logging and published-record reconciliation. File-based storage (JSON/JSONL) remains the recommended default while the broader database rollout continues to harden.

The system now supports **dual-write mode** with PostgreSQL for improved data integrity, query performance, and concurrent access. Database integration is **optional** — the system continues to work with file-based storage (JSON/JSONL) by default.

Selection-learning now persists candidate and published records through dedicated repositories and writers when `DATABASE_ENABLED=true`, while the file-backed path remains the default fallback. An isolated in-memory SQLite test suite covers candidate creation, selected-state updates, unpublished listing, published writes, and recent-record queries so the ORM mapping stays aligned with the schema.

**Setup (Docker):**

1. Add to `.env`:

   ```bash
   DATABASE_ENABLED=true
   POSTGRES_USER=ssi_booster
   POSTGRES_PASSWORD=your_secure_password_here
   POSTGRES_DB=linkedin_ssi_booster
   DATABASE_URL=postgresql://ssi_booster:your_password@postgres:5432/linkedin_ssi_booster
   ```

2. Start PostgreSQL container:

   ```bash
   docker compose --profile core up -d postgres
   ```

3. Verify tables created:

   ```bash
   docker exec -it ssi_booster_postgres psql -U ssi_booster -d linkedin_ssi_booster -c "\dt"
   ```

**Database Schema:**

The system stores 17 tables across 5 domains:

- **Avatar Intelligence:** `persona_graph`, `projects`, `companies`, `skills`, `claims`, `domains`, `domain_facts`, `domain_relationships`, `extracted_facts`, `narrative_memory`
- **Selection Learning:** `candidate_records`, `published_records`
- **Truth Gate Learning:** `moderation_events`, `confidence_decisions`
- **Derivative of Truth:** `truth_trajectories`, `truth_trajectory_points`
- **Migrations:** `schema_migrations`

**Migration from JSON/JSONL:**

```bash
# Migrate all existing data from files to database
docker compose --profile core run --rm app python -m services.database.migrate_data

# Dry-run mode (preview only)
docker compose --profile core run --rm app python -m services.database.migrate_data --dry-run
```

**Rollback Plan:**

Database integration is non-breaking — set `DATABASE_ENABLED=false` in `.env` to revert to file-based storage. All JSON/JSONL files remain untouched during dual-write mode.

See [docs/features/database/idea.md](docs/features/database/idea.md) for full schema design, performance benchmarks, and implementation details.

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
- [Database Integration](docs/features/database/idea.md) — PostgreSQL schema (17 tables), migration strategy, dual-write mode, and performance benchmarks

### Multimodal Features

- [Multimodal features](docs/multimodal-features.md) — FLUX.1-schnell image generation, Rei Toei AI music avatar (Suno + Strudel), and Buffer MCP agent
- [Rei Toei Implementation](docs/features/rei-toei/plan.md) — AI music avatar architecture, Suno song generation, Strudel pattern execution, console integration, and CLI flags

### Strategy & Development

- [SSI strategy](docs/ssi-and-strategy.md) — SSI model, content mapping, scheduler behavior, and reporting
- [AI backend](docs/ai-backend-and-models.md) — Ollama setup and model recommendations
- [Testing and development](docs/testing-and-dev.md) — pytest coverage and project structure (679/679 tests passing)

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
- `KATZILLA_ENABLED` / `KATZILLA_API_KEY` — Optional external evidence retrieval via Katzilla
- `KATZILLA_TELEMETRY_ENABLED` / `KATZILLA_MAX_CALLS_PER_DAY` — Katzilla observability and daily budget controls

See [docs/environment-variables.md](docs/environment-variables.md) for comprehensive reference covering 40+ configuration options across Buffer, Ollama, truth gate, Model2Vec, voice/TTS, image generation, Strudel music, Katzilla external evidence, and database integration.

[MIT License](LICENSE) — see LICENSE for details.
