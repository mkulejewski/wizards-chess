"""Authoritative chess domain model."""

from wizard_chess.domain.events import MoveExecuted
from wizard_chess.domain.exceptions import (
    AmbiguousMoveError,
    InvalidCommandError,
    InvalidFenError,
    InvalidMoveError,
    NoMoveToRedoError,
    NoMoveToUndoError,
    WizardChessError,
)
from wizard_chess.domain.game import ChessGame
from wizard_chess.domain.move import ChessMove
from wizard_chess.domain.results import GameResult, GameStatus, PlayerColor

__all__ = [
    "AmbiguousMoveError",
    "ChessGame",
    "ChessMove",
    "GameResult",
    "GameStatus",
    "InvalidCommandError",
    "InvalidFenError",
    "InvalidMoveError",
    "MoveExecuted",
    "NoMoveToRedoError",
    "NoMoveToUndoError",
    "PlayerColor",
    "WizardChessError",
]
