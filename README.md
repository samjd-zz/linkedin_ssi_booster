<p align="center">
  <img src="media/favicons/logo1.png" alt="LinkedIn SSI Booster Logo" width="150">
</p>

# LinkedIn SSI Booster - :muscle: POWERED by Buffer.com!

##### <u>— Persona-Grounded Truth-Gated Adaptive-Continual-Learning Hybrid-RAG Agent with Domain-Knowledge-Graph</u>


[![Version alpha-v0.0.2.7](https://img.shields.io/badge/version-alpha--v0.0.2.7-orange.svg)]()[![spaCy](https://img.shields.io/badge/spaCy-NLP-09A3D5.svg?logo=spacy&logoColor=white)](https://spacy.io/)[![FLUX.1](https://img.shields.io/badge/FLUX.1-Image%20Gen-FF6B6B.svg)](https://github.com/black-forest-labs/flux)[![Strudel](https://img.shields.io/badge/Strudel-Music%20Agent-9B59B6.svg)](https://strudel.cc/)[![CUDA 12.4](https://img.shields.io/badge/CUDA-12.4-76B900.svg?logo=nvidia)](https://developer.nvidia.com/cuda-toolkit)[![Buffer API](https://img.shields.io/badge/Buffer-API-231F20.svg)](https://buffer.com/)[![License MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

<img src="media/favicons/2-score-ring_256x256.png" alt="SSI Score Ring" width="80" align="right">
<img src="media/favicons/2-score-ring_256x256.png" alt="SSI Score Ring" width="80" align="left">

**LinkedIn SSI Booster** isn't just a prompt wrapper — it's an adaptive continual learning automation system for content, curation, and persona growth. It combines spaCy-based NLP, a persona graph, BM25 retrieval, a truth gate, confidence scoring, a NetworkX-powered knowledge graph, and local memory to generate, curate, rank, and route posts.

Sign up for Buffer with my partner link — http://join.buffer.com/samjd42 — to start scheduling, publishing, and analyzing your social posts in one place while supporting my work.

------

## 🧠 Intelligence Stack

##### _<ul><u>— Why This Is Smarter Than Just 'AI Writes Posts'</u></ul>_

- **Advanced NLP with spaCy** — Theme/claim extraction, semantic similarity, sentiment/tone analysis, and two advanced curation/grounding features:
  - **Fact Suggestion:** When the truth gate drops a sentence, spaCy suggests the closest matching fact or evidence from your persona graph, or recommends how to rephrase for grounding.
  - **Contextual Summarization:** spaCy generates concise, context-aware summaries of curated articles, improving the quality of commentary and learning signals.

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

## 🎨 New: Local Image Generation (FLUX.1-schnell)

The system now includes a high-fidelity image generation pipeline powered by **FLUX.1-schnell** running locally on your GPU. This allows you to generate professional, persona-aligned visuals for your LinkedIn posts without cloud costs or privacy concerns.

- **VRAM Optimized:** Built specifically for consumer hardware (tested on **RTX 3060 12GB**).
- **GGUF Quantization:** Uses 4-bit quantized "brains" to fit a state-of-the-art transformer model into local memory.
- **Sequential Execution:** Intelligent VRAM management automatically unloads LLM models before firing up the image generator to prevent OOM (Out of Memory) crashes.
- **Aesthetic Grounding:** Prompts are generated by the agent to match the technical tone and theme of your specific post.

## 🎵 New: Strudel Live-Coding Music Agent

> **Inspiration:** This exciting new addition to the platform is inspired by [Switch Angel](https://www.youtube.com/@Switch-Angel) [Github: strudel-scripts](https://github.com/switchangel/strudel-scripts) [Do I have your attention???](https://youtube.com/shorts/sjsS60OTXSQ?si=s4lk7A1hsDyc5cTM) 

The system now includes an autonomous music generation agent powered by **Strudel.js** (live-coding music language) and the **Strudel MCP server**. This agent generates algorithmic music patterns using Gemma 4 and sends them to a WebSocket bridge for real-time audio playback.

- **Autonomous Agent Service:** Runs as a standalone Docker service (`strudel-mcp-agent`) in the stack.
- **Live-Coding Generation:** Uses Gemma 4's native system prompt support to generate clean, executable Strudel.js code without markdown fluff.
- **WebSocket Bridge Integration:** Connects to the Strudel MCP server's WebSocket interface to evaluate patterns in real-time.
- **Container-Native:** All components (Ollama, Strudel MCP server, agent) run in Docker with automatic dependency management and health checks.
- **Persona-Aligned Music:** Future enhancement will tie music generation to LinkedIn post themes and sentiment for multimedia content creation.

## 📤 New: Buffer MCP Agent

The system now includes an autonomous Buffer integration agent powered by the **Buffer Model Context Protocol (MCP)**. This agent generates Buffer API requests using Gemma 4 and sends them directly to Buffer's MCP server for seamless social media management.

- **Autonomous Agent Service:** Runs as a standalone Docker service (`buffer-mcp-agent`) in the stack.
- **Natural Language Interface:** Uses Gemma 4 to translate plain English commands into properly formatted Buffer MCP requests.
- **Direct MCP Integration:** Connects to Buffer's official MCP server at `https://mcp.buffer.com/mcp` — no custom bridge required.
- **Full Buffer API Access:** List channels, create posts, manage drafts, schedule content, and more via conversational commands.
- **Container-Native:** Runs alongside Ollama in Docker with automatic authentication using your `BUFFER_API_KEY`.
- **Future Enhancement:** Voice-controlled Buffer operations and automatic post-performance analytics reporting.

------

## 🏆 What is the LinkedIn SSI?

The [LinkedIn Social Selling Index](https://www.linkedin.com/sales/ssi) is a 0–100 score LinkedIn updates daily. It measures how effectively you build your personal brand, find the right people, engage with insights, and build relationships — the four pillars LinkedIn's algorithm uses to determine how widely your content and profile are surfaced to others.

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
- Integrates seamlessly with LinkedIn SSI Booster for hands-off publishing

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

## 🗺️ Docs map

- [Setup guide](docs/setup.md) — environment, dependencies, persona graph, and calendar setup.
- [Architecture guide](docs/architecture.md) — learning pipeline, grounding flow, truth gate, and curation ranking.
- [Persona and Avatar Intelligence](docs/persona-and-avatar.md) — persona graph, system prompt, memory, confidence, explainability, and continual learning.
- [Continual Learning (NLP-extracted knowledge)](docs/features/continual-learning/idea.md) — how the avatar accumulates new knowledge from external content.
- [Domain Knowledge Graph](docs/domain-knowledge.md) — domain-level expertise that isn't tied to specific projects.
- [Usage guide](docs/usage-schedule-curate-console.md) — scheduling, curation, console mode, channels, and CLI examples.
- [SSI strategy](docs/ssi-and-strategy.md) — SSI model, content mapping, scheduler behavior, and reporting.
- [AI backend](docs/ai-backend-and-models.md) — Ollama setup and model recommendations.
- [Testing and development](docs/testing-and-dev.md) — pytest coverage and project structure. All tests pass (343/343)
- [Selection learning](docs/selection-learning.md) — candidate logging, reconciliation, and acceptance priors.
- [Derivative of Truth (DoT) framework](docs/derivative-of-truth.md) — mathematical model, five-layer truth gate pipeline, DoT vs spaCy sim comparison, env var reference, and how scoring improves over time.

## 🐳 Docker Compose (Recommended)

Run the full stack — Ollama LLM server + Wyoming Piper TTS + SSI Booster app — with a single command, no local Python environment required.

The stack uses **Docker Profiles** to manage hardware resources. Run the lightweight `core` profile daily and only spin up the `full` profile (FLUX image gen) when you need post visuals.

### Services overview

| Service | Profile | Description |
| --- | --- | --- |
| `ollama` | `core`, `full` | Ollama LLM server — GPU-accelerated, persisted via named `ollama_data` volume |
| `ollama-init` | `core`, `full` | One-shot init container — pulls `OLLAMA_MODEL` + `OLLAMA_MODEL_FALLBACK` then exits |
| `piper` | `core`, `full` | Wyoming Piper TTS server on port `10200` — downloads voice model on first start |
| `strudel-music-server` | `core`, `full` | Strudel MCP server — provides WebSocket API for live-coding music evaluation on port `3000` |
| `strudel-mcp-agent` | `core`, `full` | Strudel music generation agent — uses Gemma 4 to generate Strudel.js patterns and sends to MCP server |
| `buffer-mcp-agent` | `core`, `full` | Buffer MCP agent — uses Gemma 4 to generate Buffer API requests and sends to official Buffer MCP server |
| `flux-init` | `full` | One-shot Alpine container — downloads FLUX.1-schnell GGUF weights via Civitai; `flux-app` depends on it |
| `flux-app` | `full` | FLUX.1-schnell inference service — compiles GPU-accelerated `llama-cpp-python`; waits for `flux-init` to complete |
| `app` | `core`, `full` | SSI Booster application — Python 3.11 + spaCy (`core_base` Dockerfile stage) |

### 1. Prerequisites

- **Docker Engine** (Linux) or **Docker Desktop** (Windows/Mac)
  - Windows: enable **WSL 2** in Docker Desktop settings for GPU access
- **NVIDIA Container Toolkit** (Linux only) — required for GPU passthrough; Docker Desktop handles this automatically on Windows/WSL 2
- **CUDA 12.4.1+** drivers on the host
- **RTX 3060 12 GB or better** — strongly recommended for FLUX.1-schnell; 8 GB cards may st
- **Node.js environment in Playwright image** — handled automatically by `strudel-music-server` container (no manual setup required)ruggle
- **Civitai API key** — required by `flux-init` to download the GGUF model weights
- **PulseAudio** running on the host — required for voice output (`CONSOLE_USE_VOICE=true`)

### 2. First-time setup

```bash
# 1. Copy and fill in your environment file
cp .env.example .env
# Required: BUFFER_API_KEY, CIVITAI_API_KEY, PERSONA_SYSTEM_PROMPT, SSI_* vars
# OLLAMA_BASE_URL is overridden to http://ollama:11434 by docker-compose.yml automatically

# 2. Copy avatar data files (bind-mounted into the container at runtime)
cp data/avatar/persona_graph.example.json   data/avatar/persona_graph.json
cp data/avatar/domain_knowledge.example.json data/avatar/domain_knowledge.json
cp data/avatar/narrative_memory.example.json data/avatar/narrative_memory.json
cp content_calendar.example.py               content_calendar.py

# Optional domain knowledge packs — auto-merged at load time
cp data/avatar/domain_knowledge_java.json   data/avatar/domain_knowledge_java.json
cp data/avatar/domain_knowledge_python.json data/avatar/domain_knowledge_python.json

# 3. Edit persona_graph.json with your real career facts
```

> **FLUX model weights:** When running `--profile full`, `flux-init` downloads the GGUF weights automatically before `flux-app` starts. No manual step required. To pre-download weights without starting the full stack: `docker compose --profile full run --rm flux-init`

### 3. Launch the stack

Use `run.sh` — it auto-detects your user ID for PulseAudio passthrough:

```bash
# Standard mode — LLM + TTS + analytics (daily use)
bash run.sh --profile core up -d

# Full mode — adds FLUX image generation
bash run.sh --profile full up -d

# Or use docker compose directly (no audio passthrough)
docker compose --profile core up -d
```

`ollama-init` will pull `OLLAMA_MODEL` and `OLLAMA_MODEL_FALLBACK` on first start then exit. Under `--profile full`, `flux-init` runs first, then `flux-app` starts once weights are downloaded, then `app` starts. Leave `ollama`, `piper`, `flux-app`, and `app` running.

### 4. Run commands

```bash
# Interactive persona console with voice (TTY required)
docker compose --profile core run --rm -it app python main.py --console

# Console with DoT verification enabled
docker compose --profile core run --rm -it app python main.py --console --verify

# Dry-run schedule (no Buffer calls)
docker compose --profile core run --rm app python main.py --schedule --week 1 --dry-run

# Curate AI news → Buffer Ideas
docker compose --profile core run --rm app python main.py --curate

# Monitor Strudel agent logs
docker compose logs -f strudel-mcp-agent

# Monitor Buffer MCP agent logs
docker compose logs -f buffer-mcp-agent

# Run Buffer MCP agent with custom prompt (one-off)
docker compose --profile core run --rm buffer-mcp-agent python agents/buffer_mcp_agent.py

# Record today's SSI scores
docker compose --profile core run --rm app python main.py --save-ssi 10.49 9.69 11.0 12.15
```

### Docker notes

| Topic | Detail |
| Strudel MCP server | Clones [williamzujkowski/strudel-mcp-server](https://github.com/williamzujkowski/strudel-mcp-server) on first start and builds automatically — no manual setup required |
| Strudel agent code | Mounted read-only from `./agents/` — edit `strudel_mcp_agent.py` and restart service to apply changes |
| Rebuilding after code changes | `docker compose build app` (or `strudel-mcp-agent` for agent-only changes)
| `OLLAMA_BASE_URL` | Overridden to `http://ollama:11434` by `docker-compose.yml` — do not change it in `.env` for Docker use |
| Ollama model storage | Persisted in the named `ollama_data` Docker volume (declared at the bottom of `docker-compose.yml`) — survives `docker compose down` and container restarts |
| Runtime data (`data/`, `yt-vid-data/`) | Bind-mounted from the host — changes are visible immediately |
| Voice / audio | `run.sh` exports `USER_UID=$(id -u)` and mounts the PulseAudio socket; requires `CONSOLE_USE_VOICE=true` in `.env` |
| FLUX model weights | Stored in `./models/flux/` on the host — downloaded by `flux-init`, mounted read-only into `flux-app` and `app` |
| Rebuilding after code changes | `docker compose build app` |
| GPU passthrough | All GPU services use `deploy.resources.reservations.devices` — requires [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) on Linux |

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

Copy `.env.example` to `.env` and fill in the values. Key variables:

```bash
# Buffer API
BUFFER_API_KEY=your_buffer_api_key_here

# Ollama LLM
OLLAMA_MODEL=gemma4:e4b              # primary model
OLLAMA_MODEL_FALLBACK=qwen3.5:9b     # fallback on empty/error response
OLLAMA_BASE_URL=http://localhost:11434  # overridden to http://ollama:11434 in Docker
OLLAMA_NUM_CTX=32768                 # context window (tokens)

# Image generation (FLUX — full profile only)
CIVITAI_API_KEY=your_civitai_key
FLUX_MODEL_PATH=/app/models/flux/flux1-schnell-Q4_K_S.gguf
IMAGE_OUTPUT_DIR=/app/yt-vid-data

# Voice / TTS (Docker — use run.sh for audio passthrough)
CONSOLE_USE_VOICE=true
WYOMING_PIPER_HOST=piper             # 'localhost' for local dev
WYOMING_PIPER_PORT=10200
CONSOLE_VOICE_SPEAKER=896            # speaker ID for en_US-libritts_r-medium

# PulseAudio passthrough — set automatically by run.sh
HOST_UID=1000
PULSE_RUNTIME_DIR=/run/user/1000/pulse
```

**LLM & retrieval**

- `OLLAMA_MODEL` — Primary model for all generation calls (e.g. `gemma4:e4b`).
- `OLLAMA_MODEL_FALLBACK` — Auto-retried once on empty output or error (default: `qwen3.5:9b`).
- `OLLAMA_BASE_URL` — Ollama server URL. Overridden to `http://ollama:11434` in Docker.
- `OLLAMA_NUM_CTX` — Context window size in tokens (default: `16384`; `32768` recommended for grounded prompts).

**Truth gate**

- `TRUTH_GATE_BM25_THRESHOLD` — Min BM25 score for a sentence to be considered supported (default: `1.0`; `0.75` = permissive, `2.0` = strict).
- `TRUTH_GATE_SPACY_SIM_FLOOR` — Min spaCy cosine sim between a sentence and the source article for numeric/org/year sentences (default: `0.10`). Curation mode only.
- `TRUTH_GATE_FACT_SIM_FLOOR` — Min spaCy cosine sim between a sentence and the best-matching persona/domain fact (default: `0.05`). Runs in all modes including console.

**Continual learning**

- `EXTRACTED_CONTEXT_LIMIT` — Max extracted facts injected into curation prompts (default: `10`).
- `EXTRACTED_EVIDENCE_COUNT` — Max extracted facts used as evidence per article during grounding/DoT (default: `2`).
- `TOPIC_SIGNAL_WINDOW` — Number of most-recent extracted facts used to build adaptive topic signal (default: `50`).

**Confidence & routing**

- `AVATAR_CONFIDENCE_POLICY` — Publish-safety routing: `balanced` (default), `strict`, or `draft-first`.
- `AVATAR_LEARNING_ENABLED` — Enable narrative memory and moderation logging (default: `true`).
- `AVATAR_MAX_MEMORY_ITEMS` — Max items retained in narrative memory before FIFO trim (default: `200`).

**Model2Vec classification**

- `MODEL2VEC_ENABLED` — Enable static embedding classification (default: `true`; requires `pip install model2vec`).
- `CURATE_CLASSIFY` — Auto-classify articles on every `--curate` run, equivalent to always passing `--classify` (default: `false`).

**SSI focus weights** (should sum to 100)

- `SSI_FOCUS_ESTABLISH_BRAND` / `SSI_FOCUS_FIND_RIGHT_PEOPLE` / `SSI_FOCUS_ENGAGE_WITH_INSIGHTS` / `SSI_FOCUS_BUILD_RELATIONSHIPS` — Pillar weights for post selection. Bump a lagging pillar up.

**Voice / audio**

- `CONSOLE_USE_VOICE` — Enable Wyoming Piper TTS in console mode (default: `false`). Use `bash run.sh` for Docker to get PulseAudio passthrough.
- `WYOMING_PIPER_HOST` / `WYOMING_PIPER_PORT` — TTS server address. Use `piper`/`10200` in Docker, `localhost`/`10200` for local dev.

**Strudel music generation**

- `OLLAMA_HOST` — Ollama server URL for Strudel agent (default: `http://localhost:11434`; overridden to `http://ollama:11434` in Docker).
- `STRUDEL_WS_URL` — WebSocket URL for Strudel MCP server (default: `ws://localhost:4321`; overridden to `ws://strudel-music-server:4321` in Docker).
- `STRUDEL_MCP_URL` — HTTP URL for Strudel MCP server (default: `http://localhost:3000`; set to `http://strudel-music-server:3000` in Docker).
- `CONSOLE_VOICE_SPEAKER` — Speaker ID for multi-speaker voices (e.g. `896` for `en_US-libritts_r-medium`).
- `HOST_UID` / `PULSE_RUNTIME_DIR` — Set automatically by `run.sh`. Used by `docker-compose.yml` to mount the PulseAudio socket for your user.

**Image generation**

- `CIVITAI_API_KEY` — Required by `flux-init` to download FLUX GGUF weights.
- `FLUX_MODEL_PATH` — Path to the GGUF model inside the container (default: `/app/models/flux/flux1-schnell-Q4_K_S.gguf`).
- `IMAGE_OUTPUT_DIR` — Where generated images are saved inside the container (default: `/app/yt-vid-data`).

The setup flow requires a configured `.env`, a filled-in persona graph, a narrative memory file, and a personalized content calendar before useful scheduling or curation runs begin.

[MIT License](LICENSE) — see LICENSE for details.
