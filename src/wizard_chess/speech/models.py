"""Small structured values passed through the voice pipeline."""

from dataclasses import dataclass
from enum import StrEnum


class VoiceState(StrEnum):
    """Observable stages of one explicitly initiated voice command."""

    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AudioRecording:
    """Recognizer-neutral mono audio samples captured in memory."""

    samples: object
    sample_rate: int
    duration_seconds: float


@dataclass(frozen=True, slots=True)
class Transcript:
    """Raw output from a speech-recognition backend."""

    text: str
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class RecognitionResult:
    """Preserve both raw speech output and parser-compatible cleanup."""

    transcript: str
    normalized_text: str
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class VoiceCommandResult[CommandResultT]:
    """Successful recognition and its shared application result."""

    recognition: RecognitionResult
    command_result: CommandResultT
