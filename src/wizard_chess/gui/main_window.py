"""Main PySide6 window for the playable Wizard Chess desktop interface."""

from collections.abc import Callable
from typing import ClassVar

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from wizard_chess.application.session import GameSession
from wizard_chess.domain.exceptions import WizardChessError
from wizard_chess.gui.board_widget import ChessBoardWidget
from wizard_chess.gui.interaction import BoardInteraction, ClickResult
from wizard_chess.gui.view_model import format_game_status, format_move_history


class MainWindow(QMainWindow):
    """Thin GUI adapter over one shared authoritative game session."""

    _PROMOTION_LABELS: ClassVar[dict[str, str]] = {
        "Queen": "q",
        "Rook": "r",
        "Bishop": "b",
        "Knight": "n",
    }

    def __init__(self, session: GameSession | None = None) -> None:
        super().__init__()
        self.session = session or GameSession()
        self.interaction = BoardInteraction(self.session)
        self.setWindowTitle("Wizard Chess")
        self.resize(1040, 760)

        self.board_widget = ChessBoardWidget()
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
        self.new_button = QPushButton("New Game")
        self.undo_button = QPushButton("Undo")
        self.redo_button = QPushButton("Redo")
        self.flip_button = QPushButton("Flip Board")
        self.fen_input = QLineEdit()
        self.load_fen_button = QPushButton("Load FEN")
        self.copy_fen_button = QPushButton("Copy FEN")

        self._build_layout()
        self._connect_signals()
        self.refresh()

    def refresh(self) -> None:
        """Rerender every stateful view from the authoritative session."""
        snapshot = self.session.snapshot()
        self.board_widget.render_position(
            snapshot,
            self.interaction.selected_square,
            self.interaction.legal_destinations,
            self.interaction.orientation,
        )
        self.history_view.setPlainText(format_move_history(snapshot.move_history))
        self.status_label.setText(format_game_status(snapshot))
        self.fen_input.setText(snapshot.fen)
        self.undo_button.setEnabled(snapshot.can_undo)
        self.redo_button.setEnabled(snapshot.can_redo)
        self.command_input.setEnabled(not snapshot.result.is_over)
        self.play_button.setEnabled(not snapshot.result.is_over)

    def _build_layout(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)

        actions = QHBoxLayout()
        actions.addWidget(self.new_button)
        actions.addWidget(self.undo_button)
        actions.addWidget(self.redo_button)
        actions.addWidget(self.flip_button)
        actions.addStretch()
        outer.addLayout(actions)

        side_panel = QWidget()
        side_layout = QVBoxLayout(side_panel)
        history_title = QLabel("Move history")
        history_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        side_layout.addWidget(history_title)
        side_layout.addWidget(self.history_view, 1)
        side_layout.addWidget(QLabel("Position (FEN)"))
        side_layout.addWidget(self.fen_input)
        fen_actions = QHBoxLayout()
        fen_actions.addWidget(self.load_fen_button)
        fen_actions.addWidget(self.copy_fen_button)
        side_layout.addLayout(fen_actions)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.board_widget)
        splitter.addWidget(side_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([720, 300])
        outer.addWidget(splitter, 1)

        command_row = QHBoxLayout()
        command_row.addWidget(QLabel("Move:"))
        command_row.addWidget(self.command_input, 1)
        command_row.addWidget(self.play_button)
        outer.addLayout(command_row)

        self.status_label.setStyleSheet("font-size: 17px; font-weight: 600;")
        self.feedback_label.setStyleSheet("color: #8b3a2b;")
        outer.addWidget(self.status_label)
        outer.addWidget(self.feedback_label)
        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self.board_widget.square_clicked.connect(self._on_board_square)
        self.play_button.clicked.connect(self._submit_text)
        self.command_input.returnPressed.connect(self._submit_text)
        self.new_button.clicked.connect(self._new_game)
        self.undo_button.clicked.connect(self._undo)
        self.redo_button.clicked.connect(self._redo)
        self.flip_button.clicked.connect(self._flip)
        self.load_fen_button.clicked.connect(self._load_fen)
        self.copy_fen_button.clicked.connect(self._copy_fen)

    def _on_board_square(self, square: str) -> None:
        try:
            result = self.interaction.click_square(square)
            if result.promotion_choices:
                result = self._choose_promotion(square, result)
            if result.move_event is not None:
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
            self.interaction.clear_selection()
            self._show_feedback(result.message or "Done.", error=False)
        except WizardChessError as error:
            self._show_feedback(str(error))
        self.refresh()

    def _new_game(self) -> None:
        self.session.new_game()
        self.interaction.clear_selection()
        self._show_feedback("Started a new game.", error=False)
        self.refresh()

    def _undo(self) -> None:
        self._perform_state_action(
            lambda: f"Undid: {self.session.undo().uci()}",
        )

    def _redo(self) -> None:
        self._perform_state_action(
            lambda: f"Redid: {self.session.redo().san}",
        )

    def _perform_state_action(self, action: Callable[[], str]) -> None:
        try:
            message = action()
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
        try:
            self.session.load_fen(self.fen_input.text())
            self.interaction.clear_selection()
            self._show_feedback("FEN loaded.", error=False)
        except WizardChessError as error:
            self._show_feedback(str(error))
        self.refresh()

    def _copy_fen(self) -> None:
        QApplication.clipboard().setText(self.session.snapshot().fen)
        self._show_feedback("FEN copied.", error=False)

    def _show_feedback(self, message: str, *, error: bool = True) -> None:
        color = "#8b3a2b" if error else "#386641"
        self.feedback_label.setStyleSheet(f"color: {color};")
        self.feedback_label.setText(message)

    def closeEvent(self, event: QCloseEvent) -> None:
        event.accept()
