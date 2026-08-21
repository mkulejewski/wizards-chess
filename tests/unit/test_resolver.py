import pytest

from wizard_chess.commands.intents import MoveIntent, SanMoveIntent
from wizard_chess.commands.resolver import MoveResolver
from wizard_chess.domain.exceptions import AmbiguousMoveError, InvalidMoveError
from wizard_chess.domain.game import ChessGame
from wizard_chess.domain.move import ChessMove


def play(game: ChessGame, *moves: str) -> None:
    for move in moves:
        game.make_move(ChessMove.from_uci(move))


def test_resolver_returns_the_matching_legal_move() -> None:
    resolved = MoveResolver().resolve(MoveIntent("e2", "e4"), ChessGame())

    assert resolved == ChessMove("e2", "e4")


def test_resolver_rejects_illegal_move() -> None:
    with pytest.raises(InvalidMoveError, match="Illegal move"):
        MoveResolver().resolve(MoveIntent("e2", "e5"), ChessGame())


def test_resolver_requires_promotion_piece_when_multiple_moves_match() -> None:
    game = ChessGame("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")

    with pytest.raises(AmbiguousMoveError):
        MoveResolver().resolve(MoveIntent("a7", "a8"), game)


def test_resolver_selects_requested_underpromotion() -> None:
    game = ChessGame("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")

    assert MoveResolver().resolve(MoveIntent("a7", "a8", "n"), game) == ChessMove("a7", "a8", "n")


@pytest.mark.parametrize(
    ("notation", "expected"),
    [("e4", "e2e4"), ("Nf3", "g1f3")],
)
def test_resolver_resolves_simple_san(notation: str, expected: str) -> None:
    resolved = MoveResolver().resolve(SanMoveIntent(notation), ChessGame())

    assert resolved == ChessMove.from_uci(expected)


def test_resolver_resolves_san_pawn_capture() -> None:
    game = ChessGame()
    play(game, "e2e4", "d7d5")

    assert MoveResolver().resolve(SanMoveIntent("exd5"), game) == ChessMove.from_uci("e4d5")


def test_resolver_resolves_san_piece_capture() -> None:
    game = ChessGame()
    play(game, "e2e4", "e7e5", "g1f3", "b8c6")

    assert MoveResolver().resolve(SanMoveIntent("Nxe5"), game) == ChessMove.from_uci("f3e5")


@pytest.mark.parametrize(
    ("notation", "expected"),
    [("O-O", "e1g1"), ("O-O-O", "e1c1")],
)
def test_resolver_resolves_san_castling(notation: str, expected: str) -> None:
    game = ChessGame("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")

    assert MoveResolver().resolve(SanMoveIntent(notation), game) == ChessMove.from_uci(expected)


def test_resolver_resolves_san_promotion() -> None:
    game = ChessGame("8/4P2k/8/8/8/8/8/K7 w - - 0 1")

    assert MoveResolver().resolve(SanMoveIntent("e8=Q"), game) == ChessMove.from_uci("e7e8q")


def test_resolver_resolves_san_capture_promotion() -> None:
    game = ChessGame("3r4/4P2k/8/8/8/8/8/K7 w - - 0 1")

    assert MoveResolver().resolve(SanMoveIntent("exd8=Q"), game) == ChessMove.from_uci("e7d8q")


def test_resolver_requires_correct_check_suffix() -> None:
    game = ChessGame()
    play(game, "e2e4", "e7e5", "d1h5", "b8c6")

    assert MoveResolver().resolve(SanMoveIntent("Qxe5+"), game) == ChessMove.from_uci("h5e5")
    with pytest.raises(InvalidMoveError, match="Invalid SAN"):
        MoveResolver().resolve(SanMoveIntent("Qxe5#"), game)


def test_resolver_resolves_san_checkmate_suffix() -> None:
    game = ChessGame()
    play(game, "f2f3", "e7e5", "g2g4")

    assert MoveResolver().resolve(SanMoveIntent("Qh4#"), game) == ChessMove.from_uci("d8h4")


def test_resolver_uses_python_chess_san_disambiguation() -> None:
    game = ChessGame("4k3/8/8/8/8/1N3N2/8/4K3 w - - 0 1")

    assert MoveResolver().resolve(SanMoveIntent("Nbd2"), game) == ChessMove.from_uci("b3d2")
    with pytest.raises(AmbiguousMoveError, match="Ambiguous SAN"):
        MoveResolver().resolve(SanMoveIntent("Nd2"), game)
    with pytest.raises(InvalidMoveError, match="Illegal SAN"):
        MoveResolver().resolve(SanMoveIntent("Nad2"), game)


@pytest.mark.parametrize("notation", ["e5", "O-O", "e4+", "e4#"])
def test_resolver_rejects_illegal_or_incorrect_san_without_mutation(notation: str) -> None:
    game = ChessGame()
    original_fen = game.fen()
    original_pgn = game.to_pgn()

    with pytest.raises(InvalidMoveError):
        MoveResolver().resolve(SanMoveIntent(notation), game)

    assert game.fen() == original_fen
    assert game.to_pgn() == original_pgn
