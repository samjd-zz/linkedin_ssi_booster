"""Tests for FluxCapacitorService singleton behavior."""

from __future__ import annotations

from threading import Thread
from types import SimpleNamespace
from unittest.mock import patch


def test_get_flux_service_singleton_under_concurrency():
    """Concurrent callers should construct FluxCapacitorService once."""
    import services.flux_capacitor as fc_pkg

    created = []

    class _FakeService:
        def __init__(self) -> None:
            self.config = SimpleNamespace(enabled=False, style_preset="test")

    def _factory():
        inst = _FakeService()
        created.append(inst)
        return inst

    fc_pkg._service_instance = None

    results = []
    with patch("services.flux_capacitor.FluxCapacitorService", side_effect=_factory):
        threads = [Thread(target=lambda: results.append(fc_pkg.get_flux_service())) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

    assert len(created) == 1
    assert len(results) == 8
    assert all(obj is created[0] for obj in results)

    fc_pkg._service_instance = None
