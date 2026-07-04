# Live Demo Script: LinkedIn SSI Booster (Contest Edition)

## Demo Goal
Show, in one run, that this is not just a content toy. It is a production-grade marketing intelligence system that:
- creates grounded high-quality content fast,
- protects brand trust with truth validation,
- uses multimodal outputs (text, image, music),
- and closes the loop with learning for better performance over time.

Primary quality proof in this demo:
- Derivative of Truth (DoT) reporting for measurable trust scoring.
- Avatar explainability (`--avatar-explain`) for transparent evidence grounding.

## Why This Wins This Contest
Map your demo to the three judging criteria directly:
1. Real problem solved: consistent, factual, high-performing content production for lean media teams.
2. Convincing business value: less manual effort, better throughput, stronger brand quality control, more experiments per week.
3. Actually works: run live commands, show outputs, show artifacts on disk, and show explainable quality control in real time.

Tie-breaker message for judges:
"Most tools generate content. This system proves content quality with explicit trust gradients and evidence traces."

Core platform features to explicitly name during the demo:
- Truth-gated quality control (4-layer truth gate + DoT).
- Avatar explainability (`--avatar-explain`) and trust reporting (`--dot-report`).
- FLUX capacitor art pipeline (Ollama-first sequencing, local artifacts, reproducible metadata).
- Model2Vec classification (`--classify`) mapped to SSI strategy components.
- Confidence policy routing (`post` / `idea` / `block`) for operational safety.
- Continual learning loop (`--learn`) with acceptance-prior adaptation.
- NetworkX knowledge graph + hybrid retrieval for grounded generation.
- Multimodal operator workflow (text + art + Rei Toei music).

---

## Demo Format (12-15 minutes)

## 0) Pre-Demo Setup (5-10 min before recording)

### Checklist
- Use this repo root as working directory.
- Confirm .env is populated (Buffer and Ollama at minimum).
- If using Docker full profile, ensure FLUX model exists in models/flux.
- Close unrelated GPU-heavy apps.

### Start Stack (recommended)
```bash
bash run.sh --profile full up -d
```

### Health Sanity Check
```bash
docker compose --profile full ps
```

Look for app dependencies healthy enough to run:
- ollama
- piper
- flux services (in full profile)

If you need a safer fallback path for the demo, switch to core profile:
```bash
bash run.sh --profile core up -d
```

---

## 1) Opening Pitch (60-90 sec)

Say this clearly before running commands:

"Media teams do not fail because they lack ideas. They fail because they cannot sustain high-volume, high-quality, brand-safe output with small teams. This tool solves that by combining persona-grounded generation, multi-layer truth validation, adaptive learning, and scheduling workflow integration."

Then frame proof:

"In this demo I will show four things live: grounded generation, DoT trust scoring, avatar-level explainability, and multimodal outputs with FLUX art after Ollama."

"I will also call out how classification, confidence routing, and continual learning make this useful for media operations, not just content generation."

---

## 2) Live Proof A: Curation + Learning + Explainability (3-4 min)

Run:
```bash
source .venv/bin/activate && python main.py --curate --learn --dry-run --classify --dot-report --avatar-explain --channel linkedin --type idea
```

What to say while it runs:
- "This simulates daily content sourcing and ranking."
- "Classification maps ideas to SSI strategy, not random posting."
- "Derivative of Truth gives per-output trust signals, not just vibes."
- "Avatar explainability shows exactly which evidence was used."
- "Confidence policy routing decides what should post now versus what should stay in ideas."
- "Continual learning updates future rankings from publication outcomes."

What to point out in output:
- category/classification behavior,
- truth/DoT report snippets (gradient, uncertainty, evidence breakdown),
- avatar explain blocks (evidence IDs and grounding summary),
- confidence/routing decisions.
- learning signals that improve future source/topic ranking.

Business translation line:
"This gives my team faster content throughput with quality controls we can audit and trust."

---

## 3) Live Proof B: FLUX Art Avatar After Ollama (3-4 min)

Run schedule dry-run to trigger text-first then art path:
```bash
source .venv/bin/activate && python main.py --schedule --week 1 --dry-run --dot-report --avatar-explain --channel linkedin
```

What to say:
- "Text is generated and validated first."
- "Art render runs afterward with Ollama-first GPU policy."
- "DoT and avatar-explain quality checks happen in the same flow, so output quality and speed scale together."
- "FLUX capacitor is contest-specific leverage: reproducible visual asset generation tightly coupled to trusted text outputs."

Now prove local-first artifacts were saved:
```bash
ls -lt yt-vid-data/stories | head
ls -lt yt-vid-data/flux_capacitor | head
```

What to highlight:
- story text artifact exists,
- image artifact exists when rendered,
- metadata sidecars exist for reproducibility,
- the text quality itself is traceable via DoT and avatar-explain signals from the same run.

Judge-impact line:
"This is production behavior: deterministic artifacts plus measurable trust and explainability."

---

## 4) Live Proof C: Interactive Operator Workflow (Console) (2-3 min)

Run:
```bash
source .venv/bin/activate && python main.py --console --verify
```

Then type these in sequence:
1. Ask for a post:
   - Write a LinkedIn post about reducing CAC with better creative testing loops.
2. Generate art from the most recent response:
   - /art performance marketing control room
3. Show multimodal expansion (music avatar):
   - /rei-toei Generate a short concept for a track about async optimization loops.
What to narrate:
- "Same system, same persona, multiple output modes."
- "This is how a lean team turns one insight into multiple creative assets fast, while keeping evidence-backed quality control."

---

## 5) Close With Business Case (60-90 sec)

Use this close:

"This system gives a media team leverage, not just content. It improves speed, consistency, trust, and adaptability. The key is measurable quality: DoT trust gradients and avatar-level evidence explainability built into normal operations. If hired full-time, I would extend this into a cross-platform creative and performance optimization operating system for your media buying team."

---

## Submission Recording Tips
- Keep terminal font large and readable.
- Keep one browser tab open to show generated artifacts folder quickly.
- Do not over-explain architecture first; lead with outcomes, then show DoT and avatar-explain proof.
- If a step is slow, narrate expected behavior and proceed to the next proof point.

---

## Judge-Focused Emphasis (say this explicitly)
- "DoT report is our quality scorecard."
- "Avatar explain is our traceability layer."
- "Truth-gated quality control is non-negotiable: unsupported claims are filtered before publish."
- "FLUX capacitor adds multimodal leverage without sacrificing quality controls."
- "Together, these features make the system auditable and production-trustworthy for media operations."
