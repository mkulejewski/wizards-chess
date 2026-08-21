"""Resolution of state-independent intents against legal chess moves."""

import chess

from wizard_chess.commands.intents import MoveCommandIntent, SanMoveIntent
from wizard_chess.domain.exceptions import (
    AmbiguousMoveError,
    InvalidMoveError,
)
from wizard_chess.domain.game import ChessGame
from wizard_chess.domain.move import ChessMove


class MoveResolver:
    """Resolve a move intent to exactly one legal application move."""

    def resolve(self, intent: MoveCommandIntent, game: ChessGame) -> ChessMove:
        if isinstance(intent, SanMoveIntent):
            return self._resolve_san(intent, game)

        attempted_move = ChessMove(intent.source, intent.target, intent.promotion)
        candidates = [
            move
            for move in game.legal_moves()
            if move.source == attempted_move.source
            and move.target == attempted_move.target
            and (attempted_move.promotion is None or move.promotion == attempted_move.promotion)
        ]

        if not candidates:
            game.validate_move(attempted_move)
            raise InvalidMoveError(f"Illegal move: {attempted_move.uci()}")
        if len(candidates) > 1:
            raise AmbiguousMoveError(
                f"Move {attempted_move.source} to {attempted_move.target} "
                "requires a promotion piece"
            )
        return candidates[0]

    def _resolve_san(self, intent: SanMoveIntent, game: ChessGame) -> ChessMove:
        board = game.board
        try:
            python_move = board.parse_san(intent.notation)
        except chess.AmbiguousMoveError as error:
            raise AmbiguousMoveError(f"Ambiguous SAN move: {intent.notation}") from error
        except ValueError as error:
            raise InvalidMoveError(f"Illegal SAN move: {intent.notation}") from error

        if board.san(python_move) != intent.notation:
            raise InvalidMoveError(f"Invalid SAN for current position: {intent.notation}")

        return ChessMove.from_python_chess(python_move)
