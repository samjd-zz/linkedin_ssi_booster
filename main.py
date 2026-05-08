
"""
LinkedIn SSI Booster — main entrypoint
=======================================
Generates and schedules LinkedIn posts via the Buffer API to improve
Social Selling Index (SSI) across all four components.

AI backend: Ollama (local) — requires Ollama running on OLLAMA_BASE_URL

Usage:
    python main.py --schedule [--week N] [--dry-run] [--interactive] [--channel linkedin,youtube,threads]
            # --schedule: generate and schedule posts (or preview with --dry-run)
    python main.py --curate               [--dry-run] [--interactive] [--channel linkedin,youtube,threads] [--type idea|post]
    python main.py --console
    python main.py --report
"""

from __future__ import annotations

import os
import json
import argparse
import logging
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from colorama import Fore, Style, init as _colorama_init

from scheduler import PostScheduler
from content_calendar import CONTENT_CALENDAR
from services.buffer_service import BufferService, BufferQueueFullError, BufferRateLimitError, BufferChannelNotConnectedError
from services.selection_learning import ACCEPTANCE_WINDOW_DAYS


def _configure_stdio() -> None:
    """Keep emoji/Unicode status output from crashing Windows cp1252 shells."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (TypeError, ValueError, OSError):
            # Some wrapped streams do not allow reconfiguration; best effort only.
            pass


_configure_stdio()
_colorama_init(autoreset=True)
load_dotenv()

# --- Intelligent Startup Notice ---
def print_startup_notice():
    print(str(Fore.CYAN) + str(Style.BRIGHT) + "\n👋 Welcome to LinkedIn SSI Booster!" + str(Style.RESET_ALL))
    print(str(Fore.WHITE) + f"Acceptance window: {ACCEPTANCE_WINDOW_DAYS} days" + str(Style.RESET_ALL))
    today = datetime.now(timezone.utc).date()
    cutoff_date = today + timedelta(days=ACCEPTANCE_WINDOW_DAYS)
    print(str(Fore.WHITE) + f"Latest date for 'new' post acceptance: {cutoff_date}" + str(Style.RESET_ALL))
    print(str(Fore.YELLOW) + "\n⚠️  IMPORTANT: Posts scheduled beyond the cutoff may not count for SSI growth!" + str(Style.RESET_ALL))

    # Try to connect to Buffer and check scheduled posts
    buffer_api_key = os.getenv("BUFFER_API_KEY")
    if not buffer_api_key:
        print(str(Fore.YELLOW) + "\n⚠️  BUFFER_API_KEY not set. Buffer scheduling will be disabled." + str(Style.RESET_ALL))
        return
    # Buffer scheduling check logic is commented out for now
    # try:
    #     buffer = BufferService(api_key=buffer_api_key)
    #     channels = buffer.get_channels()
    #     for ch in channels:
    #         ch_id = ch.get("id")
    #         ch_name = ch.get("name")
    #         ch_service = ch.get("service")
    #         scheduled = buffer.get_scheduled_posts(ch_id)
    #         if not scheduled:
    #             continue
    #         # Find the latest scheduled post date
    #         max_due = None
    #         for post in scheduled:
    #             due = post.get("dueAt")
    #             if due:
    #                 try:
    #                     due_dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
    #                     if not max_due or due_dt > max_due:
    #                         max_due = due_dt
    #                 except Exception:
    #                     continue
    #         if max_due and max_due.date() > cutoff_date:
    #             print(str(Fore.YELLOW) + f"\n⚠️  WARNING: Buffer queue for {ch_name} has posts scheduled beyond the acceptance window!" + str(Style.RESET_ALL))
    # except Exception as e:
    #     print(str(Fore.YELLOW) + f"\n⚠️  Could not check Buffer queue: {e}" + str(Style.RESET_ALL))

# --- Coloured log formatter ---
class _ColourFormatter(logging.Formatter):
    _LEVEL = {
        logging.DEBUG:    str(Fore.CYAN)   + "DEBUG"    + str(Style.RESET_ALL),
        logging.INFO:     str(Fore.GREEN)  + "INFO"     + str(Style.RESET_ALL),
        logging.WARNING:  str(Fore.YELLOW) + "WARN"     + str(Style.RESET_ALL),
        logging.ERROR:    str(Fore.RED)    + "ERROR"    + str(Style.RESET_ALL),
        logging.CRITICAL: str(Fore.RED)    + str(Style.BRIGHT) + "CRITICAL" + str(Style.RESET_ALL),
    }
    def format(self, record: logging.LogRecord) -> str:
        record = logging.makeLogRecord(record.__dict__)
        record.levelname = self._LEVEL.get(record.levelno, record.levelname)
        return super().format(record)

_handler = logging.StreamHandler()
_handler.setFormatter(_ColourFormatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_handler])
logger = logging.getLogger(__name__)


from services.console_grounding import (
    parse_query_constraints,
    retrieve_relevant_facts,
    build_deterministic_grounded_reply,
    get_latest_extracted_knowledge,
    build_learned_knowledge_context,
    build_grounding_facts_block,
)
from services.ollama_service import OllamaService
from services.github_service import build_github_profile_context

def run_console(ai: OllamaService, github_context: str = "", verify: bool = False, avatar_explain: bool = False, dot_report: bool = False) -> None:
    """Run interactive persona chat mode in the terminal.
    
    When verify=True, DoT report scanning and spaCy similarity checks are displayed
    for each generated response.
    When avatar_explain=True, evidence IDs and grounding summary are printed after each LLM reply.
    When dot_report=True, Derivative of Truth report is printed after each LLM reply.
    """
    # Patterns that should always route to LLM (not deterministic fact citation)
    GENERATIVE_REQUEST_PHRASES = [
        "write", "generate", "give me", "post", "reply", "respond", "script", "make me", "create",
        "linkedin", "youtube", "x", "bluesky", "twitter", "tiktok", "thread", "mastodon", "deck", "slide"
    ]

    print(str(Fore.CYAN) + str(Style.BRIGHT) + "\n🧠 Persona Console Mode — Enhanced Query Routing" + str(Style.RESET_ALL))
    print("- No Buffer actions will be performed in this mode.")
    print()
    print(str(Fore.WHITE) + str(Style.BRIGHT) + "3 Query Routing Modes:" + str(Style.RESET_ALL))
    print()
    print(str(Fore.YELLOW) + "  1️⃣  Explicit File Request → Deterministic citation (raw facts)" + str(Style.RESET_ALL))
    print("    • persona_graph")
    print("    • extracted_knowledge")
    print("    • domain_knowledge")
    print("    • narrative_memory")
    print()
    print(str(Fore.YELLOW) + "  2️⃣  Learned Knowledge → Latest 5 extracted facts as context" + str(Style.RESET_ALL))
    print("    • from your learned knowledge, what are the AI trends?")
    print("    • based on what you learned, explain...")
    print()
    print(str(Fore.YELLOW) + "  3️⃣  Everything Else → LLM with artifact context (default)" + str(Style.RESET_ALL))
    print("    • What is RAG?")
    print("    • Explain vector search")
    print("    • What projects have you worked on?")
    print("    • write a LinkedIn post about...")
    print("    • How are you today?")
    print()
    print(str(Fore.WHITE) + "  Commands: /help, /reset, /reload, /exit" + str(Style.RESET_ALL))
    print()


    history: list[dict[str, str]] = []
    max_turns = 24

    # Load persona graph for deterministic grounding and persona chat context
    from services.avatar_intelligence import (
        load_avatar_state as _lav_console,
        normalize_evidence_facts,
        normalize_domain_facts,
        normalize_extracted_facts,
        evidence_facts_to_project_facts,
        domain_facts_to_project_facts,
        build_grounding_context,
    )
    from services.console_grounding._models import ProjectFact as _ProjectFact

    def _load_knowledge_state() -> tuple[list, str, list, list, list]:
        """Load (or reload) avatar knowledge state.
        
        Returns: (_profile_facts, _grounding_context, _raw_evidence_facts, _raw_domain_facts, _raw_extracted_facts)
        """
        avatar_state = _lav_console()
        avatar_facts = normalize_evidence_facts(avatar_state)
        
        domain_facts_raw = []
        domain_pf: list = []
        try:
            domain_facts_raw = normalize_domain_facts(avatar_state)
            domain_pf = domain_facts_to_project_facts(domain_facts_raw)
        except Exception as exc:
            logger.warning("Domain knowledge not loaded for console mode: %s", exc)
        
        extracted_raw = []
        extracted_pf: list = []
        try:
            extracted_raw = normalize_extracted_facts(avatar_state)
            extracted_pf = [
                _ProjectFact(
                    project=f.source_title or "Extracted Knowledge",
                    company="",
                    years="",
                    details=f.statement,
                    source=f"extracted_knowledge:{f.evidence_id}",
                    tags=set(f.tags or []),
                )
                for f in extracted_raw
            ]
        except Exception as exc:
            logger.warning("Extracted knowledge not loaded for console mode: %s", exc)
        
        profile_facts = evidence_facts_to_project_facts(avatar_facts) + domain_pf + extracted_pf
        grounding_ctx = build_grounding_context(avatar_facts)
        if github_context:
            grounding_ctx = f"{grounding_ctx}\n\n{github_context}" if grounding_ctx else github_context
        return profile_facts, grounding_ctx, list(avatar_facts), domain_facts_raw, extracted_raw

    _profile_facts, _grounding_context, _raw_evidence_facts, _raw_domain_facts, _raw_extracted_facts = _load_knowledge_state()
    logger.info(
        "Console mode: loaded %d grounding facts (%d total)",
        len(_profile_facts),
        len(_profile_facts),
    )

    from services.console_grounding import truth_gate_result as _tg_result

    def _print_truth_score(reply: str) -> None:
        """Print a minimal 1-line DoT + fact-sim bar after a generated reply.

        spaCy article sim is intentionally excluded — it requires a source article
        text and is always empty when article_text="" (console mode has no article).
        Fact-pool sim (best match across persona/domain facts) works in all contexts.
        
        Only runs when verify=True.
        """
        if not verify:
            return
        try:
            _, _meta = _tg_result(reply, "", _profile_facts)
            dot = _meta.truth_gradient

            if dot >= 0.75:
                _dot_col = str(Fore.GREEN)
                _dot_sym = "●"
            elif dot >= 0.45:
                _dot_col = str(Fore.YELLOW)
                _dot_sym = "◑"
            else:
                _dot_col = str(Fore.RED)
                _dot_sym = "○"

            _fsim_vals = list(_meta.fact_sim_scores.values())
            _fsim = max(_fsim_vals) if _fsim_vals else None

            def _bar(score: float, width: int = 20) -> str:
                filled = round(score * width)
                return "█" * filled + "░" * (width - filled)

            _dot_bar = _bar(dot)
            _line = (
                str(Style.DIM) + "  "
                + _dot_col + _dot_sym + str(Style.RESET_ALL)
                + str(Style.DIM) + f" DoT {dot:.2f}  " + str(Style.RESET_ALL)
                + _dot_col + _dot_bar + str(Style.RESET_ALL)
            )
            if _fsim is not None:
                if _fsim >= 0.75:
                    _fsim_col = str(Fore.GREEN)
                elif _fsim >= 0.45:
                    _fsim_col = str(Fore.YELLOW)
                else:
                    _fsim_col = str(Fore.RED)
                _fsim_bar = _bar(_fsim)
                _line += (
                    str(Style.DIM) + f"   fact sim {_fsim:.2f}  " + str(Style.RESET_ALL)
                    + _fsim_col + _fsim_bar + str(Style.RESET_ALL)
                )
            print(_line)
        except Exception:
            pass  # never interrupt the conversation for a scoring failure

    while True:
        try:
            user_input = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting console.")
            return

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in {"/exit", "/quit"}:
            print("Exiting console.")
            return
        if cmd == "/help":
            print("Commands: /help, /reset, /reload, /exit")
            print("  /reload — re-read persona graph, domain packs, and extracted_knowledge.json")
            continue
        if cmd == "/reset":
            history.clear()
            print("Conversation history cleared.")
            continue
        if cmd == "/reload":
            _profile_facts, _grounding_context, _raw_evidence_facts, _raw_domain_facts, _raw_extracted_facts = _load_knowledge_state()
            print(
                str(Fore.CYAN)
                + f"Knowledge reloaded — {len(_profile_facts)} grounding facts now active."
                + str(Style.RESET_ALL)
            )
            continue

        # Parse query to determine routing mode
        constraints = parse_query_constraints(user_input)
        
        # Route 1: Explicit file name requests → Deterministic citation (raw facts)
        if constraints.explicit_artifact_request:
            facts = retrieve_relevant_facts(_profile_facts, constraints, limit=8)
            reply = build_deterministic_grounded_reply(user_input, facts, constraints)
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": reply})
            if len(history) > max_turns * 2:
                history = history[-max_turns * 2 :]
            print(str(Fore.GREEN) + f"Sam> {reply}" + str(Style.RESET_ALL))
            continue

        # Route 2: "From your learned knowledge" → Use latest 5 extracted knowledge as context
        if constraints.use_learned_knowledge:
            learned_facts = get_latest_extracted_knowledge(_profile_facts, limit=5)
            learned_context = build_learned_knowledge_context(learned_facts)
            history.append({"role": "user", "content": user_input})
            if len(history) > max_turns * 2:
                history = history[-max_turns * 2 :]
            try:
                # Use learned knowledge as PRIMARY context (put it first and emphasize it)
                # The learned knowledge should be the focus, with persona context as background
                enhanced_context = f"{learned_context}\n\n{_grounding_context}" if _grounding_context else learned_context
                print(str(Fore.CYAN) + "🤔 Thinking..." + str(Style.RESET_ALL), end="", flush=True)
                reply = ai.chat_as_persona(history, grounding_context=enhanced_context, max_tokens=600)
                print("\r" + " " * 20 + "\r", end="", flush=True)  # Clear the "Thinking..." line
            except Exception as e:
                print("\r" + " " * 20 + "\r", end="", flush=True)  # Clear the "Thinking..." line
                print(str(Fore.RED) + f"Sam> Error: {e}" + str(Style.RESET_ALL))
                continue
            history.append({"role": "assistant", "content": reply})
            print(str(Fore.GREEN) + f"Sam> {reply}" + str(Style.RESET_ALL))
            
            if verify:
                print(str(Fore.CYAN) + "📊 Verifying..." + str(Style.RESET_ALL), end="", flush=True)
                _print_truth_score(reply)
                print("\r" + " " * 20 + "\r", end="", flush=True)  # Clear the "Verifying..." line
            
            # Print avatar-explain report if requested
            if avatar_explain:
                print(str(Fore.CYAN) + "🧠 Generating avatar-explain..." + str(Style.RESET_ALL), end="", flush=True)
                try:
                    from services.avatar_intelligence import build_explain_output, format_explain_output
                    from services.console_grounding import truth_gate_result as _tgr_r2
                    _, _gate_meta_r2 = _tgr_r2(reply, user_input, _profile_facts)
                    # Get the latest extracted facts from raw data (not ProjectFact objects)
                    _latest_extracted = list(_raw_extracted_facts)[-5:] if _raw_extracted_facts else []
                    _explain_r2 = build_explain_output(
                        evidence_facts=[],  # Route 2 uses extracted knowledge, not persona facts
                        article_ref=user_input,
                        channel="console",
                        ssi_component="general",
                        dot_per_sentence_scores=_gate_meta_r2.dot_per_sentence_scores,
                        spacy_sim_scores=_gate_meta_r2.spacy_sim_scores,
                        extracted_facts=_latest_extracted,
                    )
                    print("\r" + " " * 40 + "\r", end="", flush=True)  # Clear the status line
                    print(format_explain_output(_explain_r2))
                except Exception as _exp_err:
                    print("\r" + " " * 40 + "\r", end="", flush=True)  # Clear the status line
                    logger.debug("Avatar explain unavailable for Route 2: %s", _exp_err)
            
            # Print DoT report if requested
            if dot_report:
                print(str(Fore.CYAN) + "📈 Generating DoT report..." + str(Style.RESET_ALL), end="", flush=True)
                try:
                    from services.derivative_of_truth import (
                        EvidencePath,
                        EVIDENCE_TYPE_SECONDARY,
                        REASONING_TYPE_LOGICAL,
                        score_claim_with_truth_gradient,
                        report_truth_gradient,
                        format_truth_gradient_report,
                    )
                    from services.derivative_of_truth._reporting import format_dot_report_header
                    _dot_paths_r2 = [
                        EvidencePath(
                            source=f"extracted_knowledge:{f.source.split(':')[-1] if ':' in f.source else f.source}",
                            evidence_type=EVIDENCE_TYPE_SECONDARY,
                            reasoning_type=REASONING_TYPE_LOGICAL,
                            credibility=0.7,
                        )
                        for f in learned_facts
                    ]
                    _dot_result_r2 = score_claim_with_truth_gradient(reply, _dot_paths_r2)
                    _dot_report_dict_r2 = report_truth_gradient(reply, _dot_result_r2, verbose=True)
                    print("\r" + " " * 40 + "\r", end="", flush=True)  # Clear the status line
                    print(format_dot_report_header())
                    print(format_truth_gradient_report(_dot_report_dict_r2))
                    print()
                except Exception as _dot_err:
                    print("\r" + " " * 40 + "\r", end="", flush=True)  # Clear the status line
                    logger.debug("DoT report unavailable for Route 2: %s", _dot_err)
            
            continue

        # Route 3: Everything else → LLM with artifact context (default)
        # This includes: domain/project/tech queries, generative requests, general chat
        # Always retrieve relevant facts and use as context
        facts = retrieve_relevant_facts(_profile_facts, constraints, limit=8)
        facts_context = build_grounding_facts_block(facts, limit=8)
        history.append({"role": "user", "content": user_input})
        if len(history) > max_turns * 2:
            history = history[-max_turns * 2 :]
        try:
            # Use retrieved facts as additional context
            enhanced_context = f"{_grounding_context}\n\n{facts_context}" if _grounding_context else facts_context
            print(str(Fore.CYAN) + "🤔 Thinking..." + str(Style.RESET_ALL), end="", flush=True)
            reply = ai.chat_as_persona(history, grounding_context=enhanced_context, max_tokens=600)
            print("\r" + " " * 20 + "\r", end="", flush=True)  # Clear the "Thinking..." line
        except Exception as e:
            print("\r" + " " * 20 + "\r", end="", flush=True)  # Clear the "Thinking..." line
            print(str(Fore.RED) + f"Sam> Error: {e}" + str(Style.RESET_ALL))
            continue
        history.append({"role": "assistant", "content": reply})
        print(str(Fore.GREEN) + f"Sam> {reply}" + str(Style.RESET_ALL))
        
        if verify:
            print(str(Fore.CYAN) + "📊 Verifying..." + str(Style.RESET_ALL), end="", flush=True)
            _print_truth_score(reply)
            print("\r" + " " * 20 + "\r", end="", flush=True)  # Clear the "Verifying..." line
        
        # Print avatar-explain report if requested
        if avatar_explain:
            print(str(Fore.CYAN) + "🧠 Generating avatar-explain..." + str(Style.RESET_ALL), end="", flush=True)
            try:
                from services.avatar_intelligence import build_explain_output, format_explain_output
                from services.console_grounding import truth_gate_result as _tgr_r3
                _, _gate_meta_r3 = _tgr_r3(reply, user_input, _profile_facts)
                # Map ProjectFact sources back to original fact objects
                # For Route 3, we retrieve relevant facts and need to map them back
                # Use all raw facts as evidence for the explain report
                _explain_r3 = build_explain_output(
                    evidence_facts=list(_raw_evidence_facts) + _raw_domain_facts,
                    article_ref=user_input,
                    channel="console",
                    ssi_component="general",
                    dot_per_sentence_scores=_gate_meta_r3.dot_per_sentence_scores,
                    spacy_sim_scores=_gate_meta_r3.spacy_sim_scores,
                    extracted_facts=list(_raw_extracted_facts) if _raw_extracted_facts else None,
                )
                print("\r" + " " * 40 + "\r", end="", flush=True)  # Clear the status line
                print(format_explain_output(_explain_r3))
            except Exception as _exp_err:
                print("\r" + " " * 40 + "\r", end="", flush=True)  # Clear the status line
                logger.debug("Avatar explain unavailable for Route 3: %s", _exp_err)
        
        # Print DoT report if requested
        if dot_report:
            print(str(Fore.CYAN) + "📈 Generating DoT report..." + str(Style.RESET_ALL), end="", flush=True)
            try:
                from services.derivative_of_truth import (
                    EvidencePath,
                    EVIDENCE_TYPE_SECONDARY,
                    REASONING_TYPE_LOGICAL,
                    score_claim_with_truth_gradient,
                    report_truth_gradient,
                    format_truth_gradient_report,
                )
                from services.derivative_of_truth._reporting import format_dot_report_header
                _dot_paths_r3 = [
                    EvidencePath(
                        source=f.source,
                        evidence_type=EVIDENCE_TYPE_SECONDARY,
                        reasoning_type=REASONING_TYPE_LOGICAL,
                        credibility=0.7,
                    )
                    for f in facts
                ]
                _dot_result_r3 = score_claim_with_truth_gradient(reply, _dot_paths_r3)
                _dot_report_dict_r3 = report_truth_gradient(reply, _dot_result_r3, verbose=True)
                print("\r" + " " * 40 + "\r", end="", flush=True)  # Clear the status line
                print(format_dot_report_header())
                print(format_truth_gradient_report(_dot_report_dict_r3))
                print()
            except Exception as _dot_err:
                print("\r" + " " * 40 + "\r", end="", flush=True)  # Clear the status line
                logger.debug("DoT report unavailable for Route 3: %s", _dot_err)


def main():
    parser = argparse.ArgumentParser(description="LinkedIn SSI Booster via Buffer API")
    parser.add_argument("--schedule",  action="store_true", help="Generate and schedule posts to Buffer (use with --dry-run to preview only)")
    parser.add_argument("--curate",    action="store_true", help="Curate AI news and create ideas in Buffer")
    parser.add_argument("--console",   action="store_true", help="Open interactive persona chat mode (no Buffer calls)")
    parser.add_argument("--verify",    action="store_true", help="Enable DoT report scanning and spaCy similarity checks in console mode (requires --console)")
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
            return ["all"]
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
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("httpx").setLevel(logging.WARNING)  # suppress noisy HTTP client logs

    if args.console:
        incompatible = []
        if args.schedule:
            incompatible.append("--schedule")
        if args.curate:
            incompatible.append("--curate")
        if args.report:
            incompatible.append("--report")
        if args.save_ssi:
            incompatible.append("--save-ssi")
        if args.bsky_stats:
            incompatible.append("--bsky-stats")
        if incompatible:
            print(
                str(Fore.YELLOW)
                + f"\n⚠️  --console cannot be combined with: {', '.join(incompatible)}"
                + str(Style.RESET_ALL)
            )
            return
    def build_buffer_service() -> BufferService:
        buffer_api_key = os.getenv("BUFFER_API_KEY")
        if not buffer_api_key:
            raise ValueError("BUFFER_API_KEY environment variable is required")
        return BufferService(api_key=buffer_api_key)

    if args.avatar_learn_report:
        from services.avatar_intelligence import build_learning_report, format_learning_report
        report = build_learning_report()
        print(format_learning_report(report))
        return

    from services.ssi_tracker import SSITracker
    tracker = SSITracker()

    if args.report:
        tracker.print_report()
        return

    if args.reconcile:
        from services.selection_learning import reconcile_published
        buffer = build_buffer_service()
        channel_ids: dict[str, str | None] = {"linkedin": buffer.get_linkedin_channel_id()}
        x_id = os.getenv("BUFFER_X_CHANNEL_ID")
        bsky_id = os.getenv("BUFFER_BLUESKY_CHANNEL_ID")
        threads_id = os.getenv("BUFFER_THREADS_CHANNEL_ID")
        if x_id:
            channel_ids["x"] = x_id
        if bsky_id:
            channel_ids["bluesky"] = bsky_id
        if threads_id:
            channel_ids["threads"] = threads_id
        stats = reconcile_published(buffer, {k: v for k, v in channel_ids.items() if v is not None})
        print(str(Fore.GREEN) + "\n✅  Reconcile complete" + str(Style.RESET_ALL))
        for k, v in stats.items():
            print(f"   {k}: {v}")
        return

    if args.save_ssi:
        brand, find, engage, build = args.save_ssi
        tracker.save_scores(establish=brand, find=find, engage=engage, build=build)
        total = brand + find + engage + build
        print(str(Fore.GREEN) + f"✅  Saved SSI scores: brand={brand} find={find} engage={engage} build={build} total={total:.2f}" + str(Style.RESET_ALL))
        return

    if args.bsky_stats:
        from services.ssi_tracker import fetch_bluesky_stats
        stats = fetch_bluesky_stats()
        if stats:
            print(str(Fore.CYAN) + str(Style.BRIGHT) + f"\n📊 Bluesky stats for @{stats['handle']}" + str(Style.RESET_ALL))
            print(f"  👥 Followers    : {str(Fore.WHITE)}{stats['followers']}{str(Style.RESET_ALL)}")
            print(f"  ➡️  Following    : {stats['following']}")
            print(f"  📝 Total posts  : {stats['posts']}")
            print(str(Fore.CYAN) + f"\n  Last {stats['analysed']} posts (engagement)" + str(Style.RESET_ALL))
            print(f"  ❤️  Likes        : {stats['total_likes']}")
            print(f"  💬 Replies      : {stats['total_replies']}")
            print(f"  🔁 Reposts      : {stats['total_reposts']}")
            print(f"  🗨️  Quotes       : {stats['total_quotes']}")
            print(f"  📈 Avg / post   : {stats['avg_engagement']}")
            if stats.get("top_post"):
                tp = stats["top_post"]
                print(str(Fore.YELLOW) + f"\n  🏆 Top post ({tp['likes']}L {tp['replies']}R {tp['reposts']}RT)" + str(Style.RESET_ALL))
                print(f"  '{tp['text']}'")
                if tp["url"]:
                    print(f"  {tp['url']}")
        return

    if args.list_categories:
        from services.model2vec_service import get_model2vec_service
        svc = get_model2vec_service()
        if not svc.is_available():
            print(str(Fore.YELLOW) + "\n⚠️  Model2Vec is not available (install with: pip install model2vec numpy)" + str(Style.RESET_ALL))
            return
        categories = svc.list_categories()
        if not categories:
            print(str(Fore.YELLOW) + "\n⚠️  No categories found" + str(Style.RESET_ALL))
            return
        print(str(Fore.CYAN) + str(Style.BRIGHT) + f"\n🏷️  Model2Vec Categories ({len(categories)} total)" + str(Style.RESET_ALL))
        print()
        for name, meta in sorted(categories.items()):
            is_custom = meta.get("custom", "False") == "True"
            ssi = meta.get("ssi_component", "general")
            desc = meta.get("description", "")
            custom_marker = str(Fore.MAGENTA) + " [custom]" + str(Style.RESET_ALL) if is_custom else ""
            print(str(Fore.WHITE) + str(Style.BRIGHT) + f"  {name}" + str(Style.RESET_ALL) + custom_marker)
            print(f"    {desc[:100]}{'...' if len(desc) > 100 else ''}")
            print(str(Fore.YELLOW) + f"    → {ssi}" + str(Style.RESET_ALL))
            print()
        return

    if args.add_category:
        from services.model2vec_service import get_model2vec_service
        svc = get_model2vec_service()
        if not svc.is_available():
            print(str(Fore.YELLOW) + "\n⚠️  Model2Vec is not available (install with: pip install model2vec numpy)" + str(Style.RESET_ALL))
            return
        name, description, ssi_component = args.add_category
        valid_ssi = {"establish_brand", "find_right_people", "engage_with_insights", "build_relationships"}
        if ssi_component not in valid_ssi:
            print(str(Fore.RED) + f"\n❌  Invalid SSI component: {ssi_component}" + str(Style.RESET_ALL))
            print(f"    Valid options: {', '.join(sorted(valid_ssi))}")
            return
        success = svc.add_category(name, description, ssi_component)
        if success:
            print(str(Fore.GREEN) + f"\n✅  Added custom category: '{name}'" + str(Style.RESET_ALL))
            print(f"    Description: {description[:80]}{'...' if len(description) > 80 else ''}")
            print(str(Fore.YELLOW) + f"    SSI Component: {ssi_component}" + str(Style.RESET_ALL))
        else:
            print(str(Fore.RED) + f"\n❌  Failed to add category '{name}' (may already exist)" + str(Style.RESET_ALL))
        return

    if args.remove_category:
        from services.model2vec_service import get_model2vec_service
        svc = get_model2vec_service()
        if not svc.is_available():
            print(str(Fore.YELLOW) + "\n⚠️  Model2Vec is not available (install with: pip install model2vec numpy)" + str(Style.RESET_ALL))
            return
        names = args.remove_category
        results = svc.remove_categories(names)
        successes = [n for n, r in zip(names, results) if r]
        failures = [n for n, r in zip(names, results) if not r]
        if successes:
            print(str(Fore.GREEN) + f"\n✅  Removed {len(successes)} category(ies):" + str(Style.RESET_ALL))
            for name in successes:
                print(f"    • {name}")
        if failures:
            print(str(Fore.RED) + f"\n❌  Failed to remove {len(failures)} category(ies):" + str(Style.RESET_ALL))
            for name in failures:
                print(f"    • {name} (not found or is a default category)")
        return

    if not (args.schedule or args.curate or args.console):
        parser.print_help()
        return

    print_startup_notice()

    _github_context = build_github_profile_context(
        max_chars=int(os.getenv("GITHUB_CONTEXT_MAX_CHARS", "30000"))
    )
    if _github_context:
        logger.info("GitHub context loaded: %d chars", len(_github_context))

    ai = OllamaService(
        model=os.getenv("OLLAMA_MODEL", "llama3.2"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )

    if args.console:
        run_console(ai=ai, github_context=_github_context, verify=args.verify, avatar_explain=args.avatar_explain, dot_report=args.dot_report)
        return

    if args.curate:
        buffer = None if args.dry_run else build_buffer_service()
        from services.shared import AVATAR_CONFIDENCE_POLICY
        from services.content_curator import ContentCurator
        confidence_policy = args.confidence_policy or AVATAR_CONFIDENCE_POLICY
        curator = ContentCurator(ai_service=ai, buffer_service=buffer, confidence_policy=confidence_policy, github_context=_github_context, classify=args.classify)

        try:
            ideas = curator.curate_and_create_ideas(dry_run=args.dry_run, channel=args.channel, message_type=args.type, request_delay=5.0, interactive=args.interactive, avatar_explain=args.avatar_explain, dot_report=args.dot_report, learn=args.learn, classify=args.classify)
        except BufferQueueFullError as e:
            print(str(Fore.YELLOW) + f"\n⚠️  Buffer queue is full — no new posts were scheduled.\n   {e}\n   Free up slots at https://publish.buffer.com before running again." + str(Style.RESET_ALL))
            return
        except BufferRateLimitError as e:
            print(
                str(Fore.YELLOW)
                + f"\n⚠️  Buffer API rate limit reached.\n   {e}\n"
                + "   Wait for the retry window, then run the command again."
                + str(Style.RESET_ALL)
            )
            return
        except BufferChannelNotConnectedError as e:
            print(
                str(Fore.YELLOW)
                + f"\n⚠️  Requested channel is not connected in Buffer.\n   {e}\n"
                + "   Connect the channel in Buffer or run with a different --channel value."
                + str(Style.RESET_ALL)
            )
            return
        noun = "posts" if args.type == "post" else "ideas"

        
        return


    if args.schedule:
        week_topics = CONTENT_CALENDAR.get(f"week_{args.week}", [])
        if not week_topics:
            logger.error("No content found for week %d", args.week)
            return

        # args.channel is already a list from _parse_channels
        for channel in args.channel:
            logger.info("📝 Generating %d posts for week %d (channel: %s)...", len(week_topics), args.week, channel)
            posts = []
            from services.avatar_intelligence import (
                load_avatar_state as _lav_gen,
                normalize_evidence_facts,
                normalize_domain_facts,
                retrieve_evidence,
                evidence_facts_to_project_facts,
                EvidenceFact,
                DomainEvidenceFact,
                domain_facts_to_project_facts,
            )
            _gen_avatar_state = _lav_gen()
            if channel == "youtube" and not args.dry_run:
                Path("yt-vid-data").mkdir(exist_ok=True)
            if args.avatar_explain:
                from services.avatar_intelligence import build_explain_output, format_explain_output

            for topic in week_topics:
                logger.info("  Generating: %s", topic['title'])
                grounding_query = f"{topic['title']}. {topic['angle']}. {topic.get('ssi_component', 'establish_brand')}"
                # Combine both fact types
                _gen_avatar_facts = normalize_evidence_facts(_gen_avatar_state)
                _gen_domain_facts = normalize_domain_facts(_gen_avatar_state)
                all_facts = list(_gen_avatar_facts) + list(_gen_domain_facts)
                _ev_proj = int(os.getenv("EVIDENCE_PROJECT_COUNT", "3"))
                _ev_dom = int(os.getenv("EVIDENCE_DOMAIN_COUNT", "2"))
                relevant = retrieve_evidence(grounding_query, all_facts, limit=_ev_proj + _ev_dom)  # type: ignore[arg-type]

                # Split by type and convert
                persona_facts = [f for f in relevant if isinstance(f, EvidenceFact)]
                domain_facts = [f for f in relevant if isinstance(f, DomainEvidenceFact)]
                grounding_facts = (
                    evidence_facts_to_project_facts(persona_facts)
                    + domain_facts_to_project_facts(domain_facts)
                )

                if channel == "youtube":
                    post = ai.generate_youtube_short_script(
                        title=topic["title"],
                        angle=topic["angle"],
                        ssi_component=topic.get("ssi_component", "establish_brand"),
                        grounding_facts=grounding_facts,
                        interactive=args.interactive,
                    )
                    safe_title = re.sub(r"[^\w\-]", "_", topic["title"][:60]).strip("_")
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    script_path = Path("yt-vid-data") / f"{timestamp}_{safe_title}.txt"
                    script_content = (
                        f"TITLE: {topic['title']}\n"
                        f"SSI COMPONENT: {topic.get('ssi_component', 'establish_brand')}\n\n"
                        f"{post}\n"
                    )
                    if not args.dry_run:
                        script_path.write_text(script_content, encoding="utf-8")
                    print(str(Fore.RED) + str(Style.BRIGHT) + f"🎬 YOUTUBE SHORT SCRIPT (channel: {channel}):" + str(Style.RESET_ALL))
                    print(str(Fore.WHITE) + f"📄 TITLE:  {topic['title']}" + str(Style.RESET_ALL))
                    print(str(Fore.CYAN) + f"🎯 SSI:    {topic.get('ssi_component', 'establish_brand')}" + str(Style.RESET_ALL))
                    print(f"\n{post}\n")
                    print("GitHub: https://buff.ly/tfajNLI")
                    print("Sign up for Buffer with my partner link — join.buffer.com/samjd42  — to start scheduling, publishing, and analyzing your social posts in one place while supporting my work.")
                    if not args.dry_run:
                        print(str(Fore.GREEN) + f"💾 Saved to: {script_path}" + str(Style.RESET_ALL))
                    posts.append({**topic, "generated_text": post})
                else:
                    post = ai.generate_linkedin_post(
                        title=topic["title"],
                        angle=topic["angle"],
                        ssi_component=topic.get("ssi_component", "establish_brand"),
                        hashtags=topic.get("hashtags", []),
                        grounding_facts=grounding_facts,
                        channel=channel,
                        interactive=args.interactive,
                    )
                    # Hashtags are only appended for LinkedIn-style posts.
                    if channel not in ("x", "bluesky", "threads", "youtube"):
                        hashtag_str = " ".join(f"#{h.lstrip('#')}" for h in topic.get("hashtags", []))
                        if hashtag_str and hashtag_str not in post:
                            post = post.rstrip() + f"\n\n{hashtag_str}"
                    posts.append({**topic, "generated_text": post})

                if channel != "youtube":
                    print(str(Fore.CYAN) + f"\n{'='*60}" + str(Style.RESET_ALL))
                    print(str(Fore.WHITE) + str(Style.BRIGHT) + f"📝 TOPIC: {topic['title']} (channel: {channel})" + str(Style.RESET_ALL))
                    print(str(Fore.CYAN) + f"🎯 SSI COMPONENT: {topic.get('ssi_component', 'establish_brand')}" + str(Style.RESET_ALL))
                    print(f"\n{post}\n")

                if args.dot_report:
                    try:
                        from services.derivative_of_truth import (
                            EvidencePath,
                            EVIDENCE_TYPE_SECONDARY,
                            REASONING_TYPE_LOGICAL,
                            score_claim_with_truth_gradient,
                            report_truth_gradient,
                            format_truth_gradient_report,
                        )
                        _dot_paths = [
                            EvidencePath(
                                source=f.source if hasattr(f, "source") else str(f),
                                evidence_type=EVIDENCE_TYPE_SECONDARY,
                                reasoning_type=REASONING_TYPE_LOGICAL,
                                credibility=0.7,
                            )
                            for f in grounding_facts
                        ]
                        _dot_result = score_claim_with_truth_gradient(post, _dot_paths)
                        _dot_report_dict = report_truth_gradient(post, _dot_result, verbose=True)
                        _dot_colour = str(Fore.RED) if _dot_result.flagged else str(Fore.CYAN)
                        from services.derivative_of_truth._reporting import format_dot_report_header
                        print(format_dot_report_header())
                        print(format_truth_gradient_report(_dot_report_dict))
                        print()
                    except Exception as _dot_err:
                        logger.debug("DoT report unavailable: %s", _dot_err)

                if args.avatar_explain:
                    # Combine project and domain facts for retrieval
                    from services.avatar_intelligence import EvidenceFact, DomainEvidenceFact, normalize_extracted_facts
                    from services.console_grounding import truth_gate_result as _tgr_exp
                    _all_facts = list(_gen_avatar_facts) + list(_gen_domain_facts)
                    _ev_proj2 = int(os.getenv("EVIDENCE_PROJECT_COUNT", "3"))
                    _ev_dom2 = int(os.getenv("EVIDENCE_DOMAIN_COUNT", "2"))
                    _relevant = retrieve_evidence(grounding_query, _all_facts, limit=_ev_proj2 + _ev_dom2)  # type: ignore[arg-type]
                    
                    # Score and filter extracted facts by relevance (retrieve_evidence doesn't support ExtractedEvidenceFact type)
                    _gen_extracted_facts_all = normalize_extracted_facts(_gen_avatar_state)
                    _ev_extracted = int(os.getenv("EVIDENCE_EXTRACTED_COUNT", "2"))
                    _q_tokens = set(re.findall(r"[a-zA-Z0-9_+#.-]{2,}", grounding_query.lower()))
                    _scored_extracted = []
                    for _fact in _gen_extracted_facts_all:
                        _text = " ".join([
                            getattr(_fact, "statement", ""),
                            getattr(_fact, "source_title", ""),
                            " ".join(getattr(_fact, "tags", []) or []),
                            " ".join(getattr(_fact, "entities", []) or []),
                        ])
                        _tokens = set(re.findall(r"[a-zA-Z0-9_+#.-]{2,}", _text.lower()))
                        _score = len(_q_tokens & _tokens)
                        _scored_extracted.append((_score, _fact))
                    _scored_extracted.sort(key=lambda x: x[0], reverse=True)
                    _relevant_extracted = [f for s, f in _scored_extracted if s > 0][:_ev_extracted]
                    if not _relevant_extracted and _gen_extracted_facts_all:
                        _relevant_extracted = list(_gen_extracted_facts_all)[:_ev_extracted]
                    
                    _, _gate_meta = _tgr_exp(post, topic.get("angle", ""), grounding_facts)
                    _explain = build_explain_output(
                        evidence_facts=_relevant,
                        article_ref=topic.get("title", ""),
                        channel=channel,
                        ssi_component=topic.get('ssi_component', 'establish_brand'),
                        dot_per_sentence_scores=_gate_meta.dot_per_sentence_scores,
                        spacy_sim_scores=_gate_meta.spacy_sim_scores,
                        extracted_facts=_relevant_extracted,
                    )
                    print(format_explain_output(_explain))

            # Only schedule if not dry-run and not YouTube
            if not args.dry_run:
                if channel == "youtube":
                    print(
                        str(Fore.YELLOW)
                        + "\n⚠️  YouTube scripts were generated and saved locally, but not scheduled to Buffer.\n"
                        + "   Buffer YouTube scheduling requires a video file upload (title/category/video).\n"
                        + "   Render with lipsync.video, then upload manually."
                        + str(Style.RESET_ALL)
                    )
                    continue
                buffer = build_buffer_service()
                scheduler = PostScheduler(buffer_service=buffer)
                try:
                    scheduled = scheduler.schedule_week(posts=posts, week_number=args.week, channel=channel)
                    print(str(Fore.GREEN) + f"\n✅  Scheduled {len(scheduled)} posts to Buffer ({channel})" + str(Style.RESET_ALL))
                except BufferQueueFullError as e:
                    print(str(Fore.YELLOW) + f"\n⚠️  Buffer queue is full — no new posts were scheduled.\n   {e}\n   Free up slots at https://publish.buffer.com before running again." + str(Style.RESET_ALL))
                except BufferRateLimitError as e:
                    print(
                        str(Fore.YELLOW)
                        + f"\n⚠️  Buffer API rate limit reached.\n   {e}\n"
                        + "   Wait for the retry window, then run the command again."
                        + str(Style.RESET_ALL)
                    )
                except BufferChannelNotConnectedError as e:
                    print(
                        str(Fore.YELLOW)
                        + f"\n⚠️  Requested channel is not connected in Buffer.\n   {e}\n"
                        + "   Connect the channel in Buffer or run with a different --channel value."
                        + str(Style.RESET_ALL)
                    )



if __name__ == "__main__":
    main()
