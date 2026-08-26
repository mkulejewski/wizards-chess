import pytest

from wizard_chess.application.session import GameSession
from wizard_chess.commands.intents import (
    CastleSide,
    CommandIntent,
    CommandName,
    ContextualMoveIntent,
    PieceName,
)
from wizard_chess.commands.language import LanguageCommandParser, PolishCommandParser
from wizard_chess.commands.resolver import MoveResolver
from wizard_chess.configuration import ApplicationSettings, VoiceLanguage
from wizard_chess.domain.exceptions import AmbiguousMoveError, InvalidMoveError
from wizard_chess.domain.game import ChessGame
from wizard_chess.domain.move import ChessMove
from wizard_chess.speech.polish import PolishTranscriptNormalizer


@pytest.mark.parametrize(
    ("transcript", "normalized"),
    [
        ("E cztery", "e4"),
        ("ef trzy", "f3"),
        ("gie sześć", "g6"),
        ("Skoczek na F trzy.", "skoczek na f3"),
        ("Wieża bierze E pięć", "wieża bierze e5"),
    ],
)
def test_polish_normalization_is_deterministic(transcript: str, normalized: str) -> None:
    assert PolishTranscriptNormalizer().normalize(transcript) == normalized


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("e cztery", ContextualMoveIntent(destination="e4", piece=PieceName.PAWN)),
        ("pion na e cztery", ContextualMoveIntent(destination="e4", piece=PieceName.PAWN)),
        ("skoczek f trzy", ContextualMoveIntent(destination="f3", piece=PieceName.KNIGHT)),
        (
            "skoczek bierze e pięć",
            ContextualMoveIntent(destination="e5", piece=PieceName.KNIGHT, capture=True),
        ),
        (
            "goniec z c cztery na f siedem",
            ContextualMoveIntent(destination="f7", piece=PieceName.BISHOP, origin="c4"),
        ),
        ("roszada krótka", ContextualMoveIntent(castle=CastleSide.KINGSIDE)),
        ("długa roszada", ContextualMoveIntent(castle=CastleSide.QUEENSIDE)),
        ("cofnij", CommandIntent(CommandName.UNDO)),
        ("nowa gra", CommandIntent(CommandName.NEW)),
        ("zapisz grę", CommandIntent(CommandName.SAVE)),
        ("poddaję się", CommandIntent(CommandName.RESIGN)),
        ("remis", CommandIntent(CommandName.DRAW)),
        ("zaproponuj remis", CommandIntent(CommandName.PROPOSE_DRAW)),
        ("przyjmuję remis", CommandIntent(CommandName.ACCEPT_DRAW)),
        ("odrzucam remis", CommandIntent(CommandName.REJECT_DRAW)),
    ],
)
def test_polish_parser_emits_language_independent_intents(
    text: str, expected: ContextualMoveIntent | CommandIntent
) -> None:
    assert PolishCommandParser().parse(text) == expected


def test_english_and_polish_commands_resolve_to_the_same_move() -> None:
    english = LanguageCommandParser(VoiceLanguage.ENGLISH).parse("knight f3")
    polish = LanguageCommandParser(VoiceLanguage.POLISH).parse("skoczek f trzy")

    assert english == polish
    assert isinstance(english, ContextualMoveIntent)
    assert isinstance(polish, ContextualMoveIntent)
    assert MoveResolver().resolve(english, ChessGame()) == ChessMove.from_uci("g1f3")
    assert MoveResolver().resolve(polish, ChessGame()) == ChessMove.from_uci("g1f3")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("draw", CommandName.DRAW),
        ("call it a draw", CommandName.DRAW),
        ("propose a draw", CommandName.PROPOSE_DRAW),
        ("i offer a draw", CommandName.PROPOSE_DRAW),
        ("accept the draw", CommandName.ACCEPT_DRAW),
        ("agree to draw", CommandName.ACCEPT_DRAW),
        ("reject the draw", CommandName.REJECT_DRAW),
        ("decline draw", CommandName.REJECT_DRAW),
    ],
)
def test_english_draw_voice_variants(text: str, expected: CommandName) -> None:
    assert LanguageCommandParser(VoiceLanguage.ENGLISH).parse(text) == CommandIntent(expected)


def test_polish_pipeline_updates_the_shared_session_and_keeps_typed_san() -> None:
    session = GameSession(settings=ApplicationSettings(voice_language=VoiceLanguage.POLISH))

    session.play_text("e cztery")
    session.play_text("e5")
    session.play_text("skoczek f trzy")

    assert session.snapshot().move_history == ("e4", "e5", "Nf3")


def test_contextual_resolver_never_guesses_ambiguous_piece() -> None:
    game = ChessGame("4k3/8/8/8/8/1N3N2/8/4K3 w - - 0 1")
    intent = ContextualMoveIntent(destination="d2", piece=PieceName.KNIGHT)

    with pytest.raises(AmbiguousMoveError, match="Which knight"):
        MoveResolver().resolve(intent, game)


def test_spoken_capture_marker_must_match_the_position() -> None:
    intent = ContextualMoveIntent(destination="f3", piece=PieceName.KNIGHT, capture=True)

    with pytest.raises(InvalidMoveError, match="No legal move"):
        MoveResolver().resolve(intent, ChessGame())


def test_polish_promotion_variants_share_one_intent() -> None:
    parser = PolishCommandParser()
    expected = ContextualMoveIntent(destination="e8", piece=PieceName.PAWN, promotion="q")

    assert parser.parse("e osiem hetman") == expected
    assert parser.parse("e osiem promocja na hetmana") == expected
    assert parser.parse("pion na e osiem hetman") == expected
