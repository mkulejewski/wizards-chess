"""State-free parser for coordinate, SAN, and application commands."""

import logging
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

LOGGER = logging.getLogger(__name__)

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
_SPOKEN_PIECES = {
    "king": "K",
    "queen": "Q",
    "rook": "R",
    "bishop": "B",
    "knight": "N",
}
_SPOKEN_SUFFIXES = {"check": "+", "checkmate": "#"}


class CommandParser:
    """Parse text without consulting or modifying game state."""

    def parse(self, text: str) -> Intent:
        normalized = normalize_command(text)
        LOGGER.debug("Parsing command input: raw=%r normalized=%r", text, normalized)
        if not normalized:
            raise InvalidCommandError("Enter a move or command")

        try:
            return CommandIntent(CommandName(normalized))
        except ValueError:
            pass

        tokens = normalized.split()
        spoken_intent = self._spoken_move_intent(tokens)
        if spoken_intent is not None:
            return spoken_intent

        if tokens and tokens[0] == "move":
            tokens.pop(0)
        if len(tokens) >= 2 and tokens[1] == "to":
            tokens.pop(1)

        if len(tokens) >= 2 and _SQUARE.fullmatch(tokens[0]) and _SQUARE.fullmatch(tokens[1]):
            return self._coordinate_intent(tokens, text)

        notation = _canonicalize_san_case(re.sub(r"\s+", " ", text.strip()))
        if _SAN.fullmatch(notation):
            return SanMoveIntent(notation)

        raise InvalidCommandError(f"Could not parse command: {text}")

    def _spoken_move_intent(self, tokens: list[str]) -> MoveIntent | SanMoveIntent | None:
        """Translate narrow human piece phrases without consulting game state."""
        if not tokens:
            return None

        suffix = ""
        if tokens[-1] in _SPOKEN_SUFFIXES:
            suffix = _SPOKEN_SUFFIXES[tokens[-1]]
            tokens = tokens[:-1]
        if not tokens:
            return None

        if len(tokens) == 2 and tokens[0] == "castle":
            if tokens[1] == "kingside":
                return SanMoveIntent(f"O-O{suffix}")
            if tokens[1] == "queenside":
                return SanMoveIntent(f"O-O-O{suffix}")

        if (
            len(tokens) == 3
            and len(tokens[0]) == 1
            and tokens[0] in "abcdefgh"
            and tokens[1] == "takes"
            and _SQUARE.fullmatch(tokens[2])
        ):
            return SanMoveIntent(f"{tokens[0]}x{tokens[2]}{suffix}")

        piece_word = tokens[0]
        remainder = tokens[1:]
        if piece_word == "pawn":
            return self._spoken_pawn_intent(remainder, suffix)

        piece = _SPOKEN_PIECES.get(piece_word)
        if piece is None:
            if len(tokens) == 1 and _SQUARE.fullmatch(tokens[0]) and suffix:
                return SanMoveIntent(f"{tokens[0]}{suffix}")
            return None

        if remainder and remainder[0] == "to":
            remainder = remainder[1:]
        if len(remainder) == 1 and _SQUARE.fullmatch(remainder[0]):
            return SanMoveIntent(f"{piece}{remainder[0]}{suffix}")
        if len(remainder) == 2 and remainder[0] == "takes" and _SQUARE.fullmatch(remainder[1]):
            return SanMoveIntent(f"{piece}x{remainder[1]}{suffix}")
        if (
            len(remainder) == 2
            and _SQUARE.fullmatch(remainder[0])
            and _SQUARE.fullmatch(remainder[1])
            and not suffix
        ):
            return MoveIntent(remainder[0], remainder[1])
        return None

    @staticmethod
    def _spoken_pawn_intent(remainder: list[str], suffix: str) -> SanMoveIntent | None:
        if remainder and remainder[0] == "to":
            remainder = remainder[1:]
        if len(remainder) == 1 and _SQUARE.fullmatch(remainder[0]):
            return SanMoveIntent(f"{remainder[0]}{suffix}")
        return None

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


def _canonicalize_san_case(notation: str) -> str:
    """Restore case for compact SAN that recognizers often lowercase."""
    if notation.lower() in {"o-o", "o-o-o"}:
        return notation.upper()
    if notation and notation[0] in "kqrbn":
        notation = notation[0].upper() + notation[1:]
    return re.sub(r"=([qrbn])", lambda match: f"={match.group(1).upper()}", notation)
