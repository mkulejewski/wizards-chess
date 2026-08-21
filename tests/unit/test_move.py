import chess
import pytest

from wizard_chess.domain.exceptions import InvalidMoveError
from wizard_chess.domain.move import ChessMove


def test_move_normalizes_and_converts_coordinates() -> None:
    move = ChessMove("E2", "E4")

    assert move.source == "e2"
    assert move.target == "e4"
    assert move.uci() == "e2e4"
    assert move.to_python_chess() == chess.Move.from_uci("e2e4")


def test_move_round_trip_with_promotion() -> None:
    move = ChessMove.from_uci("a7a8n")

    assert move == ChessMove("a7", "a8", "n")
    assert ChessMove.from_python_chess(move.to_python_chess()) == move


def test_move_renders_san_with_position_context() -> None:
    assert ChessMove("g1", "f3").san(chess.Board()) == "Nf3"


@pytest.mark.parametrize(
    ("source", "target", "promotion"),
    [("z2", "e4", None), ("e2", "e9", None), ("a7", "a8", "king")],
)
def test_invalid_move_values_are_rejected(source: str, target: str, promotion: str | None) -> None:
    with pytest.raises(InvalidMoveError):
        ChessMove(source, target, promotion)


def test_san_rejects_move_illegal_in_context() -> None:
    with pytest.raises(InvalidMoveError):
        ChessMove("e2", "e5").san(chess.Board())
