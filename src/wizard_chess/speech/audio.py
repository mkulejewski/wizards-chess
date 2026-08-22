"""Bounded, in-memory microphone capture using optional python-sounddevice."""

import logging
import math
from array import array
from collections.abc import Callable
from importlib import import_module
from time import monotonic
from types import TracebackType
from typing import Protocol, Self, cast

from wizard_chess.speech.base import CancellationCheck
from wizard_chess.speech.exceptions import (
    AudioInputError,
    NoSpeechDetectedError,
    VoiceDependencyError,
    VoiceInputCancelled,
)
from wizard_chess.speech.models import AudioRecording

LOGGER = logging.getLogger(__name__)


class _RawInputStream(Protocol):
    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...

    def read(self, frames: int) -> tuple[object, bool]: ...


class _SoundDeviceModule(Protocol):
    RawInputStream: Callable[..., _RawInputStream]

    def query_devices(self, device: int | str | None, kind: str) -> object: ...


class SoundDeviceAudioInput:
    """Record one utterance from the default or configured PortAudio device."""

    def __init__(
        self,
        *,
        device: int | str | None = None,
        sample_rate: int = 16_000,
        maximum_seconds: float = 6.0,
        speech_start_timeout_seconds: float = 3.0,
        silence_seconds: float = 0.8,
        silence_threshold: float = 0.015,
    ) -> None:
        self.device = device
        self.sample_rate = sample_rate
        self.maximum_seconds = maximum_seconds
        self.speech_start_timeout_seconds = min(speech_start_timeout_seconds, maximum_seconds)
        self.silence_seconds = silence_seconds
        self.silence_threshold = silence_threshold

    def record(self, cancel_requested: CancellationCheck) -> AudioRecording:
        """Capture until post-speech silence, cancellation, or a hard duration limit."""
        sounddevice = self._load_sounddevice()
        block_size = max(1, int(self.sample_rate * 0.05))
        maximum_frames = int(self.sample_rate * self.maximum_seconds)
        start_timeout_frames = int(self.sample_rate * self.speech_start_timeout_seconds)
        silence_frames_required = int(self.sample_rate * self.silence_seconds)
        samples = array("f")
        speech_start: int | None = None
        trailing_silence_frames = 0

        try:
            sounddevice.query_devices(self.device, kind="input")
            LOGGER.info("Voice recording started")
            started_at = monotonic()
            with sounddevice.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=block_size,
                device=self.device,
                channels=1,
                dtype="float32",
            ) as stream:
                while len(samples) < maximum_frames:
                    if cancel_requested():
                        raise VoiceInputCancelled("Voice input was cancelled.")
                    raw_block, overflowed = stream.read(block_size)
                    if overflowed:
                        LOGGER.debug("Microphone input overflowed during voice recording")
                    block = array("f")
                    block.frombytes(bytes(cast(memoryview, raw_block)))
                    samples.extend(block)

                    level = self._root_mean_square(block)
                    if level >= self.silence_threshold:
                        if speech_start is None:
                            speech_start = max(0, len(samples) - len(block))
                        trailing_silence_frames = 0
                    elif speech_start is not None:
                        trailing_silence_frames += len(block)
                        if trailing_silence_frames >= silence_frames_required:
                            break
                    elif len(samples) >= start_timeout_frames:
                        raise NoSpeechDetectedError("Could not detect speech. Please try again.")

            if speech_start is None:
                raise NoSpeechDetectedError("Could not detect speech. Please try again.")

            pre_roll_frames = int(self.sample_rate * 0.2)
            trimmed = samples[max(0, speech_start - pre_roll_frames) :]
            duration = len(trimmed) / self.sample_rate
            LOGGER.info(
                "Voice recording stopped after %.2f seconds (wall time %.2f seconds)",
                duration,
                monotonic() - started_at,
            )
            return AudioRecording(trimmed, self.sample_rate, duration)
        except VoiceInputCancelled:
            raise
        except NoSpeechDetectedError:
            raise
        except Exception as error:
            LOGGER.debug("Audio-device failure", exc_info=True)
            raise AudioInputError(
                "Voice input unavailable: no usable microphone could be opened. "
                "Keyboard input remains available."
            ) from error

    @staticmethod
    def _root_mean_square(samples: array[float]) -> float:
        if not samples:
            return 0.0
        return math.sqrt(sum(sample * sample for sample in samples) / len(samples))

    @staticmethod
    def _load_sounddevice() -> _SoundDeviceModule:
        try:
            module = import_module("sounddevice")
        except (ImportError, OSError) as error:
            raise VoiceDependencyError(
                "Voice control is unavailable because optional speech dependencies are not "
                "installed. Run: uv sync --extra voice"
            ) from error
        return cast(_SoundDeviceModule, module)
