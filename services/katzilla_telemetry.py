"""Katzilla telemetry and simple daily budget controls."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path


logger = logging.getLogger(__name__)

_KATZILLA_LOG_PATH = Path("data") / "selection" / "katzilla_events.jsonl"


@dataclass
class KatzillaEvent:
    timestamp: str
    status: str
    agent: str
    action: str
    duration_ms: int
    result_count: int
    uncertainty_avg: float
    query_hash: str
    error_type: str = ""


def _today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _hash_query(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]


def record_katzilla_event(
    *,
    status: str,
    agent: str,
    action: str,
    duration_ms: int,
    result_count: int,
    uncertainty_avg: float,
    query: str,
    error_type: str = "",
) -> None:
    """Append one Katzilla telemetry event to JSONL storage."""
    event = KatzillaEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        status=status,
        agent=agent,
        action=action,
        duration_ms=max(0, int(duration_ms)),
        result_count=max(0, int(result_count)),
        uncertainty_avg=max(0.0, float(uncertainty_avg)),
        query_hash=_hash_query(query),
        error_type=error_type,
    )

    try:
        _KATZILLA_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _KATZILLA_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(event)) + "\n")
    except OSError as exc:
        logger.warning("Katzilla telemetry write failed (continuing): %s", exc)


def get_daily_katzilla_usage(day_utc: str | None = None) -> dict[str, float]:
    """Return daily call counters and uncertainty totals from telemetry log."""
    day = day_utc or _today_utc()
    calls = 0
    uncertainty_sum = 0.0

    if not _KATZILLA_LOG_PATH.exists():
        return {"calls": 0.0, "uncertainty_sum": 0.0}

    with _KATZILLA_LOG_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = str(rec.get("timestamp", ""))
            if not ts.startswith(day):
                continue

            status = str(rec.get("status", ""))
            if status != "success":
                continue

            calls += 1
            uncertainty_sum += float(rec.get("uncertainty_avg", 0.0) or 0.0)

    return {"calls": float(calls), "uncertainty_sum": float(uncertainty_sum)}


def can_call_katzilla(
    *,
    max_calls_per_day: int,
    max_uncertainty_per_day: float,
) -> tuple[bool, str]:
    """Return whether a new Katzilla call fits inside configured daily budgets."""
    usage = get_daily_katzilla_usage()
    if usage["calls"] >= float(max_calls_per_day):
        return False, "daily_call_budget_exhausted"
    if usage["uncertainty_sum"] >= float(max_uncertainty_per_day):
        return False, "daily_uncertainty_budget_exhausted"
    return True, ""
