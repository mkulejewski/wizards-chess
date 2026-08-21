from wizard_chess.application.session import GameSession
from wizard_chess.gui.view_model import format_game_status, format_move_history


def test_move_history_formats_numbered_san_pairs() -> None:
    assert format_move_history(("e4", "e5", "Nf3", "Nc6", "Bb5")) == (
        "1. e4  e5\n2. Nf3  Nc6\n3. Bb5"
    )


def test_status_formats_turn_check_checkmate_and_stalemate() -> None:
    session = GameSession()
    assert format_game_status(session.snapshot()) == "White to move"

    session.load_fen("4k3/8/8/8/8/8/4R3/4K3 b - - 0 1")
    assert format_game_status(session.snapshot()) == "Black to move — Check"

    session.new_game()
    for move in ("f3", "e5", "g4", "Qh4#"):
        session.play_text(move)
    assert format_game_status(session.snapshot()) == "Checkmate — Black wins"

    session.load_fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert format_game_status(session.snapshot()) == "Stalemate — Draw"
