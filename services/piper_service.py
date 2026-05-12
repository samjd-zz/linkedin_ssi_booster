"""Piper TTS voice synthesis service for console output using Wyoming protocol."""

from __future__ import annotations

import json
import logging
import os
import socket
from typing import Optional

logger = logging.getLogger(__name__)


def is_voice_enabled() -> bool:
    """Check if voice output is enabled via environment variable."""
    return os.getenv("CONSOLE_USE_VOICE", "false").lower() in ("true", "1", "yes")


def get_wyoming_host() -> str:
    """Get the Wyoming Piper host from environment variable or use default."""
    return os.getenv("WYOMING_PIPER_HOST", "localhost")


def get_wyoming_port() -> int:
    """Get the Wyoming Piper port from environment variable or use default."""
    try:
        return int(os.getenv("WYOMING_PIPER_PORT", "10200"))
    except ValueError:
        logger.warning("Invalid WYOMING_PIPER_PORT value, using default 10200")
        return 10200


def get_voice_name() -> str:
    """Get the voice name from environment variable or use default."""
    return os.getenv("CONSOLE_VOICE_MODEL", "en_US-libritts_r-medium")


def get_speaker_id() -> Optional[str]:
    """Get the speaker ID from environment variable or return None."""
    speaker = os.getenv("CONSOLE_VOICE_SPEAKER", "")
    return speaker if speaker else None


class PiperService:
    """Service for text-to-speech using Wyoming Piper protocol."""

    def __init__(self) -> None:
        """Initialize the Piper service."""
        self._enabled = is_voice_enabled()
        self._host = get_wyoming_host()
        self._port = get_wyoming_port()
        self._voice_name = get_voice_name()
        self._speaker_id = get_speaker_id()

    def _send_event(self, sock: socket.socket, event_type: str, data: Optional[dict] = None) -> None:
        """Send a Wyoming protocol event."""
        event: dict = {"type": event_type}
        if data:
            event["data"] = data
        message = json.dumps(event) + "\n"
        sock.sendall(message.encode("utf-8"))

    def _receive_event(self, sock: socket.socket) -> Optional[dict]:
        """Receive a Wyoming protocol event."""
        buffer = b""
        while b"\n" not in buffer:
            chunk = sock.recv(4096)
            if not chunk:
                return None
            buffer += chunk
        
        # Split on first newline
        line, remaining = buffer.split(b"\n", 1)
        event = json.loads(line.decode("utf-8"))
        
        # If there's a payload, read it
        payload_length = event.get("payload_length", 0)
        if payload_length > 0:
            payload = remaining
            while len(payload) < payload_length:
                chunk = sock.recv(payload_length - len(payload))
                if not chunk:
                    break
                payload += chunk
            event["payload"] = payload[:payload_length]
        
        return event

    def speak(self, text: str) -> bool:
        """
        Synthesize and play speech from text using Wyoming protocol.

        Args:
            text: The text to speak

        Returns:
            True if speech was successfully synthesized and played, False otherwise
        """
        if not self._enabled:
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

            # Connect to Wyoming Piper server
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)
            
            try:
                sock.connect((self._host, self._port))
                logger.debug("Connected to Wyoming Piper at %s:%d", self._host, self._port)
                
                # Send synthesize request
                synthesize_data: dict = {"text": text}
                if self._voice_name:
                    voice_data: dict = {"name": self._voice_name}
                    if self._speaker_id:
                        voice_data["speaker"] = self._speaker_id
                    synthesize_data["voice"] = voice_data
                
                self._send_event(sock, "synthesize", synthesize_data)
                logger.debug("Sent synthesize request for text: %s", text[:50])
                
                # Receive audio chunks
                audio_chunks = []
                sample_rate = None
                sample_width = None
                
                while True:
                    event = self._receive_event(sock)
                    if not event:
                        break
                    
                    event_type = event.get("type")
                    
                    if event_type == "audio-start":
                        data = event.get("data", {})
                        sample_rate = data.get("rate")
                        sample_width = data.get("width")
                        logger.debug("Audio stream started: rate=%d, width=%d", sample_rate, sample_width)
                    
                    elif event_type == "audio-chunk":
                        payload = event.get("payload", b"")
                        if payload:
                            audio_chunks.append(payload)
                    
                    elif event_type == "audio-stop":
                        logger.debug("Audio stream stopped, received %d chunks", len(audio_chunks))
                        break
                
                if not audio_chunks or not sample_rate:
                    logger.warning("No audio generated from text")
                    return False
                
                # Concatenate all audio chunks
                full_audio_bytes = b"".join(audio_chunks)
                
                # Convert bytes to numpy array based on sample width
                if sample_width == 2:  # 16-bit PCM
                    audio_data = np.frombuffer(full_audio_bytes, dtype=np.int16)
                elif sample_width == 4:  # 32-bit PCM
                    audio_data = np.frombuffer(full_audio_bytes, dtype=np.int32)
                else:
                    logger.error("Unsupported sample width: %d", sample_width)
                    return False
                
                # Normalize to float32 for sounddevice
                if sample_width == 2:
                    audio_float = audio_data.astype(np.float32) / 32768.0
                else:  # 32-bit
                    audio_float = audio_data.astype(np.float32) / 2147483648.0
                
                # Play the audio
                sd.play(audio_float, sample_rate)
                sd.wait()  # Wait until audio is finished playing
                logger.debug("Audio playback completed")
                return True
                
            finally:
                sock.close()

        except socket.timeout:
            logger.error("Connection to Wyoming Piper timed out")
            return False
        except ConnectionRefusedError:
            logger.error(
                "Could not connect to Wyoming Piper at %s:%d. "
                "Make sure the Wyoming Piper service is running.",
                self._host,
                self._port,
            )
            return False
        except Exception as e:
            logger.error("Failed to synthesize speech: %s", e)
            return False

    def is_enabled(self) -> bool:
        """Check if voice output is currently enabled and available."""
        return self._enabled


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
