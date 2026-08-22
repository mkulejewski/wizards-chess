"""Replaceable contracts for single-utterance voice input."""

from collections.abc import Callable
from typing import Protocol

from wizard_chess.speech.models import AudioRecording, Transcript

CancellationCheck = Callable[[], bool]


class AudioInput(Protocol):
    """Capture one bounded microphone utterance without knowing chess rules."""

    def record(self, cancel_requested: CancellationCheck) -> AudioRecording: ...


class SpeechRecognizer(Protocol):
    """Convert captured audio into text without knowing chess rules."""

    def transcribe(
        self,
        recording: AudioRecording,
        cancel_requested: CancellationCheck,
    ) -> Transcript: ...
