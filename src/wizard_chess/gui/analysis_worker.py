"""Qt worker for cancellable post-game analysis."""

from threading import Event

from PySide6.QtCore import QThread, Signal

from wizard_chess.analysis.models import GameAnalysis
from wizard_chess.analysis.service import AnalysisService
from wizard_chess.domain.game import ChessGame
from wizard_chess.engine.base import ChessEngine


class GameAnalysisWorker(QThread):
    """Analyse a PGN copy and emit progress without touching the live session."""

    progress = Signal(int, int)
    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(self, engine: ChessEngine, pgn: str, analysis_time_ms: int) -> None:
        super().__init__()
        self._engine = engine
        self._pgn = pgn
        self._analysis_time_ms = analysis_time_ms
        self._cancelled = Event()

    def run(self) -> None:
        game = ChessGame()
        try:
            game.load_pgn(self._pgn)
            result = AnalysisService(
                self._engine,
                analysis_time_ms=self._analysis_time_ms,
            ).analyse_game(
                game,
                on_progress=self._emit_progress,
                cancel_requested=self._cancelled.is_set,
            )
        except Exception as error:
            if not self._cancelled.is_set():
                self.failed.emit(error)
            return
        if not self._cancelled.is_set():
            self.succeeded.emit(result)

    def cancel(self, *, stop_engine: bool = False) -> None:
        self._cancelled.set()
        if stop_engine:
            self._engine.cancel_pending()

    def _emit_progress(self, completed: int, total: int) -> None:
        self.progress.emit(completed, total)


def format_game_analysis(analysis: GameAnalysis) -> str:
    """Render compact transparent analysis details for the desktop adapter."""
    rows = [
        (
            f"White ACPL {analysis.white.average_centipawn_loss:.1f} · "
            f"Black ACPL {analysis.black.average_centipawn_loss:.1f}"
        ),
        (f"Blunders: White {analysis.white.blunders}, Black {analysis.black.blunders}"),
        "",
    ]
    rows.extend(
        f"{move.ply}. {move.san} — {move.classification.value.title()} ({move.centipawn_loss} cp)"
        for move in analysis.moves
    )
    return "\n".join(rows)
