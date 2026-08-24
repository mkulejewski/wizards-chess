from collections.abc import Callable, Iterator
from threading import Event
from time import monotonic

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from wizard_chess.application.session import GameSession
from wizard_chess.configuration import (
    ApplicationSettings,
    EngineSettings,
    PlayerKind,
    PlayerSettings,
)
from wizard_chess.domain.move import ChessMove
from wizard_chess.engine.mock import FakeEngine
from wizard_chess.engine.models import EngineEvaluation, EngineLine, PositionAnalysis
from wizard_chess.gui.main_window import MainWindow
from wizard_chess.hardware.simulated_board import SimulatedPhysicalBoard
from wizard_chess.speech.base import CancellationCheck
from wizard_chess.speech.controller import VoiceController
from wizard_chess.speech.mock import MockAudioInput, MockSpeechRecognizer
from wizard_chess.speech.models import AudioRecording, Transcript


@pytest.fixture(scope="module")
def qt_application() -> Iterator[QApplication]:
    existing = QApplication.instance()
    application = existing if isinstance(existing, QApplication) else QApplication([])
    yield application


class GatedAudioInput:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self.record_count = 0

    def record(self, cancel_requested: CancellationCheck) -> AudioRecording:
        self.record_count += 1
        self.started.set()
        while not self.release.wait(0.01):
            if cancel_requested():
                break
        return AudioRecording((), 16_000, 0.1)


class GatedRecognizer:
    def __init__(self, transcript: str) -> None:
        self.transcript = transcript
        self.started = Event()
        self.release = Event()

    def transcribe(
        self,
        recording: AudioRecording,
        cancel_requested: CancellationCheck,
    ) -> Transcript:
        del recording
        self.started.set()
        while not self.release.wait(0.01):
            if cancel_requested():
                break
        return Transcript(self.transcript)


def wait_for_gui(
    application: QApplication,
    condition: Callable[[], bool],
    *,
    timeout_seconds: float = 2.0,
) -> None:
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline and not condition():
        application.processEvents()
        QTest.qWait(5)
    application.processEvents()
    assert condition()


def test_gui_renders_initial_authoritative_position(qt_application: QApplication) -> None:
    del qt_application
    window = MainWindow()

    assert window.board_widget.piece_at("a1") == "R"
    assert window.board_widget.piece_at("e1") == "K"
    assert window.board_widget.piece_at("e2") == "P"
    assert window.board_widget.piece_at("e7") == "p"
    assert window.board_widget.piece_at("e8") == "k"
    assert window.board_widget.piece_at("a8") == "r"
    assert window.status_label.text() == "White to move"

    window.close()


@pytest.mark.parametrize("command", ["e4", "e2 e4"])
def test_gui_typed_move_uses_shared_command_path(
    qt_application: QApplication, command: str
) -> None:
    del qt_application
    session = GameSession()
    window = MainWindow(session)
    window.command_input.setText(command)

    QTest.mouseClick(window.play_button, Qt.MouseButton.LeftButton)

    last_move = session.snapshot().last_move
    assert last_move is not None
    assert last_move.uci() == "e2e4"
    assert window.history_view.toPlainText() == "1. e4"
    assert window.status_label.text() == "Black to move"
    assert window.command_input.text() == ""

    window.close()


def test_gui_controls_refresh_undo_redo_flip_and_new_game(
    qt_application: QApplication,
) -> None:
    del qt_application
    session = GameSession()
    window = MainWindow(session)
    window.command_input.setText("e4")
    QTest.mouseClick(window.play_button, Qt.MouseButton.LeftButton)
    moved_fen = session.snapshot().fen
    assert window.board_widget.last_move_squares == ("e2", "e4")

    QTest.mouseClick(window.undo_button, Qt.MouseButton.LeftButton)
    assert window.history_view.toPlainText() == ""
    assert window.status_label.text() == "White to move"
    assert window.redo_button.isEnabled()
    assert window.board_widget.last_move_squares is None

    QTest.mouseClick(window.redo_button, Qt.MouseButton.LeftButton)
    assert session.snapshot().fen == moved_fen
    assert window.history_view.toPlainText() == "1. e4"
    assert window.board_widget.last_move_squares == ("e2", "e4")

    before_flip = session.snapshot()
    QTest.mouseClick(window.flip_button, Qt.MouseButton.LeftButton)
    assert window.board_widget.displayed_square(0, 0) == "h1"
    assert session.snapshot().fen == before_flip.fen
    assert session.snapshot().move_history == before_flip.move_history

    QTest.mouseClick(window.new_button, Qt.MouseButton.LeftButton)
    snapshot = session.snapshot()
    assert snapshot.move_history == ()
    assert snapshot.last_move is None
    assert window.status_label.text() == "White to move"

    window.close()


def test_gui_mixes_typed_and_clicked_moves_in_one_session(
    qt_application: QApplication,
) -> None:
    del qt_application
    physical_board = SimulatedPhysicalBoard()
    session = GameSession(physical_board)
    window = MainWindow(session)

    for command in ("e4",):
        window.command_input.setText(command)
        QTest.mouseClick(window.play_button, Qt.MouseButton.LeftButton)
    window.board_widget.square_clicked.emit("e7")
    window.board_widget.square_clicked.emit("e5")
    window.command_input.setText("Nf3")
    QTest.mouseClick(window.play_button, Qt.MouseButton.LeftButton)
    window.board_widget.square_clicked.emit("b8")
    window.board_widget.square_clicked.emit("c6")

    snapshot = session.snapshot()
    assert snapshot.move_history == ("e4", "e5", "Nf3", "Nc6")
    assert snapshot.turn.value == "white"
    assert window.history_view.toPlainText() == "1. e4  e5\n2. Nf3  Nc6"
    assert [event.uci for event in physical_board.events] == [
        "e2e4",
        "e7e5",
        "g1f3",
        "b8c6",
    ]

    window.close()


def test_gui_valid_and_invalid_fen_feedback_is_non_destructive(
    qt_application: QApplication,
) -> None:
    del qt_application
    session = GameSession()
    window = MainWindow(session)
    checked_fen = "4k3/8/8/8/8/8/4R3/4K3 b - - 0 1"
    window.fen_input.setText(checked_fen)

    QTest.mouseClick(window.load_fen_button, Qt.MouseButton.LeftButton)
    assert session.snapshot().fen == checked_fen
    assert window.status_label.text() == "Black to move — Check"

    window.fen_input.setText("invalid fen")
    QTest.mouseClick(window.load_fen_button, Qt.MouseButton.LeftButton)
    assert session.snapshot().fen == checked_fen
    assert "Invalid FEN" in window.feedback_label.text()

    window.close()


def test_gui_voice_worker_reports_states_and_updates_shared_board(
    qt_application: QApplication,
) -> None:
    session = GameSession()
    audio = GatedAudioInput()
    recognizer = GatedRecognizer("e four")
    controller = VoiceController(audio, recognizer, session.play_text)
    window = MainWindow(session, controller)

    QTest.mouseClick(window.voice_button, Qt.MouseButton.LeftButton)
    assert audio.started.wait(1.0)
    wait_for_gui(qt_application, lambda: "Listening" in window.voice_status_label.text())
    assert not window.voice_button.isEnabled()

    QTest.mouseClick(window.voice_button, Qt.MouseButton.LeftButton)
    assert audio.record_count == 1

    audio.release.set()
    assert recognizer.started.wait(1.0)
    wait_for_gui(qt_application, lambda: "Processing" in window.voice_status_label.text())

    recognizer.release.set()
    wait_for_gui(qt_application, lambda: not window.voice_active)

    assert 'Heard: "e four"' in window.voice_status_label.text()
    assert "Played: e4" in window.voice_status_label.text()
    assert session.snapshot().move_history == ("e4",)
    assert window.board_widget.piece_at("e4") == "P"
    assert window.voice_button.isEnabled()

    window.close()


def test_gui_voice_failure_is_visible_and_preserves_game_state(
    qt_application: QApplication,
) -> None:
    session = GameSession()
    original_fen = session.snapshot().fen
    controller = VoiceController(
        MockAudioInput(),
        MockSpeechRecognizer(["knight before"]),
        session.play_text,
    )
    window = MainWindow(session, controller)

    QTest.mouseClick(window.voice_button, Qt.MouseButton.LeftButton)
    wait_for_gui(qt_application, lambda: not window.voice_active)

    assert "Voice: Error" in window.voice_status_label.text()
    assert 'Heard: "knight before"' in window.voice_status_label.text()
    assert "Could not parse command" in window.voice_status_label.text()
    assert session.snapshot().fen == original_fen
    assert window.command_input.isEnabled()

    window.close()


def test_gui_engine_analysis_runs_in_worker_and_renders_candidates(
    qt_application: QApplication,
) -> None:
    board = GameSession().game.board
    move = ChessMove.from_uci("e2e4")
    engine = FakeEngine(
        default=PositionAnalysis(
            fen=board.fen(),
            lines=(
                EngineLine(
                    move=move,
                    evaluation=EngineEvaluation(score_cp=42),
                    principal_variation=(move,),
                ),
            ),
        )
    )
    settings = ApplicationSettings(engine=EngineSettings(enabled=True, analysis_enabled=True))
    window = MainWindow(GameSession(settings=settings, engine=engine))

    wait_for_gui(qt_application, lambda: "Ready" in window.engine_status_label.text())

    assert window.evaluation_bar.format() == "Evaluation: +0.42"
    assert "1. e4  +0.42" in window.analysis_view.toPlainText()
    assert "PV: e4" in window.analysis_view.toPlainText()
    window.close()
    assert engine.closed


def test_gui_engine_opponent_replies_without_a_second_move_path(
    qt_application: QApplication,
) -> None:
    reply = ChessMove.from_uci("e7e5")
    engine = FakeEngine(
        default=PositionAnalysis(
            fen="ignored",
            lines=(
                EngineLine(
                    move=reply,
                    evaluation=EngineEvaluation(score_cp=0),
                    principal_variation=(reply,),
                ),
            ),
        )
    )
    settings = ApplicationSettings(
        engine=EngineSettings(enabled=True),
        players=PlayerSettings(black_kind=PlayerKind.ENGINE),
    )
    session = GameSession(settings=settings, engine=engine)
    window = MainWindow(session)
    window.command_input.setText("e4")

    QTest.mouseClick(window.play_button, Qt.MouseButton.LeftButton)
    wait_for_gui(qt_application, lambda: session.snapshot().move_history == ("e4", "e5"))

    assert session.snapshot().turn.value == "white"
    assert window.command_input.isEnabled()
    window.close()


def test_gui_history_navigation_does_not_mutate_live_game(
    qt_application: QApplication,
) -> None:
    del qt_application
    session = GameSession()
    session.play_text("e4")
    session.play_text("e5")
    live_fen = session.snapshot().fen
    window = MainWindow(session)

    window.history_slider.setValue(1)

    assert "After ply 1" in window.history_position_label.text()
    assert window.board_widget.piece_at("e5") is None
    assert window.board_widget.piece_at("e7") == "p"
    assert session.snapshot().fen == live_fen
    assert not window.command_input.isEnabled()

    QTest.mouseClick(window.live_position_button, Qt.MouseButton.LeftButton)
    assert window.board_widget.piece_at("e5") == "p"
    assert session.snapshot().fen == live_fen
    window.close()


def test_gui_post_game_analysis_reports_progress_without_mutating_game(
    qt_application: QApplication,
) -> None:
    move = ChessMove.from_uci("e2e4")
    engine = FakeEngine(
        default=PositionAnalysis(
            fen="ignored",
            lines=(
                EngineLine(
                    move=move,
                    evaluation=EngineEvaluation(score_cp=12),
                    principal_variation=(move,),
                ),
            ),
        )
    )
    settings = ApplicationSettings(engine=EngineSettings(enabled=True))
    session = GameSession(settings=settings, engine=engine)
    session.play_text("e4")
    live_fen = session.snapshot().fen
    window = MainWindow(session)

    QTest.mouseClick(window.analyse_game_button, Qt.MouseButton.LeftButton)
    wait_for_gui(
        qt_application,
        lambda: not window.game_analysis_active,
    )

    assert "Game analysis complete" in window.engine_status_label.text()
    assert "White ACPL" in window.analysis_view.toPlainText()
    assert "1. e4" in window.analysis_view.toPlainText()
    assert session.snapshot().fen == live_fen
    window.close()
