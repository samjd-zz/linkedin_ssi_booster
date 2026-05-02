# Usage Guide

The CLI centers on three main workflows: scheduling from a private content calendar, curating from live RSS sources, and running a grounded interactive console. A `--dry-run` mode is available across flows to generate and inspect outputs without making Buffer API calls.

## Main commands

```bash
python main.py --schedule --week 1 --dry-run
python main.py --curate --dry-run
python main.py --console
python main.py --report
python main.py --save-ssi 10.49 9.69 11.0 12.15
```

`--schedule` uses `content_calendar.py`, `--curate` uses live RSS feeds filtered by niche keywords, and `--console` opens an interactive persona chat with deterministic grounding for factual project, career, and domain knowledge queries. The documentation also lists `/help`, `/reset`, and `/exit` as console commands.

## Schedule mode

`--schedule --week N` generates posts from the selected week of the content calendar and schedules them through Buffer unless `--dry-run` is supplied. The scheduler uses configured posting slots and SSI focus weights from `.env`, preserves topic order within components, and avoids repeating topics within a week.

Examples:

```bash
python main.py --schedule --week 1
python main.py --schedule --week 1 --channel x
python main.py --schedule --week 1 --channel all
python main.py --schedule --week 1 --avatar-explain
```

## Curate mode

`--curate` scans RSS feeds, filters by domain keywords, ranks candidate articles, generates commentary, and by default sends outputs to the Buffer Ideas board for review. Adding `--type post` bypasses the draft-first behavior and schedules curated posts directly to the next available queue slot.

Examples:

```bash
python main.py --curate
python main.py --curate --type post --channel linkedin
python main.py --curate --type post --channel x
python main.py --curate --confidence-policy strict
python main.py --curate --avatar-explain
```

### Console mode — welcome screen and query routing

When you run `--console`, the startup screen explains the three query modes:

```
📋 Project & career questions (deterministic, cited answers)
🧠 Domain knowledge questions (routed to domain facts)
💬 Free-form persona chat (AI-generated, grounded in persona)
```

Routing is **deterministic** — no model call is made for grounded queries. The router detects intent from the query text and retrieves the best-matching facts from the in-memory fact pool, which combines persona graph facts and domain knowledge facts.

#### Query routing rules

| Trigger pattern                                                                               | Route                      | Fact source                                          |
| --------------------------------------------------------------------------------------------- | -------------------------- | ---------------------------------------------------- |
| Contains "project", "worked on", "built", "resume"                                            | Project/career grounding   | Persona graph evidence facts                         |
| Contains "company", "where", "worked at", "employer"                                          | Company/career grounding   | Persona graph evidence facts                         |
| Contains "what is", "explain", "how does", "tell me about", "expertise", "describe", "define" | Domain knowledge grounding | Domain knowledge facts                               |
| Contains a known tech keyword (e.g. "java", "rag", "bm25", "llm")                             | Tech-tagged grounding      | Both persona and domain facts, scored by tag overlap |
| None of the above                                                                             | Free-form chat             | AI model with persona grounding context              |

#### Example queries for persona and domain knowledge

| Example Query                                    | What It Accesses                | Notes                               |
| ------------------------------------------------ | ------------------------------- | ----------------------------------- |
| What projects have you worked on?                | Persona — project facts         | Deterministic, cited                |
| Where have you worked?                           | Persona — project facts         | Lists companies from persona graph  |
| What Java or Spring Boot projects have you done? | Persona + domain — tag-filtered | Tech tag triggers mixed retrieval   |
| What is RAG?                                     | Domain knowledge                | Routes on "what is" phrase          |
| Explain BM25 retrieval.                          | Domain knowledge                | Routes on "explain" phrase          |
| How does vector search work?                     | Domain knowledge                | Routes on "how does" phrase         |
| Tell me about microservices.                     | Domain knowledge                | Routes on "tell me about" phrase    |
| What do you know about LLMs?                     | Domain knowledge                | Routes on "what do you know" phrase |
| What is prompt engineering?                      | Domain knowledge                | Routes on "what is" + tech keyword  |
| What are your skills?                            | Free-form persona chat          | No grounding trigger; handled by AI |

> **Tip:** Questions that start with "what is", "explain", "how does", or "tell me about" route directly to domain knowledge facts. Questions about projects, companies, or specific technologies route to a mixed pool of persona and domain facts. All other questions go to the AI model with persona grounding context injected.

#### Domain knowledge tech keywords (built-in)

The following terms are recognized by the console router and trigger tech-tag grounding. They can be extended via the `CONSOLE_GROUNDING_TECH_KEYWORDS` env var.

**Persona / project stack:** `java`, `spring`, `spring boot`, `spring ai`, `spring batch`, `jms`, `python`, `fastapi`, `scikit-learn`, `gymnasium`, `stable-baselines3`, `elasticsearch`, `solr`, `lucene`, `neo4j`, `rag`, `mcp`, `fastmcp`, `oracle`, `weblogic`, `jsf`, `adf`, `vaadin`, `hibernate`, `tomcat`

**Domain knowledge terms:** `llm`, `bm25`, `knn`, `k-nearest`, `vector search`, `embeddings`, `semantic search`, `microservices`, `prompt engineering`, `retrieval`, `fine-tuning`, `machine learning`, `deep learning`, `neural network`, `transformer`, `agent`, `agentic`, `api`, `rest`, `graphql`, `docker`, `kubernetes`, `kafka`, `data pipeline`, `etl`, `information retrieval`, `ranking`, `similarity`, `reranking`

## Channel behavior

The README documents channel-specific output rules across LinkedIn, X, Bluesky, Threads, YouTube, and `all`. LinkedIn appends source URLs and hashtags programmatically, while X, Bluesky, and Threads are shorter single-post outputs without hashtag appending, and YouTube produces spoken Short scripts that are saved locally rather than sent to Buffer.

| Channel    | Behavior                                                                                                |
| ---------- | ------------------------------------------------------------------------------------------------------- |
| `linkedin` | Default channel; source URL and hashtags are appended programmatically for curation output.             |
| `x`        | 280-character limit, single paragraph, no hashtag append.                                               |
| `bluesky`  | 300-character limit, X-like post behavior.                                                              |
| `threads`  | 500-character limit, conversational short post behavior, no hashtag append.                             |
| `youtube`  | Generates a spoken script, prints it, and saves it to `yt-vid-data/`; not pushed to Buffer.             |
| `all`      | Runs LinkedIn, X, Bluesky, Threads, and YouTube together, with YouTube handled as a local script artifact. |

## Curation pipeline

On each `--curate` run, the project fetches RSS entries, filters them by keyword match, ranks them by relevance, freshness, and acceptance priors, deduplicates against local caches, generates commentary, logs candidates, appends article links, and routes the result to Buffer Ideas or scheduled posts depending on flags. This makes curation both content-generation and data-collection infrastructure for later reconciliation.

## Reconcile mode

`--reconcile` compares Buffer-published posts against `data/selection/generated_candidates.jsonl` using exact Buffer post ID, article URL, or Jaccard token similarity. Matched candidates become `selected=True`, older unmatched candidates become `selected=False`, and these labels feed Beta-smoothed acceptance priors for future curation ranking.

## YouTube workflow

YouTube output is intentionally treated as a script-generation path rather than a publish path because Buffer requires a video file for YouTube. The generated script is designed for avatar or lip-sync tools, printed to screen, and written to `yt-vid-data/<timestamp>_<title>.txt` for manual rendering and upload.

### **Troubleshooting Grounding Quality**

If grounded outputs feel too generic or personal references are missing, this is usually a retrieval-configuration issue rather than a generation issue.

Common symptoms and fixes:

- Symptom: Output avoids personal project references even when relevant. Likely cause: `CONSOLE_GROUNDING_TECH_KEYWORDS` does not include terms used in your topic or persona graph. Fix: Add missing terms (for example: `spring ai`, `sentence transformers`, `pubsub+`, `fastmcp`) in lowercase.

- Symptom: Broad prompts like "Java" or "Python" miss obvious related projects. Likely cause: `CONSOLE_GROUNDING_TAG_EXPANSIONS` is too narrow. Fix: Expand umbrella tags so broad queries include adjacent stack terms (for example `java:spring|jms|oracle|weblogic`).

- Symptom: Irrelevant personal facts are injected for unrelated topics. Likely cause: Keyword list is too broad/noisy. Fix: Remove vague terms and keep only high-signal domain vocabulary.

- Symptom: Console factual answers look right, but `--curate` still feels weakly grounded.Likely cause: Curation articles use topic vocabulary that does not overlap `CURATOR_KEYWORDS` or `CONSOLE_GROUNDING_TAG_EXPANSIONS`.Fix: Add domain terms to `CURATOR_KEYWORDS` (for tech matching) or `CONSOLE_GROUNDING_TAG_EXPANSIONS` (for umbrella expansion).

- Symptom: Good posts lose one useful sentence after generation.Likely cause: The sentence contains a specific number/date/company token not present in article text or retrieved facts. Fix: Expand grounding keywords/tag expansions so the correct fact is retrieved, or rephrase the prompt/topic so the claim appears in source evidence.

- Symptom: Truth gate often removes 2+ sentences for curation posts. Likely cause: Retrieval signal is weak for that article domain, so evidence is too thin. Fix: Add domain terms to `CURATOR_KEYWORDS` and expand umbrella terms in `CONSOLE_GROUNDING_TAG_EXPANSIONS`.

1. Start with a compact keyword set that mirrors your persona graph skill and project tags.
2. Add tag expansions for umbrella terms (`java`, `python`, `rag`).
3. Run `--console` with factual prompts and confirm retrieved facts match expectations.
4. Run `--schedule --dry-run` and `--curate --dry-run` and inspect whether personal references are relevant and supported.
5. Iterate by adding/removing only a few terms at a time.
