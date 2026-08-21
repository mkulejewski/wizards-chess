from io import StringIO
from pathlib import Path

import chess
import chess.pgn
import pytest

from wizard_chess.domain.exceptions import (
    InvalidFenError,
    InvalidMoveError,
    NoMoveToRedoError,
    NoMoveToUndoError,
)
from wizard_chess.domain.game import ChessGame
from wizard_chess.domain.move import ChessMove
from wizard_chess.domain.results import GameStatus, PlayerColor
from wizard_chess.persistence.pgn_store import PgnStore


def play(game: ChessGame, *moves: str) -> None:
    for uci in moves:
        game.make_move(ChessMove.from_uci(uci))


def test_initial_position_and_defensive_board_copy() -> None:
    game = ChessGame()
    exposed = game.board
    exposed.push_uci("e2e4")

    assert game.turn is PlayerColor.WHITE
    assert game.fen() == chess.STARTING_FEN
    assert len(game.legal_moves()) == 20


def test_normal_piece_movement() -> None:
    game = ChessGame()
    play(
        game,
        "e2e4",  # pawn
        "e7e5",
        "g1f3",  # knight
        "b8c6",
        "f1b5",  # bishop
        "a7a6",
        "b5c6",
        "d7c6",
        "d1e2",  # queen
        "f8d6",
        "e1d1",  # king
    )

    assert game.board.king(chess.WHITE) == chess.D1
    assert game.turn is PlayerColor.BLACK


@pytest.mark.parametrize("uci", ["e7e5", "e2e5", "a1a4"])
def test_illegal_moves_are_rejected(uci: str) -> None:
    with pytest.raises(InvalidMoveError):
        ChessGame().make_move(ChessMove.from_uci(uci))


def test_cannot_move_into_check() -> None:
    game = ChessGame("4r1k1/8/8/8/8/8/8/4K3 w - - 0 1")

    with pytest.raises(InvalidMoveError):
        game.make_move(ChessMove.from_uci("e1e2"))


def test_must_resolve_existing_check() -> None:
    game = ChessGame("4r1k1/8/8/8/8/8/P7/4K3 w - - 0 1")

    with pytest.raises(InvalidMoveError, match="does not resolve the current check"):
        game.make_move(ChessMove.from_uci("a2a3"))


def test_cannot_expose_own_king_to_check() -> None:
    game = ChessGame("4r1k1/8/8/8/8/8/4R3/4K3 w - - 0 1")

    with pytest.raises(InvalidMoveError, match="would leave White's king in check"):
        game.make_move(ChessMove.from_uci("e2d2"))


@pytest.mark.parametrize(
    ("fen", "uci", "reason"),
    [
        (chess.STARTING_FEN, "e3e4", "there is no piece on e3"),
        (chess.STARTING_FEN, "e7e6", "it is White to move"),
        (chess.STARTING_FEN, "e1e2", "e2 is occupied by White's own pawn"),
        (chess.STARTING_FEN, "d1h4", "queen cannot move from d1 to h4"),
    ],
)
def test_illegal_move_errors_explain_the_reason(fen: str, uci: str, reason: str) -> None:
    with pytest.raises(InvalidMoveError, match=reason):
        ChessGame(fen).make_move(ChessMove.from_uci(uci))


def test_normal_capture_event_identifies_captured_square() -> None:
    game = ChessGame()
    play(game, "e2e4", "d7d5")

    event = game.make_move(ChessMove.from_uci("e4d5"))

    assert event.source_square == "e4"
    assert event.target_square == "d5"
    assert event.captured_square == "d5"
    assert event.san == "exd5"
    assert event.uci == "e4d5"
    assert not event.is_en_passant


@pytest.mark.parametrize(("move", "expected_san"), [("e1g1", "O-O"), ("e1c1", "O-O-O")])
def test_castling_events(move: str, expected_san: str) -> None:
    game = ChessGame("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")

    event = game.make_move(ChessMove.from_uci(move))

    assert event.is_castling
    assert event.san == expected_san


def test_castling_through_attacked_square_is_illegal() -> None:
    game = ChessGame("r3kr1r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")

    with pytest.raises(InvalidMoveError):
        game.make_move(ChessMove.from_uci("e1g1"))


def test_en_passant_event_identifies_actual_captured_square() -> None:
    game = ChessGame()
    play(game, "e2e4", "a7a6", "e4e5", "d7d5")

    event = game.make_move(ChessMove.from_uci("e5d6"))

    assert event.is_en_passant
    assert event.captured_square == "d5"
    assert event.san == "exd6"


@pytest.mark.parametrize("promotion", ["q", "r", "b", "n"])
def test_all_promotion_pieces(promotion: str) -> None:
    game = ChessGame("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")

    event = game.make_move(ChessMove("a7", "a8", promotion))

    assert event.promotion == promotion
    assert game.board.piece_at(chess.A8) == chess.Piece(
        {"q": chess.QUEEN, "r": chess.ROOK, "b": chess.BISHOP, "n": chess.KNIGHT}[promotion],
        chess.WHITE,
    )


def test_undo_redo_and_new_move_invalidation() -> None:
    game = ChessGame()
    play(game, "e2e4", "e7e5")
    after_two_moves = game.fen()

    assert game.undo() == ChessMove("e7", "e5")
    assert game.undo() == ChessMove("e2", "e4")
    assert game.fen() == chess.STARTING_FEN
    assert game.redo().uci == "e2e4"
    assert game.redo().uci == "e7e5"
    assert game.fen() == after_two_moves

    game.undo()
    game.make_move(ChessMove.from_uci("c7c5"))
    with pytest.raises(NoMoveToRedoError):
        game.redo()


def test_undo_redo_special_move() -> None:
    game = ChessGame("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    original = game.fen()
    game.make_move(ChessMove.from_uci("e1c1"))
    castled = game.fen()

    game.undo()
    assert game.fen() == original
    assert game.redo().is_castling
    assert game.fen() == castled


def test_empty_history_errors() -> None:
    game = ChessGame()

    with pytest.raises(NoMoveToUndoError):
        game.undo()
    with pytest.raises(NoMoveToRedoError):
        game.redo()


def test_fen_export_import_and_history_reset() -> None:
    game = ChessGame()
    play(game, "e2e4")
    fen = game.fen()
    game.undo()

    game.load_fen(fen)

    assert game.fen() == fen
    with pytest.raises(NoMoveToUndoError):
        game.undo()
    with pytest.raises(NoMoveToRedoError):
        game.redo()


@pytest.mark.parametrize("fen", ["not a fen", "8/8/8/8/8/8/8/8 w - - 0 1"])
def test_invalid_fen_is_an_application_error(fen: str) -> None:
    with pytest.raises(InvalidFenError):
        ChessGame(fen)


def test_check_status() -> None:
    result = ChessGame("4k3/8/8/8/8/8/4R3/4K3 b - - 0 1").result()

    assert result.status is GameStatus.CHECK
    assert result.notation == "*"


def test_move_sequence_detects_check_without_mate() -> None:
    game = ChessGame()
    play(game, "e2e4", "e7e5", "d1h5", "b8c6")

    event = game.make_move(ChessMove.from_uci("h5e5"))

    assert event.san == "Qxe5+"
    assert game.is_check()
    assert not game.is_checkmate()
    assert game.result().status is GameStatus.CHECK


def test_checkmate_status_and_winner() -> None:
    game = ChessGame("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")

    assert game.is_check()
    assert game.is_checkmate()
    assert game.is_game_over()
    assert game.result().status is GameStatus.CHECKMATE
    assert game.result().winner is PlayerColor.WHITE
    assert game.result().notation == "1-0"


@pytest.mark.parametrize(
    "moves",
    [
        # Corrected version of the screenshot: the queen moves diagonally to h5, not h4.
        ("e2e4", "f7f6", "d2d4", "g7g5", "d1h5"),
        # Scholar's mate.
        ("e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7"),
    ],
)
def test_move_sequences_detect_checkmate(moves: tuple[str, ...]) -> None:
    game = ChessGame()

    play(game, *moves)

    assert game.is_check()
    assert game.is_checkmate()
    assert game.is_game_over()
    assert game.result().status is GameStatus.CHECKMATE
    assert game.result().notation == "1-0"


def test_stalemate_status() -> None:
    game = ChessGame("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")

    assert game.is_stalemate()
    assert game.result().status is GameStatus.STALEMATE
    assert game.result().notation == "1/2-1/2"


def test_insufficient_material_status() -> None:
    game = ChessGame("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
    result = game.result()

    assert result.status is GameStatus.INSUFFICIENT_MATERIAL
    assert result.is_over
    with pytest.raises(InvalidMoveError, match="already over"):
        game.make_move(ChessMove.from_uci("e1e2"))


def test_seventy_five_move_automatic_draw() -> None:
    result = ChessGame("4k2r/8/8/8/8/8/8/R3K3 w - - 150 76").result()

    assert result.status is GameStatus.SEVENTY_FIVE_MOVE_DRAW
    assert result.notation == "1/2-1/2"


def test_fivefold_repetition_and_claimable_draw_status() -> None:
    game = ChessGame()
    cycle = ("g1f3", "g8f6", "f3g1", "f6g8")
    play(game, *(cycle * 2))
    assert game.result().can_claim_threefold_repetition
    assert game.result().can_claim_draw

    play(game, *(cycle * 2))
    assert game.result().status is GameStatus.FIVEFOLD_REPETITION
    assert game.is_game_over()


def test_pgn_export_is_parseable_and_contains_known_sequence() -> None:
    game = ChessGame()
    play(game, "e2e4", "e7e5", "g1f3")

    pgn = game.to_pgn()
    parsed = chess.pgn.read_game(StringIO(pgn))

    assert parsed is not None
    assert [move.uci() for move in parsed.mainline_moves()] == ["e2e4", "e7e5", "g1f3"]
    assert "1. e4 e5 2. Nf3" in pgn


def test_pgn_store_writes_utf8_file(tmp_path: Path) -> None:
    destination = tmp_path / "games" / "sample.pgn"

    saved = PgnStore().save('[Result "*"]\n\n*', destination)

    assert saved == destination
    assert destination.read_text(encoding="utf-8") == '[Result "*"]\n\n*\n'
