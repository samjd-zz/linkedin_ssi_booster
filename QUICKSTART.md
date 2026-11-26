# 🚀 LinkedIn SSI Booster — Quickstart Cheatsheet

> **Recommended launcher:** use `bash run.sh` for Docker workflows. It detects
> NVIDIA, AMD Vulkan, or Intel GPU support, applies the correct Compose override, exports
> audio runtime variables, and falls back to CPU when needed.

## 1. First-time setup

For native Ubuntu with AMD Radeon, follow the complete
[AMD Linux quickstart](docs/amd-linux-quickstart.md) first: install Docker and
Vulkan, configure your private files and database password, build the images,
initialize the models, and verify GPU offloading. Use the `core` profile on
AMD-only hosts; `full` requires NVIDIA for FLUX.

For other hardware, see the [Docker deployment guide](docs/docker-deployment.md)
and [setup guide](docs/setup.md). Docker users do not need a local Python venv.
Do not overwrite existing `.env`, persona, or calendar files when updating.

## 2. Generate & Schedule Posts

- **Preview week 1 posts (no Buffer calls):**

  ```bash
  bash run.sh --profile core run --rm app python main.py --schedule --week 1 --dry-run
  ```

- **Schedule week 1 posts to Buffer (LinkedIn):**

  ```bash
  bash run.sh --profile core run --rm app python main.py --schedule --week 1
  ```

- **Schedule to all channels:**

  ```bash
  bash run.sh --profile core run --rm app python main.py --schedule --week 1 --channel all
  ```

## 3. Console Mode — Persona Chat & Tuning

- **Chat with your persona (no Buffer calls):**

  ```bash
  bash run.sh --profile core run --rm -it app python main.py --console
  ```

  - Test how well the system knows your background, projects, and skills.
  - Try factual questions ("What projects did I do with Neo4j?"), career queries, or ask for advice.
  - Use this mode to tune your persona graph and see how changes affect grounding.
  - Console mode never writes to Buffer or posts anything — it's safe for experimentation.
  - Use `/help` to see the full command list, including `/verify`, `/avatar-explain`, `/dot-report`, `/graph-stats`, `/katzilla`, `/rei`, `/rei-toei`, and `/art`.
  - `/art` renders FLUX art from the most recent AI reply in the current console session; you can add an optional topic hint to narrow the visual prompt.

## 4. Curate AI News

- **Preview curation (no Buffer calls):**

  ```bash
  bash run.sh --profile core run --rm app python main.py --curate --dry-run
  ```

- **Push curated ideas to Buffer (review before publishing):**

  ```bash
  bash run.sh --profile core run --rm app python main.py --curate
  ```

- **Schedule curated posts directly:**

  ```bash
  bash run.sh --profile core run --rm app python main.py --curate --type post --channel linkedin
  ```

  - With the default balanced confidence policy, low-confidence output is routed to Buffer Ideas for review while medium and high confidence output can post directly.
  - `--type post` requests direct posting, but the confidence policy can still downgrade low-confidence content to Ideas or block it entirely.

## 5. Learning & Explainability

- **Reconcile published posts (improves future curation ranking):**

  ```bash
  bash run.sh --profile core run --rm app python main.py --reconcile
  ```

- **Show grounding facts after each post:**

  ```bash
  bash run.sh --profile core run --rm app python main.py --curate --avatar-explain
  ```

- **Print learning report from moderation events:**

  ```bash
  bash run.sh --profile core run --rm app python main.py --avatar-learn-report
  ```

## 6. SSI Tracking

- **Record today's SSI scores:**

  ```bash
  bash run.sh --profile core run --rm app python main.py --save-ssi 10.49 9.69 11.0 12.15
  ```

- **Print SSI report:**

  ```bash
  bash run.sh --profile core run --rm app python main.py --report
  ```

## 7. Test Everything

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

Verified Intel WSL2 laptop Rei Toei preview:

```bash
bash run.sh --profile core build app
bash run.sh --profile core run --rm app \
  python main.py --rei-generate --rei-preview \
  --rei-theme "intel laptop gpu activated"
```

---

**Pro tips:**

- Edit your persona in `data/avatar/persona_graph.json` for best results.
- Tweak keywords/feeds in `.env` (`CURATOR_KEYWORDS`, `CURATOR_RSS_FEEDS`).
- All generation is local — no cloud AI keys required.
- All learning data is stored locally and gitignored.
