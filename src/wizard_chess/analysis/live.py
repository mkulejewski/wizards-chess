"""Live position-analysis values, cache, and stale-result orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic

import chess

from wizard_chess.domain.move import ChessMove
from wizard_chess.engine.models import EngineEvaluation, PositionAnalysis


def position_key(fen: str) -> str:
    """Return a stable key retaining every FEN field that can affect legality."""
    fields = fen.split()
    if len(fields) != 6:
        raise ValueError(f"Invalid FEN position identifier: {fen!r}")
    # The full-move number does not affect chess rules. The half-move clock does
    # (fifty-move claims), so it deliberately remains part of the cache key.
    return " ".join(fields[:5])


@dataclass(frozen=True, slots=True)
class LiveAnalysisResult:
    """Deepest published engine result for one displayed game position."""

    position_id: str
    ply: int
    fen: str
    depth: int
    evaluation: EngineEvaluation
    principal_variation: tuple[ChessMove, ...] = ()
    sequence: int = 0
    timestamp_seconds: float = field(default_factory=monotonic)

    def __post_init__(self) -> None:
        if self.position_id != position_key(self.fen):
            raise ValueError("Live analysis position identifier does not match its FEN")
        if self.ply < 0:
            raise ValueError("Live analysis ply cannot be negative")
        if self.depth < 0:
            raise ValueError("Live analysis depth cannot be negative")


@dataclass(frozen=True, slots=True)
class AnalysisSelection:
    """One displayed-position generation plus any immediately reusable result."""

    generation: int
    position_id: str
    fen: str
    ply: int
    cached: LiveAnalysisResult | None


class GameAnalysisCache:
    """Temporary deepest-result cache owned for exactly one game/session."""

    def __init__(self) -> None:
        self._best: dict[str, LiveAnalysisResult] = {}

    def store(self, result: LiveAnalysisResult) -> bool:
        """Store a strictly deeper result and report whether the cache changed."""
        current = self._best.get(result.position_id)
        if current is not None and current.depth >= result.depth:
            return False
        self._best[result.position_id] = result
        return True

    def get_best(self, position: str) -> LiveAnalysisResult | None:
        """Retrieve a result by FEN or precomputed position key."""
        key = position_key(position) if len(position.split()) == 6 else position
        return self._best.get(key)

    def get_all_for_game(self) -> tuple[LiveAnalysisResult, ...]:
        """Return all deepest results in first-analysis order."""
        return tuple(self._best.values())

    def clear(self) -> None:
        self._best.clear()

    def __len__(self) -> int:
        return len(self._best)


class LiveAnalysisController:
    """Own per-game cache state and reject late results by generation and FEN."""

    def __init__(self, max_depth: int) -> None:
        if max_depth <= 0:
            raise ValueError("Live analysis maximum depth must be positive")
        self.max_depth = max_depth
        self.cache = GameAnalysisCache()
        self._generation = 0
        self._selection: AnalysisSelection | None = None
        self._sequence = 0
        self._fixed_complete: set[str] = set()

    @property
    def selection(self) -> AnalysisSelection | None:
        return self._selection

    def select(self, fen: str, ply: int) -> AnalysisSelection:
        """Select a displayed position, invalidating work for any prior position."""
        key = position_key(fen)
        current = self._selection
        if current is not None and current.position_id == key and current.ply == ply:
            refreshed = AnalysisSelection(
                generation=current.generation,
                position_id=key,
                fen=fen,
                ply=ply,
                cached=self.cache.get_best(key),
            )
            self._selection = refreshed
            return refreshed
        self._generation += 1
        selected = AnalysisSelection(
            generation=self._generation,
            position_id=key,
            fen=fen,
            ply=ply,
            cached=self.cache.get_best(key),
        )
        self._selection = selected
        return selected

    def make_result(
        self,
        selection: AnalysisSelection,
        analysis: PositionAnalysis,
    ) -> LiveAnalysisResult | None:
        """Convert one engine update into the canonical live-analysis result."""
        line = analysis.best_line
        try:
            analysis_position_id = position_key(analysis.fen)
        except ValueError:
            return None
        if line is None or analysis_position_id != selection.position_id:
            return None
        self._sequence += 1
        return LiveAnalysisResult(
            position_id=analysis_position_id,
            ply=selection.ply,
            fen=analysis.fen,
            depth=line.depth or 0,
            evaluation=line.evaluation,
            principal_variation=line.principal_variation,
            sequence=self._sequence,
        )

    def accept(self, generation: int, result: LiveAnalysisResult) -> bool:
        """Cache only a deeper result for the currently selected generation."""
        selected = self._selection
        if (
            selected is None
            or generation != selected.generation
            or result.position_id != selected.position_id
            or result.ply != selected.ply
        ):
            return False
        return self.cache.store(result)

    def store_terminal(self, selection: AnalysisSelection, board: chess.Board) -> bool:
        """Cache a canonical final evaluation without asking an engine to search."""
        if (
            not board.is_game_over(claim_draw=False)
            or self.cache.get_best(selection.position_id) is not None
        ):
            return False
        if board.is_checkmate():
            evaluation = EngineEvaluation(mate_in=-1 if board.turn == chess.WHITE else 1)
        else:
            evaluation = EngineEvaluation(score_cp=0)
        self._sequence += 1
        return self.accept(
            selection.generation,
            LiveAnalysisResult(
                position_id=selection.position_id,
                ply=selection.ply,
                fen=selection.fen,
                depth=0,
                evaluation=evaluation,
                sequence=self._sequence,
            ),
        )

    def needs_live_analysis(self, selection: AnalysisSelection) -> bool:
        best = self.cache.get_best(selection.position_id)
        return best is None or best.depth < self.max_depth

    def needs_fixed_analysis(self, selection: AnalysisSelection) -> bool:
        return selection.position_id not in self._fixed_complete

    def mark_fixed_complete(self, position_id: str) -> None:
        self._fixed_complete.add(position_id)

    def results_for(self, fens: tuple[str, ...]) -> tuple[LiveAnalysisResult | None, ...]:
        return tuple(self.cache.get_best(fen) for fen in fens)

    def invalidate_selection(self) -> None:
        """Reject all pending updates while retaining the per-game cache."""
        self._generation += 1
        self._selection = None

    def reset(self, max_depth: int | None = None) -> None:
        """Discard all state when the owning game is replaced or closed."""
        if max_depth is not None:
            if max_depth <= 0:
                raise ValueError("Live analysis maximum depth must be positive")
            self.max_depth = max_depth
        self.invalidate_selection()
        self.cache.clear()
        self._fixed_complete.clear()
        self._sequence = 0
