"""Game-state values that do not leak python-chess types."""

from dataclasses import dataclass
from enum import StrEnum


class PlayerColor(StrEnum):
    """A player side."""

    WHITE = "white"
    BLACK = "black"


class GameStatus(StrEnum):
    """The most significant current condition of the game."""

    ONGOING = "ongoing"
    CHECK = "check"
    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    INSUFFICIENT_MATERIAL = "insufficient_material"
    SEVENTY_FIVE_MOVE_DRAW = "seventy_five_move_draw"
    FIVEFOLD_REPETITION = "fivefold_repetition"
    OTHER_GAME_OVER = "other_game_over"
    RESIGNED = "resigned"
    AGREED_DRAW = "agreed_draw"


@dataclass(frozen=True, slots=True)
class GameResult:
    """A snapshot of terminal and claimable game conditions."""

    status: GameStatus
    notation: str
    winner: PlayerColor | None
    can_claim_fifty_moves: bool
    can_claim_threefold_repetition: bool

    @property
    def is_over(self) -> bool:
        """Whether the rules engine considers the game terminal."""
        return self.notation != "*"

    @property
    def can_claim_draw(self) -> bool:
        """Whether either supported claimable-draw rule applies."""
        return self.can_claim_fifty_moves or self.can_claim_threefold_repetition
