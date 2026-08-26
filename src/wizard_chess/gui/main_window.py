"""Main PySide6 window for the playable Wizard Chess desktop interface."""

from collections.abc import Callable
from dataclasses import replace
from typing import ClassVar, cast

import chess
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from wizard_chess.analysis.live import AnalysisSelection, LiveAnalysisResult
from wizard_chess.analysis.models import GameAnalysis
from wizard_chess.application.session import GameSession, PositionSnapshot, SessionResult
from wizard_chess.configuration import (
    AppearanceSettings,
    ApplicationSettings,
    BoardTheme,
    EngineAnalysisMode,
    PieceSet,
    VoiceLanguage,
)
from wizard_chess.domain.exceptions import WizardChessError
from wizard_chess.domain.move import ChessMove
from wizard_chess.engine.base import ChessEngine
from wizard_chess.engine.models import EngineDecision, PositionAnalysis
from wizard_chess.gui.analysis_worker import GameAnalysisWorker, format_game_analysis
from wizard_chess.gui.board_widget import ChessBoardWidget
from wizard_chess.gui.engine_preferences import EnginePreferencesDialog, EngineValidator
from wizard_chess.gui.engine_worker import EngineWorker
from wizard_chess.gui.evaluation_widgets import (
    EvaluationGraph,
    EvaluationSidebar,
    game_analysis_evaluations,
)
from wizard_chess.gui.game_setup import GameSetupDialog
from wizard_chess.gui.interaction import BoardInteraction, ClickResult
from wizard_chess.gui.live_analysis_worker import LiveAnalysisWorker
from wizard_chess.gui.view_model import format_game_status, format_move_history
from wizard_chess.gui.voice_worker import VoiceWorker
from wizard_chess.persistence.pgn_store import PgnStore
from wizard_chess.persistence.settings_store import SettingsStore
from wizard_chess.speech.config import VoiceConfig
from wizard_chess.speech.controller import VoiceController
from wizard_chess.speech.exceptions import VoiceCommandRejected
from wizard_chess.speech.factory import create_default_voice_controller
from wizard_chess.speech.models import VoiceCommandResult, VoiceState


class MainWindow(QMainWindow):
    """Thin GUI adapter over one shared authoritative game session."""

    _PROMOTION_LABELS: ClassVar[dict[str, str]] = {
        "Queen": "q",
        "Rook": "r",
        "Bishop": "b",
        "Knight": "n",
    }
    _PIECE_SET_LABELS: ClassVar[dict[PieceSet, str]] = {
        PieceSet.TATIANA: "Tatiana",
        PieceSet.CLASSIC_SYMBOLS: "Classic symbols",
    }
    _BOARD_THEME_LABELS: ClassVar[dict[BoardTheme, str]] = {
        BoardTheme.WALNUT: "Walnut",
        BoardTheme.BROWN: "Classic brown",
        BoardTheme.GREEN: "Tournament green",
        BoardTheme.BLUE: "Ocean blue",
        BoardTheme.SLATE: "Midnight slate",
    }

    def __init__(
        self,
        session: GameSession | None = None,
        voice_controller: VoiceController[SessionResult] | None = None,
        settings_store: SettingsStore | None = None,
        persistent_settings: ApplicationSettings | None = None,
        startup_setup_pending: bool = False,
        engine_validator: EngineValidator | None = None,
    ) -> None:
        super().__init__()
        self.session = session or GameSession()
        self._owns_voice_controller = voice_controller is None
        self._settings_store = settings_store
        self._persistent_settings = (
            persistent_settings
            if persistent_settings is not None
            else settings_store.load()
            if settings_store is not None
            else self.session.settings
        )
        self._startup_setup_pending = startup_setup_pending
        self._startup_dialog_open = False
        self._engine_validator = engine_validator
        self._game_setup_dialog: GameSetupDialog | None = None
        self._engine_preferences_dialog: EnginePreferencesDialog | None = None
        self.voice_controller = voice_controller or create_default_voice_controller(
            self.session.play_text
        )
        self._voice_worker: VoiceWorker | None = None
        self._engine_worker: EngineWorker | None = None
        self._live_analysis_worker: LiveAnalysisWorker | None = None
        self._game_analysis_worker: GameAnalysisWorker | None = None
        self._completed_game_analysis: GameAnalysis | None = None
        self._engine_failed = False
        self._analysis_failed = False
        self._timeout_refresh_revision: int | None = None
        self._closing = False
        self._viewed_ply: int | None = None
        self.interaction = BoardInteraction(self.session)
        self.setWindowTitle("Wizard Chess")
        self.resize(1040, 760)

        self.board_widget = ChessBoardWidget(self._persistent_settings.appearance)
        self.history_view = QPlainTextEdit()
        self.history_view.setReadOnly(True)
        self.history_view.setPlaceholderText("Moves will appear here")
        self.status_label = QLabel()
        self.status_label.setObjectName("gameStatus")
        self.feedback_label = QLabel()
        self.feedback_label.setWordWrap(True)
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Enter SAN or coordinates, e.g. Nf3 or g1 f3")
        self.play_button = QPushButton("Play")
        self.voice_button = QPushButton("Speak Move")
        self.voice_button.setAccessibleName("Speak Move")
        self.voice_status_label = QLabel("Voice: Idle")
        self.voice_status_label.setWordWrap(True)
        self.new_button = QPushButton("New Game…")
        self.preferences_button = QPushButton("Preferences…")
        self.undo_button = QPushButton("Undo")
        self.redo_button = QPushButton("Redo")
        self.draw_button = QPushButton("Offer Draw")
        self.reject_draw_button = QPushButton("Reject Draw")
        self.resign_button = QPushButton("Resign")
        self.flip_button = QPushButton("Flip Board")
        self.fen_input = QLineEdit()
        self.load_fen_button = QPushButton("Load FEN")
        self.copy_fen_button = QPushButton("Copy FEN")
        self.import_pgn_button = QPushButton("Import PGN")
        self.export_pgn_button = QPushButton("Export PGN")
        self.engine_status_label = QLabel("Engine: Disabled")
        self.engine_status_label.setWordWrap(True)
        self.evaluation_bar = EvaluationSidebar()
        self.evaluation_graph = EvaluationGraph()
        self.evaluation_graph.setVisible(False)
        self.analysis_view = QPlainTextEdit()
        self.analysis_view.setReadOnly(True)
        self.analysis_view.setMaximumHeight(150)
        self.analysis_view.setPlaceholderText("Candidate moves and principal variation")
        self.analyse_game_button = QPushButton("Analyse game")
        self.history_slider = QSlider(Qt.Orientation.Horizontal)
        self.history_slider.setMinimum(0)
        self.history_slider.setMaximum(0)
        self.history_position_label = QLabel("Live position")
        self.live_position_button = QPushButton("Return to live")
        self.live_position_button.setEnabled(False)
        self.clock_label = QLabel("Clocks disabled")
        self.clock_button = QPushButton("Start clock")
        self.reset_clock_button = QPushButton("Reset clock")
        self.language_combo = QComboBox()
        self.language_combo.addItem("English", VoiceLanguage.ENGLISH.value)
        self.language_combo.addItem("Polski", VoiceLanguage.POLISH.value)
        language_index = self.language_combo.findData(self.session.voice_language.value)
        self.language_combo.setCurrentIndex(max(0, language_index))
        self.piece_set_combo = QComboBox()
        self.piece_set_combo.setAccessibleName("Piece set")
        for piece_set, label in self._PIECE_SET_LABELS.items():
            self.piece_set_combo.addItem(label, piece_set.value)
        piece_set_index = self.piece_set_combo.findData(
            self._persistent_settings.appearance.piece_set.value
        )
        self.piece_set_combo.setCurrentIndex(max(0, piece_set_index))
        self.board_theme_combo = QComboBox()
        self.board_theme_combo.setAccessibleName("Board look")
        for board_theme, label in self._BOARD_THEME_LABELS.items():
            self.board_theme_combo.addItem(label, board_theme.value)
        board_theme_index = self.board_theme_combo.findData(
            self._persistent_settings.appearance.board_theme.value
        )
        self.board_theme_combo.setCurrentIndex(max(0, board_theme_index))

        self._build_layout()
        self._connect_signals()
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(250)
        self._clock_timer.timeout.connect(self._refresh_clock)
        self._clock_timer.start()
        self.refresh()

    @property
    def voice_active(self) -> bool:
        """Return whether the GUI currently owns a running voice worker."""
        return self._voice_worker is not None

    @property
    def game_analysis_active(self) -> bool:
        """Return whether post-game analysis is running in the background."""
        return self._game_analysis_worker is not None

    @property
    def game_setup_dialog(self) -> GameSetupDialog | None:
        """Expose the currently open setup dialog for deterministic GUI adapters/tests."""
        return self._game_setup_dialog

    @property
    def engine_preferences_dialog(self) -> EnginePreferencesDialog | None:
        """Expose the currently open preferences dialog, if any."""
        return self._engine_preferences_dialog

    def refresh(self) -> None:
        """Rerender every stateful view from the authoritative session."""
        live_snapshot = self.session.snapshot()
        if (
            self._completed_game_analysis is not None
            and self._completed_game_analysis.source_pgn != live_snapshot.pgn
        ):
            self._completed_game_analysis = None
        snapshot = (
            self.session.snapshot_at(self._viewed_ply)
            if self._viewed_ply is not None
            else live_snapshot
        )
        self.board_widget.render_position(
            snapshot,
            self.interaction.selected_square,
            self.interaction.legal_destinations,
            self.interaction.orientation,
        )
        self.history_view.setPlainText(format_move_history(live_snapshot.move_history))
        self.status_label.setText(
            f"Viewing position after ply {self._viewed_ply}"
            if self._viewed_ply is not None
            else format_game_status(live_snapshot)
        )
        self.fen_input.setText(snapshot.fen)
        self.undo_button.setEnabled(live_snapshot.can_undo)
        self.redo_button.setEnabled(live_snapshot.can_redo)
        live_input_enabled = self._viewed_ply is None and not live_snapshot.result.is_over
        draw_button_text = "Offer Draw"
        if live_snapshot.pending_draw_offer is not None:
            draw_button_text = "Accept Draw"
        elif live_snapshot.result.can_claim_draw:
            draw_button_text = "Claim Draw"
        self.draw_button.setText(draw_button_text)
        self.draw_button.setEnabled(self._viewed_ply is None and live_snapshot.can_request_draw)
        self.reject_draw_button.setEnabled(
            self._viewed_ply is None and live_snapshot.can_reject_draw
        )
        self.resign_button.setEnabled(self._viewed_ply is None and live_snapshot.can_resign)
        self.board_widget.setEnabled(self._viewed_ply is None)
        self.command_input.setEnabled(live_input_enabled)
        self.play_button.setEnabled(live_input_enabled)
        self.voice_button.setEnabled(live_input_enabled and not self.voice_active)
        move_count = len(live_snapshot.move_history)
        self.history_slider.blockSignals(True)
        self.history_slider.setMaximum(move_count)
        self.history_slider.setValue(
            self._viewed_ply if self._viewed_ply is not None else move_count
        )
        self.history_slider.blockSignals(False)
        self.history_position_label.setText(
            f"After ply {self._viewed_ply} of {move_count}"
            if self._viewed_ply is not None
            else f"Live position · {move_count} plies"
        )
        self.live_position_button.setEnabled(self._viewed_ply is not None)
        self._refresh_clock()
        displayed_ply = (
            self._viewed_ply if self._viewed_ply is not None else len(live_snapshot.move_history)
        )
        selection = self.session.live_analysis.select(snapshot.fen, displayed_ply)
        displayed_board = chess.Board(snapshot.fen)
        if displayed_board.is_game_over(claim_draw=False):
            self.session.live_analysis.store_terminal(selection, displayed_board)
        cached = self.session.live_analysis.cache.get_best(selection.position_id)
        if cached is not None:
            self._render_live_result(cached)
        elif self.session.analysis_mode is EngineAnalysisMode.OFF:
            self.evaluation_bar.clear("off")
        else:
            self.evaluation_bar.clear()
            if not self._game_analysis_report_is_current():
                self.analysis_view.clear()
        self._refresh_evaluation_graph(live_snapshot, displayed_ply)
        self._request_engine_work(live_snapshot, snapshot, selection)

    def _build_layout(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)

        actions = QHBoxLayout()
        actions.addWidget(self.new_button)
        actions.addWidget(self.preferences_button)
        actions.addWidget(self.undo_button)
        actions.addWidget(self.redo_button)
        actions.addWidget(self.draw_button)
        actions.addWidget(self.reject_draw_button)
        actions.addWidget(self.resign_button)
        actions.addWidget(self.flip_button)
        actions.addStretch()
        outer.addLayout(actions)

        side_panel = QWidget()
        side_layout = QVBoxLayout(side_panel)
        history_title = QLabel("Move history")
        history_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        side_layout.addWidget(history_title)
        side_layout.addWidget(self.history_view, 1)
        side_layout.addWidget(self.history_position_label)
        history_navigation = QHBoxLayout()
        history_navigation.addWidget(self.history_slider, 1)
        history_navigation.addWidget(self.live_position_button)
        side_layout.addLayout(history_navigation)
        side_layout.addWidget(QLabel("Position (FEN)"))
        side_layout.addWidget(self.fen_input)
        fen_actions = QHBoxLayout()
        fen_actions.addWidget(self.load_fen_button)
        fen_actions.addWidget(self.copy_fen_button)
        side_layout.addLayout(fen_actions)
        pgn_actions = QHBoxLayout()
        pgn_actions.addWidget(self.import_pgn_button)
        pgn_actions.addWidget(self.export_pgn_button)
        side_layout.addLayout(pgn_actions)

        engine_group = QGroupBox("Engine analysis")
        engine_layout = QVBoxLayout(engine_group)
        engine_layout.addWidget(self.engine_status_label)
        engine_layout.addWidget(self.evaluation_bar)
        engine_layout.addWidget(self.analysis_view)
        engine_layout.addWidget(self.analyse_game_button)
        side_layout.addWidget(engine_group)

        settings_group = QGroupBox("Play settings")
        settings_layout = QVBoxLayout(settings_group)
        language_row = QHBoxLayout()
        language_row.addWidget(QLabel("Voice language:"))
        language_row.addWidget(self.language_combo)
        settings_layout.addLayout(language_row)
        settings_layout.addWidget(self.clock_label)
        clock_actions = QHBoxLayout()
        clock_actions.addWidget(self.clock_button)
        clock_actions.addWidget(self.reset_clock_button)
        settings_layout.addLayout(clock_actions)
        side_layout.addWidget(settings_group)

        appearance_group = QGroupBox("Board appearance")
        appearance_layout = QVBoxLayout(appearance_group)
        piece_set_row = QHBoxLayout()
        piece_set_row.addWidget(QLabel("Pieces:"))
        piece_set_row.addWidget(self.piece_set_combo, 1)
        appearance_layout.addLayout(piece_set_row)
        board_theme_row = QHBoxLayout()
        board_theme_row.addWidget(QLabel("Board:"))
        board_theme_row.addWidget(self.board_theme_combo, 1)
        appearance_layout.addLayout(board_theme_row)
        side_layout.addWidget(appearance_group)

        board_panel = QWidget()
        board_layout = QVBoxLayout(board_panel)
        board_layout.setContentsMargins(0, 0, 0, 0)
        board_row = QHBoxLayout()
        board_row.setContentsMargins(0, 0, 0, 0)
        board_row.addWidget(self.board_widget, 1)
        board_row.addWidget(self.evaluation_bar)
        board_layout.addLayout(board_row, 1)
        board_layout.addWidget(self.evaluation_graph)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(board_panel)
        splitter.addWidget(side_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([720, 300])
        outer.addWidget(splitter, 1)

        command_row = QHBoxLayout()
        command_row.addWidget(QLabel("Move:"))
        command_row.addWidget(self.command_input, 1)
        command_row.addWidget(self.play_button)
        command_row.addWidget(self.voice_button)
        outer.addLayout(command_row)

        self.status_label.setStyleSheet("font-size: 17px; font-weight: 600;")
        self.feedback_label.setStyleSheet("color: #8b3a2b;")
        outer.addWidget(self.status_label)
        outer.addWidget(self.voice_status_label)
        outer.addWidget(self.feedback_label)
        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self.board_widget.square_clicked.connect(self._on_board_square)
        self.play_button.clicked.connect(self._submit_text)
        self.command_input.returnPressed.connect(self._submit_text)
        self.voice_button.clicked.connect(self._start_voice)
        self.new_button.clicked.connect(self._new_game)
        self.preferences_button.clicked.connect(self._open_preferences)
        self.undo_button.clicked.connect(self._undo)
        self.redo_button.clicked.connect(self._redo)
        self.draw_button.clicked.connect(self._draw)
        self.reject_draw_button.clicked.connect(self._reject_draw)
        self.resign_button.clicked.connect(self._resign)
        self.flip_button.clicked.connect(self._flip)
        self.load_fen_button.clicked.connect(self._load_fen)
        self.copy_fen_button.clicked.connect(self._copy_fen)
        self.import_pgn_button.clicked.connect(self._import_pgn)
        self.export_pgn_button.clicked.connect(self._export_pgn)
        self.clock_button.clicked.connect(self._toggle_clock)
        self.reset_clock_button.clicked.connect(self._reset_clock)
        self.language_combo.currentIndexChanged.connect(self._change_language)
        self.piece_set_combo.currentIndexChanged.connect(self._change_appearance)
        self.board_theme_combo.currentIndexChanged.connect(self._change_appearance)
        self.history_slider.valueChanged.connect(self._view_history_position)
        self.live_position_button.clicked.connect(self._return_to_live_position)
        self.analyse_game_button.clicked.connect(self._start_game_analysis)
        self.evaluation_graph.ply_selected.connect(self.history_slider.setValue)

    def _on_board_square(self, square: str) -> None:
        try:
            result = self.interaction.click_square(square)
            if result.promotion_choices:
                result = self._choose_promotion(square, result)
            if result.move_event is not None:
                self._viewed_ply = None
                self._show_feedback(f"Played: {result.move_event.san}", error=False)
        except WizardChessError as error:
            self._show_feedback(str(error))
        self.refresh()

    def _choose_promotion(self, square: str, result: ClickResult) -> ClickResult:
        available_labels = [
            label
            for label, code in self._PROMOTION_LABELS.items()
            if code in result.promotion_choices
        ]
        label, accepted = QInputDialog.getItem(
            self,
            "Choose promotion",
            "Promote pawn to:",
            available_labels,
            0,
            False,
        )
        if not accepted:
            return result
        return self.interaction.click_square(square, self._PROMOTION_LABELS[label])

    def _submit_text(self) -> None:
        text = self.command_input.text()
        try:
            result = self.session.play_text(text)
            if result.quit_requested:
                self.close()
                return
            self.command_input.clear()
            self._viewed_ply = None
            self.interaction.clear_selection()
            self._show_feedback(result.message or "Done.", error=False)
        except WizardChessError as error:
            self._show_feedback(str(error))
        self.refresh()

    def _start_voice(self) -> None:
        if self._voice_worker is not None:
            self.voice_status_label.setText("Voice: Already listening or processing")
            return

        worker = VoiceWorker(self.voice_controller)
        self._voice_worker = worker
        worker.state_changed.connect(self._on_voice_state)
        worker.succeeded.connect(self._on_voice_success)
        worker.failed.connect(self._on_voice_failure)
        worker.finished.connect(self._on_voice_finished)
        worker.finished.connect(worker.deleteLater)
        self._set_interaction_enabled(False)
        self.voice_status_label.setText("Voice: Listening...")
        worker.start()

    def _on_voice_state(self, state: object) -> None:
        if state is VoiceState.LISTENING:
            self.voice_status_label.setText("Voice: Listening...")
        elif state is VoiceState.PROCESSING:
            self.voice_status_label.setText("Voice: Processing...")
        elif state is VoiceState.SUCCESS:
            self.voice_status_label.setText("Voice: Success")
        elif state is VoiceState.ERROR:
            self.voice_status_label.setText("Voice: Error")

    def _on_voice_success(self, result: object) -> None:
        if not isinstance(result, VoiceCommandResult):
            self.voice_status_label.setText("Voice: Error\nUnexpected voice result.")
            return
        voice_result = cast(VoiceCommandResult[SessionResult], result)
        recognition = voice_result.recognition
        session_result = voice_result.command_result
        detail = session_result.message or "Done."
        self.voice_status_label.setText(
            f'Voice: Success\nHeard: "{recognition.transcript}"\n{detail}'
        )
        self.interaction.clear_selection()
        self._viewed_ply = None
        self._show_feedback(detail, error=False)
        if session_result.quit_requested:
            self.close()
            return
        self.refresh()

    def _on_voice_failure(self, error: object) -> None:
        if isinstance(error, VoiceCommandRejected):
            message = (
                f'Voice: Error\nHeard: "{error.recognition.transcript}"\n'
                f"{error.cause}\nPlease try again."
            )
            feedback = str(error.cause)
        elif isinstance(error, Exception):
            message = f"Voice: Error\n{error}"
            feedback = str(error)
        else:
            message = "Voice: Error\nUnexpected voice failure."
            feedback = "Unexpected voice failure."
        self.voice_status_label.setText(message)
        self._show_feedback(feedback)
        self.refresh()

    def _on_voice_finished(self) -> None:
        self._voice_worker = None
        self._set_interaction_enabled(True)
        self.refresh()

    def _set_interaction_enabled(
        self,
        enabled: bool,
        *,
        keep_new_game_enabled: bool = False,
    ) -> None:
        self.board_widget.setEnabled(enabled)
        self.command_input.setEnabled(enabled)
        self.play_button.setEnabled(enabled)
        self.new_button.setEnabled(enabled or keep_new_game_enabled)
        self.preferences_button.setEnabled(enabled)
        self.undo_button.setEnabled(enabled)
        self.redo_button.setEnabled(enabled)
        self.draw_button.setEnabled(enabled)
        self.reject_draw_button.setEnabled(enabled)
        self.resign_button.setEnabled(enabled)
        self.flip_button.setEnabled(enabled)
        self.fen_input.setEnabled(enabled)
        self.load_fen_button.setEnabled(enabled)
        self.copy_fen_button.setEnabled(enabled)
        self.import_pgn_button.setEnabled(enabled)
        self.export_pgn_button.setEnabled(enabled)
        self.clock_button.setEnabled(enabled and self.session.settings.clock.enabled)
        self.reset_clock_button.setEnabled(enabled and self.session.settings.clock.enabled)
        self.language_combo.setEnabled(enabled)
        self.piece_set_combo.setEnabled(enabled)
        self.board_theme_combo.setEnabled(enabled)
        self.history_slider.setEnabled(enabled)
        self.live_position_button.setEnabled(enabled and self._viewed_ply is not None)
        self.analyse_game_button.setEnabled(enabled)
        self.voice_button.setEnabled(enabled)

    def _new_game(self) -> None:
        if self._game_analysis_worker is not None:
            self._cancel_game_analysis()
        self._open_game_setup()

    def show_startup_setup(self) -> None:
        """Present the deferred startup setup without beginning engine play first."""
        self._startup_setup_pending = True
        self._open_game_setup(startup=True)

    def _open_game_setup(self, *, startup: bool = False) -> None:
        if self._game_setup_dialog is not None:
            self._game_setup_dialog.raise_()
            self._game_setup_dialog.activateWindow()
            return
        base = ApplicationSettings.from_environment(self._persistent_settings)
        dialog = GameSetupDialog(
            base,
            self,
            engine_available=lambda path: self._engine_path_available(path),
        )
        self._game_setup_dialog = dialog
        self._startup_dialog_open = startup
        dialog.engine_preferences_requested.connect(self._open_preferences)
        dialog.accepted.connect(self._apply_game_setup)
        dialog.rejected.connect(self._cancel_game_setup)
        dialog.finished.connect(self._game_setup_finished)
        dialog.open()

    def _apply_game_setup(self) -> None:
        dialog = self._game_setup_dialog
        if dialog is None:
            return
        selected = dialog.selected_settings()
        if selected.game_setup_saved:
            saved = selected
        else:
            saved = replace(
                self._persistent_settings,
                game_setup_saved=False,
                show_game_setup_on_startup=True,
            )
        self._save_preferences(saved)
        effective = ApplicationSettings.from_environment(selected)
        self._cancel_engine_activity()
        self.session.new_game(effective)
        self._engine_failed = False
        self._analysis_failed = False
        self._viewed_ply = None
        self.interaction.clear_selection()
        self._startup_setup_pending = False
        self._startup_dialog_open = False
        self._show_feedback("Started a new game.", error=False)
        self.refresh()

    def _cancel_game_setup(self) -> None:
        if not self._startup_dialog_open:
            return
        self._startup_dialog_open = False
        self._startup_setup_pending = False
        self.refresh()

    def _game_setup_finished(self, _result: int) -> None:
        self._game_setup_dialog = None

    def _open_preferences(self) -> None:
        if self._engine_preferences_dialog is not None:
            self._engine_preferences_dialog.raise_()
            self._engine_preferences_dialog.activateWindow()
            return
        parent = self._game_setup_dialog or self
        dialog = (
            EnginePreferencesDialog(self._persistent_settings, parent)
            if self._engine_validator is None
            else EnginePreferencesDialog(
                self._persistent_settings,
                parent,
                validator=self._engine_validator,
            )
        )
        self._engine_preferences_dialog = dialog
        dialog.accepted.connect(self._apply_engine_preferences)
        dialog.finished.connect(self._engine_preferences_finished)
        dialog.open()

    def _apply_engine_preferences(self) -> None:
        dialog = self._engine_preferences_dialog
        if dialog is None:
            return
        selected = dialog.selected_settings()
        self._save_preferences(selected)
        if self._game_setup_dialog is not None:
            self._game_setup_dialog.set_engine_settings(
                ApplicationSettings.from_environment(selected)
            )
        self._show_feedback(
            "Engine preferences saved. They apply when the next game starts.",
            error=False,
        )

    def _engine_preferences_finished(self, _result: int) -> None:
        self._engine_preferences_dialog = None

    def _save_preferences(self, settings: ApplicationSettings) -> None:
        self._persistent_settings = settings
        if self._settings_store is None:
            return
        try:
            self._settings_store.save(settings)
        except OSError:
            self._show_feedback("Preferences changed, but they could not be saved.")

    @staticmethod
    def _engine_path_available(path: str | None) -> bool:
        from wizard_chess.engine.factory import resolve_stockfish_path

        return resolve_stockfish_path(path) is not None

    def _cancel_engine_activity(self) -> None:
        if self._live_analysis_worker is not None and self._live_analysis_worker.isRunning():
            self._live_analysis_worker.cancel(stop_engine=True)
            self._live_analysis_worker.wait()
        self._live_analysis_worker = None
        if self._engine_worker is not None and self._engine_worker.isRunning():
            self._engine_worker.cancel(stop_engine=True)
            self._engine_worker.wait()
        self._engine_worker = None
        if self._game_analysis_worker is not None and self._game_analysis_worker.isRunning():
            self._game_analysis_worker.cancel(stop_engine=True)
            self._game_analysis_worker.wait()
        self._game_analysis_worker = None

    def _cancel_move_worker(self) -> None:
        if self._live_analysis_worker is not None and self._live_analysis_worker.isRunning():
            self._live_analysis_worker.cancel()
        if self._engine_worker is None or not self._engine_worker.isRunning():
            return
        self._engine_worker.cancel(stop_engine=True)

    def _undo(self) -> None:
        self._cancel_move_worker()
        self._perform_state_action(
            lambda: f"Undid: {self.session.undo().uci()}",
        )

    def _redo(self) -> None:
        self._cancel_move_worker()
        self._perform_state_action(
            lambda: f"Redid: {self.session.redo().san}",
        )

    def _draw(self) -> None:
        self._perform_state_action(
            lambda: self.session.request_draw().message or "Done.",
        )

    def _reject_draw(self) -> None:
        self._perform_state_action(
            lambda: self.session.reject_draw().message or "Done.",
        )

    def _resign(self) -> None:
        self._perform_state_action(
            lambda: self.session.resign().message or "Done.",
        )

    def _perform_state_action(self, action: Callable[[], str]) -> None:
        try:
            message = action()
            self._viewed_ply = None
            self.interaction.clear_selection()
            self._show_feedback(message, error=False)
        except WizardChessError as error:
            self._show_feedback(str(error))
        self.refresh()

    def _flip(self) -> None:
        self.interaction.flip()
        self._show_feedback(
            f"Board flipped: {self.interaction.orientation.value.title()} at bottom.",
            error=False,
        )
        self.refresh()

    def _load_fen(self) -> None:
        self._cancel_move_worker()
        try:
            self.session.load_fen(self.fen_input.text())
            self._viewed_ply = None
            self.interaction.clear_selection()
            self._show_feedback("FEN loaded.", error=False)
        except WizardChessError as error:
            self._show_feedback(str(error))
        self.refresh()

    def _copy_fen(self) -> None:
        QApplication.clipboard().setText(self.session.snapshot().fen)
        self._show_feedback("FEN copied.", error=False)

    def _import_pgn(self) -> None:
        source, _selected_filter = QFileDialog.getOpenFileName(
            self, "Import PGN", "", "Chess games (*.pgn);;All files (*)"
        )
        if not source:
            return
        self._cancel_move_worker()
        try:
            self.session.load_pgn(PgnStore().load(source))
            self._viewed_ply = None
            self.interaction.clear_selection()
            self._show_feedback("PGN imported.", error=False)
        except (OSError, WizardChessError) as error:
            self._show_feedback(str(error))
        self.refresh()

    def _export_pgn(self) -> None:
        destination, _selected_filter = QFileDialog.getSaveFileName(
            self, "Export PGN", "wizard-chess.pgn", "Chess games (*.pgn)"
        )
        if not destination:
            return
        try:
            path = self.session.save_game(destination)
            self._show_feedback(f"PGN exported: {path}", error=False)
        except OSError as error:
            self._show_feedback(str(error))

    def _toggle_clock(self) -> None:
        snapshot = self.session.snapshot().clock
        if snapshot is not None and snapshot.running:
            self.session.pause_clock()
        else:
            self.session.start_clock()
        self._refresh_clock()

    def _reset_clock(self) -> None:
        self.session.reset_clock()
        self._refresh_clock()

    def _refresh_clock(self) -> None:
        snapshot = self.session.snapshot().clock
        if snapshot is None:
            self.clock_label.setText("Clocks disabled")
            self.clock_button.setEnabled(False)
            self.reset_clock_button.setEnabled(False)
            return
        self.clock_label.setText(
            f"White {_format_clock(snapshot.white_seconds)}  ·  "
            f"Black {_format_clock(snapshot.black_seconds)}"
        )
        self.clock_button.setText("Pause clock" if snapshot.running else "Start clock")
        self.clock_button.setEnabled(True)
        self.reset_clock_button.setEnabled(True)
        if snapshot.expired is not None and self._timeout_refresh_revision != self.session.revision:
            self._timeout_refresh_revision = self.session.revision
            if self._engine_worker is not None and self._engine_worker.mode == "move":
                self._engine_worker.cancel(stop_engine=True)
            QTimer.singleShot(0, self.refresh)

    def _change_language(self, index: int) -> None:
        raw_language = self.language_combo.itemData(index)
        if not isinstance(raw_language, str):
            return
        language = VoiceLanguage(raw_language)
        self.session.set_voice_language(language)
        self._save_preferences(replace(self._persistent_settings, voice_language=language))
        if self._owns_voice_controller:
            config = replace(VoiceConfig.from_environment(), language=language)
            self.voice_controller = create_default_voice_controller(
                self.session.play_text,
                config,
            )
        self._show_feedback(
            (
                "Voice language: Polski"
                if language is VoiceLanguage.POLISH
                else "Voice language: English"
            ),
            error=False,
        )

    def _change_appearance(self, _index: int) -> None:
        raw_piece_set = self.piece_set_combo.currentData()
        raw_board_theme = self.board_theme_combo.currentData()
        if not isinstance(raw_piece_set, str) or not isinstance(raw_board_theme, str):
            return
        appearance = AppearanceSettings(
            piece_set=PieceSet(raw_piece_set),
            board_theme=BoardTheme(raw_board_theme),
        )
        self.board_widget.set_appearance(appearance)
        self._save_preferences(replace(self._persistent_settings, appearance=appearance))
        self._show_feedback(
            (
                f"Board appearance: {self._PIECE_SET_LABELS[appearance.piece_set]} pieces · "
                f"{self._BOARD_THEME_LABELS[appearance.board_theme]} board."
            ),
            error=False,
        )

    def _view_history_position(self, ply: int) -> None:
        live_ply = len(self.session.snapshot().move_history)
        self._viewed_ply = None if ply == live_ply else ply
        self.interaction.clear_selection()
        self.refresh()

    def _return_to_live_position(self) -> None:
        self._viewed_ply = None
        self.interaction.clear_selection()
        self.refresh()

    def _start_game_analysis(self) -> None:
        engine = self.session.engine
        if engine is None or self._engine_failed:
            self._show_feedback("Configure Stockfish before analysing a game.")
            return
        if self._engine_worker is not None or self._game_analysis_worker is not None:
            self._show_feedback("The engine is already busy.")
            return
        self._stop_live_analysis_for_game_analysis()
        worker = GameAnalysisWorker(
            engine,
            self.session.snapshot().pgn,
            self.session.settings.engine.post_game_analysis_time_ms,
        )
        self._completed_game_analysis = None
        self.evaluation_graph.setVisible(False)
        self._game_analysis_worker = worker
        worker.progress.connect(self._on_game_analysis_progress)
        worker.succeeded.connect(self._on_game_analysis_success)
        worker.failed.connect(self._on_game_analysis_failure)
        worker.finished.connect(self._on_game_analysis_finished)
        worker.finished.connect(worker.deleteLater)
        self._set_interaction_enabled(False, keep_new_game_enabled=True)
        self.engine_status_label.setText("Engine: Analysing game…")
        worker.start()

    def _stop_live_analysis_for_game_analysis(self) -> None:
        """Synchronously release the engine from live work for full-game analysis."""
        worker = self._live_analysis_worker
        if worker is None:
            return
        self.session.live_analysis.invalidate_selection()
        if worker.isRunning():
            worker.cancel(stop_engine=True)
            worker.wait()
        if self._live_analysis_worker is worker:
            self._live_analysis_worker = None

    def _cancel_game_analysis(self) -> None:
        worker = self._game_analysis_worker
        if worker is not None and worker.isRunning():
            worker.cancel(stop_engine=True)
            worker.wait()
        self._game_analysis_worker = None
        self._completed_game_analysis = None
        self.evaluation_graph.setVisible(False)
        self.engine_status_label.setText("Engine: Game analysis cancelled")
        self._set_interaction_enabled(True)
        self.refresh()

    def _on_game_analysis_progress(self, completed: int, total: int) -> None:
        self.engine_status_label.setText(f"Engine: Analysing game {completed}/{total}")

    def _on_game_analysis_success(self, result: object) -> None:
        if isinstance(result, GameAnalysis):
            if result.source_pgn != self.session.snapshot().pgn:
                self._completed_game_analysis = None
                self.engine_status_label.setText("Game analysis is obsolete; the game changed")
                self.evaluation_graph.setVisible(False)
                return
            self._completed_game_analysis = result
            self.engine_status_label.setText("Engine: Game analysis complete")
            self.analysis_view.setPlainText(format_game_analysis(result))
            current_ply = (
                self._viewed_ply
                if self._viewed_ply is not None
                else len(self.session.snapshot().move_history)
            )
            self._refresh_evaluation_graph(self.session.snapshot(), current_ply)

    def _on_game_analysis_failure(self, error: object) -> None:
        self._completed_game_analysis = None
        self.evaluation_graph.setVisible(False)
        self.engine_status_label.setText(f"Game analysis failed: {error}")

    def _on_game_analysis_finished(self) -> None:
        self._game_analysis_worker = None
        self._set_interaction_enabled(True)
        self.refresh()

    def _request_engine_work(
        self,
        live_snapshot: PositionSnapshot,
        displayed_snapshot: PositionSnapshot,
        selection: AnalysisSelection,
    ) -> None:
        engine = self.session.engine
        if self._startup_setup_pending:
            return
        if self._closing or engine is None:
            if engine is None:
                self.engine_status_label.setText("Engine: Disabled (ordinary play is available)")
            return
        if self._live_analysis_worker is not None:
            if self._live_analysis_worker.generation != selection.generation:
                self._live_analysis_worker.cancel()
            return
        if self._engine_worker is not None:
            expected_fen = (
                live_snapshot.fen if self._engine_worker.mode == "move" else displayed_snapshot.fen
            )
            if (
                self._engine_worker.fen != expected_fen
                or self._engine_worker.revision != self.session.revision
            ):
                self._engine_worker.cancel(stop_engine=True)
            return
        if self._game_analysis_worker is not None:
            return

        mode: str | None = None
        board = chess.Board(displayed_snapshot.fen)
        if self.session.engine_controls_turn() and not self.session.game.is_game_over():
            if self._engine_failed:
                return
            if self.session.prepare_engine_turn():
                mode = "move"
                board = self.session.game.board
            else:
                QTimer.singleShot(0, self.refresh)
                return
        elif (
            not self._analysis_failed
            and not board.is_game_over(claim_draw=False)
            and self.session.analysis_mode is EngineAnalysisMode.FIXED_TIME
            and self.session.live_analysis.needs_fixed_analysis(selection)
        ):
            mode = "analysis"
        elif (
            not self._analysis_failed
            and not board.is_game_over(claim_draw=False)
            and self.session.analysis_mode is EngineAnalysisMode.LIVE
            and self.session.live_analysis.needs_live_analysis(selection)
        ):
            self._start_live_analysis(engine, board, selection)
            return
        if mode is None:
            return

        worker = EngineWorker(
            engine,
            board,
            mode,
            revision=self.session.revision,
            clock=self.session.engine_clock_state() if mode == "move" else None,
        )
        self._engine_worker = worker
        worker.succeeded.connect(self._on_engine_success)
        worker.failed.connect(self._on_engine_failure)
        worker.finished.connect(self._on_engine_finished)
        worker.finished.connect(worker.deleteLater)
        self.engine_status_label.setText(
            "Engine: Thinking…" if mode == "move" else "Engine: Analysing…"
        )
        if mode == "move":
            self._set_interaction_enabled(False)
            # Undo remains a safe escape hatch: it cancels this worker first,
            # and session revision/FEN guards reject any already-queued result.
            self.undo_button.setEnabled(self.session.snapshot().can_undo)
        worker.start()

    def _start_live_analysis(
        self,
        engine: ChessEngine,
        board: chess.Board,
        selection: AnalysisSelection,
    ) -> None:
        worker = LiveAnalysisWorker(
            engine,
            board,
            selection,
            self.session.settings.engine.live_analysis_max_depth,
        )
        self._live_analysis_worker = worker
        worker.updated.connect(self._on_live_analysis_update)
        worker.failed.connect(self._on_live_analysis_failure)
        worker.finished.connect(self._on_live_analysis_finished)
        worker.finished.connect(worker.deleteLater)
        self.engine_status_label.setText(f"Engine: Live analysis · target depth {worker.max_depth}")
        worker.start()

    def _on_engine_success(
        self,
        fen: str,
        revision: int,
        mode: str,
        result: object,
    ) -> None:
        if mode == "move":
            if fen != self.session.snapshot().fen or revision != self.session.revision:
                return
            decision = (
                result
                if isinstance(result, EngineDecision)
                else EngineDecision(move=result)
                if isinstance(result, ChessMove)
                else None
            )
            if decision is not None:
                try:
                    event = self.session.commit_engine_decision(
                        decision,
                        expected_fen=fen,
                        expected_revision=revision,
                    )
                    if event is not None:
                        self._viewed_ply = None
                        self.interaction.clear_selection()
                        tablebase = (
                            f" · Syzygy hits: {decision.tablebase_hits}"
                            if decision.tablebase_hits
                            else ""
                        )
                        self._show_feedback(
                            f"Engine played: {event.san}{tablebase}",
                            error=False,
                        )
                        status = "Engine: Ready"
                        syzygy_status = getattr(
                            self.session.engine,
                            "syzygy_status",
                            "disabled",
                        )
                        if isinstance(syzygy_status, str) and syzygy_status != "disabled":
                            status += f" · Syzygy {syzygy_status}"
                        self.engine_status_label.setText(status)
                except WizardChessError as error:
                    self._show_feedback(str(error))
            return
        if isinstance(result, PositionAnalysis):
            selection = self.session.live_analysis.selection
            if selection is None or selection.fen != fen or revision != self.session.revision:
                return
            live_result = self.session.live_analysis.make_result(selection, result)
            self.session.live_analysis.mark_fixed_complete(selection.position_id)
            if live_result is not None and self.session.live_analysis.accept(
                selection.generation, live_result
            ):
                self._render_engine_analysis(result, live_result)

    def _on_engine_failure(
        self,
        fen: str,
        revision: int,
        mode: str,
        error: object,
    ) -> None:
        del fen, revision
        if mode == "analysis":
            self._analysis_failed = True
        else:
            self._engine_failed = True
        self.engine_status_label.setText(
            f"Engine unavailable: {error}. Ordinary chess remains available."
        )
        self.evaluation_bar.set_unavailable()

    def _on_engine_finished(self) -> None:
        worker = self.sender()
        if worker is self._engine_worker:
            self._engine_worker = None
        self._set_interaction_enabled(True)
        self.refresh()

    def _on_live_analysis_update(
        self,
        fen: str,
        generation: int,
        update: object,
    ) -> None:
        selection = self.session.live_analysis.selection
        if (
            selection is None
            or selection.generation != generation
            or selection.fen != fen
            or not isinstance(update, PositionAnalysis)
        ):
            return
        result = self.session.live_analysis.make_result(selection, update)
        if result is None or not self.session.live_analysis.accept(generation, result):
            return
        self._render_engine_analysis(update, result, live=True)

    def _on_live_analysis_failure(
        self,
        fen: str,
        generation: int,
        error: object,
    ) -> None:
        selection = self.session.live_analysis.selection
        if selection is None or selection.generation != generation or selection.fen != fen:
            return
        self._analysis_failed = True
        self.engine_status_label.setText(
            f"Analysis unavailable: {error}. Ordinary chess remains available."
        )
        if self.session.live_analysis.cache.get_best(selection.position_id) is None:
            self.evaluation_bar.set_unavailable()

    def _on_live_analysis_finished(self) -> None:
        worker = self.sender()
        if isinstance(worker, LiveAnalysisWorker) and worker is self._live_analysis_worker:
            cancelled = worker.selection.generation != (
                self.session.live_analysis.selection.generation
                if self.session.live_analysis.selection is not None
                else -1
            )
            self._live_analysis_worker = None
            if cancelled:
                QTimer.singleShot(0, self.refresh)

    def _render_engine_analysis(
        self,
        analysis: PositionAnalysis,
        result: LiveAnalysisResult,
        *,
        live: bool = False,
    ) -> None:
        best = analysis.best_line
        if best is None:
            self.engine_status_label.setText(
                "Engine: Terminal position" if analysis.terminal else "Engine: No line"
            )
            if not self._game_analysis_report_is_current():
                self.analysis_view.clear()
            return
        tablebase_hits = sum(line.tablebase_hits or 0 for line in analysis.lines)
        status = (
            f"Engine: Ready · Syzygy hits {tablebase_hits}" if tablebase_hits else "Engine: Ready"
        )
        syzygy_status = getattr(self.session.engine, "syzygy_status", "disabled")
        if isinstance(syzygy_status, str) and syzygy_status != "disabled":
            status += f" · Syzygy {syzygy_status}"
        if live:
            status = f"Engine: Live · depth {result.depth}/{self.session.live_analysis.max_depth}"
        self.engine_status_label.setText(status)
        self.evaluation_bar.set_result(result)
        if self._game_analysis_report_is_current():
            return
        board = chess.Board(analysis.fen)
        rows: list[str] = []
        for index, line in enumerate(analysis.lines, start=1):
            move = line.move.to_python_chess()
            san = board.san(move) if move in board.legal_moves else line.move.uci()
            rows.append(f"{index}. {san}  {line.evaluation.display()}")
        pv_board = board.copy(stack=False)
        pv_san: list[str] = []
        for move_value in best.principal_variation:
            move = move_value.to_python_chess()
            if move not in pv_board.legal_moves:
                break
            pv_san.append(pv_board.san(move))
            pv_board.push(move)
        if pv_san:
            rows.extend(("", f"PV: {' '.join(pv_san)}"))
        self.analysis_view.setPlainText("\n".join(rows))

    def _render_live_result(self, result: LiveAnalysisResult) -> None:
        """Immediately render a cached result for live or historical navigation."""
        self.evaluation_bar.set_result(result)
        self.engine_status_label.setText(f"Engine: Ready · cached depth {result.depth}")
        if self._game_analysis_report_is_current():
            return
        board = chess.Board(result.fen)
        pv_board = board.copy(stack=False)
        pv_san: list[str] = []
        for move_value in result.principal_variation:
            move = move_value.to_python_chess()
            if move not in pv_board.legal_moves:
                break
            pv_san.append(pv_board.san(move))
            pv_board.push(move)
        rows = [f"Evaluation {result.evaluation.display()} · depth {result.depth}"]
        if pv_san:
            rows = [f"1. {pv_san[0]}  {result.evaluation.display()}", "", *rows]
            rows.append(f"PV: {' '.join(pv_san)}")
        self.analysis_view.setPlainText("\n".join(rows))

    def _game_analysis_report_is_current(self) -> bool:
        analysis = self._completed_game_analysis
        return analysis is not None and analysis.source_pgn == self.session.snapshot().pgn

    def _refresh_evaluation_graph(
        self,
        live_snapshot: PositionSnapshot,
        displayed_ply: int,
    ) -> None:
        analysis = self._completed_game_analysis
        visible = (
            live_snapshot.result.is_over
            and analysis is not None
            and analysis.source_pgn == live_snapshot.pgn
        )
        self.evaluation_graph.setVisible(visible)
        if not visible or analysis is None:
            return
        self.evaluation_graph.set_evaluations(
            game_analysis_evaluations(analysis),
            displayed_ply,
        )

    def _show_feedback(self, message: str, *, error: bool = True) -> None:
        color = "#8b3a2b" if error else "#386641"
        self.feedback_label.setStyleSheet(f"color: {color};")
        self.feedback_label.setText(message)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._closing = True
        if self._voice_worker is not None and self._voice_worker.isRunning():
            self._voice_worker.cancel()
            self._voice_worker.wait()
        if self._engine_worker is not None and self._engine_worker.isRunning():
            self._engine_worker.cancel(stop_engine=True)
            self._engine_worker.wait()
        if self._live_analysis_worker is not None and self._live_analysis_worker.isRunning():
            self._live_analysis_worker.cancel(stop_engine=True)
            self._live_analysis_worker.wait()
        if self._game_analysis_worker is not None and self._game_analysis_worker.isRunning():
            self._game_analysis_worker.cancel(stop_engine=True)
            self._game_analysis_worker.wait()
        self.session.close()
        event.accept()


def _format_clock(seconds: float) -> str:
    total = max(0, round(seconds))
    minutes, remainder = divmod(total, 60)
    return f"{minutes:02d}:{remainder:02d}"
