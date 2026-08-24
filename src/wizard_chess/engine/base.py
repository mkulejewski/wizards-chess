"""Replaceable chess-engine port."""

from collections.abc import Callable
from typing import Protocol

import chess

from wizard_chess.domain.move import ChessMove
from wizard_chess.engine.models import PositionAnalysis

CancellationCheck = Callable[[], bool]


class ChessEngine(Protocol):
    """Engine operations without leaking UCI data to callers."""

    def analyse_position(
        self,
        board: chess.Board,
        *,
        count: int | None = None,
        cancel_requested: CancellationCheck | None = None,
    ) -> PositionAnalysis: ...

    def get_best_move(self, board: chess.Board) -> ChessMove | None: ...

    def get_top_moves(self, board: chess.Board, count: int = 3) -> tuple[ChessMove, ...]: ...

    def play_move(self, board: chess.Board) -> ChessMove | None: ...

    def close(self) -> None: ...
