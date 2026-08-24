"""Authoritative chess domain model."""

from wizard_chess.domain.events import MoveExecuted
from wizard_chess.domain.exceptions import (
    AmbiguousMoveError,
    AnalysisCancelledError,
    EngineCrashedError,
    EngineError,
    EngineUnavailableError,
    GameTerminationError,
    InvalidCommandError,
    InvalidFenError,
    InvalidMoveError,
    InvalidPgnError,
    NoMoveToRedoError,
    NoMoveToUndoError,
    WizardChessError,
)
from wizard_chess.domain.game import ChessGame
from wizard_chess.domain.move import ChessMove
from wizard_chess.domain.results import GameResult, GameStatus, PlayerColor

__all__ = [
    "AmbiguousMoveError",
    "AnalysisCancelledError",
    "ChessGame",
    "ChessMove",
    "EngineCrashedError",
    "EngineError",
    "EngineUnavailableError",
    "GameResult",
    "GameStatus",
    "GameTerminationError",
    "InvalidCommandError",
    "InvalidFenError",
    "InvalidMoveError",
    "InvalidPgnError",
    "MoveExecuted",
    "NoMoveToRedoError",
    "NoMoveToUndoError",
    "PlayerColor",
    "WizardChessError",
]
