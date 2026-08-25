"""Hardware-independent events emitted by domain actions."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MoveExecuted:
    """All board-level facts needed by future output adapters."""

    source_square: str
    target_square: str
    captured_square: str | None
    promotion: str | None
    is_castling: bool
    is_en_passant: bool
    san: str
    uci: str


@dataclass(frozen=True, slots=True)
class MoveAnnotation:
    """Portable timing and engine facts associated with one completed move."""

    elapsed_seconds: float | None = None
    remaining_seconds: float | None = None
    evaluation_cp: int | None = None
    mate_in: int | None = None
    depth: int | None = None
    nodes: int | None = None
    tablebase_hits: int | None = None
