"""Post-game analysis orchestration over immutable board copies."""

from __future__ import annotations

from collections.abc import Callable

import chess

from wizard_chess.analysis.classification import ClassificationPolicy
from wizard_chess.analysis.models import (
    GameAnalysis,
    MoveAnalysis,
    MoveClassification,
    SideStatistics,
)
from wizard_chess.domain.exceptions import AnalysisCancelledError
from wizard_chess.domain.game import ChessGame
from wizard_chess.domain.move import ChessMove
from wizard_chess.domain.results import PlayerColor
from wizard_chess.engine.base import ChessEngine
from wizard_chess.engine.models import EngineEvaluation, PositionAnalysis

ProgressCallback = Callable[[int, int], None]
CancellationCheck = Callable[[], bool]


class AnalysisService:
    """Replay and compare moves without modifying the original game."""

    def __init__(
        self,
        engine: ChessEngine,
        policy: ClassificationPolicy | None = None,
        *,
        analysis_time_ms: int | None = None,
    ) -> None:
        self._engine = engine
        self._policy = policy or ClassificationPolicy()
        self._analysis_time_ms = analysis_time_ms
        self._cache: dict[str, PositionAnalysis] = {}

    def analyse_game(
        self,
        game: ChessGame,
        *,
        on_progress: ProgressCallback | None = None,
        cancel_requested: CancellationCheck | None = None,
    ) -> GameAnalysis:
        """Analyze each played move, reporting progress after every ply."""
        cancellation = cancel_requested or (lambda: False)
        source_board = game.board
        moves = tuple(source_board.move_stack)
        replay = source_board.root()
        results: list[MoveAnalysis] = []
        total = len(moves)

        for index, python_move in enumerate(moves, start=1):
            if cancellation():
                raise AnalysisCancelledError("Post-game analysis was cancelled")
            mover = PlayerColor.WHITE if replay.turn == chess.WHITE else PlayerColor.BLACK
            before = self._analyse(replay, cancellation)
            before_line = before.best_line
            before_evaluation = before_line.evaluation if before_line is not None else None
            preferred = before_line.move if before_line is not None else None
            principal_variation = before_line.principal_variation if before_line is not None else ()
            played = ChessMove.from_python_chess(python_move)
            san = replay.san(python_move)
            replay.push(python_move)
            after = self._analyse(replay, cancellation)
            after_evaluation = self._evaluation_for_position(replay, after)
            loss = _centipawn_loss(mover, before_evaluation, after_evaluation)
            best_match = preferred == played
            results.append(
                MoveAnalysis(
                    ply=index,
                    color=mover,
                    san=san,
                    played_move=played,
                    preferred_move=preferred,
                    evaluation_before=before_evaluation,
                    evaluation_after=after_evaluation,
                    principal_variation=principal_variation,
                    centipawn_loss=loss,
                    classification=self._policy.classify(loss, best_move_match=best_match),
                )
            )
            if on_progress is not None:
                on_progress(index, total)

        move_results = tuple(results)
        return GameAnalysis(
            source_pgn=game.to_pgn(),
            moves=move_results,
            white=_statistics(move_results, PlayerColor.WHITE),
            black=_statistics(move_results, PlayerColor.BLACK),
        )

    def _analyse(
        self,
        board: chess.Board,
        cancellation: CancellationCheck,
    ) -> PositionAnalysis:
        fen = board.fen()
        cached = self._cache.get(fen)
        if cached is not None:
            return cached
        analysis = self._engine.analyse_position(
            board.copy(stack=False),
            count=1,
            time_ms=self._analysis_time_ms,
            cancel_requested=cancellation,
        )
        self._cache[fen] = analysis
        return analysis

    @staticmethod
    def _evaluation_for_position(
        board: chess.Board,
        analysis: PositionAnalysis,
    ) -> EngineEvaluation | None:
        line = analysis.best_line
        if line is not None:
            return line.evaluation
        if board.is_checkmate():
            return EngineEvaluation(mate_in=-1 if board.turn == chess.WHITE else 1)
        if board.is_game_over(claim_draw=False):
            return EngineEvaluation(score_cp=0)
        return None


def _centipawn_loss(
    mover: PlayerColor,
    before: EngineEvaluation | None,
    after: EngineEvaluation | None,
) -> int:
    if before is None or after is None:
        return 0
    before_cp = before.equivalent_cp()
    after_cp = after.equivalent_cp()
    return max(0, before_cp - after_cp if mover is PlayerColor.WHITE else after_cp - before_cp)


def _statistics(
    moves: tuple[MoveAnalysis, ...],
    color: PlayerColor,
) -> SideStatistics:
    selected = tuple(move for move in moves if move.color is color)
    count = len(selected)
    average = sum(move.centipawn_loss for move in selected) / count if count else 0.0
    return SideStatistics(
        moves=count,
        average_centipawn_loss=average,
        best_move_matches=sum(
            move.preferred_move == move.played_move
            for move in selected
            if move.preferred_move is not None
        ),
        inaccuracies=sum(move.classification is MoveClassification.INACCURACY for move in selected),
        mistakes=sum(move.classification is MoveClassification.MISTAKE for move in selected),
        blunders=sum(move.classification is MoveClassification.BLUNDER for move in selected),
    )
