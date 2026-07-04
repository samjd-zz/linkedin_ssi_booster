"""
Tests for services/flux_capacitor: models, config, GPU policy, pipeline, and storage.

Author: Shawn Jackson Dyck
"""

import json
import socket
import time
from pathlib import Path
from threading import Thread
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

from services.flux_capacitor._config import (
    DEFAULT_STYLE_PRESET,
    STYLE_PRESETS,
    FluxCapacitorConfig,
)
from services.flux_capacitor._models import (
    ArtAvatarRequest,
    ArtAvatarResult,
    ArtAvatarTelemetry,
    GPUGateOutcome,
    GPUJobSlot,
    GPUPolicy,
    RenderStatus,
    SourceMode,
    StylePreset,
)
from services.flux_capacitor._pipeline import GPUOrchestrator, run_art_avatar
from services.flux_capacitor._prompting import (
    apply_style_overrides,
    build_negative_prompt,
    build_prompt,
    resolve_style_preset,
)
from services.flux_capacitor.__init__ import FluxCapacitorService, get_flux_service


# =========================================================================== #
# Helpers
# =========================================================================== #


def _minimal_request(
    request_id: str = "test-req-001",
    source_mode: SourceMode = SourceMode.SCHEDULE,
    style_profile: str = "corporate_minimal",
    ollama_priority_context: bool = False,
    post_text: Optional[str] = "AI pipelines are changing how we build software.",
    **kwargs: Any,
) -> ArtAvatarRequest:
    return ArtAvatarRequest(
        request_id=request_id,
        source_mode=source_mode,
        style_profile=style_profile,
        ollama_priority_context=ollama_priority_context,
        post_text=post_text,
        **kwargs,
    )


def _default_config(**overrides) -> FluxCapacitorConfig:
    """Return a FluxCapacitorConfig with test-friendly defaults."""
    with patch.dict(
        "os.environ",
        {
            "FLUX_CAPACITOR_ENABLED": "true",
            "FLUX_CAPACITOR_MINIMAL_MODE": "false",
            "FLUX_CAPACITOR_QUEUE_WAIT_TIMEOUT_SECONDS": "5",
            **{k.upper(): str(v) for k, v in overrides.items()},
        },
    ):
        return FluxCapacitorConfig()


# =========================================================================== #
# Config validation
# =========================================================================== #


class TestFluxCapacitorConfig:
    def test_defaults_valid(self):
        # Explicitly clear the feature flag so the test validates the code default,
        # not whatever the local .env happens to contain.
        with patch.dict("os.environ", {"FLUX_CAPACITOR_ENABLED": "false"}):
            cfg = FluxCapacitorConfig()
        assert cfg.enabled is False  # default off
        assert cfg.saturation_cap == 0.55
        assert cfg.render_steps == 4

    def test_invalid_saturation_raises(self):
        with patch.dict("os.environ", {"FLUX_CAPACITOR_SATURATION_CAP": "1.5"}):
            with pytest.raises(ValueError, match="SATURATION_CAP"):
                FluxCapacitorConfig()

    def test_invalid_steps_raises(self):
        with patch.dict("os.environ", {"FLUX_CAPACITOR_RENDER_STEPS": "0"}):
            with pytest.raises(ValueError, match="RENDER_STEPS"):
                FluxCapacitorConfig()

    def test_minimal_mode_env(self):
        with patch.dict(
            "os.environ",
            {"FLUX_CAPACITOR_MINIMAL_MODE": "true", "FLUX_CAPACITOR_ENABLED": "true"},
        ):
            cfg = FluxCapacitorConfig()
        assert cfg.minimal_mode is True

    def test_style_presets_dict_populated(self):
        assert "corporate_minimal" in STYLE_PRESETS
        assert DEFAULT_STYLE_PRESET == "corporate_minimal"


# =========================================================================== #
# ArtAvatarRequest model validation
# =========================================================================== #


class TestArtAvatarRequest:
    def test_missing_text_raises(self):
        with pytest.raises(ValueError, match="post_text.*concept_text"):
            ArtAvatarRequest(
                request_id="x",
                source_mode=SourceMode.SCHEDULE,
                style_profile="corporate_minimal",
                ollama_priority_context=False,
            )

    def test_empty_request_id_raises(self):
        with pytest.raises(ValueError, match="request_id"):
            ArtAvatarRequest(
                request_id="",
                source_mode=SourceMode.SCHEDULE,
                style_profile="corporate_minimal",
                ollama_priority_context=False,
                post_text="hello",
            )

    def test_valid_request_created(self):
        req = _minimal_request()
        assert req.request_id == "test-req-001"
        assert req.source_mode == SourceMode.SCHEDULE

    def test_concept_text_only(self):
        req = ArtAvatarRequest(
            request_id="abc",
            source_mode=SourceMode.CONSOLE,
            style_profile="corporate_minimal",
            ollama_priority_context=False,
            concept_text="abstract concept about ML",
        )
        assert req.concept_text == "abstract concept about ML"
        assert req.post_text is None


# =========================================================================== #
# Style preset and clamping
# =========================================================================== #


class TestStylePresets:
    def test_resolve_known_preset(self):
        cfg = _default_config()
        preset = resolve_style_preset("corporate_minimal", cfg)
        assert preset.name == "corporate_minimal"
        assert preset.saturation_cap <= cfg.saturation_cap

    def test_resolve_unknown_fallback(self):
        cfg = _default_config()
        preset = resolve_style_preset("nonexistent_preset", cfg)
        assert preset.name == DEFAULT_STYLE_PRESET

    def test_style_clamps_enforced(self):
        with patch.dict(
            "os.environ",
            {
                "FLUX_CAPACITOR_SATURATION_CAP": "0.20",
                "FLUX_CAPACITOR_SURREAL_INTENSITY_CAP": "0.10",
            },
        ):
            cfg = FluxCapacitorConfig()
        preset = resolve_style_preset("sacred_geometry_light", cfg)
        # preset raw saturation_cap=0.55 should be clamped to 0.20
        assert preset.saturation_cap <= 0.20
        assert preset.surreal_intensity_cap <= 0.10

    def test_style_overrides_respected_within_clamps(self):
        cfg = _default_config()
        base_preset = resolve_style_preset("corporate_minimal", cfg)
        overridden = apply_style_overrides(
            base_preset,
            {"palette": "custom red palette", "saturation_cap": "0.99"},
            cfg,
        )
        assert overridden.palette == "custom red palette"
        # 0.99 should be clamped to config saturation_cap (0.55)
        assert overridden.saturation_cap <= cfg.saturation_cap


# =========================================================================== #
# Prompt assembly
# =========================================================================== #


class TestBuildPrompt:
    def test_prompt_includes_post_text(self):
        cfg = _default_config()
        req = _minimal_request(post_text="Testing AI grounding pipelines.")
        prompt = build_prompt(req, cfg)
        assert "Testing AI grounding pipelines" in prompt
        assert "Palette:" in prompt
        assert "Geometry density:" in prompt

    def test_prompt_includes_theme_cue(self):
        cfg = _default_config()
        req = _minimal_request(theme="machine learning infrastructure")
        prompt = build_prompt(req, cfg)
        assert "machine learning infrastructure" in prompt

    def test_long_post_truncated(self):
        cfg = _default_config()
        long_text = "A" * 500
        req = _minimal_request(post_text=long_text)
        prompt = build_prompt(req, cfg)
        # Prompt should not embed all 500 chars raw
        assert len(prompt) < 1200

    def test_no_content_raises(self):
        cfg = _default_config()
        # Build a request with empty strings — bypass __post_init__ by monkeypatching
        req = _minimal_request(post_text=" ")
        req.concept_text = None
        req.post_text = ""
        with pytest.raises(ValueError):
            build_prompt(req, cfg)

    def test_negative_prompt_not_empty(self):
        neg = build_negative_prompt()
        assert len(neg) > 10
        assert "nsfw" in neg


# =========================================================================== #
# GPU Orchestrator
# =========================================================================== #


class TestGPUOrchestrator:
    def _make_orchestrator(self, timeout: int = 5) -> GPUOrchestrator:
        policy = GPUPolicy(
            ollama_first=True,
            flux_after_ollama=True,
            max_concurrent_gpu_jobs=1,
            queue_wait_timeout_seconds=timeout,
        )
        return GPUOrchestrator(policy)

    def test_allowed_when_idle(self):
        orch = self._make_orchestrator()
        outcome, wait = orch.request_flux_slot("req-1", max_wait_seconds=5)
        assert outcome == GPUGateOutcome.ALLOWED
        assert wait == 0.0
        orch.release_flux_slot("req-1")

    def test_text_only_when_ollama_running_and_timeout_short(self):
        orch = self._make_orchestrator(timeout=2)
        orch.mark_ollama_start("ollama-job-1")
        outcome, wait = orch.request_flux_slot("flux-req", max_wait_seconds=2)
        assert outcome == GPUGateOutcome.TEXT_ONLY
        assert wait >= 1.9
        orch.mark_ollama_done("ollama-job-1")

    def test_allowed_after_ollama_completes(self):
        orch = self._make_orchestrator(timeout=10)
        orch.mark_ollama_start("ollama-2")

        def finish_ollama():
            time.sleep(0.5)
            orch.mark_ollama_done("ollama-2")

        t = Thread(target=finish_ollama)
        t.start()
        outcome, wait = orch.request_flux_slot("flux-2", max_wait_seconds=5)
        t.join()
        assert outcome == GPUGateOutcome.ALLOWED
        assert wait < 3.0
        orch.release_flux_slot("flux-2")

    def test_ollama_active_flag(self):
        orch = self._make_orchestrator()
        assert orch.ollama_active is False
        orch.mark_ollama_start("j1")
        assert orch.ollama_active is True
        orch.mark_ollama_done("j1")
        assert orch.ollama_active is False

    def test_context_manager_releases_slot(self):
        orch = self._make_orchestrator()
        with orch.flux_slot("req-ctx", max_wait_seconds=5) as (outcome, wait):
            assert outcome == GPUGateOutcome.ALLOWED
            assert orch._active_job is not None
        # after context exit slot should be released
        assert orch._active_job is None


# =========================================================================== #
# Pipeline: feature-disabled and minimal-mode
# =========================================================================== #


class TestPipelineDisabledPaths:
    def _make_orch(self) -> GPUOrchestrator:
        policy = GPUPolicy()
        return GPUOrchestrator(policy)

    def test_feature_disabled_returns_text_only(self):
        with patch.dict("os.environ", {"FLUX_CAPACITOR_ENABLED": "false"}):
            cfg = FluxCapacitorConfig()
        orch = self._make_orch()
        req = _minimal_request()
        result = run_art_avatar(req, cfg, orch)
        assert result.status == RenderStatus.TEXT_ONLY
        assert result.defer_reason == "feature_disabled"

    def test_minimal_mode_returns_text_only(self):
        with patch.dict(
            "os.environ",
            {
                "FLUX_CAPACITOR_ENABLED": "true",
                "FLUX_CAPACITOR_MINIMAL_MODE": "true",
            },
        ):
            cfg = FluxCapacitorConfig()
        orch = self._make_orch()
        req = _minimal_request()
        result = run_art_avatar(req, cfg, orch)
        assert result.status == RenderStatus.TEXT_ONLY
        assert result.defer_reason == "minimal_mode"

    def test_gpu_timeout_returns_text_only(self):
        with patch.dict(
            "os.environ",
            {
                "FLUX_CAPACITOR_ENABLED": "true",
                "FLUX_CAPACITOR_MINIMAL_MODE": "false",
            },
        ):
            cfg = FluxCapacitorConfig()
        policy = GPUPolicy(ollama_first=True, queue_wait_timeout_seconds=1)
        orch = GPUOrchestrator(policy)
        orch.mark_ollama_start("blocker")
        req = _minimal_request(max_wait_seconds=1)
        result = run_art_avatar(req, cfg, orch)
        assert result.status == RenderStatus.TEXT_ONLY
        orch.mark_ollama_done("blocker")

    def test_flux_import_error_returns_failed(self, tmp_path):
        with patch.dict(
            "os.environ",
            {
                "FLUX_CAPACITOR_ENABLED": "true",
                "FLUX_CAPACITOR_MINIMAL_MODE": "false",
                "FLUX_CAPACITOR_QUEUE_WAIT_TIMEOUT_SECONDS": "5",
            },
        ):
            cfg = FluxCapacitorConfig()
        policy = GPUPolicy(ollama_first=False)
        orch = GPUOrchestrator(policy)
        req = _minimal_request(max_wait_seconds=5)

        # Patch the module-level symbol to None (ImportError branch) and
        # redirect storage to tmp_path so no real filesystem writes occur.
        with patch("services.flux_capacitor._pipeline._generate_flux_image", new=None), \
             patch(
                 "services.flux_capacitor._storage.get_generated_content_dir",
                 return_value=tmp_path,
             ):
            result = run_art_avatar(req, cfg, orch)
        # FLUX unavailable → FAILED with a render_error message
        assert result.status == RenderStatus.FAILED
        assert result.render_error is not None

    def test_unresolvable_flux_service_returns_text_only(self, tmp_path):
        with patch.dict(
            "os.environ",
            {
                "FLUX_CAPACITOR_ENABLED": "true",
                "FLUX_CAPACITOR_MINIMAL_MODE": "false",
            },
        ):
            cfg = FluxCapacitorConfig()

        policy = GPUPolicy(ollama_first=False)
        orch = GPUOrchestrator(policy)
        req = _minimal_request(max_wait_seconds=5)

        with patch.dict(
            "os.environ",
            {"FLUX_SERVICE_URL": "http://flux-app:5000"},
        ), patch(
            "services.flux_capacitor._storage.get_generated_content_dir",
            return_value=tmp_path,
        ), patch(
            "services.flux_capacitor._pipeline._generate_flux_image",
            new=None,
        ), patch(
            "services.flux_capacitor._pipeline.socket.getaddrinfo",
            side_effect=socket.gaierror("dns failure"),
        ), patch("requests.post") as mock_post:
            result = run_art_avatar(req, cfg, orch)

        assert result.status == RenderStatus.TEXT_ONLY
        assert result.defer_reason == "flux_service_unreachable"
        assert result.story_path is not None
        mock_post.assert_not_called()


# =========================================================================== #
# Storage: story artifact
# =========================================================================== #


class TestStorageStoryArtifact:
    def test_save_story_returns_saved(self, tmp_path):
        cfg = FluxCapacitorConfig()

        with patch(
            "services.flux_capacitor._storage.get_generated_content_dir",
            return_value=tmp_path,  # tmp_path exists; avoids mkdir race in mock
        ):
            from services.flux_capacitor._storage import save_story_artifact

            story_path, meta_path, status = save_story_artifact(
                story_text="This is my generated post.",
                request_id="req-store-001",
                source_mode="schedule",
                channel="linkedin",
                source_url="https://example.com",
                source_title="Example Article",
                image_path=None,
                config=cfg,
            )

        assert status == "saved"
        assert story_path is not None
        assert meta_path is not None
        assert Path(story_path).exists()  # type: ignore[arg-type]

    def test_save_story_metadata_linkage(self, tmp_path):
        cfg = FluxCapacitorConfig()

        with patch(
            "services.flux_capacitor._storage.get_generated_content_dir",
            return_value=tmp_path,
        ):
            from services.flux_capacitor._storage import save_story_artifact

            _, meta_path, status = save_story_artifact(
                story_text="Grounded post content.",
                request_id="req-meta-001",
                source_mode="curate",
                channel="buffer",
                source_url="https://example.com/article",
                source_title="My Article",
                image_path="/some/image.png",
                config=cfg,
            )

        assert status == "saved"
        assert meta_path is not None
        meta = json.loads(Path(meta_path).read_text())  # type: ignore[arg-type]
        assert meta["request_id"] == "req-meta-001"
        assert meta["image_path"] == "/some/image.png"
        assert meta["source_url"] == "https://example.com/article"

    def test_empty_story_returns_skipped(self, tmp_path):
        cfg = FluxCapacitorConfig()
        with patch(
            "services.flux_capacitor._storage.get_generated_content_dir",
            return_value=tmp_path,
        ):
            from services.flux_capacitor._storage import save_story_artifact

            _, _, status = save_story_artifact(
                story_text="",
                request_id="req-empty",
                source_mode="console",
                channel=None,
                source_url=None,
                source_title=None,
                image_path=None,
                config=cfg,
            )
        assert status == "skipped"


# =========================================================================== #
# FluxCapacitorService
# =========================================================================== #


class TestFluxCapacitorService:
    def test_make_request_returns_request(self):
        with patch.dict(
            "os.environ",
            {
                "FLUX_CAPACITOR_ENABLED": "false",
                "FLUX_CAPACITOR_QUEUE_WAIT_TIMEOUT_SECONDS": "5",
            },
        ):
            svc = FluxCapacitorService()
        req = svc.make_request(post_text="hello", source_mode=SourceMode.CURATE)
        assert isinstance(req, ArtAvatarRequest)
        assert req.source_mode == SourceMode.CURATE

    def test_render_when_disabled_text_only(self):
        with patch.dict("os.environ", {"FLUX_CAPACITOR_ENABLED": "false"}):
            svc = FluxCapacitorService()
        req = svc.make_request(post_text="test post")
        result = svc.render(req)
        assert result.status == RenderStatus.TEXT_ONLY

    def test_notify_ollama_lifecycle(self):
        with patch.dict("os.environ", {"FLUX_CAPACITOR_ENABLED": "false"}):
            svc = FluxCapacitorService()
        jid = svc.notify_ollama_start()
        assert svc.orchestrator.ollama_active is True
        svc.notify_ollama_done(jid)
        assert svc.orchestrator.ollama_active is False

    def test_singleton_returns_same_instance(self):
        import services.flux_capacitor as fc_pkg

        # Reset singleton for test isolation
        fc_pkg._service_instance = None
        svc1 = get_flux_service()
        svc2 = get_flux_service()
        assert svc1 is svc2
        fc_pkg._service_instance = None  # cleanup


# ============================================================================
# DB dual-write tests
# ============================================================================


class TestSaveToDb:
    """Unit tests for services.flux_capacitor._storage.save_to_db.

    All tests run with DATABASE_ENABLED=false (default) except where
    explicitly overridden — this matches the expected deployment default.
    """

    def _call(self, **overrides: Any) -> bool:
        from services.flux_capacitor._storage import save_to_db
        from datetime import datetime

        request_id: str = overrides.get("request_id", "req-abc123")
        run_id: str = overrides.get("run_id", "run-xyz")
        source_mode: str = overrides.get("source_mode", "curate")
        render_status: str = overrides.get("render_status", "rendered")
        generated_at: datetime = overrides.get(
            "generated_at", datetime(2026, 6, 25, 12, 0, 0)
        )
        return save_to_db(
            request_id=request_id,
            run_id=run_id,
            source_mode=source_mode,
            render_status=render_status,
            generated_at=generated_at,
            **{
                k: v
                for k, v in overrides.items()
                if k not in {"request_id", "run_id", "source_mode", "render_status", "generated_at"}
            },
        )

    def test_returns_false_when_db_disabled(self) -> None:
        """save_to_db is a no-op when DATABASE_ENABLED is not true."""
        with patch.dict("os.environ", {"DATABASE_ENABLED": "false"}):
            result = self._call()
        assert result is False

    def test_returns_false_when_db_env_absent(self) -> None:
        """save_to_db is a no-op when DATABASE_ENABLED is absent."""
        env = {k: v for k, v in __import__("os").environ.items() if k != "DATABASE_ENABLED"}
        with patch.dict("os.environ", env, clear=True):
            result = self._call()
        assert result is False

    def test_returns_true_when_db_enabled_and_upsert_succeeds(self) -> None:
        """When DATABASE_ENABLED=true and the session upserts cleanly, returns True."""
        mock_record = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        with patch.dict("os.environ", {"DATABASE_ENABLED": "true"}), \
             patch("services.database.repositories.GeneratedContentRecordRepository") as MockRepo, \
             patch("services.database.session.get_session", return_value=mock_session):
            MockRepo.upsert.return_value = mock_record
            result = self._call()

        assert result is True

    def test_returns_false_on_db_import_error(self) -> None:
        """When the DB session module is unavailable, returns False (never raises)."""
        with patch.dict("os.environ", {"DATABASE_ENABLED": "true"}), \
             patch("services.database.session.get_session", side_effect=ImportError("no db")):
            result = self._call()
        assert result is False

    def test_returns_false_on_db_runtime_error(self) -> None:
        """When the DB write raises unexpectedly, returns False (never raises)."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        with patch.dict("os.environ", {"DATABASE_ENABLED": "true"}), \
             patch("services.database.session.get_session", return_value=mock_session), \
             patch("services.database.repositories.GeneratedContentRecordRepository") as MockRepo:
            MockRepo.upsert.side_effect = RuntimeError("db is down")
            result = self._call()
        assert result is False

    def test_optional_fields_propagate(self) -> None:
        """Optional linkage fields are forwarded to the repository."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        with patch.dict("os.environ", {"DATABASE_ENABLED": "true"}), \
             patch("services.database.session.get_session", return_value=mock_session), \
             patch("services.database.repositories.GeneratedContentRecordRepository") as MockRepo:
            MockRepo.upsert.return_value = MagicMock()
            self._call(
                candidate_id="cand-001",
                channel="linkedin",
                ssi_component="establish_brand",
                story_path="/data/story.txt",
                image_path="/data/img.png",
            )

        _, kwargs = MockRepo.upsert.call_args
        assert kwargs["candidate_id"] == "cand-001"
        assert kwargs["channel"] == "linkedin"
        assert kwargs["ssi_component"] == "establish_brand"
        assert kwargs["story_path"] == "/data/story.txt"
        assert kwargs["image_path"] == "/data/img.png"
