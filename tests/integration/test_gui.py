from collections.abc import Callable, Iterator
from pathlib import Path
from threading import Event
from time import monotonic

import chess
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import wizard_chess.gui.main_window as main_window_module
from wizard_chess.analysis.live import LiveAnalysisResult, position_key
from wizard_chess.application.session import GameSession, SessionResult
from wizard_chess.configuration import (
    AppearanceSettings,
    ApplicationSettings,
    BoardTheme,
    EngineAnalysisMode,
    EngineSettings,
    PieceSet,
    PlayerKind,
    PlayerSettings,
    VoiceLanguage,
)
from wizard_chess.domain.exceptions import AnalysisCancelledError
from wizard_chess.domain.move import ChessMove
from wizard_chess.domain.results import GameStatus
from wizard_chess.engine.base import AnalysisUpdate
from wizard_chess.engine.mock import FakeEngine
from wizard_chess.engine.models import (
    EngineClockState,
    EngineDecision,
    EngineEvaluation,
    EngineLine,
    PositionAnalysis,
)
from wizard_chess.gui.main_window import MainWindow
from wizard_chess.hardware.simulated_board import SimulatedPhysicalBoard
from wizard_chess.persistence.settings_store import SettingsStore
from wizard_chess.speech.base import CancellationCheck
from wizard_chess.speech.config import VoiceConfig
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


class GatedLiveEngine(FakeEngine):
    def __init__(self) -> None:
        super().__init__()
        self.live_started = Event()
        self.live_cancelled = Event()
        self.live_request_count = 0

    def analyse_live(
        self,
        board: chess.Board,
        *,
        max_depth: int,
        on_update: AnalysisUpdate,
        cancel_requested: CancellationCheck | None = None,
    ) -> None:
        self.live_request_count += 1
        self.live_started.set()
        if self.live_request_count == 1:
            while cancel_requested is None or not cancel_requested():
                self.live_cancelled.wait(0.005)
            self.live_cancelled.set()
            return
        move = ChessMove.from_python_chess(next(iter(board.legal_moves)))
        on_update(
            PositionAnalysis(
                fen=board.fen(),
                lines=(
                    EngineLine(
                        move=move,
                        evaluation=EngineEvaluation(score_cp=20),
                        principal_variation=(move,),
                        depth=max_depth,
                    ),
                ),
            )
        )


class GatedPostGameEngine(FakeEngine):
    def __init__(self) -> None:
        super().__init__()
        self.started = Event()
        self.release = Event()
        self.cancelled = Event()

    def analyse_position(
        self,
        board: chess.Board,
        *,
        count: int | None = None,
        time_ms: int | None = None,
        cancel_requested: CancellationCheck | None = None,
    ) -> PositionAnalysis:
        del count, time_ms
        self.started.set()
        while not self.release.wait(0.005):
            if cancel_requested is not None and cancel_requested():
                self.cancelled.set()
                raise AnalysisCancelledError("Game analysis was cancelled")
        if cancel_requested is not None and cancel_requested():
            self.cancelled.set()
            raise AnalysisCancelledError("Game analysis was cancelled")
        return super().analyse_position(board, cancel_requested=cancel_requested)

    def cancel_pending(self) -> None:
        self.release.set()


class GatedEngineMoves(FakeEngine):
    def __init__(self) -> None:
        super().__init__()
        self.request_count = 0
        self.thinking = Event()
        self.cancelled = Event()
        self._poll = Event()

    def play_move(
        self,
        board: chess.Board,
        *,
        clock: EngineClockState | None = None,
        cancel_requested: CancellationCheck | None = None,
    ) -> EngineDecision | None:
        del board, clock
        self.request_count += 1
        if self.request_count == 1:
            return EngineDecision(move=ChessMove.from_uci("e2e4"))
        self.thinking.set()
        while cancel_requested is None or not cancel_requested():
            self._poll.wait(0.005)
        self.cancelled.set()
        return None


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


def test_gui_owned_recognizer_tracks_the_selected_voice_language(
    qt_application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qt_application
    monkeypatch.delenv("WIZARD_CHESS_VOICE_LANGUAGE", raising=False)
    monkeypatch.delenv("WIZARD_CHESS_VOICE_MODEL", raising=False)
    configs: list[VoiceConfig] = []

    def create_controller(
        submit_command: Callable[[str], SessionResult],
        config: VoiceConfig | None = None,
    ) -> VoiceController[SessionResult]:
        assert config is not None
        configs.append(config)
        return VoiceController(MockAudioInput(), MockSpeechRecognizer(), submit_command)

    monkeypatch.setattr(
        main_window_module,
        "create_default_voice_controller",
        create_controller,
    )
    session = GameSession(settings=ApplicationSettings(voice_language=VoiceLanguage.POLISH))
    window = MainWindow(session)

    assert (configs[-1].language, configs[-1].model) == (VoiceLanguage.POLISH, "base")

    window.language_combo.setCurrentIndex(
        window.language_combo.findData(VoiceLanguage.ENGLISH.value)
    )
    assert (configs[-1].language, configs[-1].model) == (VoiceLanguage.ENGLISH, "base.en")

    window.language_combo.setCurrentIndex(
        window.language_combo.findData(VoiceLanguage.POLISH.value)
    )
    assert (configs[-1].language, configs[-1].model) == (VoiceLanguage.POLISH, "base")
    assert session.voice_language is VoiceLanguage.POLISH

    window.close()


def test_gui_switches_and_persists_board_appearance_without_changing_game(
    qt_application: QApplication, tmp_path: Path
) -> None:
    del qt_application
    session = GameSession()
    original = session.snapshot()
    store = SettingsStore(tmp_path / "settings.json")
    window = MainWindow(session, settings_store=store)

    assert window.board_widget.piece_set is PieceSet.TATIANA
    assert window.board_widget.board_theme is BoardTheme.WALNUT
    assert window.piece_set_combo.count() == 2
    assert window.board_theme_combo.count() == 5

    window.piece_set_combo.setCurrentIndex(
        window.piece_set_combo.findData(PieceSet.CLASSIC_SYMBOLS.value)
    )
    window.board_theme_combo.setCurrentIndex(
        window.board_theme_combo.findData(BoardTheme.BLUE.value)
    )

    assert window.board_widget.piece_set is PieceSet.CLASSIC_SYMBOLS
    assert window.board_widget.board_theme is BoardTheme.BLUE
    assert store.load().appearance == AppearanceSettings(
        piece_set=PieceSet.CLASSIC_SYMBOLS,
        board_theme=BoardTheme.BLUE,
    )
    assert session.snapshot().fen == original.fen
    assert session.snapshot().move_history == original.move_history

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


def test_gui_draw_button_offers_rejects_on_move_and_accepts_on_second_click(
    qt_application: QApplication,
) -> None:
    del qt_application
    session = GameSession()
    window = MainWindow(session)

    assert window.draw_button.isEnabled()
    assert window.draw_button.text() == "Offer Draw"
    assert not window.reject_draw_button.isEnabled()
    assert window.resign_button.isEnabled()

    QTest.mouseClick(window.draw_button, Qt.MouseButton.LeftButton)
    assert session.snapshot().pending_draw_offer is not None
    assert window.draw_button.text() == "Accept Draw"
    assert window.reject_draw_button.isEnabled()

    QTest.mouseClick(window.reject_draw_button, Qt.MouseButton.LeftButton)
    assert session.snapshot().pending_draw_offer is None
    assert not window.draw_button.isEnabled()
    assert not window.reject_draw_button.isEnabled()

    window.command_input.setText("e4")
    QTest.mouseClick(window.play_button, Qt.MouseButton.LeftButton)
    assert session.snapshot().pending_draw_offer is None
    assert not session.snapshot().result.is_over
    assert window.draw_button.text() == "Offer Draw"
    assert window.draw_button.isEnabled()

    QTest.mouseClick(window.draw_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(window.draw_button, Qt.MouseButton.LeftButton)
    assert session.snapshot().result.status is GameStatus.AGREED_DRAW
    assert not window.draw_button.isEnabled()
    assert not window.reject_draw_button.isEnabled()
    assert not window.resign_button.isEnabled()

    window.close()


def test_gui_resign_button_and_human_only_availability(
    qt_application: QApplication,
) -> None:
    del qt_application
    engine_to_move_settings = ApplicationSettings(
        players=PlayerSettings(white_kind=PlayerKind.ENGINE)
    )
    engine_session = GameSession(
        settings=engine_to_move_settings,
        engine_factory=lambda _settings: None,
    )
    engine_window = MainWindow(engine_session)

    assert not engine_window.draw_button.isEnabled()
    assert not engine_window.reject_draw_button.isEnabled()
    assert not engine_window.resign_button.isEnabled()
    engine_window.close()

    human_session = GameSession()
    human_window = MainWindow(human_session)
    QTest.mouseClick(human_window.resign_button, Qt.MouseButton.LeftButton)

    assert human_session.snapshot().result.status is GameStatus.RESIGNED
    assert not human_window.resign_button.isEnabled()
    assert not human_window.draw_button.isEnabled()
    assert not human_window.reject_draw_button.isEnabled()
    human_window.close()


def test_gui_draw_button_claims_rules_draw_against_engine(
    qt_application: QApplication,
) -> None:
    del qt_application
    settings = ApplicationSettings(players=PlayerSettings(black_kind=PlayerKind.ENGINE))
    session = GameSession(settings=settings, engine_factory=lambda _settings: None)
    session.load_fen("4k2r/8/8/8/8/8/8/R3K3 w - - 100 51")
    window = MainWindow(session)

    assert window.draw_button.text() == "Claim Draw"
    assert window.draw_button.isEnabled()
    assert not window.reject_draw_button.isEnabled()

    QTest.mouseClick(window.draw_button, Qt.MouseButton.LeftButton)

    assert session.snapshot().result.status is GameStatus.FIFTY_MOVE_RULE_CLAIM
    assert not window.draw_button.isEnabled()
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
    setup_dialog = window.game_setup_dialog
    assert setup_dialog is not None
    setup_dialog.accept()
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


def test_gui_can_cancel_engine_thinking_and_undo_last_engine_move(
    qt_application: QApplication,
) -> None:
    engine = GatedEngineMoves()
    settings = ApplicationSettings(
        engine=EngineSettings(enabled=True),
        players=PlayerSettings(
            white_kind=PlayerKind.ENGINE,
            black_kind=PlayerKind.ENGINE,
        ),
    )
    session = GameSession(settings=settings, engine=engine)
    window = MainWindow(session)

    wait_for_gui(qt_application, lambda: engine.thinking.is_set())
    assert session.snapshot().move_history == ("e4",)
    assert window.undo_button.isEnabled()

    QTest.mouseClick(window.undo_button, Qt.MouseButton.LeftButton)

    wait_for_gui(qt_application, lambda: engine.cancelled.is_set())
    assert session.snapshot().move_history == ()
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
    assert window.evaluation_graph.isHidden()
    window.close()


def test_post_game_analysis_preempts_live_analysis_after_resignation(
    qt_application: QApplication,
) -> None:
    engine = GatedLiveEngine()
    settings = ApplicationSettings(
        engine=EngineSettings(
            enabled=True,
            analysis_mode=EngineAnalysisMode.LIVE,
            live_analysis_max_depth=10,
        )
    )
    session = GameSession(settings=settings, engine=engine)
    session.play_text("e4")
    window = MainWindow(session)
    assert engine.live_started.wait(1.0)

    session.play_text("resign")
    window.refresh()
    assert session.snapshot().result.status is GameStatus.RESIGNED

    QTest.mouseClick(window.analyse_game_button, Qt.MouseButton.LeftButton)

    assert engine.live_cancelled.wait(1.0)
    wait_for_gui(qt_application, lambda: not window.game_analysis_active)
    assert "White ACPL" in window.analysis_view.toPlainText()
    assert "1. e4" in window.analysis_view.toPlainText()
    window.close()


def test_new_game_remains_enabled_and_cancels_post_game_analysis(
    qt_application: QApplication,
) -> None:
    engine = GatedPostGameEngine()
    settings = ApplicationSettings(engine=EngineSettings(enabled=True))
    session = GameSession(
        settings=settings,
        engine=engine,
        engine_factory=lambda _settings: None,
    )
    session.play_text("e4")
    session.play_text("resign")
    window = MainWindow(session)

    QTest.mouseClick(window.analyse_game_button, Qt.MouseButton.LeftButton)
    assert engine.started.wait(1.0)
    assert window.game_analysis_active
    assert window.new_button.isEnabled()
    assert not window.command_input.isEnabled()

    QTest.mouseClick(window.new_button, Qt.MouseButton.LeftButton)

    assert engine.cancelled.wait(1.0)
    assert not window.game_analysis_active
    setup_dialog = window.game_setup_dialog
    assert setup_dialog is not None
    setup_dialog.accept()
    assert session.snapshot().move_history == ()
    assert not session.snapshot().result.is_over
    window.close()


def test_gui_live_analysis_updates_depth_cache_and_historical_sidebar(
    qt_application: QApplication,
) -> None:
    initial = chess.Board()
    after_e4 = initial.copy(stack=False)
    after_e4.push_uci("e2e4")

    def updates(board: chess.Board, scores: tuple[int, ...]) -> tuple[PositionAnalysis, ...]:
        move = ChessMove.from_python_chess(next(iter(board.legal_moves)))
        return tuple(
            PositionAnalysis(
                fen=board.fen(),
                lines=(
                    EngineLine(
                        move=move,
                        evaluation=EngineEvaluation(score_cp=score),
                        principal_variation=(move,),
                        depth=depth,
                    ),
                ),
            )
            for depth, score in zip((5, 8, 12), scores, strict=True)
        )

    engine = FakeEngine(
        live_updates={
            initial.fen(): updates(initial, (10, 18, 24)),
            after_e4.fen(): updates(after_e4, (12, 16, 20)),
        }
    )
    settings = ApplicationSettings(
        engine=EngineSettings(
            enabled=True,
            analysis_mode=EngineAnalysisMode.LIVE,
            live_analysis_max_depth=12,
        )
    )
    session = GameSession(settings=settings, engine=engine)
    window = MainWindow(session)

    wait_for_gui(
        qt_application,
        lambda: (
            window.evaluation_bar.result is not None and window.evaluation_bar.result.depth == 12
        ),
    )
    assert window.evaluation_bar.format() == "Evaluation: +0.24"

    window.command_input.setText("e4")
    QTest.mouseClick(window.play_button, Qt.MouseButton.LeftButton)
    wait_for_gui(
        qt_application,
        lambda: (
            window.evaluation_bar.result is not None
            and window.evaluation_bar.result.fen == after_e4.fen()
            and window.evaluation_bar.result.depth == 12
        ),
    )
    assert len(session.live_analysis.cache) == 2

    window.history_slider.setValue(0)
    assert window.evaluation_bar.result is not None
    assert window.evaluation_bar.result.fen == initial.fen()
    assert window.evaluation_bar.format() == "Evaluation: +0.24"
    window.close()


def test_gui_position_change_cancels_previous_live_stream(
    qt_application: QApplication,
) -> None:
    engine = GatedLiveEngine()
    settings = ApplicationSettings(
        engine=EngineSettings(
            enabled=True,
            analysis_mode=EngineAnalysisMode.LIVE,
            live_analysis_max_depth=10,
        )
    )
    session = GameSession(settings=settings, engine=engine)
    window = MainWindow(session)
    assert engine.live_started.wait(1.0)

    session.play_text("e4")
    window.refresh()

    assert engine.live_cancelled.wait(1.0)
    wait_for_gui(qt_application, lambda: engine.live_request_count == 2)
    assert window.evaluation_bar.result is not None
    assert window.evaluation_bar.result.fen == session.snapshot().fen
    window.close()


def test_finished_game_preserves_report_graph_and_sidebar_analysis(
    qt_application: QApplication,
) -> None:
    move = ChessMove.from_uci("e2e4")
    engine = FakeEngine(
        default=PositionAnalysis(
            fen="ignored",
            lines=(
                EngineLine(
                    move=move,
                    evaluation=EngineEvaluation(score_cp=25),
                    principal_variation=(move,),
                ),
            ),
        )
    )
    settings = ApplicationSettings(engine=EngineSettings(enabled=True))
    session = GameSession(settings=settings, engine=engine)
    for command in ("f3", "e5", "g4", "Qh4#"):
        session.play_text(command)
    fens = session.position_fens()
    for ply, fen in enumerate(fens):
        session.live_analysis.cache.store(
            LiveAnalysisResult(
                position_id=position_key(fen),
                ply=ply,
                fen=fen,
                depth=10 + ply,
                evaluation=EngineEvaluation(score_cp=900),
            )
        )
    window = MainWindow(session)

    assert window.evaluation_graph.isHidden()
    QTest.mouseClick(window.analyse_game_button, Qt.MouseButton.LeftButton)
    wait_for_gui(qt_application, lambda: not window.game_analysis_active)

    assert not window.evaluation_graph.isHidden()
    assert window.evaluation_graph.values == (0.25, 0.25, 0.25, 0.25, 0.25)
    report = window.analysis_view.toPlainText()
    assert "White ACPL" in report
    assert "1. f3" in report
    assert "(0 cp)" in report

    window.history_slider.setValue(1)
    assert window.evaluation_graph.current_ply == 1
    assert window.evaluation_bar.result is not None
    assert window.evaluation_bar.result.ply == 1
    assert window.analysis_view.toPlainText() == report

    QTest.mouseClick(window.undo_button, Qt.MouseButton.LeftButton)
    assert window.evaluation_graph.isHidden()
    window.close()
