"""Data models used by selection learning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CandidateRecord:
    """One generated post candidate captured at curation time."""

    candidate_id: str
    timestamp: str
    article_url: str
    article_title: str
    article_source: str
    ssi_component: str
    channel: str
    text_hash: str
    text_snippet: str
    buffer_id: str | None
    route: str
    selected: bool | None
    selected_at: str | None
    run_id: str
    themes: list[str] = field(default_factory=list)
    sentiment: dict[str, Any] = field(default_factory=dict)
    user_feedback: dict[str, Any] = field(default_factory=dict)
    # Model2Vec classification metadata (optional — populated when --classify is used)
    primary_category: str = ""
    primary_ssi_component: str = ""
    category_confidence: float = 0.0


@dataclass
class PublishedRecord:
    """One confirmed-published post fetched from Buffer (status=SENT)."""

    buffer_id: str
    channel: str
    text_snippet: str
    published_at: str
    fetched_at: str
    candidate_id: str | None


@dataclass
class FeaturePrior:
    """Beta-smoothed acceptance rate for one feature bucket."""

    feature_key: str
    feature_value: str
    n_selected: int
    n_total: int
    acceptance_rate: float
    boost_factor: float = 1.0

    @property
    def source(self) -> str:
        """Extract source from feature_key if it's a source feature."""
        if self.feature_key == "source":
            return self.feature_value
        return ""

    @property
    def ssi_component(self) -> str:
        """Extract ssi_component from feature_key if it's an ssi feature."""
        if self.feature_key == "ssi_component":
            return self.feature_value
        return ""
