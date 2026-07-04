# Live Demo Script: LinkedIn SSI Booster (Contest Edition)

## The story

This demo is about one problem: a small media buying team needs to move faster without giving up trust.

SSI Booster helps with that by turning research and persona knowledge into grounded posts, useful ideas, and optional creative assets. It also learns from what gets published, so the next round is smarter.

## What to say up front

"They do not need more AI text. They need a system that helps them ship better creative faster, stay grounded in the facts, and prove why an idea is worth trusting."

"That is what this tool does. It takes a signal, turns it into something usable, and shows its work."

## The live demo

Start with the content and learning flow:

```bash
source .venv/bin/activate && python main.py --curate --learn --dry-run --classify --dot-report --avatar-explain --channel linkedin --type idea
```

While it runs, say:

"This is the daily workflow: find something useful, classify it by strategy, score how trustworthy it is, and decide whether it should become a post or just an idea."

"The important part is that the system shows its evidence. It is not guessing in the dark."

Point at the output and call out the trust scoring, the evidence snippets, and the routing decision.

Then show the same workflow turning into a creative asset:

```bash
source .venv/bin/activate && python main.py --schedule --week 1 --dry-run --dot-report --avatar-explain --channel linkedin
```

Say:

"Now the same validated story can become something the team actually uses. The text gets checked first, then the creative path can follow."

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
