import pytest

from wizard_chess.application.session import GameSession
from wizard_chess.configuration import (
    ApplicationSettings,
    PlayerKind,
    PlayerSettings,
    VoiceLanguage,
)
from wizard_chess.domain.exceptions import GameTerminationError
from wizard_chess.domain.results import GameStatus, PlayerColor


def test_generic_draw_command_offers_then_accepts_but_a_move_rejects() -> None:
    session = GameSession()

    offered = session.play_text("draw")
    assert "offers a draw" in (offered.message or "")
    assert session.snapshot().pending_draw_offer is PlayerColor.WHITE
    assert not session.snapshot().result.is_over

    session.play_text("e4")
    assert session.snapshot().pending_draw_offer is None
    assert not session.snapshot().result.is_over

    session.play_text("draw")
    accepted = session.play_text("draw")
    assert accepted.message == "Game drawn by agreement."
    assert session.snapshot().result.status is GameStatus.AGREED_DRAW


def test_explicit_draw_commands_share_the_pending_offer_pipeline() -> None:
    session = GameSession()

    session.play_text("offer a draw")
    assert session.snapshot().pending_draw_offer is PlayerColor.WHITE
    session.play_text("decline draw")
    assert session.snapshot().pending_draw_offer is None
    assert not session.snapshot().can_request_draw

    with pytest.raises(GameTerminationError, match="already offered"):
        session.play_text("propose draw")

    session.play_text("e4")
    session.play_text("propose draw")
    session.play_text("accept the draw offer")
    assert session.snapshot().result.status is GameStatus.AGREED_DRAW


def test_polish_draw_commands_share_the_pending_offer_pipeline() -> None:
    settings = ApplicationSettings(voice_language=VoiceLanguage.POLISH)
    session = GameSession(settings=settings)

    session.play_text("zaproponuj remis")
    assert session.snapshot().pending_draw_offer is PlayerColor.WHITE
    session.play_text("odrzucam propozycję remisu")
    assert session.snapshot().pending_draw_offer is None

    with pytest.raises(GameTerminationError, match="już zaproponowano"):
        session.play_text("remis")

    session.play_text("e cztery")
    session.play_text("remis")
    session.play_text("akceptuję remis")
    assert session.snapshot().result.status is GameStatus.AGREED_DRAW


def test_draw_requires_two_humans_and_only_current_human_can_resign() -> None:
    human_vs_engine = ApplicationSettings(players=PlayerSettings(black_kind=PlayerKind.ENGINE))
    session = GameSession(settings=human_vs_engine, engine_factory=lambda _settings: None)

    snapshot = session.snapshot()
    assert snapshot.can_resign
    assert not snapshot.can_request_draw
    with pytest.raises(GameTerminationError, match="two human players"):
        session.play_text("draw")

    session.play_text("resign")
    assert session.snapshot().result.status is GameStatus.RESIGNED

    engine_to_move = ApplicationSettings(players=PlayerSettings(white_kind=PlayerKind.ENGINE))
    session = GameSession(settings=engine_to_move, engine_factory=lambda _settings: None)
    assert not session.snapshot().can_resign
    with pytest.raises(GameTerminationError, match="human player"):
        session.play_text("resign")


def test_explicit_accept_and_reject_require_a_pending_offer() -> None:
    session = GameSession()

    with pytest.raises(GameTerminationError, match="no draw offer"):
        session.play_text("accept draw")
    with pytest.raises(GameTerminationError, match="no draw offer"):
        session.play_text("reject draw")


def test_propose_draw_claims_threefold_repetition_without_acceptance() -> None:
    session = GameSession()
    cycle = ("Nf3", "Nf6", "Ng1", "Ng8")
    for move in cycle * 2:
        session.play_text(move)

    assert session.snapshot().result.can_claim_threefold_repetition
    result = session.play_text("propose draw")

    assert result.message == "Draw claimed by threefold repetition."
    assert session.snapshot().pending_draw_offer is None
    assert session.snapshot().result.status is GameStatus.THREEFOLD_REPETITION_CLAIM


def test_human_can_claim_fifty_move_draw_against_engine_without_acceptance() -> None:
    settings = ApplicationSettings(players=PlayerSettings(black_kind=PlayerKind.ENGINE))
    session = GameSession(settings=settings, engine_factory=lambda _settings: None)
    session.load_fen("4k2r/8/8/8/8/8/8/R3K3 w - - 100 51")

    assert session.snapshot().result.can_claim_fifty_moves
    assert session.snapshot().can_request_draw
    result = session.play_text("draw")

    assert result.message == "Draw claimed by the fifty-move rule."
    assert session.snapshot().pending_draw_offer is None
    assert session.snapshot().result.status is GameStatus.FIFTY_MOVE_RULE_CLAIM
