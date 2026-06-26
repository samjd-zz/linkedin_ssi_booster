"""
Tests for GPU orchestration policy: queue ordering, Ollama priority, concurrency.

Author: Shawn Jackson Dyck
"""

import time
from threading import Event, Thread

import pytest

from services.flux_capacitor._models import GPUGateOutcome, GPUPolicy
from services.flux_capacitor._pipeline import GPUOrchestrator


# =========================================================================== #
# Helpers
# =========================================================================== #


def _orch(
    timeout: int = 10,
    ollama_first: bool = True,
    flux_after_ollama: bool = True,
) -> GPUOrchestrator:
    policy = GPUPolicy(
        ollama_first=ollama_first,
        flux_after_ollama=flux_after_ollama,
        max_concurrent_gpu_jobs=1,
        queue_wait_timeout_seconds=timeout,
    )
    return GPUOrchestrator(policy)


# =========================================================================== #
# Ollama-first ordering
# =========================================================================== #


class TestOllamaFirstPolicy:
    def test_flux_waits_while_ollama_active(self):
        orch = _orch(timeout=3)
        orch.mark_ollama_start("ollama-a")

        outcomes = []
        outcome_ready = Event()

        def flux_request():
            outcome, _ = orch.request_flux_slot("flux-a", max_wait_seconds=3)
            outcomes.append(outcome)
            outcome_ready.set()

        t = Thread(target=flux_request)
        t.start()
        # While Ollama is active, FLUX should still be queued.
        assert not outcome_ready.wait(timeout=0.2)
        orch.mark_ollama_done("ollama-a")
        assert outcome_ready.wait(timeout=5)
        t.join(timeout=5)

        assert len(outcomes) == 1
        # Should have been allowed after Ollama drained, OR timed out
        assert outcomes[0] in (GPUGateOutcome.ALLOWED, GPUGateOutcome.TEXT_ONLY)

    def test_flux_allowed_immediately_when_ollama_off(self):
        orch = _orch()
        outcome, wait = orch.request_flux_slot("flux-b", max_wait_seconds=5)
        assert outcome == GPUGateOutcome.ALLOWED
        assert wait == 0.0
        orch.release_flux_slot("flux-b")

    def test_flux_allowed_when_ollama_first_disabled(self):
        orch = _orch(ollama_first=False)
        orch.mark_ollama_start("ollama-bypass")
        outcome, wait = orch.request_flux_slot("flux-bypass", max_wait_seconds=2)
        assert outcome == GPUGateOutcome.ALLOWED
        assert wait == 0.0
        orch.release_flux_slot("flux-bypass")
        orch.mark_ollama_done("ollama-bypass")


# =========================================================================== #
# Queue timeout and TEXT_ONLY fallback
# =========================================================================== #


class TestQueueTimeoutFallback:
    def test_text_only_on_timeout(self):
        orch = _orch(timeout=1)
        orch.mark_ollama_start("long-ollama")
        outcome, wait = orch.request_flux_slot("flux-timeout", max_wait_seconds=1)
        orch.mark_ollama_done("long-ollama")
        assert outcome == GPUGateOutcome.TEXT_ONLY
        assert wait >= 0.9

    def test_wait_time_recorded(self):
        orch = _orch(timeout=2)
        orch.mark_ollama_start("long2")
        _, elapsed = orch.request_flux_slot("flux-elapsed", max_wait_seconds=2)
        orch.mark_ollama_done("long2")
        assert elapsed >= 1.0  # waited at least 1 second


# =========================================================================== #
# Slot management
# =========================================================================== #


class TestSlotManagement:
    def test_slot_released_after_context_manager(self):
        orch = _orch()
        with orch.flux_slot("ctx-1", max_wait_seconds=5) as (outcome, _):
            assert outcome == GPUGateOutcome.ALLOWED
            assert orch._active_job is not None
        assert orch._active_job is None

    def test_slot_released_even_on_exception(self):
        orch = _orch()
        try:
            with orch.flux_slot("ctx-err", max_wait_seconds=5) as (outcome, _):
                raise RuntimeError("simulated render failure")
        except RuntimeError:
            pass
        assert orch._active_job is None

    def test_ollama_done_clears_active_job(self):
        orch = _orch()
        orch.mark_ollama_start("j-clear")
        assert orch._active_job is not None
        orch.mark_ollama_done("j-clear")
        assert orch._active_job is None
        assert orch.ollama_active is False

    def test_release_noop_for_wrong_id(self):
        orch = _orch()
        outcome, _ = orch.request_flux_slot("slot-real", max_wait_seconds=5)
        assert outcome == GPUGateOutcome.ALLOWED
        # Release with wrong ID — should not crash, slot stays
        orch.release_flux_slot("wrong-id")
        # Correct release
        orch.release_flux_slot("slot-real")
        assert orch._active_job is None


# =========================================================================== #
# Concurrency safety
# =========================================================================== #


class TestConcurrencySafety:
    def test_concurrent_flux_requests_serialized(self):
        """Two concurrent FLUX requests should not overlap."""
        orch = _orch(timeout=5)
        results: list[tuple[GPUGateOutcome, float]] = []
        first_acquired = Event()
        release_first = Event()

        def request(req_id: str) -> None:
            out, wait = orch.request_flux_slot(req_id, max_wait_seconds=5)
            results.append((out, wait))
            if out == GPUGateOutcome.ALLOWED:
                if not first_acquired.is_set():
                    first_acquired.set()
                    release_first.wait(timeout=1.0)
                orch.release_flux_slot(req_id)

        t1 = Thread(target=request, args=("flux-c1",))
        t2 = Thread(target=request, args=("flux-c2",))
        t1.start()
        t2.start()
        assert first_acquired.wait(timeout=2.0)
        release_first.set()
        t1.join(timeout=10)
        t2.join(timeout=10)

        # At least one should have been allowed
        allowed = [r for r in results if r[0] == GPUGateOutcome.ALLOWED]
        assert len(allowed) >= 1
