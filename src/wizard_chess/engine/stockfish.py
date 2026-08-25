"""Lazy Stockfish/UCI adapter implemented through python-chess."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from pathlib import Path

import chess
import chess.engine

from wizard_chess.configuration import EngineSettings, EngineStrength, StockfishPlayerMode
from wizard_chess.domain.exceptions import (
    AnalysisCancelledError,
    EngineCrashedError,
    EngineUnavailableError,
)
from wizard_chess.domain.move import ChessMove
from wizard_chess.engine.base import CancellationCheck
from wizard_chess.engine.models import (
    EngineClockState,
    EngineDecision,
    EngineEvaluation,
    EngineLine,
    PositionAnalysis,
)

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
        self._engine_name: str | None = None
        self.syzygy_status = "disabled"

    @property
    def is_running(self) -> bool:
        return self._engine is not None

    @property
    def engine_name(self) -> str | None:
        return self._engine_name

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
            identity = getattr(engine, "id", {})
            self._engine_name = str(identity.get("name", "Stockfish"))
            self._configure_syzygy(engine, available)
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
        time_ms: int | None = None,
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
            time=(time_ms or self.settings.post_game_analysis_time_ms) / 1000,
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

    def play_move(
        self,
        board: chess.Board,
        *,
        clock: EngineClockState | None = None,
        cancel_requested: CancellationCheck | None = None,
    ) -> EngineDecision | None:
        """Select a move using either a fixed limit or the supplied game clocks."""
        cancellation = cancel_requested or (lambda: False)
        if cancellation():
            raise AnalysisCancelledError("Engine play was cancelled")
        position = board.copy(stack=True)
        if position.is_game_over(claim_draw=False):
            return None
        self.start()
        engine = self._require_engine()
        limit = self._player_limit(clock)
        try:
            result = engine.play(position, limit, info=chess.engine.INFO_ALL)
        except (chess.engine.EngineTerminatedError, BrokenPipeError) as error:
            self._engine = None
            raise EngineCrashedError("The chess engine stopped unexpectedly") from error
        except chess.engine.EngineError as error:
            raise EngineCrashedError("The chess engine could not select a move") from error
        if cancellation():
            raise AnalysisCancelledError("Engine play was cancelled")
        if result.move is None:
            return None
        return self._normalize_decision(result.move, result.info)

    def cancel_pending(self) -> None:
        """Force-stop current UCI work; the lazy adapter can restart on demand."""
        engine, self._engine = self._engine, None
        if engine is None:
            return
        try:
            engine.close()
        except (chess.engine.EngineError, OSError):
            LOGGER.debug("Engine cancellation cleanup failed", exc_info=True)

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

    def _player_limit(self, clock: EngineClockState | None) -> chess.engine.Limit:
        if self.settings.player_mode is StockfishPlayerMode.FIXED_ANALYSIS_TIME:
            return chess.engine.Limit(
                time=self.settings.player_move_analysis_time_ms / 1000,
                depth=self.settings.analysis_depth,
            )
        if clock is None:
            raise EngineUnavailableError("Game-clock Stockfish play requires an active clock")
        return chess.engine.Limit(
            white_clock=max(0.0, clock.white_seconds),
            black_clock=max(0.0, clock.black_seconds),
            white_inc=max(0.0, clock.white_increment_seconds),
            black_inc=max(0.0, clock.black_increment_seconds),
        )

    def _configure_syzygy(
        self,
        engine: chess.engine.SimpleEngine,
        available: Mapping[str, object],
    ) -> None:
        configured_path = self.settings.syzygy_path
        if not configured_path:
            self.syzygy_status = "disabled"
            return
        path = Path(configured_path).expanduser()
        if not path.is_dir():
            self.syzygy_status = f"unavailable: directory not found ({path})"
            LOGGER.warning("Syzygy disabled: directory not found: %s", path)
            return
        if not os.access(path, os.R_OK | os.X_OK):
            self.syzygy_status = f"unavailable: directory is unreadable ({path})"
            LOGGER.warning("Syzygy disabled: directory is unreadable: %s", path)
            return
        try:
            wdl_tables: set[str] = {file.stem for file in path.glob("*.rtbw")}
            dtz_tables: set[str] = {file.stem for file in path.glob("*.rtbz")}
        except OSError:
            wdl_tables = set()
            dtz_tables = set()
        if not wdl_tables and not dtz_tables:
            self.syzygy_status = f"unavailable: no tablebase files found ({path})"
            LOGGER.warning("Syzygy disabled: no .rtbw/.rtbz files found in %s", path)
            return
        incomplete = wdl_tables != dtz_tables
        if incomplete:
            LOGGER.warning(
                "Syzygy directory has an incomplete WDL/DTZ file set; available tables "
                "will still be configured: %s",
                path,
            )
        if "SyzygyPath" not in available:
            self.syzygy_status = "unsupported by selected engine"
            LOGGER.warning("Syzygy disabled: selected engine has no SyzygyPath option")
            return

        options: dict[str, str | int | bool] = {"SyzygyPath": str(path)}
        if "SyzygyProbeLimit" in available:
            option = available["SyzygyProbeLimit"]
            maximum = getattr(option, "max", self.settings.syzygy_probe_limit)
            options["SyzygyProbeLimit"] = min(
                self.settings.syzygy_probe_limit,
                int(maximum) if maximum is not None else self.settings.syzygy_probe_limit,
            )
        if "Syzygy50MoveRule" in available:
            options["Syzygy50MoveRule"] = self.settings.syzygy_50_move_rule
        try:
            engine.configure(options)
        except (ValueError, chess.engine.EngineError) as error:
            self.syzygy_status = f"configuration rejected: {error}"
            LOGGER.warning("Syzygy configuration rejected; using normal search: %s", error)
            return
        self.syzygy_status = (
            f"ready with incomplete WDL/DTZ set: {path}" if incomplete else f"ready: {path}"
        )
        LOGGER.info("Syzygy configured from %s", path)

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
            depth=_optional_int_info(info, "depth"),
            selective_depth=_optional_int_info(info, "seldepth"),
            nodes=_optional_int_info(info, "nodes"),
            nps=_optional_int_info(info, "nps"),
            tablebase_hits=_optional_int_info(info, "tbhits"),
            search_time_seconds=_optional_float_info(info, "time"),
        )

    def _normalize_decision(
        self,
        move: chess.Move,
        info: chess.engine.InfoDict,
    ) -> EngineDecision:
        score = info.get("score")
        return EngineDecision(
            move=ChessMove.from_python_chess(move),
            evaluation=normalize_score(score) if isinstance(score, chess.engine.PovScore) else None,
            depth=_optional_int_info(info, "depth"),
            selective_depth=_optional_int_info(info, "seldepth"),
            nodes=_optional_int_info(info, "nodes"),
            nps=_optional_int_info(info, "nps"),
            tablebase_hits=_optional_int_info(info, "tbhits"),
            search_time_seconds=_optional_float_info(info, "time"),
            engine_name=self._engine_name,
        )


def _optional_int_info(info: chess.engine.InfoDict, name: str) -> int | None:
    value = info.get(name)  # type: ignore[literal-required]
    return int(value) if isinstance(value, int) else None


def _optional_float_info(info: chess.engine.InfoDict, name: str) -> float | None:
    value = info.get(name)  # type: ignore[literal-required]
    return float(value) if isinstance(value, int | float) else None
