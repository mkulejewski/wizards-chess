from pathlib import Path

import pytest

from wizard_chess.application.clock import ChessClock
from wizard_chess.application.session import GameSession
from wizard_chess.configuration import ClockSettings
from wizard_chess.domain.exceptions import GameTerminationError, InvalidPgnError
from wizard_chess.domain.game import ChessGame
from wizard_chess.domain.move import ChessMove
from wizard_chess.domain.results import GameStatus, PlayerColor
from wizard_chess.persistence.game_store import GameStore


def test_pgn_round_trip_preserves_moves_start_position_and_metadata() -> None:
    game = ChessGame(metadata={"Event": "Local match", "White": "Ada", "Black": "Jan"})
    for uci in ("e2e4", "e7e5", "g1f3", "b8c6"):
        game.make_move(ChessMove.from_uci(uci))

    restored = ChessGame()
    restored.load_pgn(game.to_pgn())

    assert restored.fen() == game.fen()
    assert restored.move_history() == ("e4", "e5", "Nf3", "Nc6")
    assert restored.metadata == {"Event": "Local match", "White": "Ada", "Black": "Jan"}


def test_invalid_pgn_does_not_replace_session_state() -> None:
    session = GameSession()
    session.play_text("e4")
    original = session.snapshot()

    with pytest.raises(InvalidPgnError):
        session.load_pgn('[Event "broken"]\n\n1. e5')

    assert session.snapshot().fen == original.fen


def test_resignation_and_agreed_draw_are_domain_game_results() -> None:
    resigned = ChessGame()
    result = resigned.resign(PlayerColor.WHITE)

    assert result.status is GameStatus.RESIGNED
    assert result.winner is PlayerColor.BLACK
    assert result.notation == "0-1"
    with pytest.raises(GameTerminationError):
        resigned.agree_draw()

    drawn = ChessGame()
    assert drawn.agree_draw().status is GameStatus.AGREED_DRAW
    assert drawn.result().notation == "1/2-1/2"


def test_game_store_uses_unique_saves_and_recovery_slot(tmp_path: Path) -> None:
    store = GameStore(tmp_path)

    first = store.save('[Result "*"]\n\n*', "same")
    second = store.save('[Result "*"]\n\n*', "same")
    recovery = store.autosave('[Result "1/2-1/2"]\n\n1/2-1/2')

    assert first.name == "same.pgn"
    assert second.name == "same-1.pgn"
    assert recovery.name == "recovery.pgn"
    assert store.recover() is not None
    assert "1/2-1/2" in (store.recover() or "")


def test_monotonic_clock_switches_with_increment_and_pauses() -> None:
    now = [100.0]
    clock = ChessClock(
        ClockSettings(enabled=True, initial_seconds=60, increment_seconds=2),
        now=lambda: now[0],
    )

    clock.start(PlayerColor.WHITE)
    now[0] += 5
    clock.switch(PlayerColor.BLACK)
    switched = clock.snapshot()
    assert switched.white_seconds == pytest.approx(57)
    assert switched.black_seconds == pytest.approx(60)
    assert switched.active is PlayerColor.BLACK

    now[0] += 4
    clock.pause()
    paused = clock.snapshot()
    assert paused.black_seconds == pytest.approx(56)
    assert not paused.running
