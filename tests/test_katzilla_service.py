import pytest

from services.katzilla_service import (
    KatzillaAuthError,
    KatzillaEnvelope,
    KatzillaInputError,
    KatzillaRateLimitError,
    KatzillaService,
    KatzillaUpstreamError,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or str(payload)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self):
        return self._payload


def test_katzilla_service_requires_api_key() -> None:
    with pytest.raises(ValueError):
        KatzillaService(api_key="")


def test_katzilla_query_action_success(monkeypatch: pytest.MonkeyPatch) -> None:
    service = KatzillaService(api_key="token", base_url="https://katzilla.dev")

    def _fake_post(url, headers, json, timeout):
        assert url == "https://katzilla.dev/api/health/fda-recalls"
        assert headers["X-API-Key"] == "token"
        assert json["query"] == "latest FDA recalls"
        return _FakeResponse(
            200,
            {
                "data": [{"title": "Recall A"}],
                "quality": {"confidence": "high", "uncertainty": 0.1},
                "citation": {"source_name": "FDA"},
                "meta": {"provider": "katzilla"},
            },
        )

    monkeypatch.setattr("services.katzilla_service.requests.post", _fake_post)

    env = service.query_action("health", "fda-recalls", "latest FDA recalls")
    assert isinstance(env, KatzillaEnvelope)
    assert isinstance(env.data, list)
    assert env.citation["source_name"] == "FDA"


def test_katzilla_query_action_maps_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    service = KatzillaService(api_key="token")

    def _fake_post(url, headers, json, timeout):
        return _FakeResponse(401, {"message": "unauthorized"})

    monkeypatch.setattr("services.katzilla_service.requests.post", _fake_post)

    with pytest.raises(KatzillaAuthError):
        service.query_action("health", "fda-recalls", "latest FDA recalls")


def test_katzilla_query_action_maps_input_error(monkeypatch: pytest.MonkeyPatch) -> None:
    service = KatzillaService(api_key="token")

    def _fake_post(url, headers, json, timeout):
        return _FakeResponse(422, {"message": "bad query"})

    monkeypatch.setattr("services.katzilla_service.requests.post", _fake_post)

    with pytest.raises(KatzillaInputError):
        service.query_action("health", "fda-recalls", "latest FDA recalls")


def test_katzilla_query_action_retries_upstream(monkeypatch: pytest.MonkeyPatch) -> None:
    service = KatzillaService(api_key="token", max_retries=1)
    calls = {"n": 0}

    def _fake_post(url, headers, json, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeResponse(503, {"message": "upstream unavailable"})
        return _FakeResponse(
            200,
            {
                "data": [{"title": "Recovered"}],
                "quality": {},
                "citation": {},
                "meta": {},
            },
        )

    monkeypatch.setattr("services.katzilla_service.requests.post", _fake_post)

    env = service.query_action("hazards", "usgs-earthquakes", "earthquakes today")
    assert env.data[0]["title"] == "Recovered"
    assert calls["n"] == 2


def test_katzilla_query_action_retries_then_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    service = KatzillaService(api_key="token", max_retries=1)

    def _fake_post(url, headers, json, timeout):
        return _FakeResponse(429, {"message": "slow down"})

    monkeypatch.setattr("services.katzilla_service.requests.post", _fake_post)

    with pytest.raises(KatzillaRateLimitError):
        service.query_action("government", "congress-bills", "ai safety bills")
