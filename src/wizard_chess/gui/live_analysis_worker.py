"""Qt worker for one cancellable continuous engine-analysis stream."""

import logging
from threading import Event

import chess
from PySide6.QtCore import QThread, Signal

from wizard_chess.analysis.live import AnalysisSelection
from wizard_chess.engine.base import ChessEngine
from wizard_chess.engine.models import PositionAnalysis

LOGGER = logging.getLogger(__name__)


class LiveAnalysisWorker(QThread):
    """Stream immutable-position updates without touching Qt widgets."""

    updated = Signal(str, int, object)
    failed = Signal(str, int, object)

    def __init__(
        self,
        engine: ChessEngine,
        board: chess.Board,
        selection: AnalysisSelection,
        max_depth: int,
    ) -> None:
        super().__init__()
        self._engine = engine
        self._board = board.copy(stack=True)
        self.selection = selection
        self.fen = self._board.fen()
        self.generation = selection.generation
        self.max_depth = max_depth
        self._cancelled = Event()

    def run(self) -> None:
        LOGGER.debug(
            "Live analysis worker started: generation=%d max_depth=%d FEN=%s",
            self.generation,
            self.max_depth,
            self.fen,
        )
        try:
            self._engine.analyse_live(
                self._board,
                max_depth=self.max_depth,
                on_update=self._emit_update,
                cancel_requested=self._cancelled.is_set,
            )
        except Exception as error:
            if not self._cancelled.is_set():
                LOGGER.exception("Live analysis worker failed: generation=%d", self.generation)
                self.failed.emit(self.fen, self.generation, error)

    def cancel(self, *, stop_engine: bool = False) -> None:
        """Request normal stream shutdown, optionally terminating a stuck process."""
        self._cancelled.set()
        LOGGER.debug("Live analysis worker cancellation requested: generation=%d", self.generation)
        if stop_engine:
            self._engine.cancel_pending()

    def _emit_update(self, analysis: PositionAnalysis) -> None:
        if not self._cancelled.is_set():
            self.updated.emit(self.fen, self.generation, analysis)
