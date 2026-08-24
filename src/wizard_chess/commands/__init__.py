"""Typed-command interpretation."""

from wizard_chess.commands.intents import (
    CastleSide,
    CheckClaim,
    CommandIntent,
    CommandName,
    ContextualMoveIntent,
    MoveIntent,
    PieceName,
    SanMoveIntent,
)
from wizard_chess.commands.language import LanguageCommandParser
from wizard_chess.commands.parser import CommandParser
from wizard_chess.commands.resolver import MoveResolver

__all__ = [
    "CastleSide",
    "CheckClaim",
    "CommandIntent",
    "CommandName",
    "CommandParser",
    "ContextualMoveIntent",
    "LanguageCommandParser",
    "MoveIntent",
    "MoveResolver",
    "PieceName",
    "SanMoveIntent",
]
