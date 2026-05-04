"""Category performance analytics for selection learning.

Tracks which content categories perform best for different SSI components,
providing insights into category-based content strategy.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CategoryPerformance:
    """Performance metrics for a single category."""

    category: str
    ssi_component: str
    total_candidates: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    avg_rank_score: float = 0.0
    acceptance_rate: float = 0.0

    def update_acceptance_rate(self) -> None:
        """Recalculate acceptance rate from counts."""
        total = self.accepted_count + self.rejected_count
        self.acceptance_rate = (
            self.accepted_count / total if total > 0 else 0.0
        )


@dataclass
class CategoryAnalyticsReport:
    """Comprehensive category performance report."""

    total_categories_tracked: int = 0
    total_candidates_analyzed: int = 0
    category_performance: dict[str, CategoryPerformance] = field(
        default_factory=dict
    )
    ssi_component_breakdown: dict[str, list[CategoryPerformance]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def top_categories_by_acceptance(
        self, limit: int = 5
    ) -> list[CategoryPerformance]:
        """Return top N categories by acceptance rate."""
        return sorted(
            self.category_performance.values(),
            key=lambda p: p.acceptance_rate,
            reverse=True,
        )[:limit]

    def top_categories_by_ssi(
        self, ssi_component: str, limit: int = 3
    ) -> list[CategoryPerformance]:
        """Return top N categories for a specific SSI component."""
        return sorted(
            self.ssi_component_breakdown.get(ssi_component, []),
            key=lambda p: p.acceptance_rate,
            reverse=True,
        )[:limit]


def compute_category_analytics(
    candidates: list[Any],
) -> CategoryAnalyticsReport:
    """Compute category performance analytics from candidate records.

    Args:
        candidates: List of CandidateRecord objects with category metadata

    Returns:
        CategoryAnalyticsReport with performance metrics
    """
    report = CategoryAnalyticsReport()
    category_stats: dict[
        tuple[str, str], dict[str, Any]
    ] = defaultdict(
        lambda: {
            "total": 0,
            "accepted": 0,
            "rejected": 0,
            "rank_scores": [],
        }
    )

    for candidate in candidates:
        category = getattr(candidate, "primary_category", None)
        ssi = getattr(candidate, "primary_ssi_component", None)
        status = getattr(candidate, "status", "pending")
        rank_score = getattr(candidate, "rank_score", 0.0)

        if not category or not ssi:
            continue

        key = (category, ssi)
        stats = category_stats[key]
        stats["total"] += 1
        stats["rank_scores"].append(rank_score)

        if status == "accepted":
            stats["accepted"] += 1
        elif status == "rejected":
            stats["rejected"] += 1

        report.total_candidates_analyzed += 1

    # Build performance objects
    for (category, ssi), stats in category_stats.items():
        perf = CategoryPerformance(
            category=category,
            ssi_component=ssi,
            total_candidates=stats["total"],
            accepted_count=stats["accepted"],
            rejected_count=stats["rejected"],
            avg_rank_score=(
                sum(stats["rank_scores"]) / len(stats["rank_scores"])
                if stats["rank_scores"]
                else 0.0
            ),
        )
        perf.update_acceptance_rate()
        report.category_performance[f"{category}:{ssi}"] = perf
        report.ssi_component_breakdown[ssi].append(perf)

    report.total_categories_tracked = len(report.category_performance)
    return report


def format_category_analytics_report(
    report: CategoryAnalyticsReport,
) -> str:
    """Format category analytics report for console display."""
    from colorama import Fore, Style

    lines = [
        str(Fore.CYAN)
        + str(Style.BRIGHT)
        + "\n📊 Category Performance Analytics"
        + str(Style.RESET_ALL),
        "",
        f"  Total candidates analyzed: {report.total_candidates_analyzed}",
        f"  Categories tracked: {report.total_categories_tracked}",
        "",
    ]

    # Top performing categories overall
    top = report.top_categories_by_acceptance(limit=5)
    if top:
        lines.append(
            str(Fore.GREEN)
            + "  🏆 Top Categories by Acceptance Rate"
            + str(Style.RESET_ALL)
        )
        for i, perf in enumerate(top, 1):
            rate_pct = perf.acceptance_rate * 100
            color = (
                str(Fore.GREEN)
                if rate_pct >= 50
                else str(Fore.YELLOW)
                if rate_pct >= 25
                else str(Fore.RED)
            )
            lines.append(
                f"    {i}. {perf.category} ({perf.ssi_component})"
            )
            lines.append(
                f"       {color}{rate_pct:.1f}% acceptance{str(Style.RESET_ALL)} "
                f"({perf.accepted_count}/{perf.total_candidates} accepted)"
            )
            lines.append(
                f"       Avg rank score: {perf.avg_rank_score:.3f}"
            )
        lines.append("")

    # Per-SSI component breakdown
    ssi_components = [
        "establish_brand",
        "find_right_people",
        "engage_with_insights",
        "build_relationships",
    ]
    for ssi in ssi_components:
        top_for_ssi = report.top_categories_by_ssi(ssi, limit=3)
        if top_for_ssi:
            lines.append(
                str(Fore.YELLOW)
                + f"  📌 {ssi.replace('_', ' ').title()}"
                + str(Style.RESET_ALL)
            )
            for perf in top_for_ssi:
                rate_pct = perf.acceptance_rate * 100
                lines.append(
                    f"    • {perf.category}: {rate_pct:.1f}% acceptance "
                    f"({perf.accepted_count}/{perf.total_candidates})"
                )
            lines.append("")

    return "\n".join(lines)