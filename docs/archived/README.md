# LinkedIn SSI Booster — Persona-Grounded Learning · Hybrid RAG Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version: alpha-v0.0.1.5](https://img.shields.io/badge/version-alpha--v0.0.1.5-orange.svg)]()

Automates LinkedIn post generation and scheduling via local Ollama to systematically grow your LinkedIn Social Selling Index (SSI) score.

## 🧠 Intelligence Stack — Why This Is Smarter Than Just 'AI Writes Posts'

**LinkedIn SSI Booster** isn't just a prompt wrapper — it's a full-stack, learning automation system for content, curation, and persona growth. Here's what makes it unique:

- **Advanced NLP with spaCy** — Theme/claim extraction, semantic similarity, sentiment/tone analysis, and two advanced curation/grounding features:
  - **Fact Suggestion:** When the truth gate drops a sentence, spaCy suggests the closest matching fact or evidence from your persona graph, or recommends how to rephrase for grounding.
  - **Contextual Summarization:** spaCy generates concise, context-aware summaries of curated articles, improving the quality of commentary and learning signals.
- **Persona-grounded generation** — Every post is written in your real technical voice, with facts, projects, and outcomes pulled from your private persona graph (not just keywords or a bio blurb).
- **Hybrid RAG + agent pipeline** — Combines BM25 retrieval, deterministic validation, and multi-step agent orchestration for high factuality and variety.
- **Curation learning loop** — The system tracks every generated candidate, learns which ones you actually publish, and automatically floats the best sources/topics to the top in future runs (Beta-smoothed acceptance priors per source/SSI component).
- **Truth gate** — Post-generation filter removes unsupported claims (numbers, dates, company names, project-tech mismatches) for maximum credibility.
- **Confidence scoring & policy routing** — Each post is scored for grounding, novelty, and repetition; you control what gets scheduled, sent to Ideas, or blocked entirely.
- **Memory & repetition penalty** — The system remembers recent themes and claims, penalizing repeated angles so your feed stays fresh.
- **Explainability & learning reports** — CLI flags let you see exactly which facts grounded each post, and generate advisory reports from moderation history.
- **No cloud AI keys required** — All generation is local (Ollama), with persona and learning data stored only on your machine.

**Result:**
You get a self-improving, persona-driven content engine that adapts to your taste, avoids repetition, and systematically grows your SSI — with full transparency and control.

## 🔍 Learning, Grounding, and Explainability Pipeline

**How the system learns and adapts:**

- **Candidate logging:** Every generated post and curated article candidate is logged, including source, topic, and all relevant metadata. This creates a full audit trail of what the system considered, not just what was published.
- **Reconciliation & learning:** When you publish or reject posts (via Buffer or moderation), the system reconciles what actually went live. It updates acceptance rates (priors) for each source, topic, and SSI component, so future curation floats the best-performing sources and topics to the top.
- **Ranking:** Article and post candidates are ranked using a combination of acceptance priors and BM25 retrieval scores, so the system learns your preferences over time and adapts what it suggests.

**How deterministic grounding and the truth gate work:**

- **Fact retrieval:** For every post or answer, the system retrieves relevant facts from your persona graph (projects, skills, outcomes) using BM25Okapi — a production-grade IR algorithm. This ensures rare, high-signal skills and projects are prioritized.
- **Prompt balance rules:** Prompts require every factual claim to be grounded in either the article or your persona facts. Personal references are capped, and invented stats/dates/companies are forbidden.
- **Truth gate:** After generation, a deterministic filter removes any sentence with unsupported numbers, dates, company names, or project-tech mismatches unless the claim is found in your evidence. This keeps outputs credible and on-brand.

**Explainability and transparency:**

- **Avatar explain mode:** Use `--avatar-explain` to see which facts grounded each post, so you know exactly where every claim came from.
- **Learning reports:** Use `--avatar-learn-report` to print a summary of what the system has learned from your moderation and publishing history — see which sources, topics, and angles are working best.
- **All learning data is local:** No cloud logging or external analytics — all logs, priors, and learning data are stored locally and gitignored for privacy.

**Bottom line:**
You get a transparent, adaptive, and fully auditable content engine that not only generates posts, but learns from your real publishing decisions and gives you full control over what gets scheduled, published, or blocked.

## What is the LinkedIn SSI?

The [LinkedIn Social Selling Index](https://www.linkedin.com/sales/ssi) is a 0–100 score LinkedIn updates daily. It measures how effectively you build your personal brand, find the right people, engage with insights, and build relationships — the four pillars LinkedIn's algorithm uses to determine how widely your content and profile are surfaced to others.

A higher SSI directly correlates with more profile views, post reach, and inbound connection requests. LinkedIn's own data shows that professionals with an SSI above 70 get 45% more opportunities than those below 30.

The score breaks down into four components (25 points each):

| Component                             | What LinkedIn measures                                                            |
| ------------------------------------- | --------------------------------------------------------------------------------- |
| **Establish your professional brand** | Completeness of profile, consistency of posting, saves/shares on your content     |
| **Find the right people**             | Profile searches landing on you, connection acceptance rate, right-audience reach |
| **Engage with insights**              | Shares, comments, and reactions on industry content; thought leadership signals   |
| **Build relationships**               | Connection growth, message response rate, relationship depth                      |

### Why automate it?

SSI decays if you go quiet — LinkedIn penalises inconsistency. Manually writing 3 posts per week, curating industry articles with original commentary, and maintaining an on-brand voice across hundreds of posts is simply not sustainable alongside a full-time engineering role.

This tool handles the repeatable parts:

- **Consistent cadence** — scheduled content is added to your Buffer queue, where Buffer owns cadence and posting times
- **On-brand content** — every post is grounded in your real projects, real numbers, and real technical voice via a detailed persona prompt
- **All four SSI pillars** — the content calendar and curator rotate across all four components so no single pillar is neglected
- **Curation pipeline** — fetches today's AI/GovTech news, filters by your niche, and generates commentary that you can either:
  - push to Buffer Ideas for review and manual approval (default), or
  - schedule directly as posts to your Buffer queue (using `--type post`)

You control whether curated content is reviewed before publishing or scheduled directly. The tool removes the blank-page problem, but you decide what goes live.

## How it works

1. **Content calendar** — 4 weeks of topics, each mapped to a specific SSI component and angle, ensuring balanced coverage and unique perspectives 2. **NLP pipeline (spaCy)** — Every post and candidate is analyzed for:
   - **Theme/claim extraction:** Named entities and noun chunks are extracted for narrative memory and topic tracking.
   - **Semantic similarity:** Used for repetition penalty and paraphrase detection, ensuring fresh content.
   - **Sentiment/tone analysis:** Each post is scored for polarity and tone, supporting moderation and reporting.
   - **Fact Suggestion:** When the truth gate drops a sentence, spaCy suggests the closest matching fact or evidence from your persona graph, or recommends how to rephrase for grounding.
   - **Contextual Summarization:** spaCy generates concise, context-aware summaries of curated articles, improving the quality of commentary and learning signals.
   - All NLP logic is implemented in `services/spacy_nlp.py` and covered by unit tests.
   - The calendar is defined in `content_calendar.py` as a dictionary with `week_1` to `week_4`, each containing a list of post topics.
   - Each topic includes:
     - `title`: The main subject of the post
     - `angle`: A unique perspective or story for that topic (prevents generic/rehash content)
     - `ssi_component`: One of `establish_brand`, `find_right_people`, `engage_with_insights`, or `build_relationships` — ensuring every post directly supports a specific SSI pillar
     - `hashtags`: A list of relevant hashtags (used for LinkedIn posts)
   - The calendar is designed to:
     - Rotate through all four SSI components over four weeks, so no pillar is neglected
     - Draw topics from real projects, technical wins, and lessons learned, not generic AI content
     - Provide a distinct "angle" for each post, so every week’s content feels fresh and specific

2. **AI post creation** — Ollama writes posts as plain text, personalised to you (see below)

3. **Post scheduling** — The scheduler sends selected calendar posts to Buffer's queue without explicit publish times. Buffer owns final queue placement, cadence, and posting times.
   - Scheduling is CLI-triggered (`python main.py --schedule --week N`) — there is no always-running local background scheduler process in this repo.
   - The scheduler uses your `.env` SSI focus weights to determine how many posts per week should target each SSI component (e.g., if `establish_brand` is set to 40%, it will get more posts that week).
   - If there are not enough posts for a component, the scheduler fills remaining slots with available topics, always ensuring variety.
   - Posts are never repeated within a week, and the order within each component is preserved.

4. **Content curator** — fetches AI/GovTech news and creates ideas for curation posts

5. **SSI tracker** — weekly report with specific actions per component

### Hybrid RAG + Agent Workflow

This project is not just a single prompt call. It operates as a practical **Persona Graph · Truth-Grounded Learning · Hybrid RAG** agent-style pipeline:

- **Retrieval grounding**: profile facts are scored and ranked per topic/article using **BM25Okapi** — the same algorithm used in production hybrid RAG systems (Elasticsearch, Lucene, OpenSearch). Rare, domain-specific skills score sharply higher than common words, so a query like `"Python"` doesn't pull in every project equally.
- **Generation orchestration**: channel-aware generation rules are applied for LinkedIn/X/Bluesky/YouTube.
- **Deterministic validation**: a truth gate removes unsupported numeric/date/company claim sentences post-generation.
- **Operational automation**: curation, scheduling, and SSI-targeted content balancing are executed end-to-end.

In short: retrieve relevant facts with BM25, write with strict context, validate deterministically, then publish/schedule through Buffer.

## How post personalisation works

Every post is plain text — there's no audio or special format involved.  
"Personalised to you" means the AI prompt is pre-loaded with four layers of context so the output reads like _you_ wrote it, not a generic AI:

**1. Your persona graph (`data/avatar/persona_graph.json`)**  
The authoritative identity source for every post: your name, role, location, specialties, and real project outcomes, stored as a structured JSON graph (projects, companies, skills, role history, and verifiable claims). Copy from `data/avatar/persona_graph.example.json`, fill in your own details, and edit directly in the repo — no env var required. Gitignored so your personal career data stays private. At startup, `load_avatar_state()` reads the graph and builds a ranked list of `EvidenceFact` objects used for all grounding, retrieval, and persona chat. Optionally enriched with live GitHub data via `services/github_service.py` — repo metadata plus compact README summaries (configurable) so the model has stronger project context.

GitHub enrichment details:

- Source data: public repo name, description, primary language, topics, stars, and optional README summary text
- README handling: markdown is cleaned to plain text, then clipped to sentence boundaries for compact prompt injection
- Caching: repo metadata is cached in `github_repos_cache.json` and README summaries in `github_readmes_cache.json` (24h TTL)
- Filtering: use `GITHUB_REPO_FILTER` to include only selected repos
- Context budgeting: GitHub context is assembled with hard caps so prompts stay stable and fast

GitHub context controls in `.env`:

- `GITHUB_INCLUDE_README_SUMMARIES` (default `true`)
- `GITHUB_REPO_MAX_COUNT` (default `12`)
- `GITHUB_README_MAX_CHARS` (default `1200`)
- `GITHUB_CONTEXT_MAX_CHARS` (default `30000`)

**2. Persona system prompt (`PERSONA_SYSTEM_PROMPT` in `.env`)**  
A detailed persona loaded into every AI call, covering:

- Identity and credibility anchors — **domain-separated**: AI projects (2024–present) are listed separately from legacy infrastructure (TPG/USPS JMS work, pre-2024) with a hard rule forbidding the model from blending them
- Target audience, voice guidance, and forbidden phrases
- **Technical glossary** — 10 authoritative definitions (RAG, BM25, kNN, MCP, FastMCP, JMS, SentenceTransformers, CRISP-DM, etc.) with a hard rule: never expand an abbreviation that isn't in the glossary (prevents hallucinations like "RAG = Reactive Agent Framework")

**3. Writing rules (configurable via `.env`, loaded by `ollama_service.py`)**  
Per-pillar instructions injected into every AI call. All four are overridable in `.env` without touching code (`SSI_ESTABLISH_BRAND`, `SSI_FIND_RIGHT_PEOPLE`, `SSI_ENGAGE_WITH_INSIGHTS`, `SSI_BUILD_RELATIONSHIPS`). The defaults live in `services/shared.py`. Built-in rules:

- Never start with "I"
- Never use filler phrases ("Game changer", "Excited to share", "landscape", "leverage", etc.)
- No bullet points in the body — short punchy paragraphs only
- Hook in the first line (bold claim, surprising stat, or short story)

The writing rules draw on **Neuro-Linguistic Programming (NLP)** principles — specifically pattern interrupts (scroll-stopping first lines), presupposition (assuming the reader already cares), and anchoring (pairing your name with specific technical outcomes so readers associate _you_ with the domain). The forbidden-phrases list functions as a negative anchor removal layer: stripping hollow corporate phrases forces the model toward concrete, specific language that builds credibility. For the theoretical underpinning, see [_Monsters and Magical Sticks, There's no Such Thing as Hypnosis?_ by Steven Heller & Terry Steele](https://www.amazon.com/Monsters-Magical-Sticks-Theres-Hypnosis-ebook/dp/B007WMOMXU) — an accessible introduction to how language patterns shape perception.
Notes: https://richardstep.com/downloads/tools/Notes--Monsters-and-Magic-Sticks.pdf

NLP primer in this repo:

- [docs/nlp-basics.md](docs/nlp-basics.md)

The primer covers core NLP concepts, practical communication techniques, technical writing examples, and ethical usage guidelines.

AI-TDD project documentation:

- [docs/idea.md](docs/idea.md) — full product idea and scope
- [docs/prd.md](docs/prd.md) — product requirements document
- [docs/design.md](docs/design.md) — technical design with Mermaid diagrams

**4. Per-post angle and SSI mapping (`content_calendar.py`)**  
Each topic in the calendar has:

- a specific `angle` (e.g. _"contrast AI-TDD with vibe coding"_) so every post has a distinct point of view
- an explicit `ssi_component` so the system can guarantee all four SSI pillars are covered over time

For curated posts (`--curate`), `content_curator.py` filters RSS feeds by your niche keywords (RAG, Neo4j, GovTech, MCP, Spring AI…) so only domain-relevant articles are ever posted — not random tech news.

**Guaranteed output integrity**

Hashtags (for `--schedule` targeting LinkedIn) and source article links (for `--curate`) are always appended programmatically _after_ the model responds — never left to the model to include or place correctly. X posts skip hashtag appending entirely — X's 280-character limit leaves no room for them, and the prompt instructs the model to write a single tight paragraph instead of the multi-paragraph LinkedIn format.

`--schedule` and `--curate` apply a three-layer grounding strategy:

1. **Fact retrieval** — a small set of relevant facts is retrieved from the persona graph and injected into each prompt.
2. **Balance rules** — prompt-level instructions require every factual claim to come from either the article text or the provided profile facts, cap personal references to at most one per post, and forbid invented numbers/dates/companies.
3. **Truth gate** — a lightweight post-generation filter scans each sentence for numeric claims, year references, dollar amounts, company-name patterns, and project-technology misattributions. Any sentence whose specific token is not found in the article text or grounding facts is silently removed. General opinions, hooks, and rhetorical questions pass through untouched.

### How Deterministic Grounding Works (Console, Schedule, Curate)

Deterministic grounding is a safety layer that reduces hallucinated personal claims by forcing outputs to stay anchored to known profile facts.

#### What Problem It Solves

Large models are strong at style but can still invent plausible-sounding background details (project names, companies, years, implementation claims). Grounding prevents that by treating loaded profile context as the source of truth.

#### Grounding Pipeline

1. Load persona facts  
   The app loads structured facts from `data/avatar/persona_graph.json` via `load_avatar_state()` — project, company, years, details, skills.
2. Detect constraints from the request  
   Query intent is analyzed for project/company lookups and technology tags (for example Java, Spring, RAG, Neo4j).
3. Retrieve relevant facts  
   Facts are ranked using **BM25Okapi** (`rank_bm25`) — a probabilistic IR algorithm that accounts for term-frequency saturation (a skill appearing many times doesn't keep adding score) and inverse document frequency (a rare skill like `fastmcp` scores sharply higher than a common one like `python`). The BM25 corpus is built per-query from all persona graph projects; skills are weighted 3× in the document tokens to reflect their signal value. Falls back to hand-weighted keyword overlap if `rank_bm25` is not installed.
4. Apply balance rules in prompts (`--schedule` and `--curate`)  
   The model is told that every factual claim must come from the article or profile facts. Personal references are capped at one per post. Invented stats, dates, and company names are explicitly forbidden. If the model mentions a specific project by name, it may only attribute technologies that appear in that project's detail field.
5. Post-process output with the truth gate  
   A lightweight deterministic filter strips sentences containing unsupported numeric/date/company claims or project-technology misattributions. The rest of the post is left intact — no rewriting occurs.

#### Console Mode Behavior

When a question is factual (for example: what projects, where, when, what stack), console mode can answer deterministically from parsed facts with source references instead of relying on free-form generation.

#### Schedule and Curate Behavior

For weekly scheduling and article curation:

- Relevant facts are selected per topic/article.
- Balance rules in the prompt cap personal references, require article-grounded claims, and prohibit attributing technologies to a named project unless those technologies appear in the project's detail.
- The truth gate strips sentences with unsupported numeric/date/company claims or project-technology misattributions after generation.

This keeps posts authentic while lowering risk of fabricated bio details.

#### Environment Controls

You can tune tech matching with:

- `CONSOLE_GROUNDING_TECH_KEYWORDS` — tech terms for deterministic retrieval (used by `--console` and `--curate`)
- `CONSOLE_GROUNDING_TAG_EXPANSIONS` — maps umbrella terms to related stack terms (e.g. `java:spring|jms|oracle`)
- `TRUTH_GATE_DOMAIN_TERMS` — comma-separated domain-wide terms that bypass truth gate project-claim checks (e.g. `llm,ai,ml,api,model`). Defaults are built-in; set this to override.

These controls affect which profile facts are considered relevant during retrieval.

Fallback behavior for `--curate`:

- Tech keywords: falls back to `CURATOR_KEYWORDS` (the RSS-filtering keyword list).
- Tag expansions: falls back to `CONSOLE_GROUNDING_TAG_EXPANSIONS`.

Recommended tuning order:

1. Expand `CURATOR_KEYWORDS` for article vocabulary coverage.
2. Expand `CONSOLE_GROUNDING_TAG_EXPANSIONS` for umbrella-term mapping.

#### Truth Gate Behavior and Configuration

The truth gate runs after model generation (and cleanup) for LinkedIn generation and curation flows.
It checks each sentence independently and removes only sentences that contain unsupported specific claims.

What it checks:

- Numeric claims (for example: `40%`, `3x`, `500ms`, `2 hours`)
- Year references (for example: `2021`, `2024`)
- Dollar amounts (for example: `$2M`)
- Company-name style patterns in context (for example: "at Company Name", "for Company Name")
- Project-technology misattributions — when a sentence names a known project but pairs it with a tech keyword not present in that project's detail field or the article text

Evidence source used by the gate:

- Article text (for `--curate`)
- Retrieved profile grounding facts (`project`, `company`, `years`, `details`)

If a sentence contains one of the claim patterns above and its key token is not present in the evidence source, that sentence is removed.
If a sentence is opinion, framing, hook, or a rhetorical question without unsupported hard claims, it is kept.

Current configuration surface:

- `TRUTH_GATE_DOMAIN_TERMS` — comma-separated domain-wide terms (e.g. `llm,ai,ml,api,model,pipeline`) that are always allowed in project-claim context. These broad vocabulary items make sense when discussing any AI/software project and should never trigger a project-technology misattribution flag. Overrides the built-in defaults.
- Truth-gate strictness is currently code-defined in `services/console_grounding.py`.
- Practical tuning in `.env` is indirect: improving retrieval relevance (`CONSOLE_GROUNDING_TECH_KEYWORDS`, `CONSOLE_GROUNDING_TAG_EXPANSIONS`) increases available evidence and typically reduces unnecessary sentence removals.

Recommended tuning approach:

1. Start with current default-like set.
2. Run generate/curate and watch truth gate removals.
3. Add only terms that are repeatedly false positives.
4. Avoid adding specific proprietary tech names that should remain project-validate.

Also, this variable does not change:

- `unsupported_numeric` checks
- `unsupported_year` checks
- `unsupported_org` checks

In other words: `TRUTH_GATE_DOMAIN_TERMS` only affects `project_claim` filtering.

Interactive mode:

- Use `--interactive` with `--schedule` or `--curate` to pause on each flagged sentence and confirm removal (y/N).
- Without `--interactive`, flagged sentences are removed automatically as before.

Operational notes:

- The gate logs each removed sentence in full (no truncation) with a reason code (for example: `unsupported_numeric`, `unsupported_year`, `unsupported_org`, `project_claim`) followed by a summary count.
- Posts are now displayed to the screen in both `--dry-run` and regular mode for traceability tuning.
- The gate does not rewrite text; it only removes unsupported claim sentences.
- The gate is intentionally conservative and not a full external fact-checker.

#### Troubleshooting Grounding Quality

If grounded outputs feel too generic or personal references are missing, this is usually a retrieval-configuration issue rather than a generation issue.

Common symptoms and fixes:

- Symptom: Output avoids personal project references even when relevant.  
   Likely cause: `CONSOLE_GROUNDING_TECH_KEYWORDS` does not include terms used in your topic or persona graph.  
   Fix: Add missing terms (for example: `spring ai`, `sentence transformers`, `pubsub+`, `fastmcp`) in lowercase.

- Symptom: Broad prompts like "Java" or "Python" miss obvious related projects.  
   Likely cause: `CONSOLE_GROUNDING_TAG_EXPANSIONS` is too narrow.  
   Fix: Expand umbrella tags so broad queries include adjacent stack terms (for example `java:spring|jms|oracle|weblogic`).

- Symptom: Irrelevant personal facts are injected for unrelated topics.  
   Likely cause: Keyword list is too broad/noisy.  
   Fix: Remove vague terms and keep only high-signal domain vocabulary.

- Symptom: Console factual answers look right, but `--curate` still feels weakly grounded.
  Likely cause: Curation articles use topic vocabulary that does not overlap `CURATOR_KEYWORDS` or `CONSOLE_GROUNDING_TAG_EXPANSIONS`.
  Fix: Add domain terms to `CURATOR_KEYWORDS` (for tech matching) or `CONSOLE_GROUNDING_TAG_EXPANSIONS` (for umbrella expansion).

- Symptom: Good posts lose one useful sentence after generation.
  Likely cause: The sentence contains a specific number/date/company token not present in article text or retrieved facts.  
   Fix: Expand grounding keywords/tag expansions so the correct fact is retrieved, or rephrase the prompt/topic so the claim appears in source evidence.

- Symptom: Truth gate often removes 2+ sentences for curation posts.  
   Likely cause: Retrieval signal is weak for that article domain, so evidence is too thin.  
   Fix: Add domain terms to `CURATOR_KEYWORDS` and expand umbrella terms in `CONSOLE_GROUNDING_TAG_EXPANSIONS`.

1. Start with a compact keyword set that mirrors your persona graph skill and project tags.
2. Add tag expansions for umbrella terms (`java`, `python`, `rag`).
3. Run `--console` with factual prompts and confirm retrieved facts match expectations.
4. Run `--schedule --dry-run` and `--curate --dry-run` and inspect whether personal references are relevant and supported.
5. Iterate by adding/removing only a few terms at a time.

#### Important Scope

Grounding protects factual identity and project/company claims. It does not attempt to fact-check every external statement in third-party articles.

### Avatar Intelligence — Explain, Learn, Confidence

The Avatar Intelligence system adds three complementary overlays to generation and curation. All are opt-in and safe to ignore until you want to tune quality.

#### `--avatar-explain` — Transparency into grounding decisions

Add `--avatar-explain` to any `--schedule` or `--curate` run to see, after each post:

- Which evidence IDs from `data/avatar/persona_graph.json` were retrieved
- Each fact's score and the skill/tag tokens that matched the query
- Which claim tokens the truth gate evaluated

Useful when a post feels vaguely grounded or uses the wrong project. The output shows exactly which facts scored highest so you can tune `CONSOLE_GROUNDING_TECH_KEYWORDS` or the persona graph itself.

```bash
python main.py --schedule --week 1 --dry-run --avatar-explain
python main.py --curate --dry-run --avatar-explain
```

#### `--avatar-learn-report` — Advisory report from moderation history

Every time the truth gate removes or passes a sentence during a `--curate` or `--schedule` run, the decision is logged to `data/avatar/learning_log.jsonl`. Run the report at any time to see:

- Which reason codes fired most often (e.g. `unsupported_numeric`, `project_mismatch`)
- Which topic or channel types triggered the most removals
- Advisory recommendations: keywords to add, claims that need stronger grounding evidence

The report is read-only — it never modifies config files or the persona graph.

```bash
python main.py --avatar-learn-report
```

Disable logging entirely by setting `AVATAR_LEARNING_ENABLED=false` in `.env`.

#### `--confidence-policy` — Control curate publish routing

Each generated curation post receives a confidence score based on truth-gate signal, grounding hit quality, and narrative repetition. The policy maps score to publish action:

| Policy                 | High confidence | Medium confidence | Low confidence |
| ---------------------- | --------------- | ----------------- | -------------- |
| `strict`               | Scheduled post  | Ideas board       | Blocked        |
| `balanced` _(default)_ | Scheduled post  | Scheduled post    | Ideas board    |
| `draft-first`          | Ideas board     | Ideas board       | Ideas board    |

Override for a single run:

```bash
python main.py --curate --confidence-policy strict
```

Or set as the permanent default in `.env`:

```
AVATAR_CONFIDENCE_POLICY=balanced
```

The `--interactive` flag works at a different layer — it lets you manually approve/reject individual truth-gate removals sentence by sentence, regardless of the confidence policy.

#### Agent memory — preventing post repetition

Every time a post is successfully generated or curated, the tool automatically updates `data/avatar/narrative_memory.json` with two things extracted from that post:

- **Themes** — the key non-stopword tokens from the SSI component label and article title (e.g. `rag`, `retrieval`, `govtech`). Up to 10 per post, deduplicated.
- **Claims** — sentences from the post body that match bold-assertion patterns (`"the key is"`, `"you should"`, `"will replace"`, `"is the most important"`, etc.). Up to 5 per post.

Both lists are FIFO-trimmed to `AVATAR_MAX_MEMORY_ITEMS` (default 200) — oldest entries drop off as new ones are added.

**How it helps generation quality:**

The memory feeds back into every subsequent prompt in two ways:

1. **Continuity hint** — the last 5 themes and 3 open arcs are injected into the prompt as a brief sentence before the main instruction: _"Recent topics you have written about: rag, govtech, retrieval…"_. This nudges the model to take a different angle rather than repeating the same framing.

2. **Repetition penalty** — before scheduling, a `narrative_repetition_score` is computed: the fraction of recent stored claims whose key tokens overlap ≥ 50% with the new post. That score is fed into the confidence scoring formula (up to −0.10 on the final score), which can push a borderline post from `post` routing to `idea` routing under the `balanced` policy.

Over weeks of use, this means the tool naturally diversifies your content — the same "RAG is the key to reliable AI" framing stops getting direct-posted and starts landing in the Ideas board for you to rework.

**Controls:**

```
AVATAR_LEARNING_ENABLED=true        # set to false to disable all memory writes
AVATAR_MAX_MEMORY_ITEMS=200         # max items per list before FIFO trim
```

The memory file is gitignored (`data/avatar/narrative_memory.json`). It only exists locally on your machine and is seeded from `data/avatar/narrative_memory.example.json` during setup.

## Setup

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install spaCy language model for NLP features (theme extraction, similarity, sentiment analysis)
python -m spacy download en_core_web_sm

#
# The spaCy NLP engine is used for theme/claim extraction, semantic similarity, and sentiment/tone analysis. All logic is in `services/spacy_nlp.py`.
#
# Configure API keys and persona
cp .env.example .env
# Edit .env and fill in ALL required values:
#   PERSONA_SYSTEM_PROMPT → your voice/persona (template in .env.example)
#   BUFFER_API_KEY        → https://publish.buffer.com/settings/api
#   OLLAMA_BASE_URL       → default: http://localhost:11434
#   OLLAMA_MODEL          → default: llama3.2 (gemma4:26b recommended)
#   OLLAMA_NUM_CTX        → default: 4096 (16384 recommended baseline for grounded prompts)
#
# Optional — Bluesky stats (--bsky-stats):
#   BLUESKY_HANDLE       → your handle, e.g. you.bsky.social (optional, only if using Bluesky integration)
#   BLUESKY_APP_PASSWORD → generate at bsky.app → Settings → App Passwords (optional, only if using Bluesky integration)
#
# Optional — GitHub context enrichment and prompt budget tuning:
#   GITHUB_USER                  → GitHub username (enables repo enrichment)
#   GITHUB_TOKEN                 → optional token (higher API limits)
#   GITHUB_REPO_FILTER           → comma-separated repo names to include
#   GITHUB_INCLUDE_README_SUMMARIES → true/false (default true)
#   GITHUB_REPO_MAX_COUNT        → max repos included (default 12)
#   GITHUB_README_MAX_CHARS      → max chars per README summary (default 1200)
#   GITHUB_CONTEXT_MAX_CHARS     → max GitHub-derived context block size (default 30000)
#   CONSOLE_GROUNDING_TECH_KEYWORDS → comma-separated tech terms for deterministic grounding
#   CONSOLE_GROUNDING_TAG_EXPANSIONS → optional related-tag map (e.g. java:spring|jms|oracle)
#
# Optional — Avatar Intelligence controls:
#   AVATAR_LEARNING_ENABLED    → true/false — enable learning log and narrative memory (default true)
#   AVATAR_CONFIDENCE_POLICY   → strict|balanced|draft-first — curate routing policy (default balanced)
#   AVATAR_MAX_MEMORY_ITEMS    → max narrative memory items before trimming (default 200)

# Set up your persona graph (gitignored — keeps your personal data private)
cp data/avatar/persona_graph.example.json data/avatar/persona_graph.json
cp data/avatar/narrative_memory.example.json data/avatar/narrative_memory.json
# Edit data/avatar/persona_graph.json and replace ALL placeholder fields with your real data:
#   person   → your name, title, location, links
#   companies → employers and clients (id + name + aliases)
#   skills   → technologies you use (id + name + aliases + scope)
#   projects  → real projects with years, details, skill refs, and aliases
#   claims   → verifiable factual statements tied to specific projects

# Set up your personal content calendar (gitignored — keeps your strategy private)
cp content_calendar.example.py content_calendar.py
# Edit content_calendar.py and replace the placeholder topics with your own:
#   title    → post headline
#   angle    → the specific take or story you'll tell
#   ssi_component → establish_brand | find_right_people | engage_with_insights | build_relationships
#   hashtags → list of relevant hashtags
```

## Usage

```bash


# Generate + preview week 1 posts (dry run — no Buffer calls)
python main.py --schedule --week 1 --dry-run

# Multi-channel dry run: generate and display posts/scripts for all supported channels (LinkedIn, X, Bluesky, YouTube)
python main.py --schedule --week 1 --dry-run --channel all

This will generate and print posts/scripts for **all** supported channels (LinkedIn, X, Bluesky, YouTube) to the terminal, without making any Buffer API calls. The output matches the behavior of `--curate --channel all --dry-run`.

# Generate + schedule week 1 posts to Buffer (LinkedIn, default)
python main.py --schedule --week 1

# Schedule to X instead of LinkedIn
python main.py --schedule --week 1 --channel x

# Schedule to LinkedIn, X, Bluesky, and YouTube simultaneously
python main.py --schedule --week 1 --channel all

# Generate YouTube Short scripts (hard-capped at 500 chars), print to screen, and save to yt-vid-data/
# Buffer scheduling is skipped because YouTube requires a video file upload
python main.py --schedule --week 1 --channel youtube

# Curate AI news and push as Buffer Ideas (default — review before publishing)
python main.py --curate --dry-run
python main.py --curate

# Curate and schedule DIRECTLY to next available queue slot
# LinkedIn → post body + source URL + hashtags appended programmatically
python main.py --curate --type post --channel linkedin

# X → single punchy post (280-char limit, no hashtags)
python main.py --curate --type post --channel x

# Bluesky → single post (300-char limit, no hashtags)
python main.py --curate --type post --channel bluesky

# YouTube → generates 500-char spoken Short script, prints to screen, saves to yt-vid-data/
# Buffer push is skipped (YouTube requires a video file) — render with lipsync.video then upload manually
python main.py --curate --type post --channel youtube

# All channels — LinkedIn/X/Bluesky scheduled independently; YouTube script printed and saved to yt-vid-data/
python main.py --curate --type post --channel all

# Curate ideas targeted at X audience (Ideas board)
python main.py --curate --channel x

# Print weekly SSI action report
python main.py --report

# Record today's SSI component scores (from linkedin.com/sales/ssi)
python main.py --save-ssi 10.49 9.69 11.0 12.15

# Fetch live Bluesky profile + engagement stats
python main.py --bsky-stats

# Open interactive persona chat console (no Buffer calls)
python main.py --console


# Avatar Intelligence — learning and explainability
python main.py --schedule --week 1 --avatar-explain       # show evidence IDs + grounding summary after each post
python main.py --curate --avatar-explain                  # show which facts grounded each curated post

python main.py --avatar-learn-report                      # print learning report from captured moderation events

# Confidence policy — controls curate publish routing (overrides AVATAR_CONFIDENCE_POLICY)
python main.py --curate --confidence-policy strict        # only high-confidence → scheduled; medium → Ideas; low → blocked
python main.py --curate --confidence-policy balanced      # default: high+medium → scheduled; low → Ideas
python main.py --curate --confidence-policy draft-first   # all posts → Ideas board regardless of score
```

### `--schedule` vs `--curate` vs `--dry-run`

| Flag                    | Source                                                   | What it does                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ----------------------- | -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--schedule`            | Your content calendar (`content_calendar.py`)            | Writes posts from your pre-planned topics + angles; pushes them to Buffer's queue without explicit publish times                                                                                                                                                                                                                                                                                                                                                                                                  |
| `--curate`              | Live RSS feeds (Anthropic, HuggingFace, Google AI, etc.) | Fetches today's articles, filters by your niche keywords, generates commentary; default behaviour pushes to Buffer as **Ideas** (unscheduled drafts for review)                                                                                                                                                                                                                                                                                                                                                   |
| `--console`             | Persona graph + grounding                                | Opens an interactive terminal chat with your persona/context loaded. No Buffer actions are performed in this mode. Console commands: `/help`, `/reset`, `/exit`. For factual bio/project queries, a deterministic grounding layer extracts and cites matching records from `data/avatar/persona_graph.json` (project/company/year/details). Tech term matching is configurable via `CONSOLE_GROUNDING_TECH_KEYWORDS`.                                                                                             |
| `--dry-run`             | Either                                                   | Prints generated posts to the terminal only — no calls to Buffer                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `--type idea`           | `--curate`                                               | _(default)_ Push curated posts to Buffer Ideas board for manual review before publishing. LinkedIn: source URL and hashtags appended programmatically (body → URL → hashtags).                                                                                                                                                                                                                                                                                                                                    |
| `--type post`           | `--curate`                                               | Schedule curated posts **directly** to the next available Buffer queue slot. LinkedIn: source URL and hashtags appended after the post body. X: single post, 280-char limit, no hashtags. Bluesky: single post, 300-char limit, no hashtags. YouTube: script printed to screen and saved to `yt-vid-data/` — not pushed to Buffer (see below).                                                                                                                                                                    |
| `--channel linkedin`    | Either                                                   | Target LinkedIn only (default)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `--channel x`           | Either                                                   | Target X (Twitter) only — 280-char hard limit, single paragraph, no hashtags appended; requires an X account connected in Buffer                                                                                                                                                                                                                                                                                                                                                                                  |
| `--channel bluesky`     | Either                                                   | Target Bluesky only — same thread format as X; requires a Bluesky account connected in Buffer                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `--channel youtube`     | Either                                                   | Generates a **spoken Short script** (500-char / ~100–150 words) for use with lipsync.video or similar avatar tools; persona controlled by `YOUTUBE_SHORT_SYSTEM_PROMPT` in `.env`; script is printed to screen and saved to `yt-vid-data/<timestamp>_<title>.txt` — **not pushed to Buffer** (Buffer requires a video file)                                                                                                                                                                                       |
| `--channel all`         | Either                                                   | Target LinkedIn, X, Bluesky, and YouTube in one run. In **dry-run mode**, generates and displays posts/scripts for all supported channels (LinkedIn, X, Bluesky, YouTube) in the terminal, matching curate behavior. In scheduled mode, LinkedIn/X/Bluesky are scheduled independently; YouTube is generated as a local script (printed + saved to `yt-vid-data/`) because Buffer YouTube requires a video upload. If X or Bluesky is not connected in Buffer, that channel is skipped with a warning (no crash). |
| `--interactive`         | Either                                                   | Pause on each truth gate flagged sentence for user confirmation (y/N) before removal. Without this flag, flagged sentences are removed automatically.                                                                                                                                                                                                                                                                                                                                                             |
| `--avatar-explain`      | `--schedule`, `--curate`                                 | After each post is created, print the evidence IDs and grounding summary used: which persona graph facts were retrieved, how they scored, and which claim tokens were matched. Useful for diagnosing why a post is weakly or incorrectly grounded.                                                                                                                                                                                                                                                                |
| `--avatar-learn-report` | Standalone                                               | Read `data/avatar/learning_log.jsonl`, aggregate moderation events, and print a learning report: reason-code frequencies, commonly removed claim types, and advisory recommendations for tuning keywords or grounding config. Does not modify any file.                                                                                                                                                                                                                                                           |
| `--confidence-policy`   | `--curate`                                               | Override the curate publish routing for this run: `strict` (high-confidence only → scheduled; medium → Ideas; low → blocked), `balanced` (default; high+medium → scheduled; low → Ideas), `draft-first` (all output → Ideas board). Env default: `AVATAR_CONFIDENCE_POLICY`.                                                                                                                                                                                                                                      |
| `--reconcile`           | Standalone                                               | Fetches all SENT (published) posts from Buffer and reconciles them against the local `data/selection/generated_candidates.jsonl` log. Matches by Buffer post id, article URL, or Jaccard text similarity. Labels matched candidates as `selected=True` and candidates outside the 14-day acceptance window as `selected=False`. These labels build Beta-smoothed acceptance priors used to rank RSS articles on the next `--curate` run.                                                                          |

**YouTube Short workflow:** The `--channel youtube` output is a **spoken script** for a lipsync.video avatar (or similar tool), targeting ~100–150 words (500-char hard cap). The script is printed to the terminal and saved to `yt-vid-data/<timestamp>_<title>.txt` for you to copy into lipsync.video. Buffer is **not** used — YouTube requires a video file, which must be uploaded manually after rendering. The avatar persona (name, intro line, subscribe CTA) is fully configurable via `YOUTUBE_SHORT_SYSTEM_PROMPT` in your `.env`.

**Why curate goes to Ideas by default:** The AI summarises articles it found today and adds your commentary, but you should review that commentary before it goes live. Buffer Ideas sit in a drafts inbox so you can edit, approve, or discard each one. Use `--type post` to skip the review step and schedule directly.

**LinkedIn post structure:** For all LinkedIn curation (`--curate`), the final post is always assembled in this order: AI-generated commentary body → source URL → hashtags. The URL and hashtags are stripped from the AI response and re-appended by the code, so their position is guaranteed regardless of what the model outputs.

### How the curation pipeline works

Each time you run `python main.py --curate`, the following happens:

1. **Fetch** — all RSS feeds are scanned (up to `CURATOR_MAX_PER_FEED` entries each, default 10; see [Customising RSS feeds and keywords](#customising-rss-feeds-and-keywords) to add your own)
2. **Filter** — only articles whose title or summary contains a niche keyword (RAG, LLM, neo4j, MCP, GovTech, etc.) are kept
3. **Rank** — articles are scored by a weighted formula combining relevance (keyword hit density), freshness (exponential decay with a 7-day half-life), and an acceptance prior (Beta-smoothed rate derived from which past candidates were actually published). Falls back to random shuffle if no prior data exists yet.
4. **Dedup check** — article titles are checked against `published_ideas_cache.json` (a local file); any article you've already pushed to Buffer is skipped
5. **Generate** — each selected article is sent to the AI with your persona prompt and an SSI component goal; the service writes a LinkedIn post with your commentary
6. **Log candidate** — the generated post is appended to `data/selection/generated_candidates.jsonl` with metadata (source, SSI component, route, run ID) for later reconciliation
7. **Append link** — the source article URL is always appended programmatically after the AI responds (never left to the model to include)
8. **Push to Buffer Ideas** — the post is created in your Buffer Ideas board for review; after a successful push, the Buffer post id is written back to the candidate log

### Selection learning and acceptance priors

After you've run `--curate` several times, run:

```bash
python main.py --reconcile
```

This fetches all published (SENT) posts from your Buffer channels and reconciles them against `data/selection/generated_candidates.jsonl`. Matching uses a three-priority cascade:

1. **Exact Buffer post id** — if the candidate was pushed to Buffer, the id is already recorded
2. **Article URL** — the original article link appears in the published post text
3. **Jaccard token similarity** — word-token overlap ≥ 0.25 between the generated snippet and the published text

Candidates matched to a published post are labelled `selected=True`. Candidates older than 14 days with no published match are labelled `selected=False` (implicit rejection). Candidates within the 14-day window remain `selected=None` (pending).

Labelled candidates feed `compute_acceptance_priors()`, which builds a Beta-smoothed acceptance rate per `(source, ssi_component)` bucket. On the next `--curate` run, articles from sources with higher acceptance rates float to the top of the ranked list.

**Data files** (auto-created, gitignored):

- `data/selection/generated_candidates.jsonl` — one record per generated candidate
- `data/selection/published_posts_cache.jsonl` — published posts fetched from Buffer

It lives at the project root and is gitignored — it's local state, not source code. If you want to re-submit an article (e.g. after editing the persona), just delete its title from the file or clear the file entirely.

```json
[
  "Beyond Semantic Similarity: Introducing NVIDIA NeMo Retriever",
  "The Multi-Agent Trap",
  "Why Care About Prompt Caching in LLMs?"
]
```

The cache path can be overridden with `IDEAS_CACHE_PATH` in `.env` if you want to store it elsewhere.

### Customising RSS feeds and keywords

Both the RSS feed list and the keyword filter are configurable via `.env` — no code changes needed.

**`CURATOR_KEYWORDS`** — comma-separated terms matched against article titles/summaries (overrides built-in list entirely):

```ini
CURATOR_KEYWORDS=RAG,LLM,neo4j,GovTech,Spring AI,MCP,vector search
```

**`CURATOR_RSS_FEEDS`** — JSON array of `{"name": "...", "url": "..."}` objects (overrides built-in list entirely):

```ini
CURATOR_RSS_FEEDS=[{"name":"Anthropic Blog","url":"https://www.anthropic.com/rss.xml"},{"name":"My Blog","url":"https://myblog.com/feed.xml"}]
```

Leave either variable unset to use the built-in defaults (6 AI/ML feeds + 19 niche keywords).

## AI Backend

All post generation uses **Ollama** — a locally-running LLM server. No cloud AI keys required.

```bash
# 1. Install Ollama
#    Linux/WSL:
curl -fsSL https://ollama.com/install.sh | sh
#    macOS/Windows: https://ollama.com/download

# 2. Start the server
ollama serve &

# 3. Pull a model (one-time) — gemma4:26b recommended
ollama pull gemma4:26b
# Smaller/faster alternatives:
# ollama pull qwen2.5:14b     (~9 GB, strong fallback)
# ollama pull llama3.2        (~2 GB)
# ollama pull mistral-nemo    (12b)

# 4. Set the model in .env
OLLAMA_MODEL=gemma4:26b
OLLAMA_NUM_CTX=16384

# Override model for a single run
OLLAMA_MODEL=llama3.2 python main.py --curate --dry-run
```

> **Tip:** `gemma4:26b` (MoE — 3.8B active params) gives the best post quality: native system role support,
> configurable thinking mode, and strong instruction-following across long prompts. `qwen2.5:14b` is a solid
> fallback if you're VRAM-constrained (~9 GB). `llama3.2` (3b) is fastest but lower quality.
> For this repo, use `OLLAMA_NUM_CTX=16384` as the default baseline: it is usually the best quality/speed balance for
> long persona + grounding prompts. Drop to `8192` if memory/latency is tight; raise to `32768` only when logs indicate
> truncation or long grounded curation outputs degrade.

## SSI Component Mapping

Current scores are tracked in `ssi_history.json` (runtime file, gitignored). The table below shows targets only — run `--report` to see live scores with trend arrows.

| Component            | Target | Strategy                              |
| -------------------- | ------ | ------------------------------------- |
| Establish brand      | 25     | 3x/week posting via Buffer            |
| Find right people    | 20     | Connect with commenters, join groups  |
| Engage with insights | 25     | Curated posts + daily commenting      |
| Build relationships  | 25     | Reply to all comments, DM connections |
| **Total**            | **95** |                                       |

### How the content calendar and scheduling work together

1. **Calendar structure:**
   - The calendar (`content_calendar.py`) is a 4-week plan, with each week containing 3 topics. Each topic is mapped to an SSI component and has a unique angle.
2. **Scheduling logic:**
   - When you run `python main.py --schedule --week N`, the scheduler:
     - Loads the topics for week N
     - Uses your `.env` SSI focus weights to allocate posts per component (e.g., if `engage_with_insights` is set to 40%, it will try to schedule more posts from that pillar)
     - Ensures no component is neglected, and fills any gaps with available topics
   - Sends selected posts to Buffer's queue without explicit publish times
     - Never repeats a topic within a week
3. **Result:**
   - Over 4 weeks, all four SSI pillars are covered in a balanced, data-driven way, with each post having a clear purpose and unique perspective.

### Scheduler behavior

The scheduler logic lives in `scheduler.py`. Buffer owns publish timing and queue placement.

Important runtime behavior:

- Scheduling runs only when you execute `--schedule`.
- The app sends selected posts to Buffer without a `scheduled_at` timestamp.
- Buffer places the posts in its queue and performs publishing according to your Buffer settings.
- There is no daemon/cron loop in this repo that continuously schedules in the background.

### Weekly SSI update workflow

1. Check [linkedin.com/sales/ssi](https://www.linkedin.com/sales/ssi) for your latest four component scores
2. Record them to history (this drives the report and trend arrows):

   ```bash
   python main.py --save-ssi <brand> <find> <engage> <build>
   # Example:
   python main.py --save-ssi 10.49 9.69 11.0 12.15
   ```

3. View your progress report:

   ```bash
   python main.py --report
   ```

The report shows progress bars toward each target, ↑/↓/↔ trend arrows vs the previous entry, and a history table of the last 5 weekly snapshots. No code edits needed — just `--save-ssi` + `--report`.

### Controlling post-type focus

Four percentage values in `.env` control how often each pillar gets a generated post. They should add up to 100 — bump a pillar up when it's lagging, dial it back when it improves:

```ini
SSI_FOCUS_ESTABLISH_BRAND=25
SSI_FOCUS_FIND_RIGHT_PEOPLE=27
SSI_FOCUS_ENGAGE_WITH_INSIGHTS=24
SSI_FOCUS_BUILD_RELATIONSHIPS=24
```

The system uses these as-is — no formulas to think about. If `find_right_people` drops on your SSI page, move some points toward it from whichever pillar is healthiest.

## Running the tests

The project ships a [pytest](https://pytest.org) suite covering the Avatar Intelligence engine.

```bash
# install test dependency (one-time)
pip install pytest

# run all tests
pytest tests/ -v
```

| Test file                               | What it covers                                                                                                                                                                                            |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/test_avatar_state_loader.py`     | Persona graph + narrative memory loader, schema validator, safe fallback on malformed input                                                                                                               |
| `tests/test_evidence_mapping.py`        | Evidence ID stability, fact normalisation, retrieval scoring, grounding context, explain output                                                                                                           |
| `tests/test_learning_report.py`         | JSONL event capture, moderation roundtrip, heuristic rules, report aggregation and formatting                                                                                                             |
| `tests/test_confidence_scoring.py`      | Signal extraction, score thresholds (high/medium/low), full policy matrix (strict/balanced/draft-first)                                                                                                   |
| `tests/test_integration_flags.py`       | CLI flag registration (`--avatar-explain`, `--avatar-learn-report`, `--confidence-policy`, `--reconcile`), argparse rejection of invalid values                                                           |
| `tests/test_persona_graph_retrieval.py` | Real `persona_graph.json` load (17 projects), retrieval quality spot-checks, app start without `PROFILE_CONTEXT`                                                                                          |
| `tests/test_selection_learning.py`      | Candidate log writes, buffer_id updates, `_match_candidate` priority cascade, reconcile labelling (selected/rejected/pending), Beta-prior math, `get_acceptance_rate` fallbacks, `rank_articles` ordering |

All 138 tests pass with zero external API calls required.

## File Structure

```
linkedin_ssi_booster/
├── main.py                    # CLI entry point + profile context assembly
├── content_calendar.py        # 4-week topic plan
├── scheduler.py               # Buffer post scheduling logic
├── requirements.txt
├── .env.example               # Template — copy to .env and fill in keys/persona
├── data/
│   └── avatar/
│       ├── persona_graph.example.json    # Template — copy to persona_graph.json and fill in your details
│       ├── narrative_memory.example.json # Template — copy to narrative_memory.json
│       ├── persona_graph.json            # Your identity graph (gitignored — personal data)
│       ├── narrative_memory.json         # Runtime narrative memory (gitignored)
│       └── learning_log.jsonl            # Runtime moderation log (gitignored, auto-created)
├── tests/
│   ├── conftest.py            # Shared fixtures (minimal persona graph + narrative memory)
│   ├── test_avatar_state_loader.py
│   ├── test_evidence_mapping.py
│   ├── test_learning_report.py
│   ├── test_confidence_scoring.py
│   ├── test_integration_flags.py
│   └── test_persona_graph_retrieval.py
├── docs/
│   ├── idea.md                # AI-TDD idea document (full platform scope)
│   ├── prd.md                 # AI-TDD product requirements document
│   ├── design.md              # AI-TDD technical design + Mermaid diagrams
│   ├── nlp-basics.md          # NLP communication primer used by prompts
│   └── features/
│       └── avatar-intelligence-learning/  # Avatar Intelligence feature docs
│           ├── idea.md            # Feature idea: persona graph, migration, learning
│           ├── prd.md             # Product requirements + acceptance criteria
│           ├── design.md          # Technical design + migration design
│           ├── plan.md            # Phased implementation plan (1A-1E)
│           └── tasks.md           # Execution task list with agent protocol
└── services/
    ├── buffer_service.py      # Buffer GraphQL API client
    ├── ollama_service.py      # Ollama local LLM — post generation + SSI instructions
    ├── shared.py              # Shared constants, persona prompt, SSI instructions
    ├── content_curator.py     # RSS feed scraper + summariser; guaranteed link append
    ├── github_service.py      # Live GitHub profile enrichment (repo metadata + README summaries)
    └── ssi_tracker.py         # SSI report + action items
```

## Get your API keys

- **Buffer API key**: https://publish.buffer.com/settings/api → Generate API Key
- **Ollama models**: https://ollama.com/library
- **Bluesky handle/app password** (optional): bsky.app → Settings → App Passwords
- **YouTube channel** (optional): connect at https://publish.buffer.com → Channels → Add Channel → YouTube
- **Track your SSI**: https://linkedin.com/sales/ssi

## License

MIT — see [LICENSE](LICENSE) for details.

## Running BufferService API tests with .env

To run tests that require environment variables (like `BUFFER_API_KEY`), use [python-dotenv](https://pypi.org/project/python-dotenv/):

```bash
# Install test dependencies (one-time)
pip install -r requirements.txt

# Run all tests with .env loaded
env $(grep -v '^#' .env | xargs) pytest tests/ -v  # (only works if no spaces/quotes in .env values)

# Recommended: use python-dotenv for robust .env loading
python -m dotenv run -- python -m pytest tests/test_buffer_service.py -v
```

- The last command is safest for .env files with spaces, quotes, or special characters.
- `python-dotenv` is included in requirements.txt for this purpose.
- This ensures your Buffer API key and other secrets are loaded for integration tests.

---

## 🧩 Adaptive Selection Learning (How the System Learns What to Curate)

The curation pipeline uses **adaptive selection learning** to float the best sources and topics to the top over time, based on what you actually publish. This is achieved through:

- **Candidate logging:** Every article candidate and generated post is logged with metadata (source, topic, SSI component, etc.) in `data/selection/generated_candidates.jsonl`.
- **Reconciliation:** After posts are published (or not), running `python main.py --reconcile` matches published posts to candidates and labels them as selected or rejected.
- **Acceptance priors:** The system computes a Beta-smoothed acceptance rate for each `(source, ssi_component)` bucket, so sources/topics you actually publish more often are ranked higher in future curation runs.
- **Adaptive ranking:** On each `--curate` run, articles are ranked by a weighted formula combining relevance, freshness, and acceptance prior. This means the system learns your preferences and adapts what it suggests over time.
- **User feedback:** Manual upvotes, rejections, or edits (via Buffer or moderation) are incorporated into the learning log and affect future ranking.

**How to use it:**

1. Run `python main.py --curate` to generate and log candidates.
2. Review and publish/reject posts in Buffer (or via moderation).
3. Run `python main.py --reconcile` to update acceptance priors.
4. Future curation runs will automatically prioritize sources/topics you prefer.

**Testing:**

- See `tests/test_content_curator.py` and `tests/test_selection_learning.py` for unit tests covering adaptive ranking, candidate logging, and acceptance prior computation.

**Config:**

- All learning data is local and gitignored. No cloud analytics or external logging is used.
- You can clear or edit the candidate log at any time to reset learning.

---
