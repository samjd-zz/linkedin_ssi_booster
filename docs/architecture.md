# Architecture Guide

LinkedIn SSI Booster is built as a persona-grounded, hybrid retrieval and generation system with deterministic validation layers around model output. Its architecture combines local generation, profile fact retrieval, candidate logging, adaptive ranking, and post-generation truth filtering.

## Core pipeline

The project describes itself as a practical “Persona Graph · Truth-Grounded Learning · Hybrid RAG” workflow rather than a single prompt call. The main flow is retrieve relevant facts with BM25, generate with channel-aware rules, validate unsupported claims deterministically, then publish or route content through Buffer.

High-level stages include:

- Retrieval grounding from persona facts using BM25Okapi.
- Prompt orchestration for LinkedIn, X, Bluesky, and YouTube outputs.
- Deterministic truth-gate filtering after generation.
- Scheduling, curation, and SSI-balanced operational routing.

## Learning pipeline

The learning loop logs every generated post and curated article candidate, not just published outputs, so the system keeps a full audit trail of what it considered. It then reconciles published or rejected outcomes to update acceptance priors per source, topic, and SSI component, allowing future ranking to adapt to real publishing choices.

The ranking layer combines acceptance priors with BM25-style relevance signals so the best-performing content sources rise over time. This gives the project a practical feedback loop rather than a static generate-and-forget behavior.

## Deterministic grounding

Grounding is designed to reduce hallucinated personal claims by forcing outputs to stay anchored to known profile facts. The grounding pipeline loads persona facts, detects request constraints, retrieves relevant facts with BM25Okapi or a keyword-overlap fallback, applies prompt balance rules, and then removes unsupported claim sentences in a truth-gate pass.

The README states that prompt constraints require factual claims to come from article text or profile facts, cap personal references, and forbid invented stats, dates, and company names. It also notes that project-specific technology attribution is constrained so a named project can only be paired with technologies present in its own detail field.

## Truth gate

The truth gate evaluates sentences independently and removes only those that contain unsupported or weakly grounded claims. It uses a two-layer validation approach:

1. **BM25 Evidence Strength Check (Primary)** — Scores each sentence against a corpus built from article text and persona facts using BM25Okapi, the same probabilistic ranking algorithm used in production search engines like Elasticsearch. Sentences with BM25 scores below the configured threshold (default: 1.0) are flagged as weakly supported. This provides flexible, context-aware validation that handles paraphrasing and partial matches naturally.

2. **Strict Token Matching (Complementary)** — Validates specific claim types using exact token matching: numeric claims, year references, dollar amounts, company-style context patterns, and project-technology misattributions. These checks complement BM25 by catching exact numeric or organizational mismatches that might otherwise slip through.

Project-technology checks combine retrieved evidence with all available persona project details, merging entries for the same project. Other truth-gate checks still use their existing evidence and thresholds.

The BM25 threshold can be tuned via `TRUTH_GATE_BM25_THRESHOLD` in `.env` (0.5 = permissive, 1.0 = balanced, 2.0 = strict, 5.0 = very strict). The gate does not rewrite text, and it is intentionally conservative rather than acting as a full external fact-checker. The documentation also notes support for an `--interactive` mode that pauses on flagged sentences for manual approval.

### Deterministic Grounding & Truth Gate Flow

Below is a visual representation of how deterministic grounding and the truth gate operate:

```mermaid
flowchart TD
    A[User Request/Prompt] --> B[Load Persona Facts<br/>persona_graph.json]
    B --> C[Detect Request Constraints<br/>caps, domain terms, keywords]
    C --> D{Retrieve Relevant Facts}
    D -->|BM25Okapi| E[BM25 Retrieval]
    D -->|Fallback| F[Keyword Overlap]
    E --> G[Apply Prompt Balance Rules]
    F --> G
    G --> H[Generate Content<br/>LLM with grounded context]
    H --> I[Truth Gate Validation<br/>sentence-by-sentence]
    I --> J{Check Claims}
    J -->|Numeric claims| K[Validate against facts]
    J -->|Year references| K
    J -->|Dollar amounts| K
    J -->|Company names| K
    J -->|Project-tech pairs| K
    K --> L{All Claims<br/>Supported?}
    L -->|Yes| M[Output Final Content]
    L -->|No, unsupported| N{Interactive<br/>Mode?}
    N -->|Yes| O[Pause for Manual Approval]
    N -->|No| P[Remove Unsupported Sentences]
    O -->|Approved| M
    O -->|Rejected| P
    P --> M
    M --> Q[Route to Buffer/Ideas/Block]

    style I fill:#e1f5ff
    style K fill:#fff4e1
    style L fill:#ffe1e1
    style M fill:#e1ffe1
```

If your Markdown viewer does not support Mermaid, the flow is: Load persona facts → Detect constraints → Retrieve facts (BM25 or keyword fallback) → Apply prompt rules → Generate content → Truth gate validates each sentence → Check claims against facts → Remove unsupported claims (or interactive approval) → Output final content → Route to destination.

## Environment controls

Grounding relevance and truth validation can be tuned through `.env` values such as:

- `CONSOLE_GROUNDING_TECH_KEYWORDS`
- `CONSOLE_GROUNDING_TAG_EXPANSIONS`
- `TRUTH_GATE_DOMAIN_TERMS`
- `TRUTH_GATE_BM25_THRESHOLD` (new)

**TRUTH_GATE_BM25_THRESHOLD** sets the strictness of the BM25 evidence strength check in the truth gate. Lower values (e.g., 0.5) are more permissive, allowing weaker or paraphrased claims; higher values (e.g., 2.0 or 5.0) require stronger evidence overlap. The default is 1.0 for balanced validation. Set this in your `.env` or `.env.example` to control the threshold for sentence removal based on BM25 score.

For curation, keyword matching can also fall back to `CURATOR_KEYWORDS`, which makes retrieval quality dependent on the overlap between article vocabulary and configured domain terms.

## Curation ranking

The curation pipeline ranks articles with a weighted formula that combines keyword relevance, freshness decay, and adaptive acceptance priors. Deduplication is handled through a local cache, and every selected article becomes a logged candidate before or after Buffer routing, depending on the flow.

This architecture means the project learns not only from the model prompt context, but also from the operational outcome of what users approve, publish, or ignore.

## System Architecture Diagram

Below is a high-level system architecture diagram for the LinkedIn SSI Booster:

```mermaid
flowchart TD
        A[User/CLI] --> B[main.py]
        B --> C[Content Curation]
        B --> D[Scheduling]
        C --> E[RSS Fetch & Summarize]
        C --> F[Candidate Logging]
        F --> G[Selection Learning]
        G --> H[Acceptance Priors]
        G --> I[Reconciliation]
        E --> J[Buffer API]
        D --> J
        J --> K[Channels: LinkedIn/X/Bluesky/YouTube]
        G --> L[spaCy NLP]
        L --> G
        G --> M[Ranking]
        M --> D
        subgraph Persona Graph
            N[persona_graph.json]
            N --> G
        end
        subgraph Local Data
            O[generated_candidates.jsonl]
            P[published_posts_cache.jsonl]
            O --> G
            P --> I
        end
        G --> O
        I --> P
        D --> Q[APScheduler]
        Q --> D
        B --> R[SSI Tracker]
        R --> S[ssi_history.json]
        S --> R
```

If your Markdown viewer does not support Mermaid, refer to the textual architecture description above.
