"""Synchronous, UI-neutral orchestration of one voice command."""

import logging
from collections.abc import Callable
from threading import Event, Lock

from wizard_chess.speech.base import AudioInput, SpeechRecognizer
from wizard_chess.speech.exceptions import (
    AudioInputError,
    EmptyTranscriptError,
    SpeechRecognitionError,
    VoiceBusyError,
    VoiceCommandRejected,
    VoiceError,
    VoiceInputCancelled,
)
from wizard_chess.speech.models import (
    AudioRecording,
    RecognitionResult,
    Transcript,
    VoiceCommandResult,
    VoiceState,
)
from wizard_chess.speech.normalizer import TranscriptNormalizer

StateCallback = Callable[[VoiceState], None]

LOGGER = logging.getLogger(__name__)


class VoiceController[CommandResultT]:
    """Capture, transcribe, normalize, and submit through one shared command path."""

    def __init__(
        self,
        audio_input: AudioInput,
        recognizer: SpeechRecognizer,
        submit_command: Callable[[str], CommandResultT],
        normalizer: TranscriptNormalizer | None = None,
    ) -> None:
        self._audio_input = audio_input
        self._recognizer = recognizer
        self._submit_command = submit_command
        self._normalizer = normalizer or TranscriptNormalizer()
        self._active_lock = Lock()
        self._state_lock = Lock()
        self._cancel_requested = Event()
        self._state = VoiceState.IDLE

    @property
    def state(self) -> VoiceState:
        """Return the most recently reported lifecycle state."""
        with self._state_lock:
            return self._state

    def cancel(self) -> None:
        """Request that an active command stop before application submission."""
        self._cancel_requested.set()

    def listen_once(
        self, on_state: StateCallback | None = None
    ) -> VoiceCommandResult[CommandResultT]:
        """Process exactly one bounded recording, rejecting overlapping requests."""
        if not self._active_lock.acquire(blocking=False):
            raise VoiceBusyError("Voice input is already listening or processing.")

        self._cancel_requested.clear()
        try:
            self._report_state(VoiceState.LISTENING, on_state)
            recording = self._capture_audio()
            self._raise_if_cancelled()

            self._report_state(VoiceState.PROCESSING, on_state)
            transcript = self._recognize(recording)
            raw_text = transcript.text.strip()
            if not raw_text:
                raise EmptyTranscriptError("Could not understand speech. Please try again.")

            normalized_text = self._normalizer.normalize(raw_text)
            if not normalized_text:
                raise EmptyTranscriptError("Could not understand speech. Please try again.")

            recognition = RecognitionResult(
                transcript=raw_text,
                normalized_text=normalized_text,
                confidence=transcript.confidence,
            )
            LOGGER.debug("Voice transcript: raw=%r normalized=%r", raw_text, normalized_text)
            self._raise_if_cancelled()
            try:
                command_result = self._submit_command(normalized_text)
            except Exception as error:
                raise VoiceCommandRejected(recognition, error) from error

            result = VoiceCommandResult(recognition, command_result)
            self._report_state(VoiceState.SUCCESS, on_state)
            return result
        except VoiceError:
            self._report_state(VoiceState.ERROR, on_state)
            LOGGER.debug("Voice command failed", exc_info=True)
            raise
        finally:
            self._active_lock.release()

    def _capture_audio(self) -> AudioRecording:
        try:
            return self._audio_input.record(self._cancel_requested.is_set)
        except VoiceError:
            raise
        except Exception as error:
            raise AudioInputError(
                "Voice recording failed. Keyboard input remains available."
            ) from error

    def _recognize(self, recording: AudioRecording) -> Transcript:
        try:
            return self._recognizer.transcribe(recording, self._cancel_requested.is_set)
        except VoiceError:
            raise
        except Exception as error:
            raise SpeechRecognitionError(
                "Speech recognition failed. Keyboard input remains available."
            ) from error

    def _raise_if_cancelled(self) -> None:
        if self._cancel_requested.is_set():
            raise VoiceInputCancelled("Voice input was cancelled.")

    def _report_state(self, state: VoiceState, callback: StateCallback | None) -> None:
        with self._state_lock:
            self._state = state
        if callback is not None:
            callback(state)
