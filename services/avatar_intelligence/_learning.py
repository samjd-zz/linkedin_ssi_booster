"""Learning log writer, explain output builder, and learning report."""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import uuid
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Sequence, Union

from services.avatar_intelligence._models import (
    DomainEvidenceFact,
    EvidenceFact,
    ExtractedEvidenceFact,
    ExplainOutput,
    LearningRecommendation,
    LearningReport,
    ModerationEvent,
)
from services.avatar_intelligence._paths import LEARNING_LOG_PATH as _DEFAULT_LEARNING_LOG_PATH

logger = logging.getLogger(__name__)

# Module-level run ID — stable for the lifetime of one process invocation.
_RUN_ID: str = str(uuid.uuid4())

# Minimum event count for a pattern to be included in recommendations.
_HEURISTIC_MIN_COUNT = 2


def _learning_log_path():
    """Return the current LEARNING_LOG_PATH, respecting monkeypatching on the package."""
    pkg = sys.modules.get("services.avatar_intelligence")
    if pkg is not None:
        return getattr(pkg, "LEARNING_LOG_PATH", _DEFAULT_LEARNING_LOG_PATH)
    return _DEFAULT_LEARNING_LOG_PATH


# ---------------------------------------------------------------------------
# Learning log writer (T2.1, T2.2)
# ---------------------------------------------------------------------------


def _sentence_hash(sentence: str) -> str:
    """Return a 16-char SHA-256 hex digest of the sentence (privacy-preserving)."""
    return hashlib.sha256(sentence.encode("utf-8")).hexdigest()[:16]


def record_moderation_event(
    *,
    sentence: str,
    reason_code: str,
    decision: str,
    channel: str,
    article_ref: str,
    project_refs: list[str] | None = None,
) -> None:
    """Append one ModerationEvent to learning_log.jsonl.

    Failures emit a warning and do not interrupt the generation/publish path.

    Args:
        sentence:     The flagged sentence (hashed before storage).
        reason_code:  Truth-gate reason string (e.g. 'unsupported_numeric').
        decision:     'kept' or 'removed'.
        channel:      Publication channel (linkedin, x, bluesky, threads, youtube, all).
        article_ref:  URL or title of the source article.
        project_refs: Project IDs or names referenced in the sentence.
    """
    if decision not in ("kept", "removed"):
        logger.warning(
            "record_moderation_event: invalid decision '%s'; must be 'kept' or 'removed'",
            decision,
        )
        return

    event = ModerationEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        channel=channel,
        reason_code=reason_code,
        decision=decision,
        sentence_hash=_sentence_hash(sentence),
        article_ref=article_ref,
        project_refs=project_refs or [],
        run_id=_RUN_ID,
    )
    try:
        log_path = _learning_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(event)) + "\n")
    except OSError as exc:
        logger.warning("Learning log write failed (continuing): %s", exc)


# ---------------------------------------------------------------------------
# Explain output builder (T2.4)
# ---------------------------------------------------------------------------


def build_explain_output(
    evidence_facts: Sequence[Union[EvidenceFact, DomainEvidenceFact]],
    article_ref: str,
    channel: str,
    ssi_component: str,
    dot_per_sentence_scores: list[float] | None = None,
    spacy_sim_scores: dict[str, float] | None = None,
    extracted_facts: "Sequence[ExtractedEvidenceFact] | None" = None,
    article_title: str = "",
    article_url: str = "",
) -> ExplainOutput:
    """Build an ExplainOutput summary from the evidence facts used in a generation.

    Args:
        evidence_facts:           Persona + domain facts retrieved for grounding.
        article_ref:              Article title or URL for display.
        channel:                  Target channel (linkedin, x, bluesky, etc.).
        ssi_component:            SSI component the post targets.
        dot_per_sentence_scores:  Per-sentence DoT gradient from TruthGateMeta.
        spacy_sim_scores:         Per-sentence spaCy similarity from TruthGateMeta.
        extracted_facts:          NLP-extracted knowledge facts used as evidence.
        article_title:            Title of the article used as external evidence.
        article_url:              URL of the article used as external evidence.
    """
    ids = [f.evidence_id for f in evidence_facts]
    summaries = []
    for f in evidence_facts:
        if isinstance(f, EvidenceFact):
            summaries.append(
                f"[{f.evidence_id}] {f.project} ({f.years}) — "
                f"{f.details[:80]}{'...' if len(f.details) > 80 else ''}"
            )
        elif isinstance(f, DomainEvidenceFact):
            summaries.append(
                f"[{f.evidence_id}] {f.domain} — "
                f"{f.statement[:80]}{'...' if len(f.statement) > 80 else ''} "
                f"(Tags: {', '.join(f.tags)})"
            )
        else:
            attrs = (
                ", ".join(f"{k}={v}" for k, v in vars(f).items())
                if hasattr(f, "__dict__")
                else str(f)
            )
            summaries.append(
                f"[{getattr(f, 'evidence_id', '?')}] Unknown evidence type: {attrs}"
            )

    # Build extracted knowledge summaries
    ext_summaries: list[str] = []
    for xf in (extracted_facts or []):
        tag_str = f" (Tags: {', '.join(xf.tags)})" if xf.tags else ""
        source_str = f" \u2190 {xf.source_title[:60]}" if xf.source_title else ""
        ext_summaries.append(
            f"[{xf.evidence_id}] {xf.statement[:80]}{'...' if len(xf.statement) > 80 else ''}"
            f"{tag_str}{source_str}"
        )

    # Build article evidence one-liner
    art_evidence = ""
    if article_title or article_url:
        _title = (article_title or article_ref)[:80]
        _url = article_url[:100] if article_url else ""
        art_evidence = _title + (f" | {_url}" if _url else "")

    return ExplainOutput(
        evidence_ids=ids,
        evidence_summaries=summaries,
        article_ref=article_ref,
        channel=channel,
        ssi_component=ssi_component,
        dot_per_sentence_scores=dot_per_sentence_scores or [],
        spacy_sim_scores=spacy_sim_scores or {},
        extracted_summaries=ext_summaries,
        article_evidence=art_evidence,
    )


def format_explain_output(explain: ExplainOutput) -> str:
    """Format an ExplainOutput as a human-readable, colorized block.

    Color/icon scheme mirrors the Derivative of Truth report:
      👤 Magenta  — avatar persona facts
      📚 Blue     — domain knowledge facts
      🗂️  Cyan     — extracted knowledge facts
      🔗 White    — article / external evidence
    """
    from colorama import Fore, Style

    C = str(Fore.CYAN)
    Y = str(Fore.YELLOW)
    G = str(Fore.GREEN)
    W = str(Fore.WHITE)
    M = str(Fore.MAGENTA)
    B = str(Fore.BLUE)
    DIM = str(Style.DIM)
    R = str(Style.RESET_ALL)

    ssi_colours = {
        "establish_brand":      str(Fore.GREEN),
        "find_right_people":    str(Fore.BLUE),
        "engage_with_insights": str(Fore.YELLOW),
        "build_relationships":  str(Fore.MAGENTA),
    }
    ssi_col = ssi_colours.get(explain.ssi_component, W)

    divider = f"  {C}{'─' * 64}{R}"

    def _id_pill(eid: str) -> str:
        if eid.startswith("E"):
            return f"{M}{eid}{R}"        # avatar → magenta (matches 👤 in DoT)
        elif eid.startswith("D"):
            return f"{B}{eid}{R}"        # domain → blue   (matches 📚 in DoT)
        elif eid.startswith("X"):
            return f"{C}{eid}{R}"        # extracted → cyan (matches 🗂️ in DoT)
        return f"{W}{eid}{R}"

    id_pills = (
        "  ".join(_id_pill(eid) for eid in explain.evidence_ids)
        if explain.evidence_ids
        else f"{DIM}none{R}"
    )

    lines = [
        divider,
        f"  {Y}🧠 Avatar Explain{R}",
        f"  {DIM}Shows which facts grounded this post — credibility check per evidence source{R}",
        divider,
        f"  {C}Article  :{R} {W}{explain.article_ref}{R}",
        f"  {C}Channel  :{R} {W}{explain.channel}{R}",
        f"  {C}SSI      :{R} {ssi_col}{explain.ssi_component}{R}",
        f"  {C}Evidence :{R} {id_pills}",
        "",
    ]

    def _render_fact_line(eid: str, rest: str, icon: str, col: str) -> str:
        if len(rest) > 120:
            rest = rest[:117] + "…"
        return f"    {icon} {col}[{eid}]{R} {rest}"

    if explain.evidence_summaries:
        lines.append(f"  {C}Evidence Paths:{R}")
        for summary in explain.evidence_summaries:
            if summary.startswith("["):
                bracket_end = summary.find("]")
                if bracket_end != -1:
                    eid = summary[1:bracket_end]
                    rest = summary[bracket_end + 1:].strip()
                    if eid.startswith("E"):
                        lines.append(_render_fact_line(eid, rest, "👤", M))
                    else:
                        lines.append(_render_fact_line(eid, rest, "📚", B))
                else:
                    lines.append(f"    {summary}")
            else:
                lines.append(f"    {summary}")
    else:
        lines.append(
            f"  {DIM}No persona graph facts were used (graph is empty or not loaded).{R}"
        )

    # Extracted knowledge section
    if explain.extracted_summaries:
        lines.append("")
        lines.append(f"  {C}Extracted Knowledge:{R}")
        for summary in explain.extracted_summaries:
            if summary.startswith("["):
                bracket_end = summary.find("]")
                if bracket_end != -1:
                    eid = summary[1:bracket_end]
                    rest = summary[bracket_end + 1:].strip()
                    lines.append(_render_fact_line(eid, rest, "🗂️ ", C))
                else:
                    lines.append(f"    {summary}")
            else:
                lines.append(f"    {summary}")

    # Article external evidence section
    if explain.article_evidence:
        lines.append("")
        lines.append(f"  {C}Article (External Evidence):{R}")
        lines.append(f"    🔗 {W}{explain.article_evidence}{R}")

    if explain.dot_per_sentence_scores:
        lines.append("")
        lines.append(f"  {C}Truth Gate — Per-Sentence DoT Gradient:{R}")
        lines.append(f"  {DIM}How well each sentence is supported by available evidence — higher is better. Does not penalize for off-topic grounding.{R}")
        for i, score in enumerate(explain.dot_per_sentence_scores, 1):
            if score >= 0.70:
                bar_col = G
            elif score >= 0.50:
                bar_col = Y
            else:
                bar_col = str(Fore.RED)
            bar_width = max(1, round(score * 20))
            filled = "█" * bar_width
            empty = "░" * (20 - bar_width)
            lines.append(
                f"    {DIM}▸{R} sentence {i:>2}  "
                f"{bar_col}{filled}{W}{empty}{R}  {W}{score:.4f}{R}"
            )

    if explain.spacy_sim_scores:
        lines.append("")
        lines.append(
            f"  {C}Truth Gate — spaCy Semantic Similarity:{R}"
        )
        for sentence, sim in explain.spacy_sim_scores.items():
            short = sentence[:70] + "…" if len(sentence) > 70 else sentence
            if sim >= 0.50:
                sim_col = G
            elif sim >= 0.25:
                sim_col = Y
            else:
                sim_col = str(Fore.RED)
            lines.append(f"    {DIM}▸{R} {sim_col}{sim:.3f}{R}  {DIM}{short}{R}")

    lines.append(divider)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Learning report (T2.5, T2.6, T2.7)
# ---------------------------------------------------------------------------


def _load_learning_events() -> list[dict[str, Any]]:
    """Read all events from learning_log.jsonl; skip malformed lines."""
    log_path = _learning_log_path()
    if not log_path.exists():
        return []
    events: list[dict[str, Any]] = []
    for i, line in enumerate(
        log_path.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("Learning log line %d is not valid JSON — skipping", i)
    return events


def _apply_heuristics(
    events: list[dict[str, Any]],
) -> list[LearningRecommendation]:
    """Apply rule-based heuristics to produce advisory-only recommendations.

    Rules:
    1. project_claim kept repeatedly → suggest domain-term candidate.
    2. Numeric removals repeatedly → suggest retrieval keyword review.
    3. High removal rate per channel → suggest channel prompt adjustment.
    """
    recs: list[LearningRecommendation] = []

    project_claim_kept = [
        e for e in events
        if "project_claim" in e.get("reason_code", "") and e.get("decision") == "kept"
    ]
    if len(project_claim_kept) >= _HEURISTIC_MIN_COUNT:
        recs.append(LearningRecommendation(
            category="domain_term",
            suggestion=(
                f"You overrode {len(project_claim_kept)} 'project_claim' removals. "
                "Consider adding the repeatedly-kept tech keywords to domain knowledge "
                "or CONSOLE_GROUNDING_TECH_KEYWORDS in your .env."
            ),
            confidence="high" if len(project_claim_kept) >= 5 else "medium",
            evidence_count=len(project_claim_kept),
        ))

    numeric_removed = [
        e for e in events
        if "unsupported_numeric" in e.get("reason_code", "") and e.get("decision") == "removed"
    ]
    if len(numeric_removed) >= _HEURISTIC_MIN_COUNT:
        recs.append(LearningRecommendation(
            category="retrieval_expansion",
            suggestion=(
                f"{len(numeric_removed)} numeric claims were removed. "
                "Review whether source articles provide supporting stats, and consider "
                "adjusting retrieval tags so richer articles are prioritised."
            ),
            confidence="medium",
            evidence_count=len(numeric_removed),
        ))

    channel_removals: Counter[str] = Counter(
        e.get("channel", "unknown")
        for e in events
        if e.get("decision") == "removed"
    )
    for channel, count in channel_removals.items():
        if count >= _HEURISTIC_MIN_COUNT * 2:
            recs.append(LearningRecommendation(
                category="prompt_length",
                suggestion=(
                    f"High removal rate on '{channel}' ({count} removed sentences). "
                    "Consider adjusting the channel prompt or instruction length to "
                    "reduce hallucination pressure."
                ),
                confidence="low" if count < 10 else "medium",
                evidence_count=count,
            ))

    return recs


def build_learning_report() -> LearningReport:
    """Aggregate events from learning_log.jsonl into a structured report.

    Returns a LearningReport with zero counts when the log is empty.
    Recommendations are advisory only — this function never mutates config files.
    """
    events = _load_learning_events()

    if not events:
        return LearningReport(
            total_events=0,
            kept_count=0,
            removed_count=0,
            top_reason_codes=[],
            kept_vs_removed=[],
            recommendations=[],
        )

    kept_count = sum(1 for e in events if e.get("decision") == "kept")
    removed_count = sum(1 for e in events if e.get("decision") == "removed")

    reason_counter: Counter[str] = Counter(
        e.get("reason_code", "unknown") for e in events
    )
    top_reason_codes = reason_counter.most_common(10)

    kept_by_reason: Counter[str] = Counter(
        e.get("reason_code", "unknown")
        for e in events if e.get("decision") == "kept"
    )
    removed_by_reason: Counter[str] = Counter(
        e.get("reason_code", "unknown")
        for e in events if e.get("decision") == "removed"
    )
    all_reasons = set(kept_by_reason) | set(removed_by_reason)
    kept_vs_removed = sorted(
        [(r, kept_by_reason[r], removed_by_reason[r]) for r in all_reasons],
        key=lambda x: x[1] + x[2],
        reverse=True,
    )

    recommendations = _apply_heuristics(events)

    return LearningReport(
        total_events=len(events),
        kept_count=kept_count,
        removed_count=removed_count,
        top_reason_codes=top_reason_codes,
        kept_vs_removed=kept_vs_removed,
        recommendations=recommendations,
    )


def format_learning_report(report: LearningReport) -> str:
    """Format a LearningReport as a human-readable plain-text block."""
    lines = [
        "── Avatar Learning Report ──────────────────────────────",
        f"Total events : {report.total_events}",
        f"Kept         : {report.kept_count}",
        f"Removed      : {report.removed_count}",
        "",
    ]

    if report.top_reason_codes:
        lines.append("Top reason codes:")
        for code, count in report.top_reason_codes:
            lines.append(f"  {code:<40} {count:>4}")
        lines.append("")

    if report.kept_vs_removed:
        lines.append("Kept vs removed by reason:")
        lines.append(f"  {'Reason':<40} {'Kept':>6} {'Removed':>8}")
        lines.append(f"  {'-'*40} {'------':>6} {'--------':>8}")
        for reason, kept, removed in report.kept_vs_removed:
            lines.append(f"  {reason:<40} {kept:>6} {removed:>8}")
        lines.append("")

    if report.recommendations:
        lines.append("Recommendations (advisory only — no config files modified):")
        for rec in report.recommendations:
            lines.append(f"  [{rec.confidence.upper()}] [{rec.category}] {rec.suggestion}")
        lines.append("")
    else:
        lines.append("No recommendations (insufficient data or no patterns detected).")

    lines.append("────────────────────────────────────────────────────────")
    return "\n".join(lines)
