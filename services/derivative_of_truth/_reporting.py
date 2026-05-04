"""Report builders/formatters for Derivative of Truth results."""

from __future__ import annotations

from typing import Any

from services.derivative_of_truth._models import TruthGradientResult


def report_truth_gradient(
    claim: str,
    result: TruthGradientResult,
    verbose: bool = False,
    primary_category: str | None = None,
    primary_ssi_component: str | None = None,
) -> dict[str, Any]:
    """Produce a structured report dict for a truth gradient result."""
    report: dict[str, Any] = {
        "claim_snippet": claim[:120] + ("..." if len(claim) > 120 else ""),
        "truth_gradient": round(result.truth_gradient, 4),
        "uncertainty": round(result.uncertainty, 4),
        "confidence_penalty": round(result.confidence_penalty, 4),
        "flagged": result.flagged,
        "uncertainty_sources": result.uncertainty_sources,
        "explanation": result.explanation,
        "pln_mode": result.pln_mode,  # Phase 1: indicate PLN vs. legacy
        "truth_derivative": (
            round(result.truth_derivative, 4) if result.truth_derivative is not None else None
        ),  # Phase 2: dT/dt
        "primary_category": primary_category,  # Model2Vec classification
        "primary_ssi_component": primary_ssi_component,  # SSI component from category
    }
    if verbose:
        report["evidence_paths"] = [
            {
                "source": p.source,
                "evidence_type": p.evidence_type,
                "reasoning_type": p.reasoning_type,
                "credibility": round(p.credibility, 3),
                "uncertainty": round(p.uncertainty, 3),
                "overlap": round(p.overlap, 3),
                "chain_length": p.chain_length,
                "conflicts_with": p.conflicts_with,
                # Phase 1: PLN truth values
                "pln_strength": round(p.pln_strength, 3) if p.pln_strength is not None else None,
                "pln_confidence": round(p.pln_confidence, 3) if p.pln_confidence is not None else None,
            }
            for p in result.evidence_paths
        ]
    return report


def format_dot_report_header(label: str = "Derivative of Truth Report") -> str:
    """Return a formatted multi-line header string for the DoT report."""
    from colorama import Fore, Style
    c = str(Fore.CYAN)
    dim = str(Style.DIM)
    r = str(Style.RESET_ALL)
    w = str(Fore.WHITE)
    lines = [
        f"\n{c}🔬 {label}{r}",
        f"  {dim}╔═ Per evidence path scores two dimensions:{r}",
        f"  {dim}║  {w}cred {dim}— how trustworthy is the source?  (👤 persona ≥0.80 · 📚 domain ≥0.76 · 🗂️ extracted ~0.65 · 🔗 article ~0.55){r}",
        f"  {dim}║  {w}unc  {dim}— how relevant is it to this claim? (token overlap; low unc = high relevance){r}",
        f"  {dim}╠═ Final gradient = base_cred × (1 − uncertainty_penalty){r}",
        f"  {dim}╚═ High cred + low overlap → credible but off-topic → penalty drags score yellow/red{r}",
    ]
    return "\n".join(lines)


def format_truth_gradient_report(report: dict[str, Any]) -> str:
    """Format a truth gradient report dict as a human-readable CLI string."""
    from colorama import Fore, Style

    tg: float = report["truth_gradient"]
    unc: float = report["uncertainty"]
    cp: float = report["confidence_penalty"]
    flagged: bool = report.get("flagged", False)

    bar_width = 20
    filled = round(tg * bar_width)
    if tg >= 0.70:
        bar_colour = Fore.GREEN
    elif tg >= 0.50:
        bar_colour = Fore.YELLOW
    else:
        bar_colour = Fore.RED
    gradient_bar = (
        str(bar_colour) + "█" * filled
        + str(Fore.WHITE) + "░" * (bar_width - filled)
        + str(Style.RESET_ALL)
    )

    status = (
        f"{Fore.RED}⚠️  FLAGGED{Style.RESET_ALL}"
        if flagged
        else f"{Fore.GREEN}✅ OK{Style.RESET_ALL}"
    )
    divider = f"  {Fore.CYAN}{'─' * 64}{Style.RESET_ALL}"
    c = Fore.CYAN
    r = Style.RESET_ALL

    # Phase 1 & 2: Show PLN mode and truth derivative
    mode_indicator = f"{c}Mode:{r} PLN-enhanced" if report.get("pln_mode", False) else f"{c}Mode:{r} Legacy"
    derivative_str = ""
    if report.get("truth_derivative") is not None:
        dt_dt = report["truth_derivative"]
        dt_color = Fore.GREEN if dt_dt > 0 else (Fore.RED if dt_dt < 0 else Fore.YELLOW)
        derivative_str = f"   {c}dT/dt:{r} {dt_color}{dt_dt:+.4f}/hr{r}"
    
    # Model2Vec category classification
    category_str = ""
    if report.get("primary_category"):
        cat = report["primary_category"]
        ssi = report.get("primary_ssi_component", "")
        category_str = f"  {c}Category:{r} {Fore.MAGENTA}{cat}{r}"
        if ssi:
            category_str += f"  {c}→{r} {Fore.YELLOW}{ssi}{r}"
    
    lines = [
        divider,
        f"  {status}  {gradient_bar}  {Fore.WHITE}{tg:.4f}{r}  {mode_indicator}{derivative_str}",
        (
            f"  {c}Uncertainty:{r} {_unc_colour(unc)}{unc:.4f}{r}   "
            f"{c}Confidence Penalty:{r} {cp:.4f}"
        ),
        f"  {c}Claim:{r} {report['claim_snippet']}",
    ]
    if category_str:
        lines.append(category_str)

    if report.get("uncertainty_sources"):
        src_list = ", ".join(
            f"{Fore.YELLOW}{s}{r}" for s in report["uncertainty_sources"]
        )
        lines.append(f"  {c}Uncertainty Sources:{r} {src_list}")

    if report.get("explanation"):
        lines.append(f"  {c}Explanation:{r} {report['explanation']}")

    if "evidence_paths" in report:
        lines.append(f"  {c}Evidence Paths:{r}")
        for ep in report["evidence_paths"]:
            source: str = ep["source"]
            cred: float = ep["credibility"]
            unc_ep: float = ep["uncertainty"]
            chain: int = ep["chain_length"]
            ev_type: str = ep["evidence_type"]
            re_type: str = ep["reasoning_type"]

            if source.startswith("avatar:"):
                icon, src_colour = "👤", Fore.MAGENTA
            elif source.startswith("domain:"):
                icon, src_colour = "📚", Fore.BLUE
            elif source.startswith("extracted_knowledge:"):
                icon, src_colour = "🗂️", Fore.CYAN
            else:
                icon, src_colour = "🔗", Fore.WHITE

            cred_col = Fore.GREEN if cred >= 0.75 else (Fore.YELLOW if cred >= 0.62 else Fore.RED)
            unc_col = Fore.RED if unc_ep >= 0.29 else (Fore.YELLOW if unc_ep >= 0.16 else Fore.GREEN)

            # Phase 1: Show PLN truth values if present
            pln_str = ""
            if ep.get("pln_strength") is not None and ep.get("pln_confidence") is not None:
                pln_s = ep["pln_strength"]
                pln_c = ep["pln_confidence"]
                pln_s_col = Fore.GREEN if pln_s >= 0.7 else (Fore.YELLOW if pln_s >= 0.5 else Fore.RED)
                pln_c_col = Fore.GREEN if pln_c >= 0.7 else (Fore.YELLOW if pln_c >= 0.5 else Fore.RED)
                pln_str = f"  PLN<s={pln_s_col}{pln_s:.2f}{r}, c={pln_c_col}{pln_c:.2f}{r}>"

            lines.append(
                f"    {icon} {src_colour}{source}{r}  "
                f"[{ev_type} / {re_type}]  "
                f"cred={cred_col}{cred:.2f}{r}  "
                f"unc={unc_col}{unc_ep:.2f}{r}  "
                f"chain={chain}{pln_str}"
            )
            lines.append(_explain_evidence_path_line(ep))

    lines.append(divider)

    dim = str(Style.DIM)
    evidence_paths = report.get("evidence_paths", []) if isinstance(report, dict) else []
    overlaps = [float(ep.get("overlap", 0.0)) for ep in evidence_paths if float(ep.get("overlap", 0.0)) > 0.0]
    avg_overlap = (sum(overlaps) / len(overlaps)) if overlaps else None
    unc_level = "high" if unc >= 0.35 else ("moderate" if unc >= 0.20 else "low")
    support_pct = int(round(tg * 100))

    # Coloured metric fragments burst through the dim surrounding text
    spct_col = Fore.GREEN if support_pct >= 70 else (Fore.YELLOW if support_pct >= 50 else Fore.RED)
    aln_col = (
        Fore.GREEN if avg_overlap is not None and avg_overlap >= 0.45
        else (Fore.YELLOW if avg_overlap is not None and avg_overlap >= 0.25 else Fore.RED)
    )
    unc_foot_col = Fore.GREEN if unc_level == "low" else (Fore.YELLOW if unc_level == "moderate" else Fore.RED)

    support_note = f"support {spct_col}{support_pct}/100{r}{dim}"
    alignment_note = (
        f"avg claim-evidence alignment {aln_col}{avg_overlap:.2f}{r}{dim}"
        if avg_overlap is not None
        else "alignment unavailable (no overlap-bearing paths)"
    )
    unc_note = f"uncertainty {unc_foot_col}{unc_level} ({unc:.2f}){r}{dim}"

    if flagged:
        footer_note = (
            f"  {dim}⚠  Weak support ({support_note}): {alignment_note}; {unc_note}.\n"
            f"     Review carefully before publishing and tighten claim-to-evidence grounding.{r}"
        )
    elif tg >= 0.70 and (avg_overlap is None or avg_overlap >= 0.45):
        footer_note = (
            f"  {dim}ℹ  Strong support ({support_note}): {alignment_note}; {unc_note}.\n"
            f"     Output is well-backed by the supplied evidence.{r}"
        )
    else:
        footer_note = (
            f"  {dim}ℹ  Moderate support ({support_note}): {alignment_note}; {unc_note}.\n"
            f"     Improve by making claims more explicit and evidence-linked.{r}"
        )
    lines.append(footer_note)
    lines.append(divider)
    lines.append(
        f"  {Fore.WHITE}Legend  "
        f"cred: {Fore.GREEN}≥0.75 high{Fore.WHITE} · {Fore.YELLOW}0.62–0.74 mod{Fore.WHITE} · {Fore.RED}<0.62 low{Fore.WHITE}   "
        f"unc: {Fore.GREEN}≤0.15 low{Fore.WHITE} · {Fore.YELLOW}0.16–0.28 mod{Fore.WHITE} · {Fore.RED}≥0.29 high{Fore.WHITE}   "
        f"gradient: {Fore.GREEN}≥0.70 strong{Fore.WHITE} · {Fore.YELLOW}0.50–0.69 moderate{Fore.WHITE} · {Fore.RED}<0.50 weak{r}"
    )
    return "\n".join(lines)


def _unc_colour(value: float) -> str:
    """Return a colorama colour code based on uncertainty magnitude."""
    from colorama import Fore
    if value >= 0.29:
        return str(Fore.RED)
    if value >= 0.16:
        return str(Fore.YELLOW)
    return str(Fore.GREEN)


def _explain_evidence_path_line(ep: dict[str, Any]) -> str:
    """Generate a one-sentence explanation for a single evidence path entry."""
    source: str = ep.get("source", "")
    ev_type: str = ep.get("evidence_type", "")
    re_type: str = ep.get("reasoning_type", "")
    cred: float = ep.get("credibility", 0.5)
    unc: float = ep.get("uncertainty", 0.2)
    chain: int = ep.get("chain_length", 1)

    if source.startswith("avatar:"):
        node = source.split(":", 1)[1]
        source_desc = f"first-hand persona fact from your avatar graph ('{node}')"
    elif source.startswith("domain:"):
        node = source.split(":", 1)[1]
        source_desc = f"user-curated domain knowledge ('{node}')"
    else:
        source_desc = f"knowledge source ('{source}')"

    ev_desc = {
        "primary": "Direct",
        "secondary": "Corroborating",
        "derived": "Inferred",
        "pattern": "Pattern-based",
    }.get(ev_type, "Evidence from")

    re_desc = {
        "logical": "logically reasoned",
        "statistical": "statistically supported",
        "analogy": "reasoned by analogy",
        "pattern": "pattern-matched",
    }.get(re_type, "reasoned")

    if cred >= 0.80:
        cred_qual = "high credibility"
    elif cred >= 0.60:
        cred_qual = "moderate-high credibility"
    elif cred >= 0.40:
        cred_qual = "moderate credibility"
    else:
        cred_qual = "lower credibility"

    if unc >= 0.35:
        unc_qual = "high uncertainty - treat with caution"
    elif unc >= 0.20:
        unc_qual = "moderate uncertainty from source variability"
    else:
        unc_qual = "low uncertainty"

    chain_note = "" if chain <= 1 else f" ({chain} inference hops to reach this fact)"

    overlap: float = ep.get("overlap", 0.0)
    if overlap >= 0.60:
        overlap_note = f", strong claim alignment ({overlap:.2f})"
    elif overlap >= 0.30:
        overlap_note = f", moderate claim alignment ({overlap:.2f})"
    elif overlap > 0.0:
        overlap_note = f", weak claim alignment ({overlap:.2f}) - output may diverge from evidence"
    else:
        overlap_note = ""

    return (
        f"      -> {ev_desc} {source_desc}{chain_note}, {re_desc}. "
        f"{cred_qual.capitalize()} ({cred:.2f}), {unc_qual} ({unc:.2f}){overlap_note}."
    )
