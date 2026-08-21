"""Speech input adapter contracts and test implementations."""

from wizard_chess.speech.base import SpeechRecognizer
from wizard_chess.speech.mock import MockSpeechRecognizer

__all__ = ["MockSpeechRecognizer", "SpeechRecognizer"]
