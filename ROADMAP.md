# SSI Booster Roadmap

This document outlines planned features, integrations, and research directions for the SSI Booster platform. Items are listed in order of priority and feasibility.

---

## ✅ Complete: Katzilla.dev Integration (Phases 1-6)

**One API. Every US government dataset. Citations baked into every response.**

[Katzilla.dev](https://katzilla.dev/) is fully integrated as an optional external evidence source for avatar knowledge grounding. Katzilla provides **287+ tool-use actions across 32 agent-ready categories**, wrapping every major US government dataset behind a single REST API with built-in citation tracking.

### What Katzilla Provides

- **283,051+ validated datasets** — SEC filings, FDA recalls, Federal Register, Congressional records, clinical trials, USGS earthquakes, labor statistics, and more
- **Citation contract** — Every response includes `source_name`, `source_url`, `retrieved_at`, `data_hash` (SHA256 verification), `license`, and `update_frequency`
- **Quality metadata** — Freshness (seconds since last update), source uptime (7-day rolling), confidence scores, and certainty ratings
- **Token optimization** — Field filtering, compact mode, pagination, unit conversion, and summary aggregation to reduce LLM costs
- **Multiple SDKs** — TypeScript, Python, LangChain, Anthropic Claude, MCP, and Agent2Agent protocol support

### How It Fits SSI Booster

- **Expand evidence base** — Supplement persona facts with real-world government data (e.g., verify company claims against SEC filings, check labor statistics for hiring trends)
- **Enhanced truth validation** — Truth gate layers can verify claims against primary sources with cryptographic verification (`data_hash`)
- **Automatic citation** — Every Katzilla-sourced fact includes full provenance (source URL, retrieval timestamp, license)
- **Continual learning boost** — Knowledge extraction pipeline gains access to 283K+ datasets without manual curation

### What Was Built (6 Phases)

- **Phase 1** — `services/katzilla_service.py`: HTTP client, envelope validation, error mapping, safe retry
- **Phase 2** — `services/avatar_intelligence/_katzilla_adapter.py`: envelope → `ExternalEvidenceFact` with full citation provenance
- **Phase 3** — Retrieval integration: action allowlist (congress-bills, fda-recalls, usgs-earthquakes), compact format, bounded result caps, graceful fallback
- **Phase 4** — Truth-gate & DoT wiring: external facts flow into `ExplainOutput`, `_gate_helpers.py` credibility tier (0.55), and `external_fact_to_evidence_path()` for DoT scoring
- **Phase 5** — Console `/katzilla <query>` command for deterministic citation-first output; curation enrichment pipelines external facts through all channel dispatch methods
- **Phase 6** — `services/katzilla_telemetry.py`: JSONL event store, `can_call_katzilla()` daily call/uncertainty budget guard, env knobs (`KATZILLA_TELEMETRY_ENABLED`, `KATZILLA_MAX_CALLS_PER_DAY`, `KATZILLA_MAX_UNCERTAINTY_PER_DAY`)

### Configuration

All features are **default-off** (`KATZILLA_ENABLED=false`). Set `KATZILLA_ENABLED=true` and `KATZILLA_API_KEY` to activate. See [docs/environment-variables.md](docs/environment-variables.md) for all knobs.

### Status

**✅ Complete** — 23 files, 16 tests, fully committed and pushed (June 2026)

> **Learn more:** [Katzilla Documentation](https://katzilla.dev/docs) — REST API with 287+ actions, TypeScript/Python SDKs, and Agent2Agent protocol support

---

## 🏛️ Research Phase: RIA Canadian Law Knowledge Integration

**Regulatory Intelligence Assistant (RIA) — 400K+ structured Canadian regulations as avatar grounding.**

We're reviewing how to bring avatar intelligence to the [Regulatory Intelligence Assistant](https://github.com/samjd-zz/regulatory-intelligence-assistant) project as well as give the SSI avatars access to **structured Canadian legal and regulatory knowledge** for enhanced domain grounding.

### What RIA Provides

- **399,705 searchable documents** — 4,240 Canadian regulations + 395,465 regulatory sections (PostgreSQL + Elasticsearch + Neo4j)
- **Neo4j Knowledge Graph** — 278,858 nodes + 470,353 relationships linking legislation → sections → regulations → policies → programs
- **Multi-tier search** — 5-tier fallback architecture (Elasticsearch → Neo4j Graph → PostgreSQL FTS → Metadata) with <50ms-500ms response times
- **AI-powered Q&A** — RAG pipeline with chain-of-thought reasoning, citation support, and confidence scoring (Gemini API)
- **Compliance validation** — Real-time requirement extraction and field-level validation (<50ms)
- **Bilingual support** — Full English/French coverage of Canadian federal regulations

### How It Fits SSI Booster

- **Legal grounding for regulatory claims** — Ground claims about Canadian employment insurance, data protection, corporate law, or government programs against actual legislation
- **Neo4j graph integration** — Extend the NetworkX knowledge graph with Canadian legal relationships (e.g., "This regulation implements Section X of Act Y")
- **Citation-backed assertions** — Every regulatory claim includes section numbers, act names, and official references
- **Domain expansion** — Add GovTech, regulatory compliance, and public sector AI as first-class SSI categories

### Technical Approach

- RIA API integration via new `services/ria_service.py` module (REST API at localhost:8000)
- Hybrid knowledge graph — persona facts + domain facts + **RIA legal facts** (legislation sections, regulations, programs)
- Cross-system citation tracking — RIA's PostgreSQL/Neo4j/Elasticsearch responses feed the truth gate with structured legal references
- Bilingual knowledge base — French regulatory terms auto-translate to English for BM25 retrieval compatibility

### Future Vision

We're exploring the possibility of **merging SSI Booster and RIA into one complete grounded avatar platform**. RIA already has a production-ready React frontend with full UI plumbing (FastAPI backend, real-time chat), which could serve as the unified interface for truth-gated, regulatory-aware, persona-driven content automation — combining SSI Booster's learning pipeline with RIA's legal knowledge infrastructure.

### Status

**Research phase** — evaluating API integration, knowledge graph merge strategy, and cross-border regulatory scope

**RIA Upgrade:** The Regulatory Intelligence Assistant is being upgraded and will be deployed as a Docker image to support the SSI Booster avatar, providing seamless integration with the existing Docker Compose stack for local-first regulatory knowledge grounding. The official Docker image will be published to [Docker Hub](https://hub.docker.com/) for easy public access and deployment.

> **Learn more:** [RIA GitHub Repository](https://github.com/samjd-zz/regulatory-intelligence-assistant) — FastAPI backend, React frontend, PostgreSQL + Neo4j + Elasticsearch stack, 397 tests passing

---

## 🎨 Alex Grey Avatar Enhancement

**High-fidelity persona-aligned image generation enhancements.**

The local image generation pipeline (FLUX.1-schnell) is being enhanced with Alex Grey-inspired aesthetic guidance for persona-aligned visual content. This will enable the avatar to generate visuals that match the technical/artistic fusion style associated with the project's identity.

### Status

**Active development** — FLUX.1 integration complete, persona aesthetic tuning in progress

---

## 📤 Ollama Buffer MCP Agent

The system now includes an autonomous Buffer integration agent powered by the **Buffer Model Context Protocol (MCP)**. This agent generates Buffer API requests using Gemma 4 and sends them directly to Buffer's MCP server for seamless social media management.

- **Autonomous Agent Service:** Runs as a standalone Docker service (`buffer-mcp-agent`) in the stack.
- **Natural Language Interface:** Uses Gemma 4 to translate plain English commands into properly formatted Buffer MCP requests.
- **Direct MCP Integration:** Connects to Buffer's official MCP server at `https://mcp.buffer.com/mcp` — no custom bridge required.
- **Full Buffer API Access:** List channels, create posts, manage drafts, schedule content, and more via conversational commands.
- **Container-Native:** Runs alongside Ollama in Docker with automatic authentication using your `BUFFER_API_KEY`.

---

## 📊 Future Considerations

- **Database integration hardening** — expand the PostgreSQL dual-write layer beyond selection-learning records, keep the JSON/JSONL fallback intact, and continue validating schema/repository alignment as the rollout grows.
- **Multi-avatar support** — Deploy multiple personas with isolated knowledge graphs (requires Neo4j backend)
- **Voice-controlled Buffer operations** — Extend Wyoming Piper TTS integration for hands-free content management
- **Automated post-performance analytics** — Buffer API metrics integration for learning signal feedback
- **Cross-platform expansion** — Instagram, TikTok, Mastodon channel support
- **Enterprise deployment** — Multi-user, multi-tenant architecture with RBAC

---

## 🤝 Contributing Ideas

Have a feature request or integration idea? Open an issue on [GitHub](https://github.com/samjd-zz/linkedin_ssi_booster/issues) with the `enhancement` label.

---

**Last Updated:** June 2026
