"""Shutdown avoids unused FLUX requests while retaining resource release."""

import logging
import socket
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import main
from services.flux_capacitor import _pipeline as pipeline


@pytest.mark.parametrize("remote_used", [False, True])
@pytest.mark.parametrize("outcome", ["ok", "http_error", "connection_error"])
def test_cleanup_only_unloads_used_remote_runtime_and_retains_failed_state(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    remote_used: bool, outcome: str,
) -> None:
    import requests

    ai = Mock()
    local = Mock()
    post = Mock(return_value=SimpleNamespace(ok=outcome == "ok", status_code=500, text="failed"))
    if outcome == "connection_error":
        post.side_effect = requests.ConnectionError("unavailable")
    monkeypatch.setenv("FLUX_SERVICE_URL", "http://flux-test:5000")
    monkeypatch.setattr(pipeline, "_REMOTE_RUNTIME_USED", remote_used)
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setitem(sys.modules, "services.image_generation", SimpleNamespace(unload_flux_runtime=local))
    monkeypatch.setattr(main.gc, "collect", Mock())
    # Do not trim the shared test process's heap.
    monkeypatch.setattr("ctypes.CDLL", Mock())
    with caplog.at_level(logging.INFO):
        main._run_post_generation_cleanup(ai, "schedule")
    ai.unload.assert_called_once_with(wait_seconds=10.0)
    local.assert_called_once()
    if remote_used:
        post.assert_called_once_with("http://flux-test:5000/unload", timeout=30)
        assert pipeline._REMOTE_RUNTIME_USED is (outcome != "ok")
        if outcome != "ok":
            assert "failed" in caplog.text or "status=500" in caplog.text
    else:
        post.assert_not_called()
    assert "Stage end stage=cleanup.total" in caplog.text
    assert "Stage end stage=cleanup.ollama" in caplog.text
    assert "Stage end stage=cleanup.heap" in caplog.text


def test_cleanup_does_not_import_unused_local_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins

    original_import = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "services.image_generation":
            raise AssertionError("Cleanup must not import an unused image runtime")
        return original_import(name, *args, **kwargs)

    monkeypatch.delitem(sys.modules, "services.image_generation", raising=False)
    monkeypatch.delenv("FLUX_SERVICE_URL", raising=False)
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(main.gc, "collect", Mock())
    monkeypatch.setattr("ctypes.CDLL", Mock())
    main._run_post_generation_cleanup(Mock(), "schedule")


def test_cleanup_continues_if_ollama_unload_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    ai = Mock()
    ai.unload.side_effect = ConnectionError("unavailable")
    local = Mock()
    monkeypatch.setitem(sys.modules, "services.image_generation", SimpleNamespace(unload_flux_runtime=local))
    monkeypatch.delenv("FLUX_SERVICE_URL", raising=False)
    monkeypatch.setattr(main.gc, "collect", Mock())
    monkeypatch.setattr("ctypes.CDLL", Mock())
    main._run_post_generation_cleanup(ai, "schedule")
    local.assert_called_once()


@pytest.mark.parametrize("mode", ["disabled", "minimal", "dns_failure", "success", "request_failure"])
def test_remote_runtime_tracking_starts_only_when_generation_is_attempted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str,
) -> None:
    import requests
    from services.flux_capacitor import (
        ArtAvatarRequest, FluxCapacitorConfig, GPUPolicy, SourceMode,
    )

    monkeypatch.setenv("FLUX_CAPACITOR_ENABLED", "true" if mode != "disabled" else "false")
    monkeypatch.setenv("FLUX_CAPACITOR_MINIMAL_MODE", "true" if mode == "minimal" else "false")
    monkeypatch.setenv("FLUX_CAPACITOR_OLLAMA_FIRST", "false")
    monkeypatch.setenv("FLUX_SERVICE_URL", "http://flux-test:5000")
    monkeypatch.setattr(pipeline, "_REMOTE_RUNTIME_USED", False)
    monkeypatch.setattr("services.flux_capacitor._storage.get_generated_content_dir", Mock(return_value=tmp_path))
    monkeypatch.setattr(pipeline, "save_to_db", Mock())
    dns = Mock(return_value=[])
    if mode == "dns_failure":
        dns.side_effect = socket.gaierror("No such host")
    monkeypatch.setattr(pipeline.socket, "getaddrinfo", dns)
    post = Mock(return_value=SimpleNamespace(ok=True))
    if mode == "request_failure":
        post.side_effect = requests.ConnectionError("Interrupted")
    monkeypatch.setattr(requests, "post", post)
    request = ArtAvatarRequest(
        request_id="runtime-test", source_mode=SourceMode.SCHEDULE,
        style_profile="corporate_minimal", ollama_priority_context=False,
        post_text="A grounded post.",
    )
    pipeline.run_art_avatar(request, FluxCapacitorConfig(), pipeline.GPUOrchestrator(GPUPolicy(ollama_first=False)))
    assert pipeline._REMOTE_RUNTIME_USED is (mode in {"success", "request_failure"})
    assert post.call_count == (1 if mode in {"success", "request_failure"} else 0)
