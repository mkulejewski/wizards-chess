"""Future-facing physical chessboard interface."""

from typing import Protocol

from wizard_chess.domain.events import MoveExecuted


class PhysicalBoard(Protocol):
    """An output adapter capable of reflecting accepted digital moves."""

    def execute_move(self, event: MoveExecuted) -> None: ...
