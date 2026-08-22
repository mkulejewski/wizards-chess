"""Controlled failures exposed by the voice input adapter."""

from wizard_chess.speech.models import RecognitionResult


class VoiceError(Exception):
    """Base class for expected voice-control failures."""


class VoiceDependencyError(VoiceError):
    """Raised when an optional local voice dependency is unavailable."""


class AudioInputError(VoiceError):
    """Raised when a microphone cannot capture an utterance."""


class NoSpeechDetectedError(AudioInputError):
    """Raised when the bounded recording contains no detectable speech."""


class RecognizerInitializationError(VoiceError):
    """Raised when the local recognition model cannot be initialized."""


class SpeechRecognitionError(VoiceError):
    """Raised when a loaded recognizer cannot transcribe an utterance."""


class EmptyTranscriptError(SpeechRecognitionError):
    """Raised when recognition completes without usable text."""


class VoiceBusyError(VoiceError):
    """Raised when a second recording is requested before the first ends."""


class VoiceInputCancelled(VoiceError):
    """Raised when application shutdown cancels a voice command."""


class VoiceCommandRejected(VoiceError):
    """Preserve recognition details when shared command handling rejects text."""

    def __init__(self, recognition: RecognitionResult, cause: Exception) -> None:
        super().__init__(str(cause))
        self.recognition = recognition
        self.cause = cause
