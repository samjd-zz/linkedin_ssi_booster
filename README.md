<p align="center">
  <img src="media/favicons/logo1.png" alt="LinkedIn SSI Booster Logo" width="150">
</p>

# SSI Booster - :muscle: POWERED by Buffer.com!

<details>
<summary>🇯🇵 <b>日本語の概要はこちら (Click to expand Japanese summary)</b></summary>

<br />

### 概要 (Overview)

本ポートフォリオは、高い信頼性と決定論的な設計（Deterministic Engineering）に基づいた、実践的なAI/知能システムの構築原則を示しています。単なるプロンプト生成にとどまらず、検証可能なロジック、耐障害性マルチエージェント、および高精度なハイブリッド検索（BM25 + kNN）を備えたシステムを開発・運用しています。

### 主要プロジェクト (Featured Architectures)

- **LinkedIn SSI Booster**: 真偽検証ゲート（Truth-Gated）と継続的学習機能を備えた自動化エージェント。BM25、NetworkX、spaCyを統合し、ハルシネーション（幻覚）を防止。
- **Regulatory Intelligence Assistant (RIA)**: G7 GovAI Grand Challenge向け多層検索アーキテクチャ。Elasticsearch、Neo4jグラフトラバーサル、ベクトル検索により、カナダ連邦法データを高精度に解析。
- **Answer42**: 学術研究分析のための9エージェントパイプライン。Spring Batchによるフォールバック処理とサーキットブレーカーを備え、クラウドAPIからローカルOllamaへ自動切り替え。

### コア技術 (Key Technical Pillars)

1. **ハイブリッドRAG & 応答検証**: BM25によるキーワードスコアリング、NetworkXの構造解析、spaCyの意味検証を融合した多段階検証レイヤー（Truth Gate）。
2. **マルチエージェントオーケストレーション**: Spring管理の耐障害性、MCP/FastMCPプロトコルによるサービス間連携、ハードウェア制約に配慮したローカルルーティング。
3. **ディープインデキシング & 検索**: Elasticsearch, Neo4j, ベクトル検索 (kNN) を組み合わせた多層フォールバックにより、サブ500msの低遅延検索を実現。
4. **エンタープライズ & イベントストリーミング**: Java/JMSを用いた高スループットなエンタープライズシステム構築実績。

### 日本語のNLPと継続学習 (Japanese NLP & Continual Learning)

本システムは**日本語の記事から直接学習**します。新宿・東京の音楽シーンを中心に8つの日本語RSSフィード（Real Sound 音楽、CINRA、Spincoaster、FNMNL、Arban（新宿ピットイン系ジャズ）、block.fm、Higher Frequency、Qetic）を取り込み、spaCyの日本語パイプラインで解析します。

- **自動言語ルーティング** — 文字種（ひらがな・カタカナ・漢字）を検出し、`ja_core_news_md` と `en_core_web_md` を自動で切り替え
- **形態素解析** — SudachiPy（`spacy[ja]`）による日本語トークナイズ。Dockerイメージにモデルを同梱済み
- **固有表現抽出・要約・重複排除** — 抽出された事実は知識グラフに統合され、生成時の根拠として再利用されます
- **発表・新・開発・公開・導入** — 要約スコアリングは日本語の告知表現を加点対象として認識します

**現状の制約も明記しています。** ノイズフィルタは英語正規表現のみのため、日本語サイトのナビゲーションやフッターが本文に混入します。そのため日本語の抽出は英語より**再現率が高く適合率が低い**状態です。

なお、以前制約として記載していた以下は修正済みです——`ja_core_news_md` は `noun_chunks` を**実装しています**（spaCy 3.8.16 で検証済み）。文分割は `。！？` で正しく動作し、entities／tags の分類は空白ではなく抽出元（NER か名詞句か）で行います。詳細は [docs/spacy-extraction.md](docs/spacy-extraction.md) を参照してください。

### クリエイティブ & 音楽ノード (Creative Node: Rei Toei)

AIシステム設計に加え、ウィリアム・ギブスンのSF小説『アイドル（Idoru）』にインスパイアされたバーチャルペルソナ・アバター**「Rei Toei（東江麗）」**を通じて、VocaloidやSuno等を活用したサイバーポップ／インダストリアル音響のAI音声・音楽制作を行っています。

- 👤 **LinkedIn:** [Shawn Jackson-Dyck](https://linkedin.com/in/shawn-jackson-dyck-52aa74358/)
- 🎶 **Suno (Rei Toei):** [@samjd42](https://suno.com/@samjd42)

</details>

> **⚙️ Project Status:** Stable and actively maintained. Core features are production-ready, with ongoing refinement in image styling, music workflows, and research integrations. See [ROADMAP.md](ROADMAP.md) for longer-term directions.

##### <u>— Persona-Grounded Truth-Gated Adaptive-Continual-Learning Hybrid-RAG Multi-Avatar Content-Creation platform with Domain-Knowledge-Graph. Not your average [llm-wiki · GitHub](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 🤪

<p align="center">
  <a href="#"><img src="https://img.shields.io/badge/version-alpha--v0.0.3.5-F97316.svg" alt="Version alpha-v0.0.3.5"></a>
  <a href="https://developer.nvidia.com/cuda-toolkit"><img src="https://img.shields.io/badge/CUDA-13.2.0-76B900.svg?logo=nvidia" alt="CUDA 13.2.0"></a>
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
  <a href="docs/testing-and-dev.md"><img src="https://img.shields.io/badge/tests-885%20passed-16A34A.svg" alt="Tests 885 passed"></a>
  <a href="docs/testing-and-dev.md"><img src="https://img.shields.io/badge/coverage-98%25-brightgreen.svg" alt="Coverage 98%"></a>
</p>

<img src="media/favicons/2-score-ring_256x256.png" alt="SSI Score Ring" width="80" align="right">
<img src="media/favicons/2-score-ring_256x256.png" alt="SSI Score Ring" width="80" align="left">

**SSI Booster** is more than a prompt wrapper. It is an adaptive, continual-learning automation system for content, curation, and persona growth. It combines spaCy NLP, a persona graph, BM25 retrieval, a truth gate, confidence scoring, a NetworkX knowledge graph, and local memory to generate, curate, rank, and route posts.

Sign up for Buffer with my partner link — http://join.buffer.com/samjd42 — to schedule, publish, and analyze your social posts in one place while supporting this project.

---

## 🧠 Intelligence Stack

##### Why this is smarter than "AI writes posts"

- **Advanced multi-language NLP with spaCy** — theme/claim extraction, semantic similarity, fact suggestion when the truth gate drops a sentence, and multi-language routing (English `en_core_web_md` + Japanese `ja_core_news_md` with the SudachiPy tokenizer). The curator ships 8 Japanese-language music feeds out of the box, so the Japanese pipeline learns from real native-language sources rather than translated text. Preprocessing filters boilerplate before fact storage. See [docs/spacy-extraction.md](docs/spacy-extraction.md) and [docs/knowledge-extraction-improvement.md](docs/knowledge-extraction-improvement.md).
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

**Result:** A self-improving, persona-driven content engine that adapts to your taste, avoids repetition, and grows your SSI with full transparency and explainability.

---

## 📋 Status & Roadmap

The SSI Booster is feature-complete for its core workflows and is now focused on refinement and research. See **[ROADMAP.md](ROADMAP.md)** for:

- Ongoing platform polish (persona aesthetic tuning, UX and docs cleanup)
- MCP workflow hardening and integration refinement
- 🎯 Planned comic storyboard module for 3-panel grounded visual narratives
- Research track: RIA Canadian law knowledge integration (regulatory grounding)

**Have ideas?** [Open a GitHub issue](https://github.com/samjd-zz/linkedin_ssi_booster/issues) with the `enhancement` label.

---

## 🎵 Rei Toei - AI Music Avatar

<p align="center">
  <img src="media/rei-selfie1.jpg" alt="Rei Toei Selfie" width="320">
</p>

> **Inspiration:** Cyberpop-aesthetic AI music avatar inspired by [Rei Toei](https://en.wikipedia.org/wiki/Rei_Toei) from William Gibson's novel _Idoru_. See [Rei Toei Customization Guide](docs/rei-toei-customization.md) for full details on architecture, customization, and persona tuning.

**Rei Toei** transforms the SSI Booster into a **creative knowledge expression platform**, converting your curated technical knowledge into algorithmic music. See [Rei Toei Implementation Plan](docs/features/rei-toei/plan.md) for architecture, commands, and usage examples.

Listen to Rei Toei's music on Suno: [suno.com/@samjd42](https://suno.com/@samjd42)

**Current capabilities:**

- **Suno Vocal Songs** — Generate cyberpop industrial techno concepts with structured lyrics grounded in extracted knowledge (Suno integration ✅)
- **Japanese-aware lyric production** — Rei can generate English or Japanese lyrics using her mora-aware Japanese lyric knowledge, kana/kanji guidance, and Vocaloid-oriented delivery rules
- **Controlled lyric language selection** — `bilingual` mode is the default; its configurable Japanese-script lyric-line target defaults to 25%, while explicit `english` or `japanese` modes are deterministic
- **Knowledge boundaries** — Rei uses her own music and Japanese lyric-production knowledge. Sam uses the general Japanese domain packs for grounded study and conversation; Rei does not directly retrieve those study facts. Rei may receive selected Sam project, skill, and company names as optional creative inspiration, along with technical themes extracted from curated articles.
- **Strudel Live-Coding Patterns** — Translate technical themes into algorithmic music (Strudel MCP integration ✅)
- **Strudel Runtime Guardrails** — Auto-reject known runtime-invalid constructs (for example `.wrap(...)`) and enforce strict workshop syntax (`sound(...)` / `.sound(...)`, no legacy `s(...)` aliases)
- **Docker Audio Patch Path** — Default Docker command uses `scripts/strudel_mcp_patched.sh` to patch an upstream media-routing issue that can cause silent browser playback
- **Knowledge Grounding** — Every lyric is validated via Derivative of Truth for factual accuracy

**Access in console:**

```bash
python main.py --console
Sam> /rei-toei                    # Switch to Rei's persona
Rei> What concept should we sonify today?
You> Generate a song about async programming
Rei> [Generates song with Suno prompt and evidence IDs]
You> /sam                         # Switch back to Sam when you're done
```

After you enter Rei mode, plain follow-up messages stay with Rei until you switch back with `/sam` or exit the console.

---

## 🖼️ Image Generation with FLUX.1

<p align="center">
  <img src="media/alex-grey.jpg" alt="Alex Grey style visual" width="320">
</p>

> **Inspiration:** Visual style direction is Alex Grey-inspired, tuned for persona-aligned, symbolic technical storytelling.

> **Marketing focus:** The FLUX prompt stack is tuned for professional B2B outcomes by default, using a corporate-minimal preset plus a marketing-oriented style system prompt (clean hierarchy, brand-safe color discipline, conversion-oriented storytelling), with a dedicated `marketing_editorial` preset for campaign-ready LinkedIn creatives.

Generate persona-aligned visual content using FLUX.1-schnell locally.

**Current status:** FLUX.1 integration is stable; persona aesthetic tuning remains in progress (see [ROADMAP.md](ROADMAP.md)).

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

The image pipeline does not use a separate persona graph identity. It renders from source story text (schedule, curate, or console), applies the active style preset (default `corporate_minimal`, with built-ins including `marketing_editorial`, `sacred_geometry_light`, and `tech_dark`), incorporates `FLUX_CAPACITOR_STYLE_SYSTEM_PROMPT`, supports optional realism hints (`FLUX_CAPACITOR_REALISM_HINT` globally or per-request `realism_hint`), and accepts optional `knowledge_context` from the caller. In console mode, `/art` renders from the most recent assistant reply (or an explicit topic hint), and asking Sam to depict or draw Japanese characters, artwork, or cultural subjects automatically triggers an inline FLUX image render.

See [docs/flux-art-avatar.md](docs/flux-art-avatar.md) for configuration, style presets, GPU sequencing, and terminal display details. See [docs/multimodal-features.md](docs/multimodal-features.md) for the broader multimodal overview.

---

## 🏆 What is the Social Selling Index (SSI)?

The [LinkedIn Social Selling Index](https://www.linkedin.com/sales/ssi) is a 0-100 score that LinkedIn updates daily. It measures how effectively you build your personal brand, find the right people, engage with insights, and build relationships - the four pillars LinkedIn's algorithm uses to determine how widely your content and profile are surfaced.

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

- **Consistent cadence** — scheduled content is added to your Buffer queue, where Buffer owns publish cadence and posting times
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

The SSI Booster integrates with **Buffer for seamless social scheduling**. Scheduled calendar posts and curated posts are pushed to your Buffer queue (or Ideas for review) via the Buffer GraphQL API; Buffer owns the final queue placement, cadence, and publish times.

**Why Buffer?**

- Optimal posting times for maximum reach
- Multi-channel management (LinkedIn, Twitter, etc.)
- Queue management and performance analytics
- Full integration with SSI Booster's confidence routing (post → ideas → block)

**Support the project:** Use our [Buffer partner link](https://join.buffer.com/samjd42) to help fund development while getting started with Buffer scheduling!

**Roadmap Focus:** See [ROADMAP.md](ROADMAP.md) for next steps on the **Ollama Buffer MCP Agent** — a natural language interface to Buffer operations powered by Gemma 4 (code complete, Docker service active, unit tests added; live endpoint validation and consumer wiring pending).

## 👥 Multi-Client Operations (one repo, many clients)

For agencies or consultants handling multiple Buffer accounts, the recommended approach is one env file per client plus isolated cache/output paths.

- Full runbook: [docs/multi-client-runbook.md](docs/multi-client-runbook.md)
- Helpers:
  - `scripts/create-client.sh` (scaffold env + client folders)
  - `scripts/client-env.sh` (load and validate client env)
  - `scripts/run-client.sh` (run any `main.py` command with a client env)
  - `scripts/run-client-curate.sh` (preset curate workflow)

Quick examples:

```bash
scripts/create-client.sh acme
scripts/run-client.sh acme -- --schedule --week 1 --channel linkedin --type post
scripts/run-client-curate.sh acme
scripts/run-client-curate.sh acme --live --type post --reconcile
```

Use unique per-client values for `IDEAS_CACHE_PATH`, `GENERATED_CONTENT_DIR`, and (if enabled) `DATABASE_URL`/`POSTGRES_DB` to avoid cross-client data contamination.

---

## 🔍 Learning, Grounding, and Explainability Pipeline

- **Candidate logging** — every post and article candidate is logged with full metadata for a complete audit trail.
- **Reconciliation & priors** — Buffer publication outcomes update Beta-smoothed acceptance priors per source/topic/SSI component; well-performing sources float upward over time.
- **Ranking** — candidates ranked by acceptance priors × BM25 scores, continuously adapting to your preferences.
- **Signal flow** — truth gate reason codes → confidence scorer (`post`/`idea`/`block`) → Buffer reconciliation → priors update. Sources that reliably produce clean, grounded posts rise; sources that trigger heavy filtering sink.
- **Deterministic grounding** — BM25Okapi retrieves persona/domain facts for every generation; prompts forbid invented stats, dates, or companies. The four-layer truth gate enforces this post-generation.
- **Multi-language extraction** — spaCy routes text to `en_core_web_md` or `ja_core_news_md` by character set, then summarizes, extracts entities/tags, and de-duplicates before writing facts to the knowledge graph.

See [docs/learning-pipeline.md](docs/learning-pipeline.md) · [docs/spacy-extraction.md](docs/spacy-extraction.md) · [docs/selection-learning.md](docs/selection-learning.md) · [docs/derivative-of-truth.md](docs/derivative-of-truth.md).

---

## 🧮 Derivative of Truth (DoT) + Probabilistic Logic Networks (PLN)

Every generated sentence receives a composite truth gradient score across four terms: evidence quality × reasoning strength × source credibility × claim-evidence token overlap (Jaccard). Sentences below `TRUTH_GRADIENT_FLAG_THRESHOLD` (default 0.35) are flagged `weak_dot_gradient` and removed before publication.

PLN brings formal logic reasoning (deduction, induction, abduction, revision) with truth trajectory tracking (`dT/dt`) and dual-mode PLN vs legacy comparison. PLN is active by default. Use `--dot-report` to print the full gradient, evidence, and uncertainty breakdown for any run.

See [docs/derivative-of-truth.md](docs/derivative-of-truth.md) · [docs/dot-pln-enhancement.md](docs/dot-pln-enhancement.md).

---

## 🧩 Knowledge Graph: NetworkX Core, Neo4j for Expansion

The core knowledge graph uses NetworkX — in-memory, pure Python, fast for the graph sizes a single avatar generates. Neo4j is the scale-out path for multi-avatar, enterprise, or bulk-import scenarios approaching the ~100k node/edge range where NetworkX starts to strain, requiring persistent disk-backed storage and Cypher queries.

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

### 🇯🇵 Learning from Japanese sources

The curator ships with 8 Japanese-language music feeds covering the Shinjuku/Tokyo scene — Real Sound 音楽, CINRA, Spincoaster, FNMNL, Arban (jazz / 新宿ピットイン), block.fm, Higher Frequency, and Qetic. These are real native-language sources, not translations, so the `ja_core_news_md` pipeline gets exercised end to end: SudachiPy tokenization, NER, semantic similarity, lemma-based BM25 retrieval, and fact extraction into the same knowledge graph English articles feed.

Routing is automatic — `detect_language()` checks for Hiragana, Katakana, or Kanji and picks the matching model from `SPACY_MODELS`. Keyword filtering is substring-based, so Japanese feeds need Japanese keywords; `CURATOR_KEYWORDS_EXTRA` appends them without discarding the English defaults.

**Known limitations, stated plainly:** Every noise filter is an English regex, so Japanese site chrome (nav menus, share buttons, footer links) still passes through into statement text. Japanese extraction is therefore higher-recall and lower-precision than English — useful as retrieval evidence, noisier per fact.

Previously documented here as a limitation, now fixed: `ja_core_news_md` **does** implement `noun_chunks` (verified on spaCy 3.8.16), sentence splitting now fires on `。！？`, and entities/tags are split by source (NER vs noun chunks) rather than by ASCII whitespace — the old whitespace rule filed every Japanese theme as a tag because Japanese is written without spaces.

Full breakdown in [docs/spacy-extraction.md](docs/spacy-extraction.md), including the shared search tokenizer and batched spaCy processing used by retrieval and grounding.

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
- [Multi-client runbook](docs/multi-client-runbook.md) — one-repo workflow for managing multiple client accounts with per-client env files and helper scripts

### Core Intelligence & Learning

- [Architecture guide](docs/architecture.md) — learning pipeline, grounding flow, truth gate, and curation ranking
- [Learning pipeline](docs/learning-pipeline.md) — truth gate layers, confidence scoring, routing policies, and explainability features
- [spaCy extraction](docs/spacy-extraction.md) — what each article teaches the avatar, the `ExtractedFact` schema, language routing, and tuning knobs
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
- [Testing and development](docs/testing-and-dev.md) — pytest coverage and project structure (885 collected; 885 passed, 0 failed)

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
python -m spacy download ja_core_news_md  # recommended: Japanese multi-language NLP
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
- `REI_LYRIC_LANGUAGE` — `bilingual` (default), `japanese`, or `english`; explicit language modes ignore the probability setting
- `REI_JAPANESE_LYRIC_PROBABILITY` — Japanese selection probability in bilingual mode (default: `0.25`)
- `KATZILLA_ENABLED` / `KATZILLA_API_KEY` — Optional external evidence retrieval via Katzilla
- `KATZILLA_TELEMETRY_ENABLED` / `KATZILLA_MAX_CALLS_PER_DAY` — Katzilla observability and daily budget controls

See [docs/environment-variables.md](docs/environment-variables.md) for comprehensive reference covering 40+ configuration options across Buffer, Ollama, truth gate, Model2Vec, voice/TTS, image generation, Strudel music, Katzilla external evidence, and database integration.

[MIT License](LICENSE) — see LICENSE for details.
