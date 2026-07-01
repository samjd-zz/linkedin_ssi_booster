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

## 🎨 FLUX Art Avatar After Ollama — Phase 2 Complete

**Single-GPU art-avatar pipeline with restrained corporate-art aesthetic.**

The `services/flux_capacitor/` package is now implemented and tested. The pipeline enforces strict Ollama-first GPU sequencing on the RTX 3060 and provides a full local-first artifact persistence contract for generated story text and render metadata.

### What Was Built (Phase 1 — June 2026)

- ✅ **`services/flux_capacitor/_config.py`** — Environment-driven feature flags, style clamps, GPU policy defaults, 3 built-in style presets
- ✅ **`services/flux_capacitor/_models.py`** — Typed `ArtAvatarRequest`, `ArtAvatarResult`, `ArtAvatarTelemetry`, `GPUPolicy`, `StylePreset`, `GPUJobSlot` dataclasses
- ✅ **`services/flux_capacitor/_prompting.py`** — Prompt assembly with preset resolution, style override clamping, and `FLUX_CAPACITOR_STYLE_SYSTEM_PROMPT` persona injection
- ✅ **`services/flux_capacitor/_pipeline.py`** — `GPUOrchestrator` (threading.Lock gate, Ollama-first priority queue, `flux_slot()` context manager) + `run_art_avatar()` orchestration
- ✅ **`services/flux_capacitor/_storage.py`** — Local-first story artifact + image metadata sidecar persistence via `services.shared.get_generated_content_dir`
- ✅ **`services/flux_capacitor/__init__.py`** — `FluxCapacitorService` singleton, `make_request()` factory, `notify_ollama_start/done()` lifecycle hooks
- ✅ **44 tests** — All passing (`test_flux_capacitor_pipeline.py` + `test_gpu_orchestration_policy.py`)

### What Was Built (Phase 2 — Completed)

- ✅ **Schedule / curate / console integration** — `FluxCapacitorService` is wired into `main.py` rendering flows (`_render_schedule_art_avatar`, `_render_curate_art_avatar`, `_render_console_art_avatar`)
- ✅ **DB-second schema** — optional `generated_content_records` table plus repository support implemented in `services/database/models.py` and `services/database/repositories.py`
- ✅ **Config/docs alignment** — `FLUX_CAPACITOR_*` and related display/realism variables documented and surfaced in `.env.example`, environment docs, CLI docs, and deployment docs
- ✅ **Integration coverage** — dedicated flow tests added for schedule and curate/console integration; singleton and orchestration coverage retained

### Configuration

All features are **default-off** (`FLUX_CAPACITOR_ENABLED=false`). Requires `--profile full` Docker profile to render images. See [docs/features/flux-art-avatar-after-ollama/plan.md](docs/features/flux-art-avatar-after-ollama/plan.md) for the full plan.

### Status

**Phase 2 complete** — FLUX art-avatar package + main-flow integration + DB-second schema + docs/config alignment complete (July 2026)

---

## 🎨 Alex Grey Avatar Enhancement (Polish Track)

**Status:** Core implementation complete; this track is now focused on aesthetic quality iteration.

The FLUX.1 art-avatar infrastructure is complete (GPU orchestration, flow integration, persistence, DB-second indexing). Remaining work is creative tuning rather than systems integration.

### Completed Foundation

- ✅ Ollama-first GPU sequencing in `services/flux_capacitor/_pipeline.py`
- ✅ Local-first artifact persistence via `services.shared.get_generated_content_dir`
- ✅ Unified generated-content paths (`GENERATED_CONTENT_DIR`, `FLUX_CAPACITOR_SUBDIR`, `FLUX_CAPACITOR_STORIES_SUBDIR`)
- ✅ Optional DB-second indexing via `generated_content_records`
- ✅ Schedule / curate / console hooks active in `main.py`

### Next Enhancements (Optional)

- Additional style/prompt tuning passes for stronger persona-specific visual identity
- Expanded preset experimentation and evaluation loops
- Artifact quality benchmarking for render consistency across profiles

---

## 🤖 Ollama Buffer MCP Agent — In Progress

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

## 🎵 Rei Toei AI Music Avatar — Complete

**Status:** Complete ✅ (retry safety, MCP stdio flow, Suno integration, console routing, and tests).

Rei Toei is the music-avatar subsystem for generating persona-aligned sonic output using **Suno vocal generation + Strudel live-coding patterns**.

### Completed

- ✅ Strudel MCP agent hardening (health checks, exponential backoff, bounded timeouts, structured logging)
- ✅ MCP stdio flow enabled via `STRUDEL_MCP_COMMAND` and `agents/strudel_mcp_agent.py`
- ✅ Suno pipeline integrated in `services/rei_toei_service.py`
- ✅ Console routing available via `/rei` and `/rei-toei` commands in `main.py`
- ✅ Test coverage added for Rei console routing and CLI flows

### Follow-on Enhancements (Optional)

- Automated scheduled-pipeline music generation for recurring sonic branding
- Additional voice/prompt templates and genre packs
- Post-generation analytics loop for song/pattern performance

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

**Last Updated:** July 2026 (feature status cleanup; FLUX Phase 2 + Rei Toei marked complete)
