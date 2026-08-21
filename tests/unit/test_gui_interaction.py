import pytest

from wizard_chess.application.session import GameSession
from wizard_chess.domain.exceptions import InvalidMoveError
from wizard_chess.domain.move import ChessMove
from wizard_chess.gui.interaction import (
    BoardInteraction,
    BoardOrientation,
    cell_for_square,
    square_for_cell,
)
from wizard_chess.hardware.simulated_board import SimulatedPhysicalBoard


@pytest.mark.parametrize(
    ("row", "column", "white_square", "black_square"),
    [(0, 0, "a8", "h1"), (0, 7, "h8", "a1"), (7, 0, "a1", "h8"), (7, 7, "h1", "a8")],
)
def test_board_coordinate_mapping_in_both_orientations(
    row: int, column: int, white_square: str, black_square: str
) -> None:
    assert square_for_cell(row, column, BoardOrientation.WHITE) == white_square
    assert square_for_cell(row, column, BoardOrientation.BLACK) == black_square
    assert cell_for_square(white_square, BoardOrientation.WHITE) == (row, column)
    assert cell_for_square(black_square, BoardOrientation.BLACK) == (row, column)


def test_piece_selection_uses_authoritative_legal_destinations() -> None:
    interaction = BoardInteraction(GameSession())

    interaction.click_square("e2")

    assert interaction.selected_square == "e2"
    assert set(interaction.legal_destinations) == {"e3", "e4"}


def test_click_to_move_executes_authoritative_move_event() -> None:
    physical_board = SimulatedPhysicalBoard()
    session = GameSession(physical_board)
    interaction = BoardInteraction(session)

    interaction.click_square("e2")
    result = interaction.click_square("e4")

    assert result.move_event is not None
    assert result.move_event.uci == "e2e4"
    assert session.snapshot().piece_at("e4") == "P"
    assert interaction.selected_square is None
    assert physical_board.events == [result.move_event]


def test_illegal_click_does_not_mutate_or_emit_event() -> None:
    physical_board = SimulatedPhysicalBoard()
    session = GameSession(physical_board)
    interaction = BoardInteraction(session)
    initial_fen = session.snapshot().fen

    interaction.click_square("e2")
    result = interaction.click_square("e5")

    assert result.move_event is None
    assert session.snapshot().fen == initial_fen
    assert physical_board.events == []
    assert interaction.selected_square is None


def test_clicking_another_movable_piece_switches_selection() -> None:
    interaction = BoardInteraction(GameSession())

    interaction.click_square("e2")
    interaction.click_square("g1")

    assert interaction.selected_square == "g1"
    assert set(interaction.legal_destinations) == {"f3", "h3"}


def test_flip_is_presentation_only_and_click_mapping_remains_correct() -> None:
    physical_board = SimulatedPhysicalBoard()
    session = GameSession(physical_board)
    interaction = BoardInteraction(session)
    original = session.snapshot()

    interaction.flip()
    assert interaction.orientation is BoardOrientation.BLACK
    assert session.snapshot().fen == original.fen
    assert session.snapshot().move_history == original.move_history
    assert physical_board.events == []

    source_cell = cell_for_square("e2", interaction.orientation)
    target_cell = cell_for_square("e4", interaction.orientation)
    interaction.click_square(square_for_cell(*source_cell, interaction.orientation))
    interaction.click_square(square_for_cell(*target_cell, interaction.orientation))

    assert session.snapshot().last_move == ChessMove("e2", "e4")
    assert [event.uci for event in physical_board.events] == ["e2e4"]


def test_click_promotion_requires_choice_and_supports_underpromotion() -> None:
    session = GameSession()
    session.load_fen("8/4P2k/8/8/8/8/8/K7 w - - 0 1")
    interaction = BoardInteraction(session)

    interaction.click_square("e7")
    request = interaction.click_square("e8")
    assert request.promotion_choices == ("q", "r", "b", "n")
    assert session.snapshot().piece_at("e7") == "P"

    result = interaction.click_square("e8", "n")
    assert result.move_event is not None
    assert result.move_event.uci == "e7e8n"
    assert session.snapshot().piece_at("e8") == "N"


def test_invalid_promotion_choice_is_rejected_without_mutation() -> None:
    session = GameSession()
    session.load_fen("8/4P2k/8/8/8/8/8/K7 w - - 0 1")
    interaction = BoardInteraction(session)
    interaction.click_square("e7")
    original_fen = session.snapshot().fen

    with pytest.raises(InvalidMoveError, match="Invalid promotion"):
        interaction.click_square("e8", "king")

    assert session.snapshot().fen == original_fen


def test_click_castling_uses_normal_domain_move() -> None:
    session = GameSession()
    session.load_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    interaction = BoardInteraction(session)

    interaction.click_square("e1")
    assert {"c1", "g1"}.issubset(interaction.legal_destinations)
    result = interaction.click_square("g1")

    assert result.move_event is not None
    assert result.move_event.is_castling
    assert session.snapshot().piece_at("g1") == "K"
    assert session.snapshot().piece_at("f1") == "R"


def test_click_en_passant_comes_from_authoritative_legal_moves() -> None:
    session = GameSession()
    session.load_fen("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
    interaction = BoardInteraction(session)

    interaction.click_square("e5")
    assert "d6" in interaction.legal_destinations
    result = interaction.click_square("d6")

    assert result.move_event is not None
    assert result.move_event.is_en_passant
    assert session.snapshot().piece_at("d6") == "P"
    assert session.snapshot().piece_at("d5") is None


def test_move_event_equivalence_for_san_coordinates_and_clicks() -> None:
    boards = [SimulatedPhysicalBoard() for _ in range(3)]
    sessions = [GameSession(board) for board in boards]

    sessions[0].play_text("e4")
    sessions[1].play_text("e2 e4")
    interaction = BoardInteraction(sessions[2])
    interaction.click_square("e2")
    interaction.click_square("e4")

    assert boards[0].events == boards[1].events == boards[2].events
    assert all(session.snapshot().last_move == ChessMove("e2", "e4") for session in sessions)
