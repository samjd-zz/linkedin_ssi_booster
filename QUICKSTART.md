# 🚀 LinkedIn SSI Booster — Quickstart Cheatsheet

## 1. Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_md  # Recommended: includes word vectors
cp .env.example .env
# Fill in PERSONA_SYSTEM_PROMPT, BUFFER_API_KEY, OLLAMA_BASE_URL, OLLAMA_MODEL, etc.
cp data/avatar/persona_graph.example.json data/avatar/persona_graph.json
cp data/avatar/narrative_memory.example.json data/avatar/narrative_memory.json
cp content_calendar.example.py content_calendar.py
```

## 2. Generate & Schedule Posts

- **Preview week 1 posts (no Buffer calls):**

  ```bash
  python main.py --schedule --week 1 --dry-run
  ```

- **Schedule week 1 posts to Buffer (LinkedIn):**

  ```bash
  python main.py --schedule --week 1
  ```

- **Schedule to all channels:**

  ```bash
  python main.py --schedule --week 1 --channel all
  ```

## 3. Console Mode — Persona Chat & Tuning

- **Chat with your persona (no Buffer calls):**

  ```bash
  python main.py --console
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
  python main.py --curate --dry-run
  ```

- **Push curated ideas to Buffer (review before publishing):**

  ```bash
  python main.py --curate
  ```

- **Schedule curated posts directly:**

  ```bash
  python main.py --curate --type post --channel linkedin
  ```

  - With the default balanced confidence policy, low-confidence output is routed to Buffer Ideas for review while medium and high confidence output can post directly.
  - `--type post` requests direct posting, but the confidence policy can still downgrade low-confidence content to Ideas or block it entirely.

## 5. Learning & Explainability

- **Reconcile published posts (improves future curation ranking):**

  ```bash
  python main.py --reconcile
  ```

- **Show grounding facts after each post:**

  ```bash
  python main.py --curate --avatar-explain
  ```

- **Print learning report from moderation events:**

  ```bash
  python main.py --avatar-learn-report
  ```

## 6. SSI Tracking

- **Record today's SSI scores:**

  ```bash
  python main.py --save-ssi 10.49 9.69 11.0 12.15
  ```

- **Print SSI report:**

  ```bash
  python main.py --report
  ```

## 7. Test Everything

```bash
python -m pytest tests/ -v
```

---

**Pro tips:**

- Edit your persona in `data/avatar/persona_graph.json` for best results.
- Tweak keywords/feeds in `.env` (`CURATOR_KEYWORDS`, `CURATOR_RSS_FEEDS`).
- All generation is local — no cloud AI keys required.
- All learning data is stored locally and gitignored.
