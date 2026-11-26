# AMD Linux Docker Quickstart

This walkthrough is for a **fresh native Ubuntu installation** with an AMD
Radeon GPU. It uses Ollama's Vulkan backend and the Docker `core` profile; it
does not install ROCm or require NVIDIA hardware. Other Linux distributions
need their own Docker and Vulkan package instructions. GPU support depends on
the actual card, drivers, and Ollama version; detection alone is not proof of
GPU inference.

## 1. Prerequisites

- Install Git, Docker Engine, and the Docker Compose plugin. See
  [Docker's Ubuntu installation guide](https://docs.docker.com/engine/install/ubuntu/).
- Ensure your user can run `docker` without `sudo` and the daemon is running.
  Docker documents its [Linux post-installation options](https://docs.docker.com/engine/install/linux-postinstall/);
  membership in the `docker` group grants root-level privileges.
- Allow substantial disk space and time for the first image build, spaCy
  models, Ollama models, and Argos model download. These steps need internet.
- The default ports are `127.0.0.1:11434` for Ollama and `5432` for PostgreSQL.
  PostgreSQL is published on all host interfaces by the current Compose
  configuration, even when database integration is disabled. Use a strong
  password and review [Docker's firewall limitations](https://docs.docker.com/engine/install/ubuntu/#firewall-limitations)
  before running on an untrusted network.

On Ubuntu, check Docker and install Mesa's Vulkan tools:

```bash
docker version
docker compose version
docker info
sudo apt update
sudo apt install git mesa-vulkan-drivers vulkan-tools
vulkaninfo --summary
```

`docker info` must succeed without `sudo`. `vulkaninfo` should list the Radeon
device, not just a software renderer such as `llvmpipe`. If it does not, fix
the host driver before continuing. These commands do not verify container GPU
access.

## 2. Clone and configure

```bash
git clone https://github.com/samjd-zz/linkedin_ssi_booster.git
cd linkedin_ssi_booster
cp -n .env.example .env
cp -n data/avatar/persona_graph.example.json data/avatar/persona_graph.json
cp -n data/avatar/domain_knowledge.example.json data/avatar/domain_knowledge.json
cp -n data/avatar/narrative_memory.example.json data/avatar/narrative_memory.json
cp -n content_calendar.example.py content_calendar.py
```

`cp -n` preserves existing files. Edit `.env` privately:

- Replace `POSTGRES_PASSWORD` with a unique, strong **alphanumeric** password
  before the first start. PostgreSQL starts even with `DATABASE_ENABLED=false`.
  The alphanumeric restriction avoids URL-escaping problems in Compose's
  generated database URL. Compose builds that URL from the `POSTGRES_*` values.
- `DATABASE_ENABLED=true` is the example default. Set it to `false` if you
  prefer file-based application storage; the PostgreSQL service still starts.
- Leave `OLLAMA_BASE_URL` as supplied: Compose overrides it for the app. The
  example models are `gemma4:e4b` and `qwen3.5:9b`; adjust both model names
  before initialization if the GPU or available memory needs smaller models.
  Smaller models may reduce output quality.
- A Buffer API key is needed for live scheduling and curation, **not** for
  console chat or the dry-run preview below. Replace the placeholder before
  using Buffer. Customize the optional `PERSONA_SYSTEM_PROMPT` if desired.
- Leave voice disabled for this first `core` run; Piper is in `full`.

The database password is initialized only when its data volume is first
created; changing `.env` later does not change an existing database password.
Do not delete an existing volume to resolve this: follow the
[database troubleshooting guide](docker-operations.md#database-connection-failed).

Edit `data/avatar/persona_graph.json` and `content_calendar.py` to replace
example facts and topics. The shipped `domain_knowledge_*.json` packs are
automatically loaded; review their contents for suitability. Never commit or
share `.env`, personal data, build images containing it, or unredacted logs.

## 3. Build and initialize

Run these commands from the repository root:

```bash
# Check configuration without printing secrets; expect an AMD detection message.
bash run.sh --profile core config --quiet

# Build both images and start only the required long-running services.
bash run.sh --profile core build app argos-init
bash run.sh --profile core up -d ollama postgres

# Wait for both configured Ollama models to be present; failures stop this command.
bash run.sh --profile core run --rm ollama-init

# Start the app dependencies and verify the CLI. Argos downloads on first use.
bash run.sh --profile core run --rm app python main.py --help
```

The AMD detection message means the Vulkan override was selected, not that GPU
offloading succeeded. `ollama-init` is a one-shot service; running `app` alone
does **not** wait for it. `argos-init` is also one-shot, but must complete
successfully before the app starts. A first build or download can take a while.
Warnings about missing `CIVITAI_API_KEY` or `HF_TOKEN` are expected for `core`.

## 4. Verify generation and GPU use

Start the console in an interactive terminal:

```bash
bash run.sh --profile core run --rm app python main.py --console
```

Ask a short question, wait for a reply, then use `/exit`. Console chat does not
publish to Buffer. Immediately inspect the loaded model and server logs:

```bash
bash run.sh --profile core exec ollama ollama ps
bash run.sh --profile core logs --tail 100 ollama
```

Check `PROCESSOR` and the logs for the Radeon/Vulkan backend and GPU layer
offloading. Run the query again if the model has already unloaded. A CPU-only
or partially offloaded result is possible even when Vulkan was selected.
On an 8 GB card, model size and context length can limit offloading.

Preview calendar posts without publishing:

```bash
bash run.sh --profile core run --rm app python main.py --schedule --week 1 --dry-run
```

Review the output before configuring live Buffer operations. To stop the
stack later, run `bash run.sh --profile core down`; do not add `-v` unless
you intentionally want to delete named volumes and their data.

## Troubleshooting

- **No AMD detection:** inspect `ls /dev/dri` and
  `cat /sys/class/drm/card*/device/vendor`; AMD reports `0x1002`. On machines
  with multiple GPUs, the launcher prioritizes a usable NVIDIA runtime.
- **Vulkan selected but CPU used:** check the host's `vulkaninfo`, Ollama logs,
  device access, and model size. On a multi-GPU host, select a Vulkan index
  shown in Ollama logs, for example
  `GGML_VK_VISIBLE_DEVICES=1 bash run.sh --profile core up -d ollama`;
  use the same setting on later `run.sh` invocations.
- **Model missing or download failed:** rerun
  `bash run.sh --profile core run --rm ollama-init` after checking model names
  and connectivity. Both primary and configured fallback must succeed.
- **Argos failed:** inspect `bash run.sh --profile core logs --tail 100 argos-init`,
  fix network or disk issues, and retry the app command.
- **Port or database errors:** see
  [Docker troubleshooting](docker-operations.md#troubleshooting). Avoid
  stopping unrelated services or deleting volumes without checking first.

The `full` profile includes FLUX, which still requires NVIDIA CUDA; use `core`
on AMD-only systems. Physical Radeon inference must be verified on the tester's
own hardware.
