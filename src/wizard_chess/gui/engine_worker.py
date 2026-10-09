"""Qt worker for engine analysis and replies outside the GUI event thread."""

import logging
from threading import Event

import chess
from PySide6.QtCore import QThread, Signal

from wizard_chess.engine.base import ChessEngine
from wizard_chess.engine.models import EngineClockState

LOGGER = logging.getLogger(__name__)


class EngineWorker(QThread):
    """Run one immutable-position request and tag its result with the source FEN."""

    succeeded = Signal(str, int, str, object)
    failed = Signal(str, int, str, object)

    def __init__(
        self,
        engine: ChessEngine,
        board: chess.Board,
        mode: str,
        *,
        revision: int,
        clock: EngineClockState | None = None,
    ) -> None:
        super().__init__()
        self._engine = engine
        self._board = board.copy(stack=True)
        self.fen = self._board.fen()
        self.revision = revision
        self.mode = mode
        self._clock = clock
        self._cancelled = Event()

    def run(self) -> None:
        LOGGER.debug(
            "Engine worker started: mode=%s revision=%d FEN=%s",
            self.mode,
            self.revision,
            self.fen,
        )
        try:
            if self.mode == "move":
                result = self._engine.play_move(
                    self._board,
                    clock=self._clock,
                    cancel_requested=self._cancelled.is_set,
                )
            else:
                result = self._engine.analyse_position(
                    self._board,
                    cancel_requested=self._cancelled.is_set,
                )
        except Exception as error:
            if not self._cancelled.is_set():
                LOGGER.exception("Engine worker failed: mode=%s", self.mode)
                self.failed.emit(self.fen, self.revision, self.mode, error)
            return
        if not self._cancelled.is_set():
            LOGGER.debug("Engine worker completed: mode=%s revision=%d", self.mode, self.revision)
            self.succeeded.emit(self.fen, self.revision, self.mode, result)

    def cancel(self, *, stop_engine: bool = False) -> None:
        """Mark this request stale; adapters discard any late result."""
        self._cancelled.set()
        LOGGER.debug("Engine worker cancellation requested: mode=%s", self.mode)
        if stop_engine:
            self._engine.cancel_pending()
