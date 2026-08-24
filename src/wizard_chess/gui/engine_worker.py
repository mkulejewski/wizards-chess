"""Qt worker for engine analysis and replies outside the GUI event thread."""

from threading import Event

import chess
from PySide6.QtCore import QThread, Signal

from wizard_chess.engine.base import ChessEngine


class EngineWorker(QThread):
    """Run one immutable-position request and tag its result with the source FEN."""

    succeeded = Signal(str, str, object)
    failed = Signal(str, str, object)

    def __init__(self, engine: ChessEngine, board: chess.Board, mode: str) -> None:
        super().__init__()
        self._engine = engine
        self._board = board.copy(stack=True)
        self.fen = self._board.fen()
        self.mode = mode
        self._cancelled = Event()

    def run(self) -> None:
        try:
            if self.mode == "move":
                result = self._engine.play_move(self._board)
            else:
                result = self._engine.analyse_position(
                    self._board,
                    cancel_requested=self._cancelled.is_set,
                )
        except Exception as error:
            self.failed.emit(self.fen, self.mode, error)
            return
        if not self._cancelled.is_set():
            self.succeeded.emit(self.fen, self.mode, result)

    def cancel(self) -> None:
        """Mark this request stale; adapters discard any late result."""
        self._cancelled.set()
