"""Katzilla API service wrapper.

This module centralizes all Katzilla HTTP communication, response envelope
validation, retry behavior, and error mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import requests


logger = logging.getLogger(__name__)


class KatzillaError(RuntimeError):
    """Base exception for Katzilla failures."""


class KatzillaAuthError(KatzillaError):
    """Authentication or authorization failed."""


class KatzillaRateLimitError(KatzillaError):
    """Rate limit reached."""


class KatzillaQuotaError(KatzillaError):
    """Account quota exhausted."""


class KatzillaInputError(KatzillaError):
    """Input payload is invalid."""


class KatzillaUpstreamError(KatzillaError):
    """Katzilla upstream data provider failure."""


class KatzillaServerError(KatzillaError):
    """Katzilla server-side failure."""


@dataclass
class KatzillaEnvelope:
    """Normalized Katzilla response envelope."""

    data: Any
    quality: dict[str, Any]
    citation: dict[str, Any]
    meta: dict[str, Any]


class KatzillaService:
    """HTTP client for Katzilla agent/action invocation."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://katzilla.dev",
        timeout_seconds: float = 6.0,
        default_format: str = "compact",
        max_retries: int = 1,
    ) -> None:
        if not api_key:
            raise ValueError("KATZILLA_API_KEY is required when Katzilla is enabled.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.default_format = default_format
        self.max_retries = max_retries
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _build_action_url(self, agent: str, action: str) -> str:
        return f"{self.base_url}/api/{agent}/{action}"

    def _raise_for_status(self, response: requests.Response) -> None:
        status = response.status_code
        detail = response.text
        try:
            payload = response.json()
            detail = str(payload.get("error") or payload.get("message") or payload)
        except ValueError:
            pass

        if status in (401, 403):
            raise KatzillaAuthError(detail)
        if status == 429:
            raise KatzillaRateLimitError(detail)
        if status == 402:
            raise KatzillaQuotaError(detail)
        if status in (400, 404, 409, 422):
            raise KatzillaInputError(detail)
        if status in (502, 503, 504):
            raise KatzillaUpstreamError(detail)
        if status >= 500:
            raise KatzillaServerError(detail)
        raise KatzillaError(detail)

    def _validate_envelope(self, payload: dict[str, Any]) -> KatzillaEnvelope:
        if "data" not in payload:
            raise KatzillaError("Katzilla response missing required 'data' field")

        quality = payload.get("quality") or {}
        citation = payload.get("citation") or {}
        meta = payload.get("meta") or {}

        if not isinstance(quality, dict):
            raise KatzillaError("Katzilla response 'quality' must be an object")
        if not isinstance(citation, dict):
            raise KatzillaError("Katzilla response 'citation' must be an object")
        if not isinstance(meta, dict):
            raise KatzillaError("Katzilla response 'meta' must be an object")

        return KatzillaEnvelope(data=payload["data"], quality=quality, citation=citation, meta=meta)

    def query_action(
        self,
        agent: str,
        action: str,
        query: str,
        result_limit: int = 3,
        response_format: str | None = None,
        fields: list[str] | None = None,
    ) -> KatzillaEnvelope:
        """Invoke a Katzilla action and return a validated response envelope."""
        if not agent or not action:
            raise ValueError("agent and action are required")
        if not query.strip():
            raise ValueError("query must be non-empty")

        payload: dict[str, Any] = {
            "query": query,
            "format": response_format or self.default_format,
            "limit": max(1, result_limit),
        }
        if fields:
            payload["fields"] = fields

        url = self._build_action_url(agent, action)

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout_seconds,
                )
                if not response.ok:
                    self._raise_for_status(response)
                parsed = response.json()
                if not isinstance(parsed, dict):
                    raise KatzillaError("Katzilla response must be a JSON object")
                return self._validate_envelope(parsed)
            except (KatzillaRateLimitError, KatzillaUpstreamError, KatzillaServerError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise
                logger.warning(
                    "Retrying Katzilla request (%s/%s): %s",
                    attempt + 1,
                    self.max_retries,
                    exc,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise KatzillaUpstreamError(str(exc)) from exc
                logger.warning(
                    "Retrying Katzilla request after transport error (%s/%s): %s",
                    attempt + 1,
                    self.max_retries,
                    exc,
                )

        raise KatzillaError(str(last_error) if last_error else "Unknown Katzilla error")
