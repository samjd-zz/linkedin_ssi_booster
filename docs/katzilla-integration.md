# Katzilla.dev Integration

One API. Every major US government dataset. Citations baked into every response.

[Katzilla.dev](https://katzilla.dev/) is an optional external evidence source for avatar knowledge grounding, providing **287+ tool-use actions across 32 agent-ready categories** — SEC filings, FDA recalls, Federal Register, Congressional records, clinical trials, USGS earthquakes, labor statistics, and more — behind a single REST API with built-in citation tracking.

**Status:** Complete (6 phases, 23 files, 16 tests) — default off (`KATZILLA_ENABLED=false`).

---

## What Katzilla Provides

- **283,051+ validated datasets** with freshness metadata (seconds since last update), source uptime (7-day rolling), confidence scores, and certainty ratings
- **Citation contract** — every response includes `source_name`, `source_url`, `retrieved_at`, `data_hash` (SHA-256 verification), `license`, and `update_frequency`
- **Token optimisation** — field filtering, compact mode, pagination, unit conversion, and summary aggregation

---

## How It Fits SSI Booster

| Use Case | Detail |
|---|---|
| Expand evidence base | Supplement persona facts with real-world government data (e.g. verify company claims against SEC filings, labour statistics for hiring trends) |
| Enhanced truth validation | Truth gate layers verify claims against primary sources with cryptographic verification (`data_hash`) |
| Automatic citation | Every Katzilla-sourced fact includes full provenance (source URL, retrieval timestamp, license) |
| Continual learning boost | Knowledge extraction pipeline gains access to 283K+ datasets without manual curation |
| Console command | `/katzilla <query>` returns a deterministic citation-first reply |

---

## Action Allowlist

The integration uses a bounded allowlist to prevent runaway API usage:

```python
KATZILLA_ACTION_ALLOWLIST = ["congress-bills", "fda-recalls", "usgs-earthquakes"]
```

Override with `KATZILLA_ACTION_ALLOWLIST` env var (comma-separated action names).

---

## Truth Gate Integration

External Katzilla facts enter the evidence pipeline at credibility tier **0.55** (below persona facts at `1.0`, above raw article text). They feed:

- `ExplainOutput` in `services/console_grounding/_gate_helpers.py`
- `external_fact_to_evidence_path()` for Derivative of Truth gradient scoring
- The console `/katzilla <query>` command returns a structured citation-first reply with full source attribution

---

## Budget Controls (`services/katzilla_telemetry.py`)

A JSONL event store and daily budget guard prevent unexpected API cost:

```bash
KATZILLA_TELEMETRY_ENABLED=true
KATZILLA_MAX_CALLS_PER_DAY=100         # daily call cap
KATZILLA_MAX_UNCERTAINTY_PER_DAY=50.0  # accumulated uncertainty budget
```

`can_call_katzilla()` checks both caps before any API call. Telemetry is written to `data/katzilla_telemetry.jsonl`.

---

## Console Command

```bash
python main.py --console
Sam> /katzilla FDA recalls for contaminated foods 2024
```

Returns a structured answer with full citation provenance from the Katzilla API.

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `KATZILLA_ENABLED` | `false` | Enable Katzilla evidence retrieval |
| `KATZILLA_API_KEY` | _(required when enabled)_ | Katzilla API key |
| `KATZILLA_BASE_URL` | `https://api.katzilla.dev` | API base URL |
| `KATZILLA_ACTION_ALLOWLIST` | `congress-bills,fda-recalls,usgs-earthquakes` | Allowed action names |
| `KATZILLA_COMPACT_FORMAT` | `true` | Reduce response verbosity for token savings |
| `KATZILLA_MAX_RESULTS_PER_ACTION` | `5` | Result cap per action call |
| `KATZILLA_TELEMETRY_ENABLED` | `true` | Enable usage telemetry |
| `KATZILLA_MAX_CALLS_PER_DAY` | `100` | Daily call budget |
| `KATZILLA_MAX_UNCERTAINTY_PER_DAY` | `50.0` | Daily uncertainty budget |

See [docs/environment-variables.md](environment-variables.md) for the full reference.

---

## Implementation Files

| File | Purpose |
|---|---|
| `services/katzilla_service.py` | HTTP client, envelope validation, error mapping, safe retry |
| `services/avatar_intelligence/_katzilla_adapter.py` | Envelope → `ExternalEvidenceFact` with full citation provenance |
| `services/katzilla_telemetry.py` | JSONL event store, daily budget guard |

> **Learn more:** [Katzilla Documentation](https://katzilla.dev/docs) — REST API reference, 287+ action catalogue, TypeScript/Python SDKs, and Agent2Agent protocol support.
