"""Believed physical piece placement, separate from chess rules and history."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import cast

import chess

from wizard_chess.hardware.errors import PhysicalBoardDesynchronized, PhysicalBoardUnknown
from wizard_chess.hardware.models import PhysicalSynchronization


class PhysicalPieceColor(StrEnum):
    WHITE = "white"
    BLACK = "black"


class PhysicalPieceType(StrEnum):
    PAWN = "pawn"
    KNIGHT = "knight"
    BISHOP = "bishop"
    ROOK = "rook"
    QUEEN = "queen"
    KING = "king"


_PIECE_TYPES = {
    "p": PhysicalPieceType.PAWN,
    "n": PhysicalPieceType.KNIGHT,
    "b": PhysicalPieceType.BISHOP,
    "r": PhysicalPieceType.ROOK,
    "q": PhysicalPieceType.QUEEN,
    "k": PhysicalPieceType.KING,
}


@dataclass(frozen=True, slots=True)
class PhysicalPiece:
    """Minimal stable identity for one physical chess piece."""

    identifier: str
    color: PhysicalPieceColor
    piece_type: PhysicalPieceType

    @classmethod
    def from_symbol(cls, symbol: str, *, identifier: str) -> PhysicalPiece:
        if len(symbol) != 1 or symbol.lower() not in _PIECE_TYPES:
            raise ValueError(f"Invalid chess piece symbol: {symbol}")
        color = PhysicalPieceColor.WHITE if symbol.isupper() else PhysicalPieceColor.BLACK
        return cls(identifier=identifier, color=color, piece_type=_PIECE_TYPES[symbol.lower()])

    @property
    def symbol(self) -> str:
        symbol = self.piece_type.value[0]
        if self.piece_type is PhysicalPieceType.KNIGHT:
            symbol = "n"
        return symbol.upper() if self.color is PhysicalPieceColor.WHITE else symbol


@dataclass(frozen=True, slots=True)
class OnSquare:
    """A piece believed to be resting on one board square."""

    square: str

    def __post_init__(self) -> None:
        normalized = self.square.lower()
        if normalized not in chess.SQUARE_NAMES:
            raise ValueError(f"Invalid chess square: {self.square}")
        object.__setattr__(self, "square", normalized)


@dataclass(frozen=True, slots=True)
class UnknownLocation:
    """A physical piece whose location cannot currently be trusted."""

    reason: str


PhysicalLocation = OnSquare | UnknownLocation


@dataclass(frozen=True, slots=True)
class PhysicalPiecePlacement:
    piece: PhysicalPiece
    location: PhysicalLocation


PieceSymbols = Mapping[str, str] | Iterable[tuple[str, str]]


@dataclass(frozen=True, slots=True)
class PhysicalBoardState:
    """Immutable snapshot of believed physical placement and synchronization."""

    placements: tuple[PhysicalPiecePlacement, ...]
    synchronization: PhysicalSynchronization = PhysicalSynchronization.UNKNOWN

    def __post_init__(self) -> None:
        identifiers: set[str] = set()
        squares: set[str] = set()
        for placement in self.placements:
            if placement.piece.identifier in identifiers:
                raise ValueError(f"Duplicate physical piece id: {placement.piece.identifier}")
            identifiers.add(placement.piece.identifier)
            if isinstance(placement.location, OnSquare):
                if placement.location.square in squares:
                    raise ValueError(f"Multiple physical pieces on {placement.location.square}")
                squares.add(placement.location.square)

    @classmethod
    def from_piece_symbols(
        cls,
        pieces: PieceSymbols,
        *,
        synchronization: PhysicalSynchronization = PhysicalSynchronization.SYNCHRONIZED,
    ) -> PhysicalBoardState:
        """Seed believed placement from an authoritative presentation snapshot."""
        items: Iterable[tuple[str, str]] = (
            cast(Mapping[str, str], pieces).items() if isinstance(pieces, Mapping) else pieces
        )
        placements: list[PhysicalPiecePlacement] = []
        for square, symbol in sorted(items):
            normalized = square.lower()
            piece = PhysicalPiece.from_symbol(
                symbol,
                identifier=f"{symbol.lower()}-{normalized}-{symbol.isupper()}",
            )
            placements.append(PhysicalPiecePlacement(piece, OnSquare(normalized)))
        return cls(tuple(placements), synchronization)

    @classmethod
    def from_chess_board(
        cls,
        board: chess.Board,
        *,
        synchronization: PhysicalSynchronization = PhysicalSynchronization.SYNCHRONIZED,
    ) -> PhysicalBoardState:
        """Seed from a copied authoritative board without retaining it as state."""
        pieces = (
            (chess.square_name(square), piece.symbol())
            for square, piece in board.piece_map().items()
        )
        return cls.from_piece_symbols(pieces, synchronization=synchronization)

    @property
    def pieces(self) -> Mapping[str, PhysicalPiece]:
        """Return an immutable square-to-piece view of known placements."""
        return MappingProxyType(
            {
                placement.location.square: placement.piece
                for placement in self.placements
                if isinstance(placement.location, OnSquare)
            }
        )

    @property
    def has_unknown_locations(self) -> bool:
        return any(isinstance(item.location, UnknownLocation) for item in self.placements)

    def piece_at(self, square: str) -> PhysicalPiece | None:
        return self.pieces.get(square.lower())

    def location_of(self, identifier: str) -> PhysicalLocation | None:
        for placement in self.placements:
            if placement.piece.identifier == identifier:
                return placement.location
        return None

    def with_synchronization(self, synchronization: PhysicalSynchronization) -> PhysicalBoardState:
        if self.has_unknown_locations:
            synchronization = PhysicalSynchronization.UNKNOWN
        return replace(self, synchronization=synchronization)

    def validate_simple_move(self, source_square: str, target_square: str) -> None:
        """Validate physical occupancy only, never chess legality."""
        if self.synchronization is PhysicalSynchronization.UNKNOWN:
            raise PhysicalBoardUnknown("Physical board placement is unknown")
        if self.synchronization is PhysicalSynchronization.DESYNCHRONIZED:
            raise PhysicalBoardDesynchronized("Physical board is desynchronized")
        if self.piece_at(source_square) is None:
            raise PhysicalBoardDesynchronized(
                f"No physical piece is believed to be on {source_square}"
            )
        if self.piece_at(target_square) is not None:
            raise PhysicalBoardDesynchronized(f"Physical destination {target_square} is occupied")

    def complete_simple_move(self, source_square: str, target_square: str) -> PhysicalBoardState:
        """Return the post-completion placement for an already-authorized simple move."""
        source = source_square.lower()
        target = target_square.lower()
        if self.has_unknown_locations:
            raise PhysicalBoardUnknown("Physical board contains an unknown piece location")
        if self.piece_at(target) is not None:
            raise PhysicalBoardDesynchronized(f"Physical destination {target} is occupied")
        moved = False
        updated: list[PhysicalPiecePlacement] = []
        for placement in self.placements:
            if isinstance(placement.location, OnSquare) and placement.location.square == source:
                updated.append(PhysicalPiecePlacement(placement.piece, OnSquare(target)))
                moved = True
            else:
                updated.append(placement)
        if not moved:
            raise PhysicalBoardUnknown(f"No known physical piece can be moved from {source}")
        return PhysicalBoardState(tuple(updated), PhysicalSynchronization.SYNCHRONIZED)

    def mark_move_uncertain(self, source_square: str, reason: str) -> PhysicalBoardState:
        """Forget the moving piece's location after execution may have begun."""
        source = source_square.lower()
        updated = tuple(
            PhysicalPiecePlacement(placement.piece, UnknownLocation(reason))
            if isinstance(placement.location, OnSquare) and placement.location.square == source
            else placement
            for placement in self.placements
        )
        return PhysicalBoardState(updated, PhysicalSynchronization.UNKNOWN)

    def placement_symbols(self) -> Mapping[str, str]:
        return MappingProxyType({square: piece.symbol for square, piece in self.pieces.items()})

    def matches_piece_symbols(self, pieces: PieceSymbols) -> bool:
        if self.has_unknown_locations:
            return False
        items: Iterable[tuple[str, str]] = (
            cast(Mapping[str, str], pieces).items() if isinstance(pieces, Mapping) else pieces
        )
        expected = {square.lower(): symbol for square, symbol in items}
        return dict(self.placement_symbols()) == expected

    def matches_chess_board(self, board: chess.Board) -> bool:
        expected = (
            (chess.square_name(square), piece.symbol())
            for square, piece in board.piece_map().items()
        )
        return self.matches_piece_symbols(expected)
