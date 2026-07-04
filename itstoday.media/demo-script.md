# Live Demo Script: LinkedIn SSI Booster (Contest Edition)

## The story

This demo is about one problem: a small media buying team needs to move faster without giving up trust.

SSI Booster helps with that by turning research and persona knowledge into grounded posts, useful ideas, and optional creative assets. It also has a mass-learning pass that ingests RSS feeds and updates the system without posting anything.

## What to say up front

"They do not need more AI text. They need a system that helps them ship better creative faster, stay grounded in the facts, and prove why an idea is worth trusting."

"That is what this tool does. It takes a signal, turns it into something usable, and shows its work."

## The live demo

Start with the content and learning flow:

```bash
source .venv/bin/activate && python main.py --curate --learn --dry-run --classify
```

While it runs, say:

"This is the learning pass: it reads RSS feeds, extracts knowledge, classifies what it finds, and updates the system without posting anything."

"This pass is extraction-only, so it is about mass learning, not generation or publishing."

Point at the output and call out the new knowledge being captured and the fact that nothing is sent to Buffer.

Then show a normal curate run where learning happens automatically even without `--learn`:

```bash
source .venv/bin/activate && python main.py --curate --classify --dot-report --avatar-explain
```

Say:

"This is the live curate path. It generates content, it can show DoT and avatar explain, and the code also learns from the article even without --learn because this is not a dry run."

"So the system has two different learn modes: a bulk extraction pass with --learn --dry-run, and the normal live curate path where learning happens automatically as part of generation."

"At the end of the live curate path, the code also auto-renders art for eligible channels, so the demo can show a text-to-visual handoff without any extra step."

Then show the Rei Toei path with a direct theme:

```bash
source .venv/bin/activate && python main.py --rei-generate --rei-theme async optimization loops
```

Say:

"This is the bonus multimodal path. I can give it a theme directly, and it will generate a song concept from that theme instead of needing the theme to be discovered first."

"If there is no Suno key, it still generates and saves the local song data, which is enough to prove the workflow."

Then show the no-theme Rei path:

```bash
source .venv/bin/activate && python main.py --rei-generate
```

Say:

"This version loads Rei's persona and domain knowledge, then looks at the learned avatar facts to pick a theme automatically."

"If there are no extracted facts yet, the code tells you to run --curate --learn first."

"The Rei service also has an optional Sam-persona inspiration layer behind an env flag, but the direct --rei-generate CLI path does not wire GitHub context into that flow."

If you want to show a published or reviewable output path afterward, then use the schedule flow:

```bash
source .venv/bin/activate && python main.py --schedule --week 1 --dry-run --dot-report --avatar-explain --channel linkedin
```

Say:

"Now the same validated story can become something the team actually uses. The text gets checked first, then the creative path can follow."

"And at the end of the schedule path, art is also rendered automatically for eligible channels, so the workflow finishes with both text and visual output."

If you want a quick visual proof, show the saved artifacts:

```bash
ls -lt yt-vid-data/stories | head
ls -lt yt-vid-data/flux_capacitor | head
```

Then finish in console mode:

```bash
source .venv/bin/activate && python main.py --console --verify
```

Use one normal prompt, then `/art`, then `/rei-toei` if you want to show the system can branch into other formats.

## Closing line

"This is not just content generation. It is a workflow that helps a media team move faster, keep quality high, and learn from what works. If I were hired full-time, I would extend this into a creative and performance operating system for the team."

## The three things the judges should remember

- It solves a real media buying problem.
- It proves the work with evidence and trust scoring.
- It actually runs and produces useful output.
