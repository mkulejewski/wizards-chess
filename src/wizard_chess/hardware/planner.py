"""Pure translation from canonical move facts to abstract machine operations."""

from dataclasses import dataclass, field

from wizard_chess.domain.events import MoveExecuted
from wizard_chess.hardware.errors import UnsupportedPhysicalMove
from wizard_chess.hardware.geometry import BoardGeometry
from wizard_chess.hardware.models import (
    HardwareOperation,
    MoveTo,
    PhysicalMoveRequest,
    SetMagnet,
    UnsupportedMoveReason,
)


@dataclass(frozen=True, slots=True)
class PhysicalMovePlanner:
    """Plan only ordinary non-capturing moves in Stage 3.1."""

    geometry: BoardGeometry = field(default_factory=BoardGeometry)

    def plan(self, move: MoveExecuted | PhysicalMoveRequest) -> tuple[HardwareOperation, ...]:
        request = PhysicalMoveRequest.from_event(move) if isinstance(move, MoveExecuted) else move
        if request.is_castling:
            raise UnsupportedPhysicalMove(UnsupportedMoveReason.CASTLING_NOT_IMPLEMENTED)
        if request.is_en_passant:
            raise UnsupportedPhysicalMove(UnsupportedMoveReason.EN_PASSANT_NOT_IMPLEMENTED)
        if request.promotion is not None:
            raise UnsupportedPhysicalMove(UnsupportedMoveReason.PROMOTION_NOT_IMPLEMENTED)
        if request.captured_square is not None:
            raise UnsupportedPhysicalMove(UnsupportedMoveReason.CAPTURE_NOT_IMPLEMENTED)
        source = self.geometry.square_to_position(request.source_square)
        target = self.geometry.square_to_position(request.target_square)
        return (
            MoveTo(source.x, source.y),
            SetMagnet(True),
            MoveTo(target.x, target.y),
            SetMagnet(False),
        )
