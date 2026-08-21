"""State-free parser for coordinate, SAN, and application commands."""

import re

from wizard_chess.commands.intents import (
    CommandIntent,
    CommandName,
    Intent,
    MoveIntent,
    SanMoveIntent,
)
from wizard_chess.commands.normalizer import normalize_command
from wizard_chess.domain.exceptions import InvalidCommandError

_SQUARE = re.compile(r"^[a-h][1-8]$")
_SAN = re.compile(
    r"^(?:"
    r"O-O(?:-O)?"
    r"|[a-h](?:[1-8]|x[a-h][1-8])(?:=[QRBN])?"
    r"|[KQRBN](?:[a-h]|[1-8]|[a-h][1-8])?x?[a-h][1-8]"
    r")[+#]?$"
)
_PROMOTIONS = {
    "q": "q",
    "queen": "q",
    "r": "r",
    "rook": "r",
    "b": "b",
    "bishop": "b",
    "n": "n",
    "knight": "n",
}


class CommandParser:
    """Parse text without consulting or modifying game state."""

    def parse(self, text: str) -> Intent:
        normalized = normalize_command(text)
        if not normalized:
            raise InvalidCommandError("Enter a move or command")

        try:
            return CommandIntent(CommandName(normalized))
        except ValueError:
            pass

        tokens = normalized.split()
        if tokens and tokens[0] == "move":
            tokens.pop(0)
        if len(tokens) >= 2 and tokens[1] == "to":
            tokens.pop(1)

        if len(tokens) >= 2 and _SQUARE.fullmatch(tokens[0]) and _SQUARE.fullmatch(tokens[1]):
            return self._coordinate_intent(tokens, text)

        notation = re.sub(r"\s+", " ", text.strip())
        if _SAN.fullmatch(notation):
            return SanMoveIntent(notation)

        raise InvalidCommandError(f"Could not parse command: {text}")

    def _coordinate_intent(self, tokens: list[str], original_text: str) -> MoveIntent:
        """Build a coordinate intent after the coordinate prefix has been recognized."""

        promotion: str | None = None
        remainder = tokens[2:]
        if remainder:
            if remainder[0] in {"promote", "promotion"}:
                remainder.pop(0)
            if remainder and remainder[0] == "to":
                remainder.pop(0)
            if len(remainder) != 1 or remainder[0] not in _PROMOTIONS:
                raise InvalidCommandError(f"Invalid promotion in command: {original_text}")
            promotion = _PROMOTIONS[remainder[0]]

        return MoveIntent(source=tokens[0], target=tokens[1], promotion=promotion)
