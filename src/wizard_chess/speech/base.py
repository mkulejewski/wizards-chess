"""Future-facing speech recognition interface."""

from typing import Protocol


class SpeechRecognizer(Protocol):
    """A replaceable producer of text transcripts."""

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def next_transcript(self) -> str | None: ...
