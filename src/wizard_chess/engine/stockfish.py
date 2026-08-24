"""Lazy Stockfish/UCI adapter implemented through python-chess."""

from __future__ import annotations

import logging
from collections.abc import Mapping

import chess
import chess.engine

from wizard_chess.configuration import EngineSettings, EngineStrength
from wizard_chess.domain.exceptions import (
    AnalysisCancelledError,
    EngineCrashedError,
    EngineUnavailableError,
)
from wizard_chess.domain.move import ChessMove
from wizard_chess.engine.base import CancellationCheck
from wizard_chess.engine.models import EngineEvaluation, EngineLine, PositionAnalysis

LOGGER = logging.getLogger(__name__)

_SKILL_LEVELS: Mapping[EngineStrength, int] = {
    EngineStrength.BEGINNER: 0,
    EngineStrength.CASUAL: 3,
    EngineStrength.CLUB: 7,
    EngineStrength.STRONG_CLUB: 11,
    EngineStrength.EXPERT: 15,
    EngineStrength.MASTER: 18,
    EngineStrength.MAXIMUM: 20,
}


def normalize_score(score: chess.engine.PovScore) -> EngineEvaluation:
    """Normalize a python-chess score from White's perspective."""
    white_score = score.white()
    mate = white_score.mate()
    if mate is not None:
        return EngineEvaluation(mate_in=mate)
    return EngineEvaluation(score_cp=white_score.score() or 0)


class StockfishEngine:
    """Own one lazily started UCI subprocess and normalize all public output."""

    def __init__(self, settings: EngineSettings) -> None:
        self.settings = settings
        self._engine: chess.engine.SimpleEngine | None = None

    @property
    def is_running(self) -> bool:
        return self._engine is not None

    def start(self) -> None:
        """Start and configure the process once."""
        if self._engine is not None:
            return
        if not self.settings.enabled:
            raise EngineUnavailableError("Chess engine features are disabled")
        if not self.settings.path:
            raise EngineUnavailableError(
                "Stockfish is not configured; choose an executable in Engine Preferences"
            )
        engine: chess.engine.SimpleEngine | None = None
        try:
            engine = chess.engine.SimpleEngine.popen_uci(self.settings.path)
            available = engine.options
            options: dict[str, str | int | bool | None] = {}
            if "Threads" in available:
                options["Threads"] = self.settings.threads
            if "Hash" in available:
                options["Hash"] = self.settings.hash_mb
            if "Skill Level" in available:
                options["Skill Level"] = _SKILL_LEVELS[self.settings.strength]
            if options:
                engine.configure(options)
        except (OSError, ValueError, chess.engine.EngineError) as error:
            if engine is not None:
                try:
                    engine.quit()
                except (chess.engine.EngineError, OSError):
                    LOGGER.debug("Temporary engine cleanup failed", exc_info=True)
            LOGGER.warning("Stockfish startup failed: %s", error)
            raise EngineUnavailableError(
                f"Stockfish could not be started from {self.settings.path!r}"
            ) from error
        self._engine = engine
        LOGGER.info("Chess engine started")

    def analyse_position(
        self,
        board: chess.Board,
        *,
        count: int | None = None,
        cancel_requested: CancellationCheck | None = None,
    ) -> PositionAnalysis:
        """Analyze a defensive board copy and return White-perspective lines."""
        cancellation = cancel_requested or (lambda: False)
        if cancellation():
            raise AnalysisCancelledError("Engine analysis was cancelled")
        position = board.copy(stack=True)
        fen = position.fen()
        if position.is_game_over(claim_draw=False):
            return PositionAnalysis(fen=fen, terminal=True)
        self.start()
        engine = self._require_engine()
        requested = count or self.settings.multipv
        limit = chess.engine.Limit(
            time=self.settings.analysis_time_ms / 1000,
            depth=self.settings.analysis_depth,
        )
        try:
            raw = engine.analyse(position, limit, multipv=requested)
        except (chess.engine.EngineTerminatedError, BrokenPipeError) as error:
            self._engine = None
            raise EngineCrashedError("The chess engine stopped unexpectedly") from error
        except chess.engine.EngineError as error:
            raise EngineCrashedError("The chess engine could not analyse this position") from error
        if cancellation():
            raise AnalysisCancelledError("Engine analysis was cancelled")
        lines = tuple(self._normalize_info(position, info) for info in raw)
        return PositionAnalysis(fen=fen, lines=lines)

    def get_best_move(self, board: chess.Board) -> ChessMove | None:
        analysis = self.analyse_position(board, count=1)
        return analysis.best_line.move if analysis.best_line is not None else None

    def get_top_moves(self, board: chess.Board, count: int = 3) -> tuple[ChessMove, ...]:
        return tuple(line.move for line in self.analyse_position(board, count=count).lines)

    def play_move(self, board: chess.Board) -> ChessMove | None:
        return self.get_best_move(board)

    def close(self) -> None:
        """Shut down the owned process, tolerating an already-dead engine."""
        engine, self._engine = self._engine, None
        if engine is None:
            return
        try:
            engine.quit()
        except (chess.engine.EngineError, OSError):
            LOGGER.debug("Engine was already unavailable during shutdown", exc_info=True)
        LOGGER.info("Chess engine stopped")

    def _require_engine(self) -> chess.engine.SimpleEngine:
        if self._engine is None:
            raise EngineUnavailableError("The chess engine is unavailable")
        return self._engine

    @staticmethod
    def _normalize_info(board: chess.Board, info: chess.engine.InfoDict) -> EngineLine:
        score = info.get("score")
        pv = info.get("pv", [])
        if not isinstance(score, chess.engine.PovScore) or not pv:
            raise EngineCrashedError("The chess engine returned incomplete analysis")
        moves = pv
        return EngineLine(
            move=ChessMove.from_python_chess(moves[0]),
            evaluation=normalize_score(score),
            principal_variation=tuple(ChessMove.from_python_chess(move) for move in moves),
        )
