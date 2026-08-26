from types import MappingProxyType
from typing import cast

import chess
import pytest

from wizard_chess.hardware.board_state import (
    OnSquare,
    PhysicalBoardState,
    PhysicalPiece,
    PhysicalPieceColor,
    PhysicalPieceType,
    UnknownLocation,
)
from wizard_chess.hardware.models import PhysicalSynchronization


def test_standard_position_seeds_distinct_physical_piece_placement() -> None:
    board = chess.Board()
    state = PhysicalBoardState.from_chess_board(board)

    pawn = state.piece_at("e2")
    assert pawn is not None
    assert pawn.color is PhysicalPieceColor.WHITE
    assert pawn.piece_type is PhysicalPieceType.PAWN
    assert state.piece_at("e7") is not None
    assert len(state.pieces) == 32
    assert state.synchronization is PhysicalSynchronization.SYNCHRONIZED
    assert not hasattr(state, "legal_moves")


def test_physical_piece_mapping_is_immutable_and_game_remains_distinct() -> None:
    board = chess.Board()
    state = PhysicalBoardState.from_chess_board(board)
    mutable_view = cast(dict[str, PhysicalPiece], state.pieces)

    with pytest.raises(TypeError):
        mutable_view["e2"] = state.pieces["a2"]

    board.push_uci("e2e4")
    assert state.piece_at("e2") is not None
    assert state.piece_at("e4") is None


def test_completed_move_returns_new_state_and_preserves_piece_identity() -> None:
    before = PhysicalBoardState.from_chess_board(chess.Board()).with_synchronization(
        PhysicalSynchronization.EXECUTING
    )
    pawn = before.piece_at("e2")

    after = before.complete_simple_move("e2", "e4")

    assert before.piece_at("e2") == pawn
    assert before.piece_at("e4") is None
    assert after.piece_at("e2") is None
    assert after.piece_at("e4") == pawn
    assert after.synchronization is PhysicalSynchronization.SYNCHRONIZED


def test_partial_move_failure_replaces_square_with_unknown_location() -> None:
    before = PhysicalBoardState.from_chess_board(chess.Board()).with_synchronization(
        PhysicalSynchronization.EXECUTING
    )
    pawn = before.piece_at("e2")
    assert pawn is not None

    failed = before.mark_move_uncertain("e2", "carriage stopped between squares")

    assert failed.piece_at("e2") is None
    assert isinstance(failed.location_of(pawn.identifier), UnknownLocation)
    assert failed.synchronization is PhysicalSynchronization.UNKNOWN
    assert not failed.matches_chess_board(chess.Board())


def test_known_location_value_validates_and_normalizes_square() -> None:
    assert OnSquare("E2").square == "e2"
    with pytest.raises(ValueError, match="Invalid chess square"):
        OnSquare("i9")


def test_piece_placement_comparison_ignores_non_placement_chess_metadata() -> None:
    board = chess.Board()
    state = PhysicalBoardState.from_chess_board(board)
    same_placement_different_turn = chess.Board(board.fen()).mirror().mirror()
    same_placement_different_turn.turn = chess.BLACK

    assert state.matches_chess_board(same_placement_different_turn)
    assert isinstance(state.placement_symbols(), MappingProxyType)
