"""Idealized chess-square geometry for transport-neutral planning."""

from dataclasses import dataclass

import chess

from wizard_chess.hardware.models import PhysicalPosition


@dataclass(frozen=True, slots=True)
class BoardGeometry:
    """Map square centers to deterministic logical coordinates."""

    origin_x: float = 0.0
    origin_y: float = 0.0
    square_pitch: float = 1.0
    invert_x: bool = False
    invert_y: bool = False

    def __post_init__(self) -> None:
        if self.square_pitch <= 0:
            raise ValueError("Square pitch must be positive")

    def square_to_position(self, square: str) -> PhysicalPosition:
        """Return the logical center coordinate for a valid algebraic square."""
        normalized = square.lower()
        if normalized not in chess.SQUARE_NAMES:
            raise ValueError(f"Invalid chess square: {square}")
        index = chess.parse_square(normalized)
        file_index = chess.square_file(index)
        rank_index = chess.square_rank(index)
        x_index = 7 - file_index if self.invert_x else file_index
        y_index = 7 - rank_index if self.invert_y else rank_index
        return PhysicalPosition(
            x=self.origin_x + x_index * self.square_pitch,
            y=self.origin_y + y_index * self.square_pitch,
        )
