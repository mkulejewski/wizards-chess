"""Expected application failures exposed by Wizard Chess."""


class WizardChessError(Exception):
    """Base class for expected Wizard Chess failures."""


class InvalidMoveError(WizardChessError):
    """Raised when a move is malformed or illegal in the current position."""


class InvalidCommandError(WizardChessError):
    """Raised when text cannot be interpreted as a supported command."""


class AmbiguousMoveError(InvalidMoveError):
    """Raised when an intent matches more than one legal move."""


class InvalidFenError(WizardChessError):
    """Raised when a FEN string does not describe a valid chess position."""


class NoMoveToUndoError(WizardChessError):
    """Raised when undo is requested at the start of a position."""


class NoMoveToRedoError(WizardChessError):
    """Raised when redo is requested without an undone move."""
