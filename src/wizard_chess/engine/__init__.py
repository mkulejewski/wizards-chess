"""Optional engine port and Stockfish implementation."""

from wizard_chess.engine.base import ChessEngine
from wizard_chess.engine.factory import create_stockfish_engine
from wizard_chess.engine.mock import FakeEngine
from wizard_chess.engine.models import (
    EngineClockState,
    EngineDecision,
    EngineEvaluation,
    EngineLine,
    PositionAnalysis,
    evaluation_share,
)
from wizard_chess.engine.stockfish import StockfishEngine, normalize_score

__all__ = [
    "ChessEngine",
    "EngineClockState",
    "EngineDecision",
    "EngineEvaluation",
    "EngineLine",
    "FakeEngine",
    "PositionAnalysis",
    "StockfishEngine",
    "create_stockfish_engine",
    "evaluation_share",
    "normalize_score",
]
