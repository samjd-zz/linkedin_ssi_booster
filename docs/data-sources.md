# Data Sources Configuration

The SSI Booster reads persona and knowledge data from a configurable set of paths.
By default everything lives in `data/avatar/`, but every path can be overridden via
environment variables — letting you point individual files, whole directories, or
multiple knowledge sources at whatever layout works for your setup.

---

## Resolution hierarchy

For each data file, the tool resolves the path in this order:

```
1. Individual env var   (e.g. PERSONA_GRAPH_PATH=/my/custom/path.json)
       ↓ not set
2. AVATAR_DATA_DIR + default filename   (e.g. /my/data/dir/persona_graph.json)
       ↓ not set
3. Repo-relative default   (data/avatar/persona_graph.json)
```

Setting `AVATAR_DATA_DIR` is enough for most cases. Individual overrides let you
break specific files out of that directory without moving everything.

---

## Environment variables

### Base directory

| Variable | Default | Description |
|---|---|---|
| `AVATAR_DATA_DIR` | `data/avatar` | Root directory for all data files. Relative paths are resolved from the working directory (the repo root when running normally). |

### Individual path overrides

Each of these takes precedence over `AVATAR_DATA_DIR` for its specific file.

| Variable | Default filename | Description |
|---|---|---|
| `PERSONA_GRAPH_PATH` | `persona_graph.json` | Career facts, projects, skills, outcomes. The primary identity file. |
| `NARRATIVE_MEMORY_PATH` | `narrative_memory.json` | Recent themes and claims — used to apply repetition penalty across posts. |
| `DOMAIN_KNOWLEDGE_PATH` | `domain_knowledge.json` | Domain-level expertise facts merged into the knowledge graph at load time. |
| `LEARNING_LOG_PATH` | `learning_log.jsonl` | Append-only log of continually extracted knowledge from RSS articles. |
| `EXTRACTED_KNOWLEDGE_PATH` | `extracted_knowledge.json` | Consolidated extracted knowledge, built from the learning log. |

### Multiple domain knowledge sources

| Variable | Format | Description |
|---|---|---|
| `DOMAIN_KNOWLEDGE_EXTRA_PATHS` | Semicolon-separated paths | Additional domain knowledge JSON files to merge with `DOMAIN_KNOWLEDGE_PATH` at load time. Useful for combining a personal domain pack with an org-wide one. |

---

## Common configurations

### Default (no configuration needed)

```
data/avatar/
├── persona_graph.json
├── narrative_memory.json
├── domain_knowledge.json
├── learning_log.jsonl
└── extracted_knowledge.json
```

No env vars required. Copy the `.example.json` files and fill them in.

---

### Forked repo with data outside the tool directory

If you're using this as a submodule and your data lives in a parent repo:

```bash
# .env
AVATAR_DATA_DIR=../data/avatar          # sibling directory
# or
AVATAR_DATA_DIR=/absolute/path/to/data  # absolute path
```

---

### Personal persona + shared org domain knowledge

Keep your personal career facts private while pulling in org-wide domain knowledge
that applies to all team members:

```bash
# .env
PERSONA_GRAPH_PATH=/home/user/private/persona_graph.json
NARRATIVE_MEMORY_PATH=/home/user/private/narrative_memory.json
DOMAIN_KNOWLEDGE_PATH=data/avatar/domain_knowledge.json
DOMAIN_KNOWLEDGE_EXTRA_PATHS=/org/shared/org_domain_knowledge.json
```

---

### Multiple domain knowledge sources merged at runtime

```bash
# .env
AVATAR_DATA_DIR=data/avatar
DOMAIN_KNOWLEDGE_EXTRA_PATHS=/org/tech_stack.json;/project/project_domain.json
```

All paths in `DOMAIN_KNOWLEDGE_EXTRA_PATHS` are merged with the primary
`DOMAIN_KNOWLEDGE_PATH` at load time. Duplicate keys use last-write-wins.

---

## File formats

All data files use the formats defined by their corresponding `.example.json` files
in `data/avatar/`. See `docs/persona-and-avatar.md` for schema documentation.
