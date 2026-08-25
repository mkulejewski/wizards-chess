"""Deterministic engine test double."""

from collections.abc import Mapping

import chess

from wizard_chess.domain.move import ChessMove
from wizard_chess.engine.base import CancellationCheck
from wizard_chess.engine.models import EngineClockState, EngineDecision, PositionAnalysis


class FakeEngine:
    """Return configured analyses by exact FEN without starting a process."""

    def __init__(
        self,
        analyses: Mapping[str, PositionAnalysis] | None = None,
        *,
        default: PositionAnalysis | None = None,
    ) -> None:
        self.analyses = dict(analyses or {})
        self.default = default
        self.requests: list[str] = []
        self.analysis_times_ms: list[int | None] = []
        self.play_requests: list[tuple[str, EngineClockState | None]] = []
        self.closed = False

    @property
    def engine_name(self) -> str:
        return "Fake Stockfish"

    def analyse_position(
        self,
        board: chess.Board,
        *,
        count: int | None = None,
        time_ms: int | None = None,
        cancel_requested: CancellationCheck | None = None,
    ) -> PositionAnalysis:
        del count
        if cancel_requested is not None and cancel_requested():
            from wizard_chess.domain.exceptions import AnalysisCancelledError

            raise AnalysisCancelledError("Engine analysis was cancelled")
        fen = board.fen()
        self.requests.append(fen)
        self.analysis_times_ms.append(time_ms)
        if fen in self.analyses:
            return self.analyses[fen]
        if self.default is not None:
            return PositionAnalysis(
                fen=fen,
                lines=self.default.lines,
                terminal=self.default.terminal,
            )
        return PositionAnalysis(fen=fen, terminal=board.is_game_over(claim_draw=False))

    def get_best_move(self, board: chess.Board) -> ChessMove | None:
        line = self.analyse_position(board, count=1).best_line
        return line.move if line is not None else None

    def get_top_moves(self, board: chess.Board, count: int = 3) -> tuple[ChessMove, ...]:
        return tuple(line.move for line in self.analyse_position(board, count=count).lines[:count])

    def play_move(
        self,
        board: chess.Board,
        *,
        clock: EngineClockState | None = None,
        cancel_requested: CancellationCheck | None = None,
    ) -> EngineDecision | None:
        if cancel_requested is not None and cancel_requested():
            from wizard_chess.domain.exceptions import AnalysisCancelledError

            raise AnalysisCancelledError("Engine play was cancelled")
        self.play_requests.append((board.fen(), clock))
        line = self.analyse_position(board, count=1).best_line
        if line is None:
            return None
        return EngineDecision(
            move=line.move,
            evaluation=line.evaluation,
            depth=line.depth,
            selective_depth=line.selective_depth,
            nodes=line.nodes,
            nps=line.nps,
            tablebase_hits=line.tablebase_hits,
            search_time_seconds=line.search_time_seconds,
            engine_name=self.engine_name,
        )

    def cancel_pending(self) -> None:
        return

    def close(self) -> None:
        self.closed = True
