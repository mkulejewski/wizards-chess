"""Testable board orientation and click-to-move presentation logic."""

from dataclasses import dataclass
from enum import StrEnum

import chess

from wizard_chess.application.session import GameSession
from wizard_chess.domain.events import MoveExecuted
from wizard_chess.domain.exceptions import InvalidMoveError
from wizard_chess.domain.move import ChessMove


class BoardOrientation(StrEnum):
    """The side displayed at the bottom of the board."""

    WHITE = "white"
    BLACK = "black"


def square_for_cell(row: int, column: int, orientation: BoardOrientation) -> str:
    """Map a zero-based visible row and column to a chess square."""
    if not 0 <= row < 8 or not 0 <= column < 8:
        raise ValueError(f"Board cell is out of range: {row}, {column}")
    if orientation is BoardOrientation.WHITE:
        file_index = column
        rank_index = 7 - row
    else:
        file_index = 7 - column
        rank_index = row
    return chess.square_name(chess.square(file_index, rank_index))


def cell_for_square(square: str, orientation: BoardOrientation) -> tuple[int, int]:
    """Map a chess square to its zero-based visible row and column."""
    try:
        square_index = chess.parse_square(square.lower())
    except ValueError as error:
        raise ValueError(f"Invalid chess square: {square}") from error
    file_index = chess.square_file(square_index)
    rank_index = chess.square_rank(square_index)
    if orientation is BoardOrientation.WHITE:
        return 7 - rank_index, file_index
    return rank_index, 7 - file_index


@dataclass(frozen=True, slots=True)
class ClickResult:
    """Presentation result of one square click."""

    move_event: MoveExecuted | None = None
    promotion_choices: tuple[str, ...] = ()


class BoardInteraction:
    """Ephemeral selection state backed by authoritative legal moves."""

    _PROMOTION_ORDER = ("q", "r", "b", "n")

    def __init__(self, session: GameSession) -> None:
        self._session = session
        self.selected_square: str | None = None
        self.legal_destinations: tuple[str, ...] = ()
        self.orientation = BoardOrientation.WHITE

    def clear_selection(self) -> None:
        """Clear presentation-only selection and destination highlights."""
        self.selected_square = None
        self.legal_destinations = ()

    def flip(self) -> None:
        """Rotate presentation without modifying the authoritative game."""
        self.orientation = (
            BoardOrientation.BLACK
            if self.orientation is BoardOrientation.WHITE
            else BoardOrientation.WHITE
        )
        self.clear_selection()

    def click_square(self, square: str, promotion: str | None = None) -> ClickResult:
        """Select a source or submit an authoritative move for a selected destination."""
        square = square.lower()
        if square not in chess.SQUARE_NAMES:
            raise InvalidMoveError(f"Invalid clicked square: {square}")

        legal_moves = self._session.snapshot().legal_moves
        if self.selected_square is not None:
            destination_moves = tuple(
                move
                for move in legal_moves
                if move.source == self.selected_square and move.target == square
            )
            if destination_moves:
                return self._complete_move(destination_moves, promotion)

        selectable_moves = tuple(move for move in legal_moves if move.source == square)
        if selectable_moves:
            self.selected_square = square
            self.legal_destinations = tuple(
                sorted({move.target for move in selectable_moves}, key=chess.parse_square)
            )
        else:
            self.clear_selection()
        return ClickResult()

    def _complete_move(
        self, candidates: tuple[ChessMove, ...], promotion: str | None
    ) -> ClickResult:
        promotion_choices = tuple(
            piece
            for piece in self._PROMOTION_ORDER
            if any(move.promotion == piece for move in candidates)
        )
        if promotion_choices and promotion is None:
            return ClickResult(promotion_choices=promotion_choices)

        matching = tuple(move for move in candidates if move.promotion == promotion)
        if len(matching) != 1:
            raise InvalidMoveError(f"Invalid promotion choice: {promotion}")

        event = self._session.play_move(matching[0])
        self.clear_selection()
        return ClickResult(move_event=event)
