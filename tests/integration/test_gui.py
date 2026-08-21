from collections.abc import Iterator

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from wizard_chess.application.session import GameSession
from wizard_chess.gui.main_window import MainWindow
from wizard_chess.hardware.simulated_board import SimulatedPhysicalBoard


@pytest.fixture(scope="module")
def qt_application() -> Iterator[QApplication]:
    existing = QApplication.instance()
    application = existing if isinstance(existing, QApplication) else QApplication([])
    yield application


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
