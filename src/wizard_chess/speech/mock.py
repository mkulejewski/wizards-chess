"""Dependency-free speech recognizer for tests and development."""

from collections import deque
from collections.abc import Iterable


class MockSpeechRecognizer:
    """Yield predetermined transcripts while running."""

    def __init__(self, transcripts: Iterable[str] = ()) -> None:
        self._transcripts = deque(transcripts)
        self.is_running = False

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False

    def next_transcript(self) -> str | None:
        if not self.is_running or not self._transcripts:
            return None
        return self._transcripts.popleft()
