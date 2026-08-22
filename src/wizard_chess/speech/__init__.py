"""Speech input adapter contracts, values, orchestration, and test doubles."""

from wizard_chess.speech.base import AudioInput, SpeechRecognizer
from wizard_chess.speech.controller import VoiceController
from wizard_chess.speech.mock import MockAudioInput, MockSpeechRecognizer
from wizard_chess.speech.models import RecognitionResult, VoiceCommandResult, VoiceState
from wizard_chess.speech.normalizer import TranscriptNormalizer

__all__ = [
    "AudioInput",
    "MockAudioInput",
    "MockSpeechRecognizer",
    "RecognitionResult",
    "SpeechRecognizer",
    "TranscriptNormalizer",
    "VoiceCommandResult",
    "VoiceController",
    "VoiceState",
]
