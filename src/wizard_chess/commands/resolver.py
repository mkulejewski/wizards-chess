"""Resolution of state-independent intents against legal chess moves."""

import logging

import chess

from wizard_chess.commands.intents import (
    CastleSide,
    CheckClaim,
    ContextualMoveIntent,
    MoveCommandIntent,
    PieceName,
    SanMoveIntent,
)
from wizard_chess.domain.exceptions import (
    AmbiguousMoveError,
    InvalidMoveError,
)
from wizard_chess.domain.game import ChessGame
from wizard_chess.domain.move import ChessMove

LOGGER = logging.getLogger(__name__)


class MoveResolver:
    """Resolve a move intent to exactly one legal application move."""

    def resolve(self, intent: MoveCommandIntent, game: ChessGame) -> ChessMove:
        LOGGER.debug("Resolving move intent: %r", intent)
        if isinstance(intent, SanMoveIntent):
            return self._resolve_san(intent, game)
        if isinstance(intent, ContextualMoveIntent):
            return self._resolve_contextual(intent, game)

        attempted_move = ChessMove(intent.source, intent.target, intent.promotion)
        candidates = [
            move
            for move in game.legal_moves()
            if move.source == attempted_move.source
            and move.target == attempted_move.target
            and (attempted_move.promotion is None or move.promotion == attempted_move.promotion)
        ]
        LOGGER.debug(
            "Coordinate move candidates for %s: %s",
            attempted_move.uci(),
            [move.uci() for move in candidates],
        )

        if not candidates:
            game.validate_move(attempted_move)
            raise InvalidMoveError(f"Illegal move: {attempted_move.uci()}")
        if len(candidates) > 1:
            raise AmbiguousMoveError(
                f"Move {attempted_move.source} to {attempted_move.target} "
                "requires a promotion piece"
            )
        resolved = candidates[0]
        LOGGER.debug("Resolved coordinate move: %s", resolved.uci())
        return resolved

    def _resolve_san(self, intent: SanMoveIntent, game: ChessGame) -> ChessMove:
        board = game.board
        LOGGER.debug("Parsing SAN move: %s", intent.notation)
        try:
            python_move = board.parse_san(intent.notation)
        except chess.AmbiguousMoveError as error:
            raise AmbiguousMoveError(f"Ambiguous SAN move: {intent.notation}") from error
        except ValueError as error:
            raise InvalidMoveError(f"Illegal SAN move: {intent.notation}") from error

        if board.san(python_move) != intent.notation:
            raise InvalidMoveError(f"Invalid SAN for current position: {intent.notation}")

        resolved = ChessMove.from_python_chess(python_move)
        LOGGER.debug("Resolved SAN move: %s / SAN=%s", resolved.uci(), intent.notation)
        return resolved

    def _resolve_contextual(self, intent: ContextualMoveIntent, game: ChessGame) -> ChessMove:
        board = game.board
        piece_type = _PIECE_TYPES.get(intent.piece) if intent.piece is not None else None
        candidates: list[chess.Move] = []
        for move in board.legal_moves:
            moving_piece = board.piece_at(move.from_square)
            if moving_piece is None:
                continue
            if piece_type is not None and moving_piece.piece_type != piece_type:
                continue
            if intent.origin is not None and chess.square_name(move.from_square) != intent.origin:
                continue
            if (
                intent.destination is not None
                and chess.square_name(move.to_square) != intent.destination
            ):
                continue
            if intent.capture is not None and board.is_capture(move) is not intent.capture:
                continue
            promotion = chess.piece_symbol(move.promotion) if move.promotion is not None else None
            if intent.promotion is not None and promotion != intent.promotion:
                continue
            if intent.promotion is None and move.promotion is not None:
                continue
            if intent.castle is not None:
                if not board.is_castling(move):
                    continue
                kingside = chess.square_file(move.to_square) > chess.square_file(move.from_square)
                if (intent.castle is CastleSide.KINGSIDE) is not kingside:
                    continue
            if intent.check_claim is not None:
                san = board.san(move)
                if intent.check_claim is CheckClaim.CHECKMATE and not san.endswith("#"):
                    continue
                if intent.check_claim is CheckClaim.CHECK and not san.endswith(("+", "#")):
                    continue
            candidates.append(move)

        LOGGER.debug(
            "Contextual legal move candidates: %s",
            [move.uci() for move in candidates],
        )

        if not candidates:
            detail = intent.destination or intent.castle or "requested action"
            raise InvalidMoveError(f"No legal move matches {detail}")
        if len(candidates) > 1:
            piece = intent.piece.value if intent.piece is not None else "piece"
            origins = ", ".join(chess.square_name(move.from_square) for move in candidates)
            raise AmbiguousMoveError(f"Which {piece}? Legal origins: {origins}")
        resolved = ChessMove.from_python_chess(candidates[0])
        LOGGER.debug("Resolved contextual move: %s", resolved.uci())
        return resolved


_PIECE_TYPES: dict[PieceName, chess.PieceType] = {
    PieceName.PAWN: chess.PAWN,
    PieceName.KNIGHT: chess.KNIGHT,
    PieceName.BISHOP: chess.BISHOP,
    PieceName.ROOK: chess.ROOK,
    PieceName.QUEEN: chess.QUEEN,
    PieceName.KING: chess.KING,
}
