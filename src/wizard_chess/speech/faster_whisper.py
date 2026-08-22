"""Lazy local faster-whisper recognition backend."""

import logging
from collections.abc import Callable, Iterable
from importlib import import_module
from threading import Lock
from typing import Protocol, cast

from wizard_chess.speech.base import CancellationCheck
from wizard_chess.speech.exceptions import (
    RecognizerInitializationError,
    SpeechRecognitionError,
    VoiceDependencyError,
    VoiceInputCancelled,
)
from wizard_chess.speech.models import AudioRecording, Transcript

LOGGER = logging.getLogger(__name__)


class _Segment(Protocol):
    text: str


class _WhisperModel(Protocol):
    def transcribe(self, audio: object, **options: object) -> tuple[Iterable[_Segment], object]: ...


ModelFactory = Callable[..., _WhisperModel]


class _FasterWhisperModule(Protocol):
    WhisperModel: ModelFactory


class _NumpyModule(Protocol):
    float32: object

    def asarray(self, samples: object, *, dtype: object) -> object: ...


class FasterWhisperRecognizer:
    """Reuse one lazily loaded CPU model for local English transcription."""

    def __init__(
        self,
        model: str = "base.en",
        *,
        language: str = "en",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self.model_name = model
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self._model: _WhisperModel | None = None
        self._model_lock = Lock()

    def transcribe(
        self,
        recording: AudioRecording,
        cancel_requested: CancellationCheck,
    ) -> Transcript:
        """Transcribe in-memory mono samples without retaining or uploading audio."""
        if cancel_requested():
            raise VoiceInputCancelled("Voice input was cancelled.")
        model = self._get_model()
        samples = self._as_float32_array(recording.samples)
        try:
            segments, _information = model.transcribe(
                samples,
                language=self.language,
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
                condition_on_previous_text=False,
                initial_prompt=(
                    "Chess moves: e4, e5, knight f3, bishop c4, queen takes d5, "
                    "castle kingside, castle queenside."
                ),
            )
            text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        except Exception as error:
            LOGGER.debug("Speech transcription failed", exc_info=True)
            raise SpeechRecognitionError(
                "Speech recognition failed. Keyboard input remains available."
            ) from error
        if cancel_requested():
            raise VoiceInputCancelled("Voice input was cancelled.")
        return Transcript(text=text)

    def _get_model(self) -> _WhisperModel:
        if self._model is not None:
            return self._model
        with self._model_lock:
            if self._model is not None:
                return self._model
            LOGGER.info("Speech recognizer initialization started: %s", self.model_name)
            try:
                module = cast(_FasterWhisperModule, import_module("faster_whisper"))
                factory = module.WhisperModel
            except (ImportError, OSError, AttributeError) as error:
                raise VoiceDependencyError(
                    "Voice control is unavailable because optional speech dependencies are not "
                    "installed. Run: uv sync --extra voice"
                ) from error
            try:
                self._model = factory(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                )
            except Exception as error:
                LOGGER.debug("Speech model initialization failed", exc_info=True)
                raise RecognizerInitializationError(
                    "Voice recognition could not be initialized. Keyboard input remains available."
                ) from error
            LOGGER.info("Speech recognizer initialized: %s", self.model_name)
            return self._model

    @staticmethod
    def _as_float32_array(samples: object) -> object:
        try:
            numpy = cast(_NumpyModule, import_module("numpy"))
        except (ImportError, OSError) as error:
            raise VoiceDependencyError(
                "Voice control is unavailable because optional speech dependencies are not "
                "installed. Run: uv sync --extra voice"
            ) from error
        return numpy.asarray(samples, dtype=numpy.float32)
