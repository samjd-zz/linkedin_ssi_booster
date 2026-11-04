
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
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from colorama import Fore, Style, init as _colorama_init

from cli._admin import run_admin_command
from cli._curate_cli import run_curate_cli
from cli._flux_render import (
    _auto_render_art_if_requested,
    _render_console_art_avatar,
    _run_post_generation_cleanup,
)
from cli._parser import build_parser
from cli._rei_cli import run_rei_cli
from cli._schedule_cli import run_schedule_cli
from services.buffer_service import BufferService
from services.selection_learning import ACCEPTANCE_WINDOW_DAYS
from services.flux_capacitor import RenderStatus
from services.flux_capacitor._terminal import _display_art_in_terminal
from services.graph_stats import collect_domain_knowledge_profiles
from services.performance import timed_stage


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
logging.getLogger("httpx").setLevel(logging.WARNING)   # suppress "HTTP Request: POST ..." at INFO
logging.getLogger("httpcore").setLevel(logging.WARNING) # suppress underlying transport logs
logger = logging.getLogger(__name__)


from services.console_grounding import (
    parse_query_constraints,
    retrieve_relevant_facts,
    build_deterministic_grounded_reply,
    build_katzilla_citation_reply,
    get_latest_extracted_knowledge,
    build_learned_knowledge_context,
    build_grounding_facts_block,
    build_kanji_teaching_context,
)
from services.ollama_service import OllamaService
from services.github_service import build_github_profile_context
from services.piper_service import speak_text

def run_console(
    ai: OllamaService,
    github_context: str = "",
    verify: bool = False,
    avatar_explain: bool = False,
    dot_report: bool = False,
    truth_gate: bool = False,
) -> None:
    """Run interactive persona chat mode in the terminal.
    
    When verify=True, DoT report scanning and spaCy similarity checks are displayed
    for each generated response.
    When avatar_explain=True, evidence IDs and grounding summary are printed after each LLM reply.
    When dot_report=True, Derivative of Truth report is printed after each LLM reply.
    When truth_gate=True, unsupported sentences are removed before the reply is shown.
    """
    # Patterns that should always route to LLM (not deterministic fact citation)
    GENERATIVE_REQUEST_PHRASES = [
        "write", "generate", "give me", "post", "reply", "respond", "script", "make me", "create",
        "linkedin", "youtube", "x", "bluesky", "twitter", "tiktok", "thread", "mastodon", "deck", "slide"
    ]

    def _print_status() -> None:
        """Print current console mode status."""
        _status_line = str(Style.DIM) + "  Status: " + str(Style.RESET_ALL)
        _status_line += str(Fore.GREEN if verify else Fore.RED) + f"verify={'ON' if verify else 'OFF'}" + str(Style.RESET_ALL)
        _status_line += str(Style.DIM) + " | " + str(Style.RESET_ALL)
        _status_line += str(Fore.GREEN if avatar_explain else Fore.RED) + f"avatar-explain={'ON' if avatar_explain else 'OFF'}" + str(Style.RESET_ALL)
        _status_line += str(Style.DIM) + " | " + str(Style.RESET_ALL)
        _status_line += str(Fore.GREEN if dot_report else Fore.RED) + f"dot-report={'ON' if dot_report else 'OFF'}" + str(Style.RESET_ALL)
        _status_line += str(Style.DIM) + " | " + str(Style.RESET_ALL)
        _status_line += str(Fore.GREEN if truth_gate else Fore.RED) + f"truth-gate={'ON' if truth_gate else 'OFF'}" + str(Style.RESET_ALL)
        print(_status_line)

    print(str(Fore.CYAN) + str(Style.BRIGHT) + "\n🧠 Persona Console Mode — Enhanced Query Routing" + str(Style.RESET_ALL))
    print("- No Buffer actions will be performed in this mode.")
    print()
    _print_status()
    print()
    print(str(Fore.WHITE) + str(Style.BRIGHT) + "3 Query Routing Modes:" + str(Style.RESET_ALL))
    print()
    print(str(Fore.YELLOW) + "  1️⃣  Explicit File Request → Deterministic citation (raw facts)" + str(Style.RESET_ALL))
    print("    • persona_graph")
    print("    • extracted_knowledge")
    print("    • domain_knowledge")
    print("    • narrative_memory")
    print()
    print(str(Fore.YELLOW) + "  2️⃣  Learned Knowledge → Latest 5 extracted facts as context (or search)" + str(Style.RESET_ALL))
    print("    • from your learned knowledge, what are the AI trends?")
    print("    • based on what you learned, explain...")
    print("    • search your learned knowledge for RAG techniques")
    print("    • find in your learned knowledge about microservices")
    print()
    print(str(Fore.YELLOW) + "  3️⃣  Everything Else → LLM with graph-enhanced retrieval (default)" + str(Style.RESET_ALL))
    print("    • What is RAG?")
    print("    • Explain vector search")
    print("    • What projects have you worked on?")
    print("    • write a LinkedIn post about...")
    print("    • How are you today?")
    print()
    print(str(Fore.WHITE) + str(Style.BRIGHT) + "🔗 Knowledge Graph Integration:" + str(Style.RESET_ALL))
    print("    • 70% BM25 keyword matching")
    print("    • 20% graph proximity (facts closer to persona node rank higher)")
    print("    • 10% claim support (facts with more supporting edges rank higher)")
    print()
    _hr = "─" * 63
    print(str(Fore.CYAN) + f"  {_hr}" + str(Style.RESET_ALL))
    print(str(Fore.WHITE) + str(Style.BRIGHT) + "  Commands" + str(Style.RESET_ALL))
    print(str(Fore.CYAN) + f"  {_hr}" + str(Style.RESET_ALL))
    print(str(Fore.YELLOW) + "  Session   " + str(Style.RESET_ALL) + str(Fore.WHITE) + "/help  /reset  /reload  /exit  /quit" + str(Style.RESET_ALL))
    print(str(Fore.YELLOW) + "  Reports   " + str(Style.RESET_ALL) + str(Fore.WHITE) + "/verify  /avatar-explain  /dot-report" + str(Style.RESET_ALL))
    print("            " + str(Fore.WHITE) + "/truth-gate  /graph-stats  /katzilla <query>" + str(Style.RESET_ALL))
    print(str(Fore.YELLOW) + "  Identity  " + str(Style.RESET_ALL) + str(Fore.WHITE) + "/rei  /rei-toei  (sticky Rei mode)    /sam  (back to Sam)" + str(Style.RESET_ALL))
    print(str(Fore.YELLOW) + "  Creative  " + str(Style.RESET_ALL) + str(Fore.WHITE) + "/art [topic]  — FLUX render from most recent AI reply" + str(Style.RESET_ALL))
    print(str(Fore.CYAN) + f"  {_hr}" + str(Style.RESET_ALL))
    print()


    history: list[dict[str, str]] = []
    active_console_avatar = "sam"
    max_turns = 24

    def _print_console_reply(avatar: str, reply: str) -> None:
        if avatar == "rei":
            print(str(Fore.MAGENTA) + f"Rei> {reply}" + str(Style.RESET_ALL))
            return
        print(str(Fore.GREEN) + f"Sam> {reply}" + str(Style.RESET_ALL))

    def _print_console_error(avatar: str, error: str) -> None:
        speaker = "Rei" if avatar == "rei" else "Sam"
        print(str(Fore.RED) + f"{speaker}> Error: {error}" + str(Style.RESET_ALL))

    def _show_console_thinking(avatar: str) -> int:
        if avatar == "rei":
            label = "🎚️ Rei Composing..."
            color = Fore.MAGENTA
        else:
            label = "🤔 Sam Thinking..."
            color = Fore.CYAN
        print(str(color) + label + str(Style.RESET_ALL), end="", flush=True)
        return len(label)

    def _clear_console_status(width: int = 24) -> None:
        print("\r" + " " * width + "\r", end="", flush=True)

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
    from services.console_grounding._config import get_console_grounding_tag_expansions_from_graph
    from services.knowledge_graph import KnowledgeGraphManager
    from services.hybrid_retriever import HybridRetriever

    # Initialize Knowledge Graph Manager
    _kg: KnowledgeGraphManager | None = None
    _hybrid_retriever: HybridRetriever | None = None
    _tag_expansions: dict[str, set[str]] = {}

    @timed_stage(logger, "console.preparation")
    def _load_knowledge_state() -> tuple[list, str, list, list, list]:
        """Load (or reload) avatar knowledge state.
        
        Returns: (_profile_facts, _grounding_context, _raw_evidence_facts, _raw_domain_facts, _raw_extracted_facts)
        """
        nonlocal _kg, _hybrid_retriever, _tag_expansions
        avatar_state = _lav_console()
        _tag_expansions = (
            get_console_grounding_tag_expansions_from_graph(avatar_state.domain_knowledge)
            if avatar_state.domain_knowledge is not None else {}
        )
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
        try:
            _kg = KnowledgeGraphManager()
            _kg.bootstrap_from_avatar_state(avatar_state)
            _hybrid_retriever = HybridRetriever(kg=_kg)
        except Exception as kg_err:
            logger.warning("Knowledge Graph initialization failed: %s — using fallback retrieval", kg_err)
            _kg = None
            _hybrid_retriever = None
        return profile_facts, grounding_ctx, list(avatar_facts), domain_facts_raw, extracted_raw

    def _index_profile_facts(profile_facts: list) -> tuple[dict, dict, dict]:
        return (
            {
                fact.source.rsplit(":", 1)[-1]: fact
                for fact in profile_facts
                if fact.source.startswith("avatar:")
            },
            {
                fact.source.rsplit(":", 1)[-1]: fact
                for fact in profile_facts
                if fact.source.startswith("domain:")
            },
            {
                fact.source.rsplit(":", 1)[-1]: fact
                for fact in profile_facts
                if fact.source.startswith("extracted_knowledge:")
            },
        )

    _profile_facts, _grounding_context, _raw_evidence_facts, _raw_domain_facts, _raw_extracted_facts = _load_knowledge_state()
    _avatar_facts_by_id, _domain_facts_by_id, _extracted_facts_by_id = _index_profile_facts(_profile_facts)
    logger.debug(
        "Console mode: loaded %d grounding facts (%d total)",
        len(_profile_facts),
        len(_profile_facts),
    )

    _console_cleanup_done = False
    _original_excepthook = sys.excepthook

    def _run_console_exit_cleanup() -> None:
        """Best-effort memory cleanup for console shutdown."""
        nonlocal _console_cleanup_done
        if _console_cleanup_done:
            return
        _console_cleanup_done = True

        logger.info("🧹 Running console shutdown cleanup...")

        # Drop large in-memory console state before forcing collection.
        history.clear()
        _profile_facts.clear()
        _raw_evidence_facts.clear()
        _raw_domain_facts.clear()
        _raw_extracted_facts.clear()

        # Restore the process-level exception hook after console shutdown.
        try:
            sys.excepthook = _original_excepthook
        except Exception as exc:  # noqa: BLE001
            logger.debug("Console excepthook restore skipped: %s", exc)

        # Reuse the existing post-run cleanup for Ollama/FLUX/Python heap trim.
        _run_post_generation_cleanup(ai, source_mode="console")

    def _console_excepthook(exc_type, exc_value, exc_traceback) -> None:
        """Ensure cleanup runs if console mode terminates on an unhandled exception."""
        try:
            logger.error("Unhandled exception in console mode", exc_info=(exc_type, exc_value, exc_traceback))
            _run_console_exit_cleanup()
        finally:
            _original_excepthook(exc_type, exc_value, exc_traceback)

    # Protect console-mode exits not covered by explicit /exit or EOF handlers.
    sys.excepthook = _console_excepthook

    from services.console_grounding import truth_gate_result as _tg_result
    from services.console_grounding import TruthGateMeta, remove_gated_sentences

    def _apply_console_truth_gate(reply: str, facts: list) -> tuple[str, TruthGateMeta | None]:
        """Filter the reply through the truth gate when /truth-gate is ON."""
        if not truth_gate:
            return reply, None
        print(str(Fore.CYAN) + "🛡️ Truth gate..." + str(Style.RESET_ALL), end="", flush=True)
        with timed_stage(logger, "console.truth_gate"):
            _, _meta = _tg_result(reply, "", facts, channel="console", dot_facts=facts)
        print("\r" + " " * 20 + "\r", end="", flush=True)
        removed = list(getattr(_meta, "removed_sentences", []) or [])
        if not removed:
            return reply, _meta
        gated = remove_gated_sentences(reply, removed)
        print(
            str(Style.DIM)
            + f"  🛡️ Truth gate removed {len(removed)} of {getattr(_meta, 'total_sentences', len(removed))} sentences"
            + str(Style.RESET_ALL)
        )
        if not gated:
            print(str(Fore.YELLOW) + "  Truth gate removed every sentence; nothing grounded to show." + str(Style.RESET_ALL))
        return gated, _meta

    def _print_truth_score(reply: str, facts: list, gate_meta: TruthGateMeta | None = None) -> TruthGateMeta | None:
        """Print a minimal 1-line DoT + fact-sim bar after a generated reply.

        spaCy article sim is intentionally excluded — it requires a source article
        text and is always empty when article_text="" (console mode has no article).
        Fact-pool sim (best match across persona/domain facts) works in all contexts.
        
        Only runs when verify=True.
        """
        if not verify:
            return None
        try:
            _meta = gate_meta
            if _meta is None:
                with timed_stage(logger, "console.verification"):
                    _, _meta = _tg_result(reply, "", facts, channel="console", log_removals=False)
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
            return _meta
        except Exception as exc:
            logger.warning("Console verification failed: %s", exc)
            return None

    def print_graph_statistics(summary, domain_profiles=None):
        """Print graph and domain-knowledge diagnostics with aligned tables."""
        width = 76
        print("\n" + "=" * width)
        print(f"{Fore.CYAN}{Style.BRIGHT}{'GRAPH STRUCTURE ANALYSIS':^{width}}")
        print("=" * width)

        # --- 1. Core Metrics ---
        print(f"\n{Fore.YELLOW}{'--- CORE METRICS ---':^{width}}")
        print(f"{'Metric':<24} {'Count':>10}    {'Metric':<24} {'Count':>10}")
        print("-" * width)
        print(f"{'Nodes':<24} {int(summary.get('nodes', 0)):>10}    {'Edges':<24} {int(summary.get('edges', 0)):>10}")

        # --- 2. Component Breakdown ---
        print(f"\n{Fore.YELLOW}{'--- COMPONENT BREAKDOWN ---':^{width}}")
        node_types = summary.get("node_types", {})
        if node_types:
            print(f"{'Node Type':<32} {'Count':>10}")
            print("-" * 44)
            for node_type, count in sorted(node_types.items(), key=lambda item: item[1], reverse=True):
                print(f"  {str(node_type):<30} {int(count):>10}")
        else:
            print("No specific node type breakdown available.")

        # --- 3. Domain Knowledge Profiles (Sam + Rei) ---
        print(f"\n{Fore.YELLOW}{'--- DOMAIN KNOWLEDGE PROFILES ---':^{width}}")

        sam = (domain_profiles or {}).get("sam", {}) if domain_profiles else {}
        sam_totals = sam.get("totals", {}) if isinstance(sam, dict) else {}
        sam_files_loaded = int(sam.get("files_loaded", 0)) if isinstance(sam, dict) else 0
        print(f"{Fore.GREEN}Sam Domain Knowledge{Style.RESET_ALL} (files={sam_files_loaded})")
        print(
            f"  domains={int(sam_totals.get('domains', 0))}  "
            f"facts={int(sam_totals.get('facts', 0))}  "
            f"relationships={int(sam_totals.get('relationships', 0))}"
        )
        sam_files = sam.get("files", []) if isinstance(sam, dict) else []
        if sam_files:
            file_col = 44
            print(f"{'  file':<{file_col}} {'domains':>8} {'facts':>8} {'rels':>8}")
            print("  " + "-" * (file_col + 28))
            for row in sam_files:
                file_name = str(row.get("file", "unknown"))
                if len(file_name) > file_col - 2:
                    file_name = file_name[: file_col - 5] + "..."
                print(
                    f"  {file_name:<{file_col - 2}} "
                    f"{int(row.get('domains', 0)):>8} "
                    f"{int(row.get('facts', 0)):>8} "
                    f"{int(row.get('relationships', 0)):>8}"
                )
        sam_errors = sam.get("errors", []) if isinstance(sam, dict) else []
        if sam_errors:
            print(f"  {Fore.YELLOW}notes:{Style.RESET_ALL} {len(sam_errors)} Sam domain file(s) were skipped due to load errors")

        rei = (domain_profiles or {}).get("rei", {}) if domain_profiles else {}
        rei_file = str(rei.get("file", "rei_toei_domain_knowledge.json"))
        print(f"\n{Fore.MAGENTA}Rei Domain Knowledge{Style.RESET_ALL} (file={rei_file})")
        if rei.get("exists"):
            shape = rei.get("shape", {})
            print(
                f"  sections={int(rei.get('section_count', 0))}  "
                f"dict_keys={int(shape.get('dict_keys', 0))}  "
                f"list_items={int(shape.get('list_items', 0))}"
            )
            top_sections = rei.get("sections", [])[:5]
            if top_sections:
                section_col = 44
                print(f"{'  top section':<{section_col}} {'type':>10} {'size':>8}")
                print("  " + "-" * (section_col + 22))
                for section in top_sections:
                    section_name = str(section.get("name", "unknown"))
                    if len(section_name) > section_col - 2:
                        section_name = section_name[: section_col - 5] + "..."
                    print(
                        f"  {section_name:<{section_col - 2}} "
                        f"{str(section.get('type', 'n/a')):>10} "
                        f"{int(section.get('size', 0)):>8}"
                    )
        else:
            print(f"  {Fore.YELLOW}Rei domain knowledge file not available or invalid JSON.{Style.RESET_ALL}")

        print("\n" + "=" * width)
        print(f"{Fore.CYAN}{Style.BRIGHT}{'ANALYSIS COMPLETE':^{width}}")
        print("=" * width)

    while True:
        try:
            user_input = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting console.")
            _run_console_exit_cleanup()
            return

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in {"/exit", "/quit"}:
            print("Exiting console.")
            _run_console_exit_cleanup()
            return
        if cmd == "/help":
            _hr = "─" * 63
            print(str(Fore.CYAN) + _hr + str(Style.RESET_ALL))
            print(str(Fore.WHITE) + str(Style.BRIGHT) + "Commands" + str(Style.RESET_ALL))
            print(str(Fore.CYAN) + _hr + str(Style.RESET_ALL))
            print(str(Fore.YELLOW) + "Session" + str(Style.RESET_ALL))
            print("  /help            show this help")
            print("  /reset           clear conversation history")
            print("  /reload          re-read persona graph, domain packs, extracted knowledge")
            print("  /exit  /quit     leave console")
            print()
            print(str(Fore.YELLOW) + "Reports & Diagnostics" + str(Style.RESET_ALL))
            print("  /verify          toggle DoT + similarity verification on/off")
            print("  /avatar-explain  toggle avatar-explain report on/off")
            print("  /dot-report      toggle DoT report on/off")
            print("  /truth-gate      toggle truth gate on/off (shows the filtered reply)")
            print("  /graph-stats     show knowledge graph statistics")
            print("  /katzilla <q>    deterministic external evidence citations")
            print()
            print(str(Fore.YELLOW) + "Identity" + str(Style.RESET_ALL))
            print("  /rei  /rei-toei  switch to Rei Toei music avatar (sticky until /sam)")
            print("  /sam             switch back to Sam")
            print()
            print(str(Fore.YELLOW) + "Creative" + str(Style.RESET_ALL))
            print("  /art [topic]     FLUX render from the most recent AI reply")
            print("                   optional topic hint narrows visual direction")
            print(str(Fore.CYAN) + _hr + str(Style.RESET_ALL))
            continue
        if cmd == "/reset":
            history.clear()
            print("Conversation history cleared.")
            continue
        if cmd.startswith("/sam"):
            active_console_avatar = "sam"
            sam_input = user_input[len("/sam"):].strip()
            if not sam_input:
                print(str(Fore.GREEN) + "Sam> Back on the main console voice." + str(Style.RESET_ALL))
                continue
            user_input = sam_input
            cmd = user_input.lower()
        if cmd == "/reload":
            _profile_facts, _grounding_context, _raw_evidence_facts, _raw_domain_facts, _raw_extracted_facts = _load_knowledge_state()
            _avatar_facts_by_id, _domain_facts_by_id, _extracted_facts_by_id = _index_profile_facts(_profile_facts)
            try:
                from services.rei_toei_service import get_rei_service
                get_rei_service().reload(eager=False)
            except (OSError, ValueError, TypeError) as exc:
                logger.warning("Rei console knowledge reload failed: %s", exc)
            print(
                str(Fore.CYAN)
                + f"Knowledge reloaded — {len(_profile_facts)} grounding facts now active."
                + str(Style.RESET_ALL)
            )
            continue
        if cmd == "/verify":
            verify = not verify
            _status = str(Fore.GREEN) + "ON" + str(Style.RESET_ALL) if verify else str(Fore.RED) + "OFF" + str(Style.RESET_ALL)
            print(f"Verify mode: {_status}")
            _print_status()
            continue
        if cmd == "/avatar-explain":
            avatar_explain = not avatar_explain
            _status = str(Fore.GREEN) + "ON" + str(Style.RESET_ALL) if avatar_explain else str(Fore.RED) + "OFF" + str(Style.RESET_ALL)
            print(f"Avatar-explain mode: {_status}")
            _print_status()
            continue
        if cmd == "/dot-report":
            dot_report = not dot_report
            _status = str(Fore.GREEN) + "ON" + str(Style.RESET_ALL) if dot_report else str(Fore.RED) + "OFF" + str(Style.RESET_ALL)
            print(f"DoT report mode: {_status}")
            _print_status()
            continue
        if cmd == "/truth-gate":
            truth_gate = not truth_gate
            _status = str(Fore.GREEN) + "ON" + str(Style.RESET_ALL) if truth_gate else str(Fore.RED) + "OFF" + str(Style.RESET_ALL)
            print(f"Truth gate mode: {_status}")
            _print_status()
            continue
        if cmd == "/graph-stats":
            if _kg is None:
                print(str(Fore.RED) + "Knowledge Graph is not available." + str(Style.RESET_ALL))
            else:
                summary = _kg.summary()
                domain_profiles = collect_domain_knowledge_profiles(Path("data/avatar"))
                print(f"  Persona ID: {summary['persona_id']}")
                print_graph_statistics(summary, domain_profiles)
            continue
        
        # Rei Toei routing: explicit /rei command or sticky Rei mode turns
        from services.console_grounding._rei_console import (
            REI_DEFAULT_PROMPT,
            extract_rei_input,
            handle_rei_console,
            is_rei_command,
            should_handle_rei_turn,
        )

        if should_handle_rei_turn(user_input, active_console_avatar):
            import asyncio

            active_console_avatar = "rei"
            rei_input = extract_rei_input(user_input) if is_rei_command(user_input) else user_input.strip()

            if not rei_input:
                rei_input = REI_DEFAULT_PROMPT
            
            try:
                _status_width = _show_console_thinking("rei")
                with timed_stage(logger, "console.rei.turn"):
                    reply, history = asyncio.run(handle_rei_console(rei_input, ai, history, max_tokens=600))
                if len(history) > max_turns * 2:
                    history = history[-max_turns * 2 :]
                _clear_console_status(_status_width + 2)
                _print_console_reply("rei", reply)
                speak_text(reply)
            except Exception as rei_err:
                logger.error(f"Rei console error: {rei_err}")
                _clear_console_status(32)
                print(str(Fore.RED) + f"⚠️ Rei error: {rei_err}" + str(Style.RESET_ALL))
            continue

        if cmd.startswith("/art"):
            _art_topic_hint = user_input[len("/art"):].strip() or None
            _art_src = next(
                (m["content"] for m in reversed(history) if m["role"] == "assistant"),
                None,
            )
            if not _art_src and _art_topic_hint:
                _art_src = f"Visual representation of {_art_topic_hint}"
            if not _art_src:
                print(str(Fore.YELLOW) + "⚠️  No previous reply to render art from. Generate a response first or provide a topic (e.g. /art 'shrine maiden')." + str(Style.RESET_ALL))
            else:
                print(str(Fore.CYAN) + "🎨 Requesting art avatar..." + str(Style.RESET_ALL))
                _art_result = _render_console_art_avatar(ai, _art_src, _art_topic_hint)
                _art_status = _art_result.get("art_avatar_status", "unavailable")
                if _art_status == RenderStatus.RENDERED.value:
                    print(str(Fore.GREEN) + f"✅  Art rendered → {_art_result.get('art_avatar_image_path', '')}" + str(Style.RESET_ALL))
                    _display_art_in_terminal(_art_result.get("art_avatar_image_path"))
                    _story = _art_result.get("art_avatar_story_path")
                    if _story:
                        print(str(Fore.GREEN) + f"   Story → {_story}" + str(Style.RESET_ALL))
                elif _art_status in (RenderStatus.DEFERRED.value, RenderStatus.TEXT_ONLY.value):
                    print(str(Fore.YELLOW) + f"⏳  GPU busy — {_art_result.get('art_avatar_defer_reason', 'image deferred')}" + str(Style.RESET_ALL))
                else:
                    print(str(Fore.RED) + f"⚠️  Art generation: {_art_status} — {_art_result.get('art_avatar_render_error', '')}" + str(Style.RESET_ALL))
            continue

        if cmd.startswith("/katzilla"):
            query = user_input[len("/katzilla"):].strip()
            if not query:
                print(str(Fore.YELLOW) + "Usage: /katzilla <query>" + str(Style.RESET_ALL))
                continue
            try:
                from services.avatar_intelligence._retrieval import _retrieve_external_evidence

                external = _retrieve_external_evidence(query=query, category_filter=None, limit=5)
                from services.avatar_intelligence import ExternalEvidenceFact as _ExtFact
                reply = build_katzilla_citation_reply(query, [e for e in external if isinstance(e, _ExtFact)])
                history.append({"role": "user", "content": user_input})
                history.append({"role": "assistant", "content": reply})
                if len(history) > max_turns * 2:
                    history = history[-max_turns * 2 :]
                _print_console_reply("sam", reply)
            except Exception as exc:
                print(str(Fore.RED) + f"⚠️ Katzilla request failed: {exc}" + str(Style.RESET_ALL))
            continue

        # Parse query to determine routing mode
        constraints = parse_query_constraints(user_input, tag_expansions=_tag_expansions)
        
        # Route 1: Explicit file name requests → Deterministic citation (raw facts)
        if constraints.explicit_artifact_request:
            if constraints.list_domain_characters or constraints.list_domain_terms:
                facts = [
                    f
                    for f in _profile_facts
                    if f.source.startswith("domain:") or f.company == "Domain Knowledge"
                ]
            else:
                facts = retrieve_relevant_facts(_profile_facts, constraints, query=user_input, limit=8)
            reply = build_deterministic_grounded_reply(user_input, facts, constraints)
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": reply})
            if len(history) > max_turns * 2:
                history = history[-max_turns * 2 :]
            _print_console_reply("sam", reply)
            speak_text(reply)
            continue

        # Route 2: "From your learned knowledge" → Use latest 8 extracted knowledge as context
        # If user asks to search, use keyword-based search instead of latest 8
        if constraints.use_learned_knowledge:
            if constraints.search_learned_knowledge:
                from services.console_grounding._retrieval import search_learned_knowledge
                learned_facts = search_learned_knowledge(user_input, _profile_facts, limit=8)
            else:
                learned_facts = get_latest_extracted_knowledge(_profile_facts, limit=8)
            # Filter the raw lists based on the 'learned_facts' we actually retrieved
            used_extracted = [f for f in _raw_extracted_facts if any(lf.source.endswith(f.evidence_id) for lf in learned_facts)]
            learned_context = build_learned_knowledge_context(learned_facts)
            history.append({"role": "user", "content": user_input})
            if len(history) > max_turns * 2:
                history = history[-max_turns * 2 :]
            try:
                # Use learned knowledge as PRIMARY context (put it first and emphasize it)
                # The learned knowledge should be the focus, with persona context as background
                enhanced_context = f"{learned_context}\n\n{_grounding_context}" if _grounding_context else learned_context
                _status_width = _show_console_thinking("sam")
                reply = ai.chat_as_persona(history, grounding_context=enhanced_context, max_tokens=600)
                _clear_console_status(_status_width + 2)
            except Exception as e:
                _clear_console_status(24)
                _print_console_error("sam", str(e))
                history.pop()
                continue
            reply, _gate_meta = _apply_console_truth_gate(reply, learned_facts)
            if not reply:
                history.pop()
                continue
            history.append({"role": "assistant", "content": reply})
            _print_console_reply("sam", reply)
            speak_text(reply)
            _auto_render_art_if_requested(ai, reply, constraints, user_input)
            if verify:
                print(str(Fore.CYAN) + "📊 Verifying..." + str(Style.RESET_ALL), end="", flush=True)
                _gate_meta = _print_truth_score(reply, learned_facts, _gate_meta)
                print("\r" + " " * 20 + "\r", end="", flush=True)  # Clear the "Verifying..." line
            elif (avatar_explain or dot_report) and _gate_meta is None:
                if avatar_explain:
                    print(f"{Fore.CYAN}🧠 Generating avatar-explain...{Style.RESET_ALL}", end="", flush=True)
                with timed_stage(logger, "console.verification"):
                    _, _gate_meta = _tg_result(
                        reply, "", learned_facts, channel="console", dot_facts=learned_facts, log_removals=False,
                    )
            
            
            from services.shared import print_validation_reports

            print_validation_reports(
                post_text=reply,
                context_text=user_input,
                grounding_facts=_profile_facts,
                raw_evidence=[],
                raw_domain=[],
                raw_extracted=used_extracted,
                raw_external=[],
                facts_used_for_dot=learned_facts,
                verify=False,
                avatar_explain=avatar_explain,
                dot_report=dot_report,
                gate_meta=_gate_meta
            )

            continue

        # Route 3: Everything else → LLM with artifact context (default)
        # This includes: domain/project/tech queries, generative requests, general chat
        # Always retrieve relevant facts and use as context
        if _hybrid_retriever is not None:
            # Use hybrid retriever (BM25 + graph proximity + claim support)
            # Combine all raw facts (evidence + domain + extracted) for hybrid scoring
            _all_candidates = list(_raw_evidence_facts) + _raw_domain_facts + _raw_extracted_facts
            facts_ranked = _hybrid_retriever.find_facts(user_input, _all_candidates, limit=8)
            # Convert results back to ProjectFact for compatibility with build_grounding_facts_block
            from services.avatar_intelligence import EvidenceFact, DomainEvidenceFact, ExtractedEvidenceFact
            facts = []
            for f in facts_ranked:
                if isinstance(f, EvidenceFact):
                    matching = _avatar_facts_by_id.get(f.source_project_id)
                    if matching is not None:
                        facts.append(matching)
                elif isinstance(f, DomainEvidenceFact):
                    matching = _domain_facts_by_id.get(f.source_fact_id or f.evidence_id)
                    if matching is not None:
                        facts.append(matching)
                elif isinstance(f, ExtractedEvidenceFact):
                    matching = _extracted_facts_by_id.get(f.evidence_id or f.source_fact_id)
                    if matching is not None:
                        facts.append(matching)
            # Categorize only the top facts for the validation report
            # This ensures build_explain_output only sees what was actually used
            used_ev = [f for f in facts_ranked[:8] if isinstance(f, EvidenceFact)]
            used_dom = [f for f in facts_ranked[:8] if isinstance(f, DomainEvidenceFact)]
            used_ext = [f for f in facts_ranked[:8] if isinstance(f, ExtractedEvidenceFact)]
            used_external = []
            # Ensure we have at least some facts even if conversion failed
            if not facts:
                facts = retrieve_relevant_facts(_profile_facts, constraints, query=user_input, limit=8)
        else:
            # Fallback to simple retrieval when graph not available
            facts = retrieve_relevant_facts(_profile_facts, constraints, query=user_input, limit=8)
            used_ev, used_dom, used_ext, used_external = [], [], [], []

        external_context = ""
        try:
            from services.avatar_intelligence import retrieve_evidence, ExternalEvidenceFact, build_external_grounding_context

            # Distinct local results fill both slots when the pool has enough facts;
            # they would all be discarded by the external-only filter below.
            external_pool = list(_raw_evidence_facts) + list(_raw_domain_facts)
            local_ids = {f.evidence_id for f in external_pool}
            external_candidates = retrieve_evidence(
                user_input,
                external_pool,
                limit=2,
            ) if 0 < len(local_ids) < 2 else []
            used_external = [f for f in external_candidates if isinstance(f, ExternalEvidenceFact)]
            external_context = build_external_grounding_context(used_external)
        except Exception as exc:
            logger.warning("Console external evidence retrieval failed: %s", exc)
            used_external = []

        facts_context = build_grounding_facts_block(facts, limit=8)
        if constraints.is_kanji_teaching_request:
            teaching_facts = [
                fact for fact in facts
                if fact.source.startswith("domain:") or fact.company == "Domain Knowledge"
            ]
            if not teaching_facts:
                teaching_facts = [
                    fact for fact in _profile_facts
                    if fact.source.startswith("domain:") or fact.company == "Domain Knowledge"
                ]
            kanji_context = build_kanji_teaching_context(teaching_facts)
            if kanji_context:
                facts_context = f"{facts_context}\n\n{kanji_context}".strip()
        history.append({"role": "user", "content": user_input})
        if len(history) > max_turns * 2:
            history = history[-max_turns * 2 :]
        try:
            # Use retrieved facts as additional context
            enhanced_context = f"{_grounding_context}\n\n{facts_context}" if _grounding_context else facts_context
            if external_context:
                enhanced_context = f"{enhanced_context}\n\n{external_context}".strip()
            _status_width = _show_console_thinking("sam")
            reply = ai.chat_as_persona(history, grounding_context=enhanced_context, max_tokens=600)
            _clear_console_status(_status_width + 2)
        except Exception as e:
            _clear_console_status(24)
            _print_console_error("sam", str(e))
            history.pop()
            continue
        reply, _gate_meta = _apply_console_truth_gate(reply, facts)
        if not reply:
            history.pop()
            continue
        history.append({"role": "assistant", "content": reply})
        _print_console_reply("sam", reply)
        speak_text(reply)
        _auto_render_art_if_requested(ai, reply, constraints, user_input)
        if verify:
            print(str(Fore.CYAN) + "📊 Verifying..." + str(Style.RESET_ALL), end="", flush=True)
            _gate_meta = _print_truth_score(reply, facts, _gate_meta)
            print("\r" + " " * 20 + "\r", end="", flush=True)  # Clear the "Verifying..." line
        elif (avatar_explain or dot_report) and _gate_meta is None:
            if avatar_explain:
                print(f"{Fore.CYAN}🧠 Generating avatar-explain...{Style.RESET_ALL}", end="", flush=True)
            with timed_stage(logger, "console.verification"):
                _, _gate_meta = _tg_result(reply, "", facts, channel="console", dot_facts=facts, log_removals=False)

        from services.shared import print_validation_reports
        print_validation_reports(
            post_text=reply,
            context_text=user_input,
            grounding_facts=_profile_facts,
            raw_evidence=used_ev,
            raw_domain=used_dom,
            raw_extracted=used_ext,
            raw_external=used_external,
            facts_used_for_dot=facts,
            verify=False,
            avatar_explain=avatar_explain,
            dot_report=dot_report,
            gate_meta=_gate_meta
        )

def main():
    parser = build_parser()
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
        if args.reconcile:
            incompatible.append("--reconcile")
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

    if run_admin_command(args, build_buffer_service):
        return

    if not (args.schedule or args.curate or args.console or args.rei_generate or args.rei_generate_strudel):
        parser.print_help()
        return

    print_startup_notice()

    _github_context = ""
    if args.curate or args.console:
        _github_context = build_github_profile_context(
            max_chars=int(os.getenv("GITHUB_CONTEXT_MAX_CHARS", "30000"))
        )
    if _github_context:
        logger.info("GitHub context loaded: %d chars", len(_github_context))

    ai = OllamaService(
        model=os.getenv(
            "OLLAMA_MODEL",
            "gemma4:e4b" if args.rei_generate or args.rei_generate_strudel else "llama3.2",
        ),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )

    if args.console:
        run_console(
            ai=ai,
            github_context=_github_context,
            verify=args.verify,
            avatar_explain=args.avatar_explain,
            dot_report=args.dot_report,
            truth_gate=args.truth_gate,
        )
        return

    # Handle Rei Toei CLI commands — Phase 1E full implementation
    if args.rei_generate or args.rei_generate_strudel:
        run_rei_cli(args, ai)
        return

    if args.curate:
        run_curate_cli(args, ai, _github_context, build_buffer_service)
        return


    if args.schedule:
        run_schedule_cli(args, ai, build_buffer_service)


if __name__ == "__main__":
    main()
