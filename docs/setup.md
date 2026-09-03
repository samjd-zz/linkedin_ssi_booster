# Setup Guide

This guide covers the required local setup for LinkedIn SSI Booster, including Python dependencies, Ollama configuration, persona files, and content calendar initialization. The project is designed to run locally, with persona and learning data stored in gitignored files on your machine.

## Prerequisites

The setup flow uses a Python virtual environment, package installation from `requirements.txt`, and a spaCy language model for theme extraction, similarity, and sentiment-related NLP features. The spaCy logic is implemented in `services/spacy_nlp.py`.

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install "spacy[ja]"                  # required for Japanese: pulls the SudachiPy tokenizer
python -m spacy download en_core_web_md  # recommended for English: includes word vectors
python -m spacy download ja_core_news_md # optional for Japanese: multi-language NLP pack
```

Japanese needs the `spacy[ja]` extra, not just the model. spaCy has no built-in Japanese tokenizer — it delegates to SudachiPy (`sudachipy` + `sudachidict_core`), which only ships via that extra. Installing `ja_core_news_md` without it raises an import error at load time. Verify both are present:

```bash
python -c "import sudachipy; import spacy; spacy.load('ja_core_news_md'); print('ja OK')"
```

If disk space is constrained, `en_core_web_sm` and `ja_core_news_sm` also work; `ja_core_news_lg` is available when higher-resource Japanese analysis is appropriate. Configure the exact installed models with `SPACY_MODEL` and `SPACY_MODELS` (for example, `SPACY_MODELS=en_core_web_md,ja_core_news_md`). The application loads only the names configured there and does not probe missing optional Japanese models.

When a model listed in `SPACY_MODELS` is missing, the loader logs a warning and silently falls back to the English pipeline. Japanese text tokenized by the English pipeline produces meaningless spans, so NER and fact extraction return nothing useful. Treat this warning as a hard failure rather than noise:

```
[WARN] spacy_nlp: model 'ja_core_news_md' not found — run 'python -m spacy download ja_core_news_md'
```

## Environment file

Create `.env` from `.env.example` and fill in the required values for persona prompting, Buffer integration, and Ollama. The README identifies `PERSONA_SYSTEM_PROMPT`, `BUFFER_API_KEY`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, and `OLLAMA_NUM_CTX` as the core required settings.

```bash
cp .env.example .env
```

Required and notable optional settings include:

- `PERSONA_SYSTEM_PROMPT` — voice and persona prompt used across AI calls.
- `BUFFER_API_KEY` — Buffer API access for scheduling and ideas.
- `OLLAMA_BASE_URL` — local Ollama server endpoint, defaulting to `http://localhost:11434`.
- `OLLAMA_MODEL` and `OLLAMA_NUM_CTX` — local model selection and context window tuning.
- `BLUESKY_HANDLE` and `BLUESKY_APP_PASSWORD` — optional Bluesky stats and integration settings.
- `GITHUB_USER`, `GITHUB_TOKEN`, and related GitHub context controls — optional persona enrichment settings.
- `AVATAR_LEARNING_ENABLED`, `AVATAR_CONFIDENCE_POLICY`, and `AVATAR_MAX_MEMORY_ITEMS` — Avatar Intelligence learning controls.

## Persona graph

The persona graph is the authoritative identity source for generation and grounding. It stores person details, companies, skills, projects, and verifiable claims in `data/avatar/persona_graph.json`, and it is explicitly intended to stay gitignored for privacy.

```bash
cp data/avatar/persona_graph.example.json data/avatar/persona_graph.json
cp data/avatar/narrative_memory.example.json data/avatar/narrative_memory.json
```

The README says to replace placeholder values with real data for:

- `person` — name, title, location, and links.
- `companies` — employers and clients, including aliases.
- `skills` — technologies, aliases, and scope.
- `projects` — years, details, aliases, and skill references.
- `claims` — verifiable statements tied to projects.

## Content calendar

Create your private content calendar from the example file and replace placeholder topics with your own post ideas, angles, SSI mapping, and hashtags. The calendar is used by `--schedule` and is designed to spread topics across the four SSI pillars over a four-week plan.

```bash
cp content_calendar.example.py content_calendar.py
```

Each topic includes:

- `title` — post headline or subject.
- `angle` — the specific story or perspective to avoid generic output.
- `ssi_component` — one of the four SSI pillars.
- `hashtags` — LinkedIn hashtags appended programmatically.

## API keys and services

The README points users to Buffer for API key generation, Ollama for local model downloads, Bluesky for optional app passwords, and LinkedIn for viewing SSI scores. It also notes optional YouTube channel connection through Buffer.

- Buffer API key: `https://publish.buffer.com/settings/api`.
- Ollama model library: `https://ollama.com/library`.
- Bluesky app passwords: `bsky.app` settings.
- LinkedIn SSI page: `https://linkedin.com/sales/ssi`.

## First validation run

After setup, the simplest smoke test is a dry run of week 1 scheduling. This prints generated content without making Buffer calls and verifies that the local model, prompt context, and calendar are wired correctly.

```bash
python main.py --schedule --week 1 --dry-run
```
