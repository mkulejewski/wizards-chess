"""English and Polish grammars that emit shared language-independent intents."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from wizard_chess.commands.intents import (
    CastleSide,
    CheckClaim,
    CommandIntent,
    CommandName,
    ContextualMoveIntent,
    Intent,
    PieceName,
)
from wizard_chess.commands.parser import CommandParser
from wizard_chess.configuration import VoiceLanguage
from wizard_chess.domain.exceptions import InvalidCommandError
from wizard_chess.speech.polish import PolishTranscriptNormalizer

_SQUARE = re.compile(r"^[a-h][1-8]$")

_ENGLISH_COMMANDS: Mapping[str, CommandName] = {
    "new": CommandName.NEW,
    "new game": CommandName.NEW,
    "start new game": CommandName.NEW,
    "undo": CommandName.UNDO,
    "undo move": CommandName.UNDO,
    "redo": CommandName.REDO,
    "redo move": CommandName.REDO,
    "resign": CommandName.RESIGN,
    "i resign": CommandName.RESIGN,
    "draw": CommandName.DRAW,
    "agree draw": CommandName.DRAW,
    "save": CommandName.SAVE,
    "save game": CommandName.SAVE,
    "repeat": CommandName.REPEAT,
    "repeat that": CommandName.REPEAT,
    "enable analysis": CommandName.ANALYSIS_ON,
    "disable analysis": CommandName.ANALYSIS_OFF,
}

_POLISH_COMMANDS: Mapping[str, CommandName] = {
    "nowa gra": CommandName.NEW,
    "nową grę": CommandName.NEW,
    "cofnij": CommandName.UNDO,
    "cofnij ruch": CommandName.UNDO,
    "ponów": CommandName.REDO,
    "ponow": CommandName.REDO,
    "powtórz ruch": CommandName.REDO,
    "powtorz ruch": CommandName.REDO,
    "powtórz": CommandName.REPEAT,
    "powtorz": CommandName.REPEAT,
    "zapisz": CommandName.SAVE,
    "zapisz grę": CommandName.SAVE,
    "zapisz gre": CommandName.SAVE,
    "poddaję się": CommandName.RESIGN,
    "poddaje sie": CommandName.RESIGN,
    "remis": CommandName.DRAW,
}

_ENGLISH_PIECES: Mapping[str, PieceName] = {
    "pawn": PieceName.PAWN,
    "knight": PieceName.KNIGHT,
    "bishop": PieceName.BISHOP,
    "rook": PieceName.ROOK,
    "queen": PieceName.QUEEN,
    "king": PieceName.KING,
}

_POLISH_PIECES: Mapping[str, PieceName] = {
    "pion": PieceName.PAWN,
    "piona": PieceName.PAWN,
    "skoczek": PieceName.KNIGHT,
    "skoczka": PieceName.KNIGHT,
    "goniec": PieceName.BISHOP,
    "gońca": PieceName.BISHOP,
    "gonca": PieceName.BISHOP,
    "wieża": PieceName.ROOK,
    "wieza": PieceName.ROOK,
    "wieżę": PieceName.ROOK,
    "wiezę": PieceName.ROOK,
    "hetman": PieceName.QUEEN,
    "hetmana": PieceName.QUEEN,
    "król": PieceName.KING,
    "krol": PieceName.KING,
    "króla": PieceName.KING,
    "krola": PieceName.KING,
}

_PROMOTIONS: Mapping[str, str] = {
    "queen": "q",
    "hetman": "q",
    "hetmana": "q",
    "rook": "r",
    "wieża": "r",
    "wieza": "r",
    "wieżę": "r",
    "bishop": "b",
    "goniec": "b",
    "gońca": "b",
    "gonca": "b",
    "knight": "n",
    "skoczek": "n",
    "skoczka": "n",
}


class EnglishCommandParser:
    """Deterministic English domain grammar plus compact typed notation fallback."""

    def __init__(self) -> None:
        self._typed = CommandParser()

    def parse(self, text: str) -> Intent:
        normalized = " ".join(text.strip().lower().split())
        command = _ENGLISH_COMMANDS.get(normalized)
        if command is not None:
            return CommandIntent(command)
        semantic = _parse_contextual(
            normalized.split(),
            pieces=_ENGLISH_PIECES,
            to_words={"to", "from"},
            capture_words={"takes", "take", "captures", "capture"},
            check_words={"check": CheckClaim.CHECK, "checkmate": CheckClaim.CHECKMATE},
        )
        return semantic if semantic is not None else self._typed.parse(text)


class PolishCommandParser:
    """Targeted Polish chess grammar producing the same intents as English."""

    def __init__(self, normalizer: PolishTranscriptNormalizer | None = None) -> None:
        self._normalizer = normalizer or PolishTranscriptNormalizer()

    def parse(self, text: str) -> Intent:
        normalized = self._normalizer.normalize(text)
        command = _POLISH_COMMANDS.get(normalized)
        if command is not None:
            return CommandIntent(command)
        tokens = normalized.split()
        if tokens in (["roszada", "krótka"], ["krótka", "roszada"]):
            return ContextualMoveIntent(castle=CastleSide.KINGSIDE)
        if tokens in (["roszada", "długa"], ["długa", "roszada"]):
            return ContextualMoveIntent(castle=CastleSide.QUEENSIDE)
        semantic = _parse_contextual(
            tokens,
            pieces=_POLISH_PIECES,
            to_words={"na", "z"},
            capture_words={"bije", "bierze"},
            check_words={
                "szach": CheckClaim.CHECK,
                "mat": CheckClaim.CHECKMATE,
                "szachmat": CheckClaim.CHECKMATE,
            },
        )
        if semantic is not None:
            return semantic
        if tokens and _SQUARE.fullmatch(tokens[0]):
            promotion = next(
                (_PROMOTIONS[token] for token in reversed(tokens[1:]) if token in _PROMOTIONS),
                None,
            )
            if promotion is not None:
                return ContextualMoveIntent(
                    destination=tokens[0],
                    piece=PieceName.PAWN,
                    promotion=promotion,
                )
        if len(tokens) == 1 and _SQUARE.fullmatch(tokens[0]):
            return ContextualMoveIntent(destination=tokens[0], piece=PieceName.PAWN)
        raise InvalidCommandError(f"Nie rozpoznano polecenia: {text}")


class LanguageCommandParser:
    """Select an explicit language grammar while preserving English defaults."""

    def __init__(self, language: VoiceLanguage = VoiceLanguage.ENGLISH) -> None:
        self.language = language
        self._english = EnglishCommandParser()
        self._polish = PolishCommandParser()

    def parse(self, text: str) -> Intent:
        if self.language is VoiceLanguage.POLISH:
            try:
                return self._polish.parse(text)
            except InvalidCommandError:
                return self._english.parse(text)
        if self.language is VoiceLanguage.AUTO:
            try:
                return self._english.parse(text)
            except InvalidCommandError:
                return self._polish.parse(text)
        return self._english.parse(text)


def _parse_contextual(
    tokens: Sequence[str],
    *,
    pieces: Mapping[str, PieceName],
    to_words: set[str],
    capture_words: set[str],
    check_words: Mapping[str, CheckClaim],
) -> ContextualMoveIntent | None:
    if not tokens:
        return None
    working = list(tokens)
    check_claim: CheckClaim | None = None
    if len(working) >= 2 and working[-2:] == ["szach", "mat"]:
        check_claim = CheckClaim.CHECKMATE
        working = working[:-2]
    elif working and working[-1] in check_words:
        check_claim = check_words[working[-1]]
        working = working[:-1]

    if working in (["castle", "kingside"], ["short", "castle"]):
        return ContextualMoveIntent(castle=CastleSide.KINGSIDE, check_claim=check_claim)
    if working in (["castle", "queenside"], ["long", "castle"]):
        return ContextualMoveIntent(castle=CastleSide.QUEENSIDE, check_claim=check_claim)

    piece = pieces.get(working[0]) if working else None
    if piece is None:
        return None
    remainder = working[1:]
    capture: bool | None = None
    if any(token in capture_words for token in remainder):
        capture = True
        remainder = [token for token in remainder if token not in capture_words]
    promotion: str | None = None
    for token in reversed(remainder):
        if token in _PROMOTIONS:
            promotion = _PROMOTIONS[token]
            remainder.remove(token)
            break
    remainder = [token for token in remainder if token not in {"promocja", "promotion"}]
    squares = [token for token in remainder if _SQUARE.fullmatch(token)]
    if not squares:
        return None
    origin = squares[0] if len(squares) > 1 else None
    destination = squares[-1]
    return ContextualMoveIntent(
        piece=piece,
        origin=origin,
        destination=destination,
        capture=capture,
        promotion=promotion,
        check_claim=check_claim,
    )
