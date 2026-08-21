import pytest

from wizard_chess.application.session import GameSession
from wizard_chess.domain.exceptions import InvalidFenError
from wizard_chess.domain.move import ChessMove
from wizard_chess.hardware.simulated_board import SimulatedPhysicalBoard


def test_initial_snapshot_contains_authoritative_position() -> None:
    snapshot = GameSession().snapshot()

    assert snapshot.piece_at("a1") == "R"
    assert snapshot.piece_at("e1") == "K"
    assert snapshot.piece_at("e2") == "P"
    assert snapshot.piece_at("e7") == "p"
    assert snapshot.piece_at("e8") == "k"
    assert snapshot.piece_at("a8") == "r"
    assert len(snapshot.pieces) == 32
    assert not snapshot.can_undo
    assert not snapshot.can_redo


def test_san_coordinate_and_direct_moves_have_equivalent_session_results() -> None:
    sessions = [GameSession() for _ in range(3)]

    san_event = sessions[0].play_text("e4").move_event
    coordinate_event = sessions[1].play_text("e2 e4").move_event
    direct_event = sessions[2].play_move(ChessMove("e2", "e4"))

    assert san_event == coordinate_event == direct_event
    assert len({session.snapshot().fen for session in sessions}) == 1
    assert len({session.snapshot().pgn for session in sessions}) == 1
    assert all(session.snapshot().move_history == ("e4",) for session in sessions)


def test_session_normalizes_history_across_input_styles() -> None:
    session = GameSession()

    session.play_text("e4")
    session.play_text("e7 e5")
    session.play_move(ChessMove("g1", "f3"))
    session.play_text("b8-c6")

    assert session.snapshot().move_history == ("e4", "e5", "Nf3", "Nc6")
    assert session.snapshot().last_move == ChessMove("b8", "c6")


def test_session_undo_redo_and_new_game_derive_from_domain_history() -> None:
    session = GameSession()
    session.play_text("e4")
    session.play_text("e5")
    after_two_moves = session.snapshot().fen

    undone = session.undo()
    assert undone == ChessMove("e7", "e5")
    assert session.snapshot().move_history == ("e4",)
    assert session.snapshot().can_redo

    redone = session.redo()
    assert redone.san == "e5"
    assert session.snapshot().fen == after_two_moves

    session.new_game()
    snapshot = session.snapshot()
    assert snapshot.move_history == ()
    assert snapshot.last_move is None
    assert snapshot.turn.value == "white"
    assert not snapshot.can_undo


def test_session_valid_and_invalid_fen_loading_are_atomic() -> None:
    session = GameSession()
    session.play_text("e4")
    target_fen = "4k3/8/8/8/8/8/4R3/4K3 b - - 0 1"

    session.load_fen(target_fen)
    loaded = session.snapshot()
    assert loaded.fen == target_fen
    assert loaded.move_history == ()
    assert loaded.last_move is None
    assert loaded.result.status.value == "check"

    with pytest.raises(InvalidFenError):
        session.load_fen("not a fen")

    assert session.snapshot().fen == target_fen


def test_session_emits_move_events_for_play_and_redo_only() -> None:
    physical_board = SimulatedPhysicalBoard()
    session = GameSession(physical_board)

    session.play_text("e4")
    session.undo()
    session.redo()
    session.new_game()

    assert [event.uci for event in physical_board.events] == ["e2e4", "e2e4"]
