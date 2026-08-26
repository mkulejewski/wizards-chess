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


class PieceName(StrEnum):
    """Language-independent chess piece vocabulary for contextual commands."""

    PAWN = "pawn"
    KNIGHT = "knight"
    BISHOP = "bishop"
    ROOK = "rook"
    QUEEN = "queen"
    KING = "king"


class CastleSide(StrEnum):
    """A requested castling wing."""

    KINGSIDE = "kingside"
    QUEENSIDE = "queenside"


class CheckClaim(StrEnum):
    """Optional spoken assertion about the resulting position."""

    CHECK = "check"
    CHECKMATE = "checkmate"


@dataclass(frozen=True, slots=True)
class ContextualMoveIntent:
    """Language-neutral partial move resolved only from authoritative legal moves."""

    destination: str | None = None
    piece: PieceName | None = None
    origin: str | None = None
    capture: bool | None = None
    promotion: str | None = None
    castle: CastleSide | None = None
    check_claim: CheckClaim | None = None


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
    RESIGN = "resign"
    DRAW = "draw"
    PROPOSE_DRAW = "propose_draw"
    ACCEPT_DRAW = "accept_draw"
    REJECT_DRAW = "reject_draw"
    SAVE = "save"
    REPEAT = "repeat"
    ANALYSIS_ON = "analysis_on"
    ANALYSIS_OFF = "analysis_off"


@dataclass(frozen=True, slots=True)
class CommandIntent:
    """A state-management or informational command."""

    command: CommandName


MoveCommandIntent = MoveIntent | SanMoveIntent | ContextualMoveIntent
Intent = MoveCommandIntent | CommandIntent
