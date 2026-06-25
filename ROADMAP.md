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

### Coming Soon (Next Milestones)

- **Ollama-first generation sequencing** — text grounding and narrative generation complete first, then image generation starts to keep single-GPU workloads predictable.
- **System-wide local-first artifact persistence** — generated outputs are saved locally by default across features (not avatar-only), with a consistent generated-content directory strategy.
- **Unified generated-content paths** — env-driven storage layout for generated artifacts:
	- `GENERATED_CONTENT_DIR`
	- `YOUTUBE_SCRIPTS_SUBDIR`
	- `REI_TOEI_SUBDIR`
- **Database-second rollout** — PostgreSQL remains an optional secondary layer for indexing/analytics while local JSON/JSONL artifacts remain the source of truth during transition.
- **Flux capacitor service direction** — FLUX docs and feature planning align on `flux_capacitor` naming; runtime compose service naming migration remains a planned follow-up.
- **FLUX art-avatar implementation phase** — move from planning docs to runtime implementation (`services/art_avatar/*`) with channel-aware visual generation and publish safety controls.

### Status

**Active development** — FLUX.1 integration complete, persona aesthetic tuning in progress

---

## � Ollama Buffer MCP Agent — In Progress

**Status:** Code complete ✅, retry safety fixed ✅, Docker service re-enabled ✅, unit tests added ✅

The Buffer integration agent code exists (`agents/buffer_mcp_agent.py`) and is powered by **Gemma 4 + Buffer Model Context Protocol (MCP)**. **The agent has been hardened against retry loops and GPU hammering** with proper health checks, exponential backoff, and timeouts.

### What's Fixed (June 2026)

- ✅ **Health Check with Exponential Backoff:** `check_ollama_health()` prevents immediate connection failures from hammering Ollama
- ✅ **Timeouts on All Operations:** 5s health check, 30s generation, 15s HTTP send
- ✅ **Logging Infrastructure:** Replaced all `print()` calls with structured logging for Docker debugging
- ✅ **Graceful Error Handling:** Proper `sys.exit(0/1)` codes and exception handling on all async operations
- ✅ **Docker Service Re-enabled:** `buffer-mcp-agent` uncommented in `docker-compose.yml` with `restart: on-failure`
- ✅ **Environment Variable Support:** `OLLAMA_HOST`, `OLLAMA_MODEL`, `BUFFER_MCP_URL`, `BUFFER_API_KEY`, `BUFFER_PROMPT`

### What's Pending

- 🔍 **Verification Required:** Validate that Buffer MCP server endpoint (`https://mcp.buffer.com/mcp`) works as documented
- 📋 **Consumer Integration:** Wire the agent into `main.py` CLI commands or console mode

### Next Steps to Complete

1. Run live endpoint verification against Buffer MCP (`https://mcp.buffer.com/mcp`) in Docker and local flows
2. Run `docker compose --profile core up -d && docker logs -f ssi_booster_buffer_mcp_agent` to validate health check flow
3. Wire into console mode or scheduled posting pipeline if ready

---

## 🎵 Rei Toei AI Music Avatar — Strudel MCP Ready for Testing

**Status:** Code complete ✅, Strudel MCP retry safety fixed ✅, MCP stdio flow active ✅, unit tests added ✅

Rei Toei is an AI music avatar system designed to generate personalized music and sonic branding aligned with persona aesthetics. The system uses **Suno vocal generation + Strudel live-coding patterns** for composable music creation. **The Strudel MCP agent has been hardened against retry loops and GPU hammering** with proper health checks, exponential backoff, and timeouts.

### What's Fixed (June 2026)

- ✅ **Strudel MCP Health Check:** `check_ollama_health()` prevents immediate Ollama connection failures from hammering GPU
- ✅ **Exponential Backoff:** Retry failures wait 2s → 4s → 8s → 16s → 30s (max 5 retries) before giving up
- ✅ **Comprehensive Timeouts:** 5s health check, 30s generation, bounded MCP request timeouts
- ✅ **Logging Infrastructure:** Replaced all `print()` calls with structured logging for Docker debugging
- ✅ **Graceful Error Handling:** Proper `sys.exit(0/1)` codes and exception handling on all async operations
- ✅ **MCP Stdio Hardening:** `strudel-mcp-agent` runs as the single Strudel entrypoint via `STRUDEL_MCP_COMMAND`; legacy websocket bridge service removed
- ✅ **Environment Variable Support:** `OLLAMA_HOST`, `OLLAMA_MODEL`, `STRUDEL_MCP_COMMAND`, `STRUDEL_PROMPT`

### What Exists

- **Strudel MCP Agent:** `agents/strudel_mcp_agent.py` with Gemma 4 for translating music requests to live-coding Strudel patterns (now with retry safety)
- **Suno Integration:** `services/rei_toei_service.py` for voice model selection, prompt engineering, and async generation
- **Console Commands:** `/rei-compose`, `/rei-suno` for interactive music creation
- **Architecture Design:** Full async/await patterns, streaming response handling, rate-limit guards
- **Documentation:** Full docstrings and design patterns in place (see [docs/features/rei-toei/plan.md](docs/features/rei-toei/plan.md))

### What's Pending

- 🔍 **Verification Required:** Validate live-coding music patterns work as designed; test Suno API integration for voice generation
- 📋 **Console Integration:** Wire fully into console mode and scheduled generation pipeline

### Current Architecture

- **Suno-first:** Text-to-music voice generation with configurable voice models (Chirp, Bark variants)
- **Strudel-second:** Live-coding pattern generation for instrumental accompaniment (now enabled with safety fixes)
- **Async rendering:** Non-blocking generation with streaming response collection
- **Rate limiting:** Built-in guard against Suno API overuse

### Next Steps to Complete

1. Run `docker compose --profile core up -d && docker logs -f ssi_booster_strudel_agent` to validate health check and music generation flow
2. Verify live-coding pattern generation works against Strudel MCP stdio command flow
3. Wire Suno voice selection into console `/rei-suno` command with CLI `--voice` flag
4. Integrate with scheduled posting pipeline for automated sonic branding

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
