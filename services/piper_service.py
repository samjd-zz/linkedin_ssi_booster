"""Piper TTS voice synthesis service for console output."""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Global flag to track if piper is available
_PIPER_AVAILABLE = False
_piper_tts = None

try:
    from piper.voice import PiperVoice
    _PIPER_AVAILABLE = True
except ImportError:
    logger.debug("piper-tts not available — voice output disabled")


def is_voice_enabled() -> bool:
    """Check if voice output is enabled via environment variable."""
    return os.getenv("CONSOLE_USE_VOICE", "false").lower() in ("true", "1", "yes")


def get_voice_model() -> str:
    """Get the voice model from environment variable or use default."""
    return os.getenv("CONSOLE_VOICE_MODEL", "en_US-libritts_r-medium")


def get_speaker_id() -> int:
    """Get the speaker ID from environment variable or use default (902)."""
    try:
        return int(os.getenv("CONSOLE_VOICE_SPEAKER", "902"))
    except ValueError:
        logger.warning("Invalid CONSOLE_VOICE_SPEAKER value, using default 902")
        return 902


class PiperService:
    """Service for text-to-speech using Piper."""

    def __init__(self) -> None:
        """Initialize the Piper service."""
        self._voice: Optional[PiperVoice] = None
        self._enabled = is_voice_enabled()
        self._model_name = get_voice_model()
        self._speaker_id = get_speaker_id()

        if self._enabled and not _PIPER_AVAILABLE:
            logger.warning(
                "CONSOLE_USE_VOICE is enabled but piper-tts is not installed. "
                "Install with: pip install piper-tts"
            )
            self._enabled = False

    def _ensure_voice_loaded(self) -> bool:
        """Ensure the voice model is loaded. Returns True if successful."""
        if not self._enabled:
            return False

        if self._voice is not None:
            return True

        try:
            logger.info(
                "Loading Piper voice model: %s (speaker: %d)",
                self._model_name,
                self._speaker_id,
            )
            self._voice = PiperVoice.load(self._model_name, use_cuda=False)
            return True
        except Exception as e:
            logger.error("Failed to load Piper voice model: %s", e)
            self._enabled = False
            return False

    def speak(self, text: str) -> bool:
        """
        Synthesize and play speech from text.

        Args:
            text: The text to speak

        Returns:
            True if speech was successfully synthesized and played, False otherwise
        """
        if not self._ensure_voice_loaded():
            return False

        if not text or not text.strip():
            return False

        try:
            # Synthesize speech
            audio = self._voice.synthesize(text, speaker_id=self._speaker_id)
            
            # Play the audio
            # Note: piper.voice.PiperVoice.synthesize returns a numpy array
            # We need to play it using a library like sounddevice or pyaudio
            try:
                import sounddevice as sd
                import numpy as np
                
                # Piper outputs 22050 Hz audio by default
                sample_rate = 22050
                
                # Ensure audio is in the right format
                if isinstance(audio, np.ndarray):
                    sd.play(audio, sample_rate)
                    sd.wait()  # Wait until audio is finished playing
                    return True
                else:
                    logger.warning("Unexpected audio format from Piper")
                    return False
                    
            except ImportError:
                logger.warning(
                    "sounddevice not available for audio playback. "
                    "Install with: pip install sounddevice"
                )
                self._enabled = False
                return False

        except Exception as e:
            logger.error("Failed to synthesize speech: %s", e)
            return False

    def is_enabled(self) -> bool:
        """Check if voice output is currently enabled and available."""
        return self._enabled and _PIPER_AVAILABLE


# Global service instance
_piper_service: Optional[PiperService] = None


def get_piper_service() -> PiperService:
    """Get or create the global PiperService instance."""
    global _piper_service
    if _piper_service is None:
        _piper_service = PiperService()
    return _piper_service


def speak_text(text: str) -> bool:
    """
    Convenience function to speak text using the global Piper service.

    Args:
        text: The text to speak

    Returns:
        True if speech was successful, False otherwise
    """
    service = get_piper_service()
    return service.speak(text)
