"""Unit tests for Wyoming Piper TTS voice synthesis service."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from services.piper_service import (
    PiperService,
    get_piper_service,
    get_speaker_id,
    get_voice_name,
    get_wyoming_host,
    get_wyoming_port,
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

    def test_get_wyoming_host_default(self, monkeypatch):
        """Test default Wyoming host."""
        monkeypatch.delenv("WYOMING_PIPER_HOST", raising=False)
        assert get_wyoming_host() == "localhost"

    def test_get_wyoming_host_custom(self, monkeypatch):
        """Test custom Wyoming host."""
        monkeypatch.setenv("WYOMING_PIPER_HOST", "piper")
        assert get_wyoming_host() == "piper"

    def test_get_wyoming_port_default(self, monkeypatch):
        """Test default Wyoming port."""
        monkeypatch.delenv("WYOMING_PIPER_PORT", raising=False)
        assert get_wyoming_port() == 10200

    def test_get_wyoming_port_custom(self, monkeypatch):
        """Test custom Wyoming port."""
        monkeypatch.setenv("WYOMING_PIPER_PORT", "10300")
        assert get_wyoming_port() == 10300

    def test_get_wyoming_port_invalid(self, monkeypatch):
        """Test invalid port falls back to default."""
        monkeypatch.setenv("WYOMING_PIPER_PORT", "invalid")
        assert get_wyoming_port() == 10200

    def test_get_voice_name_default(self, monkeypatch):
        """Test default voice name."""
        monkeypatch.delenv("CONSOLE_VOICE_MODEL", raising=False)
        assert get_voice_name() == "en_US-libritts_r-medium"

    def test_get_voice_name_custom(self, monkeypatch):
        """Test custom voice name."""
        monkeypatch.setenv("CONSOLE_VOICE_MODEL", "en_US-amy-medium")
        assert get_voice_name() == "en_US-amy-medium"

    def test_get_speaker_id_default(self, monkeypatch):
        """Test default speaker ID (empty string)."""
        monkeypatch.delenv("CONSOLE_VOICE_SPEAKER", raising=False)
        assert get_speaker_id() is None

    def test_get_speaker_id_custom(self, monkeypatch):
        """Test custom speaker ID."""
        monkeypatch.setenv("CONSOLE_VOICE_SPEAKER", "902")
        assert get_speaker_id() == "902"

    def test_get_speaker_id_empty(self, monkeypatch):
        """Test empty speaker ID returns None."""
        monkeypatch.setenv("CONSOLE_VOICE_SPEAKER", "")
        assert get_speaker_id() is None


class TestPiperService:
    """Test PiperService class."""

    def test_init_disabled_by_default(self, monkeypatch):
        """Test service is disabled when CONSOLE_USE_VOICE is not set."""
        monkeypatch.delenv("CONSOLE_USE_VOICE", raising=False)
        service = PiperService()
        assert service.is_enabled() is False

    def test_init_enabled(self, monkeypatch):
        """Test service is enabled when configured."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "true")
        service = PiperService()
        assert service._enabled is True

    def test_speak_disabled(self, monkeypatch):
        """Test speak returns False when service is disabled."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "false")
        service = PiperService()
        result = service.speak("Hello world")
        assert result is False

    def test_speak_empty_text(self, monkeypatch):
        """Test speak returns False for empty text."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "true")
        service = PiperService()
        assert service.speak("") is False
        assert service.speak("   ") is False

    @patch("socket.socket")
    @patch("sounddevice.play")
    @patch("sounddevice.wait")
    def test_speak_success(self, mock_sd_wait, mock_sd_play, mock_socket, monkeypatch):
        """Test successful speech synthesis via Wyoming protocol."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "true")
        monkeypatch.setenv("CONSOLE_VOICE_SPEAKER", "902")
        
        # Mock socket connection
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock
        
        # Simulate Wyoming protocol responses
        audio_start = json.dumps({
            "type": "audio-start",
            "data": {"rate": 22050, "width": 2, "channels": 1}
        }) + "\n"
        
        audio_chunk = json.dumps({
            "type": "audio-chunk",
            "payload_length": 4
        }) + "\n"
        audio_payload = b"\x00\x01\x00\x02"  # 2 int16 samples
        
        audio_stop = json.dumps({"type": "audio-stop"}) + "\n"
        
        # Mock recv to return protocol messages
        mock_sock.recv.side_effect = [
            audio_start.encode("utf-8"),
            audio_chunk.encode("utf-8") + audio_payload,
            audio_stop.encode("utf-8"),
        ]
        
        service = PiperService()
        result = service.speak("Hello world")
        
        assert result is True
        mock_sock.connect.assert_called_once_with(("localhost", 10200))
        mock_sd_play.assert_called_once()
        mock_sd_wait.assert_called_once()
        mock_sock.close.assert_called_once()

    @patch("socket.socket")
    def test_speak_connection_refused(self, mock_socket, monkeypatch):
        """Test speak handles connection refused gracefully."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "true")
        
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = ConnectionRefusedError()
        mock_socket.return_value = mock_sock
        
        service = PiperService()
        result = service.speak("Hello world")
        
        assert result is False

    @patch("socket.socket")
    def test_speak_timeout(self, mock_socket, monkeypatch):
        """Test speak handles timeout gracefully."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "true")
        
        import socket as socket_module
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = socket_module.timeout()
        mock_socket.return_value = mock_sock
        
        service = PiperService()
        result = service.speak("Hello world")
        
        assert result is False

    @patch("services.piper_service.PiperService")
    def test_sounddevice_import_error(self, mock_service_class, monkeypatch):
        """Test speak handles missing sounddevice gracefully."""
        monkeypatch.setenv("CONSOLE_USE_VOICE", "true")
        
        mock_instance = MagicMock()
        mock_instance.speak.return_value = False
        mock_instance._enabled = False
        mock_service_class.return_value = mock_instance
        
        service = PiperService()
        # Simulate sounddevice import failure inside speak()
        with patch("builtins.__import__", side_effect=ImportError("No module named 'sounddevice'")):
            result = service.speak("Hello world")
        
        # Should return False when sounddevice is unavailable
        assert result is False


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
