"""Structured user intentions produced by input adapters."""

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class MoveIntent:
    """An attempt to move from one coordinate to another."""

    source: str
    target: str
    promotion: str | None = None


@dataclass(frozen=True, slots=True)
class SanMoveIntent:
    """An attempt to move using Standard Algebraic Notation."""

    notation: str


class CommandName(StrEnum):
    """Commands handled by the development CLI."""

    UNDO = "undo"
    REDO = "redo"
    FEN = "fen"
    PGN = "pgn"
    NEW = "new"
    QUIT = "quit"
    HELP = "help"
    LEGAL = "legal"


@dataclass(frozen=True, slots=True)
class CommandIntent:
    """A state-management or informational command."""

    command: CommandName


MoveCommandIntent = MoveIntent | SanMoveIntent
Intent = MoveCommandIntent | CommandIntent
