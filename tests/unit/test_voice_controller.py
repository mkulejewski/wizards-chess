from collections.abc import Callable
from threading import Event, Thread

import pytest

from wizard_chess.application.session import GameSession, SessionResult
from wizard_chess.domain.exceptions import InvalidCommandError, InvalidMoveError
from wizard_chess.speech.base import CancellationCheck
from wizard_chess.speech.controller import VoiceController
from wizard_chess.speech.exceptions import (
    AudioInputError,
    EmptyTranscriptError,
    RecognizerInitializationError,
    SpeechRecognitionError,
    VoiceBusyError,
    VoiceCommandRejected,
)
from wizard_chess.speech.mock import MockAudioInput, MockSpeechRecognizer
from wizard_chess.speech.models import AudioRecording, Transcript, VoiceCommandResult, VoiceState


class FailingAudioInput:
    def record(self, cancel_requested: CancellationCheck) -> AudioRecording:
        del cancel_requested
        raise RuntimeError("low-level audio failure")


class FailingRecognizer:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def transcribe(
        self,
        recording: AudioRecording,
        cancel_requested: CancellationCheck,
    ) -> Transcript:
        del recording, cancel_requested
        raise self.error


class BlockingAudioInput:
    def __init__(self, started: Event, release: Event) -> None:
        self.started = started
        self.release = release

    def record(self, cancel_requested: CancellationCheck) -> AudioRecording:
        self.started.set()
        while not self.release.wait(0.01):
            if cancel_requested():
                break
        return AudioRecording((), 16_000, 0.1)


def _controller(
    transcript: str,
    submit_command: Callable[[str], SessionResult],
) -> VoiceController[SessionResult]:
    return VoiceController(
        MockAudioInput(),
        MockSpeechRecognizer([transcript]),
        submit_command,
    )


def test_voice_controller_submits_normalized_text_through_shared_session() -> None:
    session = GameSession()
    states: list[VoiceState] = []

    result = _controller("e four", session.play_text).listen_once(states.append)

    assert result.recognition.transcript == "e four"
    assert result.recognition.normalized_text == "e4"
    assert result.command_result.message == "Played: e4"
    last_move = session.snapshot().last_move
    assert last_move is not None
    assert last_move.uci() == "e2e4"
    assert states == [VoiceState.LISTENING, VoiceState.PROCESSING, VoiceState.SUCCESS]


def test_voice_controller_preserves_raw_and_normalized_text_for_submitter() -> None:
    submitted: list[str] = []

    def submit(command: str) -> str:
        submitted.append(command)
        return "accepted"

    controller = VoiceController(MockAudioInput(), MockSpeechRecognizer(["Night F three."]), submit)

    result = controller.listen_once()

    assert submitted == ["knight f3"]
    assert result == VoiceCommandResult(
        recognition=result.recognition,
        command_result="accepted",
    )
    assert result.recognition.transcript == "Night F three."
    assert result.recognition.normalized_text == "knight f3"


def test_voice_controller_wraps_unexpected_recording_failure() -> None:
    controller = VoiceController(FailingAudioInput(), MockSpeechRecognizer(["e four"]), str)

    with pytest.raises(AudioInputError) as raised:
        controller.listen_once()

    assert "low-level audio failure" not in str(raised.value)
    assert controller.state is VoiceState.ERROR


@pytest.mark.parametrize(
    ("recognizer_error", "expected_type"),
    [
        (RuntimeError("backend failure"), SpeechRecognitionError),
        (
            RecognizerInitializationError("model initialization failed"),
            RecognizerInitializationError,
        ),
    ],
)
def test_voice_controller_controls_recognizer_failures(
    recognizer_error: Exception, expected_type: type[Exception]
) -> None:
    controller = VoiceController(MockAudioInput(), FailingRecognizer(recognizer_error), str)

    with pytest.raises(expected_type):
        controller.listen_once()


def test_voice_controller_rejects_empty_transcript_without_submitting() -> None:
    submitted: list[str] = []
    controller = VoiceController(
        MockAudioInput(),
        MockSpeechRecognizer([""]),
        lambda command: submitted.append(command),
    )

    with pytest.raises(EmptyTranscriptError):
        controller.listen_once()

    assert submitted == []


def test_unsupported_voice_command_preserves_parser_error_and_game_state() -> None:
    session = GameSession()
    original_fen = session.snapshot().fen

    with pytest.raises(VoiceCommandRejected) as raised:
        _controller("knight before", session.play_text).listen_once()

    assert isinstance(raised.value.cause, InvalidCommandError)
    assert raised.value.recognition.transcript == "knight before"
    assert session.snapshot().fen == original_fen


def test_legal_looking_but_illegal_voice_move_does_not_change_game_state() -> None:
    session = GameSession()
    original_fen = session.snapshot().fen

    with pytest.raises(VoiceCommandRejected) as raised:
        _controller("e five", session.play_text).listen_once()

    assert isinstance(raised.value.cause, InvalidMoveError)
    assert session.snapshot().fen == original_fen


def test_voice_controller_prevents_overlapping_recordings() -> None:
    started = Event()
    release = Event()
    controller = VoiceController(
        BlockingAudioInput(started, release),
        MockSpeechRecognizer(["e four"]),
        str,
    )
    result: list[VoiceCommandResult[str]] = []
    first = Thread(target=lambda: result.append(controller.listen_once()))
    first.start()
    assert started.wait(1.0)

    with pytest.raises(VoiceBusyError):
        controller.listen_once()

    release.set()
    first.join(timeout=1.0)
    assert not first.is_alive()
    assert len(result) == 1
