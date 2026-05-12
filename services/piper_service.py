"""Piper TTS voice synthesis service for console output."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Global flag to track if piper is available
_PIPER_AVAILABLE = False
_piper_tts = None

try:
    from piper.voice import PiperVoice
    from piper import SynthesisConfig
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


def _get_voice_model_path(model_name: str) -> Optional[Path]:
    """
    Get the path to the downloaded voice model .onnx file.
    
    Piper downloads models to ~/.local/share/piper/voices/ by default.
    Returns None if the model file doesn't exist.
    """
    # Check common locations for piper voice models
    home = Path.home()
    possible_paths = [
        home / ".local" / "share" / "piper" / "voices" / f"{model_name}.onnx",
        home / ".local" / "share" / "piper-tts" / "voices" / f"{model_name}.onnx",
        Path("/usr/share/piper/voices") / f"{model_name}.onnx",
        Path("/usr/local/share/piper/voices") / f"{model_name}.onnx",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None


def _download_voice_model(model_name: str) -> bool:
    """
    Download a Piper voice model using piper.download_voices.
    
    Returns True if download was successful, False otherwise.
    """
    try:
        logger.info("Downloading Piper voice model: %s", model_name)
        result = subprocess.run(
            ["python3", "-m", "piper.download_voices", model_name],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        
        if result.returncode == 0:
            logger.info("Successfully downloaded voice model: %s", model_name)
            return True
        else:
            logger.error(
                "Failed to download voice model %s: %s",
                model_name,
                result.stderr,
            )
            return False
    except subprocess.TimeoutExpired:
        logger.error("Voice model download timed out after 5 minutes")
        return False
    except Exception as e:
        logger.error("Failed to download voice model: %s", e)
        return False


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
            # Check if model is already downloaded
            model_path = _get_voice_model_path(self._model_name)
            
            if model_path is None:
                logger.info(
                    "Voice model %s not found locally, attempting download...",
                    self._model_name,
                )
                if not _download_voice_model(self._model_name):
                    logger.error("Failed to download voice model: %s", self._model_name)
                    self._enabled = False
                    return False
                
                # Try to find the model again after download
                model_path = _get_voice_model_path(self._model_name)
                if model_path is None:
                    logger.error(
                        "Voice model %s still not found after download",
                        self._model_name,
                    )
                    self._enabled = False
                    return False
            
            logger.info(
                "Loading Piper voice model from: %s (speaker: %d)",
                model_path,
                self._speaker_id,
            )
            self._voice = PiperVoice.load(str(model_path), use_cuda=False)
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
            # Import audio playback library
            try:
                import sounddevice as sd
                import numpy as np
            except ImportError:
                logger.warning(
                    "sounddevice not available for audio playback. "
                    "Install with: pip install sounddevice"
                )
                self._enabled = False
                return False
            
            # Synthesize speech using streaming API
            # voice.synthesize() returns an iterator of AudioChunk objects
            # At this point _voice is guaranteed to be loaded by _ensure_voice_loaded
            assert self._voice is not None, "Voice should be loaded at this point"
            
            audio_chunks = []
            sample_rate = None
            sample_width = None
            
            # Create synthesis config with speaker_id for multi-speaker models
            syn_config = SynthesisConfig(speaker_id=self._speaker_id)
            
            for chunk in self._voice.synthesize(text, syn_config=syn_config):
                # Extract audio data from chunk
                if sample_rate is None:
                    sample_rate = chunk.sample_rate
                    sample_width = chunk.sample_width
                
                # Convert bytes to numpy array
                audio_data = np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16)
                audio_chunks.append(audio_data)
            
            if not audio_chunks:
                logger.warning("No audio generated from text")
                return False
            
            # Concatenate all chunks
            full_audio = np.concatenate(audio_chunks)
            
            # Normalize to float32 for sounddevice
            audio_float = full_audio.astype(np.float32) / 32768.0
            
            # Play the audio
            sd.play(audio_float, sample_rate)
            sd.wait()  # Wait until audio is finished playing
            return True

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
