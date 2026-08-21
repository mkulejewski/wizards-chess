"""Application-level chess move values."""

from __future__ import annotations

from dataclasses import dataclass

import chess

from wizard_chess.domain.exceptions import InvalidMoveError

PROMOTION_PIECES: dict[str, chess.PieceType] = {
    "q": chess.QUEEN,
    "r": chess.ROOK,
    "b": chess.BISHOP,
    "n": chess.KNIGHT,
}


@dataclass(frozen=True, slots=True)
class ChessMove:
    """A coordinate move independent of the underlying chess library."""

    source: str
    target: str
    promotion: str | None = None

    def __post_init__(self) -> None:
        source = self.source.lower()
        target = self.target.lower()
        promotion = self.promotion.lower() if self.promotion is not None else None

        if source not in chess.SQUARE_NAMES or target not in chess.SQUARE_NAMES:
            raise InvalidMoveError(f"Invalid move coordinates: {self.source} to {self.target}")
        if promotion is not None and promotion not in PROMOTION_PIECES:
            raise InvalidMoveError(f"Invalid promotion piece: {self.promotion}")

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "promotion", promotion)

    @classmethod
    def from_python_chess(cls, move: chess.Move) -> ChessMove:
        """Create an application move from a python-chess move."""
        promotion = chess.piece_symbol(move.promotion) if move.promotion is not None else None
        return cls(
            source=chess.square_name(move.from_square),
            target=chess.square_name(move.to_square),
            promotion=promotion,
        )

    @classmethod
    def from_uci(cls, uci: str) -> ChessMove:
        """Parse a UCI coordinate move."""
        try:
            return cls.from_python_chess(chess.Move.from_uci(uci.lower()))
        except ValueError as error:
            raise InvalidMoveError(f"Invalid UCI move: {uci}") from error

    def to_python_chess(self) -> chess.Move:
        """Convert this value into a python-chess move."""
        return chess.Move(
            from_square=chess.parse_square(self.source),
            to_square=chess.parse_square(self.target),
            promotion=(PROMOTION_PIECES[self.promotion] if self.promotion is not None else None),
        )

    def uci(self) -> str:
        """Return the move in Universal Chess Interface notation."""
        return self.to_python_chess().uci()

    def san(self, board: chess.Board) -> str:
        """Return SAN using a board positioned immediately before this move."""
        move = self.to_python_chess()
        if move not in board.legal_moves:
            raise InvalidMoveError(f"Move is not legal in this position: {self.uci()}")
        return board.san(move)
