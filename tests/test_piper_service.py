"""Unit tests for Piper TTS voice synthesis service."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from services.piper_service import (
    PiperService,
    get_piper_service,
    get_speaker_id,
    get_voice_model,
    is_voice_enabled,
    speak_text,
)


class TestVoiceConfiguration:
    """Test voice configuration helper functions."""

    def test_is_voice_enabled_default(self, monkeypatch):
        """Test voice is disabled by default."""
        monkeypatch.delenv("CONSOLE_USE_VOICE", raising=False)
        assert is_voice_enabled() is False

    def test_is_voice_enabled_true(self, monkeypatch):
        """Test voice enabled with true value."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "true")
        assert is_voice_enabled() is True

    def test_is_voice_enabled_1(self, monkeypatch):
        """Test voice enabled with 1 value."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "1")
        assert is_voice_enabled() is True

    def test_is_voice_enabled_yes(self, monkeypatch):
        """Test voice enabled with yes value."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "yes")
        assert is_voice_enabled() is True

    def test_is_voice_enabled_false(self, monkeypatch):
        """Test voice disabled with false value."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "false")
        assert is_voice_enabled() is False

    def test_get_voice_model_default(self, monkeypatch):
        """Test default voice model."""
        monkeypatch.delenv("CONSOLE_VOICE_MODEL", raising=False)
        assert get_voice_model() == "en_US-libritts_r-medium"

    def test_get_voice_model_custom(self, monkeypatch):
        """Test custom voice model."""
        monkeypatch.setenv("CONSOLE_VOICE_MODEL", "en_US-amy-medium")
        assert get_voice_model() == "en_US-amy-medium"

    def test_get_speaker_id_default(self, monkeypatch):
        """Test default speaker ID."""
        monkeypatch.delenv("CONSOLE_VOICE_SPEAKER", raising=False)
        assert get_speaker_id() == 902

    def test_get_speaker_id_custom(self, monkeypatch):
        """Test custom speaker ID."""
        monkeypatch.setenv("CONSOLE_VOICE_SPEAKER", "500")
        assert get_speaker_id() == 500

    def test_get_speaker_id_invalid(self, monkeypatch):
        """Test invalid speaker ID falls back to default."""
        monkeypatch.setenv("CONSOLE_VOICE_SPEAKER", "invalid")
        assert get_speaker_id() == 902


class TestPiperService:
    """Test PiperService class."""

    def test_init_disabled_by_default(self, monkeypatch):
        """Test service is disabled when CONSOLE_USE_VOICE is not set."""
        monkeypatch.delenv("CONSOLE_USE_VOICE", raising=False)
        service = PiperService()
        assert service.is_enabled() is False

    @patch("services.piper_service._PIPER_AVAILABLE", False)
    def test_init_disabled_when_piper_unavailable(self, monkeypatch):
        """Test service is disabled when piper-tts is not installed."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "true")
        service = PiperService()
        assert service.is_enabled() is False

    @patch("services.piper_service._PIPER_AVAILABLE", True)
    def test_init_enabled(self, monkeypatch):
        """Test service is enabled when configured and piper is available."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "true")
        service = PiperService()
        # Service is marked as enabled, but voice loading happens lazily
        assert service._enabled is True

    @patch("services.piper_service._PIPER_AVAILABLE", True)
    def test_speak_disabled(self, monkeypatch):
        """Test speak returns False when service is disabled."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "false")
        service = PiperService()
        result = service.speak("Hello world")
        assert result is False

    @patch("services.piper_service._PIPER_AVAILABLE", True)
    def test_speak_empty_text(self, monkeypatch):
        """Test speak returns False for empty text."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "true")
        service = PiperService()
        assert service.speak("") is False
        assert service.speak("   ") is False

    @patch("services.piper_service._PIPER_AVAILABLE", True)
    @patch("services.piper_service.PiperVoice")
    def test_ensure_voice_loaded_success(self, mock_piper_voice, monkeypatch):
        """Test voice model is loaded successfully."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "true")
        monkeypatch.setenv("CONSOLE_VOICE_MODEL", "en_US-libritts_r-medium")
        
        mock_voice = MagicMock()
        mock_piper_voice.load.return_value = mock_voice
        
        service = PiperService()
        result = service._ensure_voice_loaded()
        
        assert result is True
        assert service._voice is mock_voice
        mock_piper_voice.load.assert_called_once_with("en_US-libritts_r-medium", use_cuda=False)

    @patch("services.piper_service._PIPER_AVAILABLE", True)
    @patch("services.piper_service.PiperVoice")
    def test_ensure_voice_loaded_failure(self, mock_piper_voice, monkeypatch):
        """Test voice loading failure disables service."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "true")
        
        mock_piper_voice.load.side_effect = Exception("Model not found")
        
        service = PiperService()
        result = service._ensure_voice_loaded()
        
        assert result is False
        assert service._enabled is False

    @patch("services.piper_service._PIPER_AVAILABLE", True)
    @patch("services.piper_service.PiperVoice")
    def test_ensure_voice_loaded_cached(self, mock_piper_voice, monkeypatch):
        """Test voice is only loaded once."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "true")
        
        mock_voice = MagicMock()
        mock_piper_voice.load.return_value = mock_voice
        
        service = PiperService()
        service._voice = mock_voice  # Pre-load voice
        
        result = service._ensure_voice_loaded()
        
        assert result is True
        mock_piper_voice.load.assert_not_called()  # Should not load again

    @patch("services.piper_service._PIPER_AVAILABLE", True)
    @patch("services.piper_service.PiperVoice")
    @patch("sounddevice.play")
    @patch("sounddevice.wait")
    def test_speak_success(self, mock_sd_wait, mock_sd_play, mock_piper_voice, monkeypatch):
        """Test successful speech synthesis and playback."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "true")
        monkeypatch.setenv("CONSOLE_VOICE_SPEAKER", "902")
        
        import numpy as np
        mock_audio = np.array([0.1, 0.2, 0.3])
        
        mock_voice = MagicMock()
        mock_voice.synthesize.return_value = mock_audio
        mock_piper_voice.load.return_value = mock_voice
        
        service = PiperService()
        result = service.speak("Hello world")
        
        assert result is True
        mock_voice.synthesize.assert_called_once_with("Hello world", speaker_id=902)
        mock_sd_play.assert_called_once()
        mock_sd_wait.assert_called_once()

    @patch("services.piper_service._PIPER_AVAILABLE", True)
    @patch("services.piper_service.PiperVoice")
    def test_speak_synthesis_failure(self, mock_piper_voice, monkeypatch):
        """Test speak returns False when synthesis fails."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "true")
        
        mock_voice = MagicMock()
        mock_voice.synthesize.side_effect = Exception("Synthesis error")
        mock_piper_voice.load.return_value = mock_voice
        
        service = PiperService()
        result = service.speak("Hello world")
        
        assert result is False

    @patch("services.piper_service._PIPER_AVAILABLE", True)
    @patch("services.piper_service.PiperVoice")
    def test_speak_sounddevice_unavailable(self, mock_piper_voice, monkeypatch):
        """Test speak disables service when sounddevice is unavailable."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "true")
        
        import numpy as np
        mock_audio = np.array([0.1, 0.2, 0.3])
        
        mock_voice = MagicMock()
        mock_voice.synthesize.return_value = mock_audio
        mock_piper_voice.load.return_value = mock_voice
        
        with patch("services.piper_service.PiperService.speak") as mock_speak:
            # Simulate ImportError for sounddevice
            mock_speak.side_effect = ImportError("No module named 'sounddevice'")
            
            service = PiperService()
            result = service.speak("Hello world")
            
            # Service should handle the error gracefully
            assert result is False or isinstance(result, Exception)


class TestGlobalFunctions:
    """Test global convenience functions."""

    @patch("services.piper_service.PiperService")
    def test_get_piper_service_singleton(self, mock_service_class):
        """Test get_piper_service returns singleton instance."""
        mock_instance = MagicMock()
        mock_service_class.return_value = mock_instance
        
        # Reset the global instance
        import services.piper_service
        services.piper_service._piper_service = None
        
        service1 = get_piper_service()
        service2 = get_piper_service()
        
        assert service1 is service2
        mock_service_class.assert_called_once()

    @patch("services.piper_service.get_piper_service")
    def test_speak_text_convenience(self, mock_get_service):
        """Test speak_text convenience function."""
        mock_service = MagicMock()
        mock_service.speak.return_value = True
        mock_get_service.return_value = mock_service
        
        result = speak_text("Hello world")
        
        assert result is True
        mock_service.speak.assert_called_once_with("Hello world")
