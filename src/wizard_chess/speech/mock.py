"""Dependency-free voice test doubles."""

from collections import deque
from collections.abc import Iterable

from wizard_chess.speech.base import CancellationCheck
from wizard_chess.speech.models import AudioRecording, Transcript


class MockAudioInput:
    """Return one in-memory placeholder recording without audio hardware."""

    def __init__(self, recording: AudioRecording | None = None) -> None:
        self.recording = recording or AudioRecording((), 16_000, 0.0)
        self.record_count = 0

    def record(self, cancel_requested: CancellationCheck) -> AudioRecording:
        if cancel_requested():
            return AudioRecording((), 16_000, 0.0)
        self.record_count += 1
        return self.recording


class MockSpeechRecognizer:
    """Return predetermined transcripts for orchestration tests and development."""

    def __init__(self, transcripts: Iterable[str] = ()) -> None:
        self._transcripts = deque(transcripts)
        self.is_running = False

    def transcribe(
        self,
        recording: AudioRecording,
        cancel_requested: CancellationCheck,
    ) -> Transcript:
        del recording
        if cancel_requested() or not self._transcripts:
            return Transcript("")
        return Transcript(self._transcripts.popleft())

    # Retain the Stage 1 development seam for callers that used it directly.
    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False

    def next_transcript(self) -> str | None:
        if not self.is_running or not self._transcripts:
            return None
        return self._transcripts.popleft()
