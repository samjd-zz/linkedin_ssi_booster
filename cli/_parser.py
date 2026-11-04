"""Argument parser for the LinkedIn SSI Booster CLI."""

import argparse


def build_parser() -> argparse.ArgumentParser:
    """Build the main.py argument parser."""
    parser = argparse.ArgumentParser(description="LinkedIn SSI Booster via Buffer API")
    parser.add_argument("--schedule",  action="store_true", help="Generate and schedule posts to Buffer (use with --dry-run to preview only)")
    parser.add_argument("--curate",    action="store_true", help="Curate AI news and create ideas in Buffer")
    parser.add_argument("--console",   action="store_true", help="Open interactive persona chat mode (no Buffer calls)")
    parser.add_argument("--verify",    action="store_true", help="Enable DoT report scanning and spaCy similarity checks in console mode (requires --console)")
    parser.add_argument("--truth-gate", action="store_true", help="Start console mode with the truth gate ON: unsupported sentences are removed before replies are shown (requires --console)")
    parser.add_argument("--report",    action="store_true", help="Print SSI component report")
    parser.add_argument("--save-ssi",  nargs=4, metavar=("BRAND", "FIND", "ENGAGE", "BUILD"),
                        type=float, help="Record today's SSI scores: --save-ssi 10.49 9.69 11.0 12.15")
    parser.add_argument("--bsky-stats", action="store_true", help="Fetch and display live Bluesky profile stats")
    parser.add_argument("--week",      type=int, default=1, help="Week number from content calendar (1-4)")
    parser.add_argument("--dry-run",   action="store_true", help="Preview posts without pushing to Buffer")
    _VALID_CHANNELS = {"linkedin", "x", "bluesky", "threads", "youtube", "facebook", "all"}

    def _parse_channels(value: str) -> list[str]:
        parts = [v.strip() for v in value.split(",") if v.strip()]
        invalid = [p for p in parts if p not in _VALID_CHANNELS]
        if invalid:
            parser.error(f"invalid --channel value(s): {', '.join(invalid)}. Choose from: {', '.join(sorted(_VALID_CHANNELS))}")
        if "all" in parts:
            # Expand "all" to individual channels for generation loop
            return ["linkedin", "x", "bluesky", "threads", "youtube", "facebook"]
        return parts

    parser.add_argument("--channel",   type=_parse_channels, default=["linkedin"],
                        help="Target channel(s) as comma-separated list: linkedin,x,bluesky,threads,youtube,all (default: linkedin)")
    parser.add_argument("--type",      choices=["idea", "post"], default="idea",
                        help="idea: add to Buffer Ideas board; post: schedule directly to next available queue slot (default: idea)")
    parser.add_argument("--debug",     action="store_true", help="Enable DEBUG-level logging (shows raw API payloads and responses)")
    parser.add_argument("--interactive", action="store_true", help="Pause for user confirmation on each truth gate removal")
    parser.add_argument("--avatar-explain", action="store_true", help="Print evidence IDs and grounding summary after each generation")
    parser.add_argument("--avatar-learn-report", action="store_true", help="Print learning report from captured moderation events and exit")
    parser.add_argument("--confidence-policy", choices=["strict", "balanced", "draft-first"], default=None,
                        help="Confidence policy for curate path: strict|balanced|draft-first (default: AVATAR_CONFIDENCE_POLICY env var, else balanced)")
    parser.add_argument("--dot-report", action="store_true",
                        help="Display Derivative of Truth (truth gradient, uncertainty, evidence breakdown) for each generated post")
    parser.add_argument("--learn", action="store_true",
                        help="Extract and persist knowledge from curated articles into extracted_knowledge.json (skipped on --dry-run unless this flag is also set)")
    parser.add_argument("--reconcile", action="store_true",
                        help="Fetch published Buffer posts and reconcile with generated candidates to build acceptance priors")
    parser.add_argument("--classify", action="store_true",
                        help="Batch-classify articles via Model2Vec before curation (requires: pip install model2vec)")
    parser.add_argument("--add-category", nargs=3, metavar=("NAME", "DESCRIPTION", "SSI_COMPONENT"),
                        help="Add a custom category: --add-category 'AI Research' 'Machine learning papers and studies' establish_brand")
    parser.add_argument("--list-categories", action="store_true",
                        help="List all available Model2Vec categories with descriptions and SSI component mapping")
    parser.add_argument("--remove-category", nargs="+", metavar="NAME",
                        help="Remove custom categories by name: --remove-category 'AI Research' 'Government Tech'")

    # Rei Toei Music Generation
    rei_group = parser.add_argument_group("Rei Toei Music Generation")
    rei_group.add_argument("--rei-generate", action="store_true",
                           help="Generate Suno song from recent knowledge")
    rei_group.add_argument("--rei-generate-strudel", action="store_true",
                           help="Generate Strudel pattern instead of Suno")
    rei_group.add_argument("--rei-theme", type=str,
                           help="Generate music for specific theme")
    rei_group.add_argument("--rei-explain", action="store_true",
                           help="Show reasoning for generation choices")
    rei_group.add_argument("--rei-preview", action="store_true",
                           help="Preview without saving/executing")
    rei_group.add_argument("--rei-execute", action="store_true",
                           help="Execute Strudel pattern (requires --rei-generate-strudel)")
    return parser
