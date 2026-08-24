"""Structured, persistable results for move-by-move game analysis."""

from dataclasses import dataclass
from enum import StrEnum

from wizard_chess.domain.move import ChessMove
from wizard_chess.domain.results import PlayerColor
from wizard_chess.engine.models import EngineEvaluation


class MoveClassification(StrEnum):
    """Project-defined quality bands based on centipawn loss."""

    BEST = "best"
    EXCELLENT = "excellent"
    GOOD = "good"
    INACCURACY = "inaccuracy"
    MISTAKE = "mistake"
    BLUNDER = "blunder"


@dataclass(frozen=True, slots=True)
class MoveAnalysis:
    """Analysis of one played move and its surrounding positions."""

    ply: int
    color: PlayerColor
    san: str
    played_move: ChessMove
    preferred_move: ChessMove | None
    evaluation_before: EngineEvaluation | None
    evaluation_after: EngineEvaluation | None
    principal_variation: tuple[ChessMove, ...]
    centipawn_loss: int
    classification: MoveClassification


@dataclass(frozen=True, slots=True)
class SideStatistics:
    """Aggregated transparent metrics for one player."""

    moves: int
    average_centipawn_loss: float
    best_move_matches: int
    inaccuracies: int
    mistakes: int
    blunders: int


@dataclass(frozen=True, slots=True)
class GameAnalysis:
    """Complete analysis that never replaces or mutates the source game."""

    source_pgn: str
    moves: tuple[MoveAnalysis, ...]
    white: SideStatistics
    black: SideStatistics
    engine_name: str = "uci"
    schema_version: int = 1
