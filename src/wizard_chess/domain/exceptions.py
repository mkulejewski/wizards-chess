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


class InvalidPgnError(WizardChessError):
    """Raised when PGN cannot be parsed into one valid main-line game."""


class GameTerminationError(WizardChessError):
    """Raised when a requested non-move game termination is not valid."""


class EngineError(WizardChessError):
    """Base class for controlled chess-engine failures."""


class EngineUnavailableError(EngineError):
    """Raised when the configured chess engine cannot be started."""


class EngineCrashedError(EngineError):
    """Raised when an active chess engine terminates unexpectedly."""


class AnalysisCancelledError(EngineError):
    """Raised when an engine or post-game analysis request is cancelled."""


class NoMoveToUndoError(WizardChessError):
    """Raised when undo is requested at the start of a position."""


class NoMoveToRedoError(WizardChessError):
    """Raised when redo is requested without an undone move."""
