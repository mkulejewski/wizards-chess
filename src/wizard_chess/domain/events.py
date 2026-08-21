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
