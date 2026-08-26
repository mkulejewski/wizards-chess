"""Hardware-neutral values shared by planners, controllers, and orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from wizard_chess.domain.events import MoveExecuted


class HardwareControllerState(StrEnum):
    """Lifecycle of the machine controller, independent of board occupancy."""

    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    UNCALIBRATED = "uncalibrated"
    READY = "ready"
    EXECUTING = "executing"
    FAULT = "fault"
    ESTOP = "estop"


class PhysicalSynchronization(StrEnum):
    """Relationship between believed physical and authoritative digital placement."""

    SYNCHRONIZED = "synchronized"
    EXECUTING = "executing"
    DESYNCHRONIZED = "desynchronized"
    UNKNOWN = "unknown"


class HardwareResultStatus(StrEnum):
    """Transport-independent controller response semantics."""

    ACK = "ack"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAULT = "fault"
    TIMEOUT = "timeout"


class PhysicalExecutionStatus(StrEnum):
    """Outcome of reproducing one already-authorized chess move."""

    COMPLETED = "completed"
    UNSUPPORTED = "unsupported"
    REJECTED = "rejected"
    FAILED = "failed"


class UnsupportedMoveReason(StrEnum):
    """Special physical sequences intentionally deferred from Stage 3.1."""

    CAPTURE_NOT_IMPLEMENTED = "capture_not_implemented"
    CASTLING_NOT_IMPLEMENTED = "castling_not_implemented"
    EN_PASSANT_NOT_IMPLEMENTED = "en_passant_not_implemented"
    PROMOTION_NOT_IMPLEMENTED = "promotion_not_implemented"


@dataclass(frozen=True, slots=True)
class PhysicalPosition:
    """A transport-neutral point in idealized board coordinates."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class MoveTo:
    """Move the carriage to one logical physical position."""

    x: float
    y: float

    @property
    def position(self) -> PhysicalPosition:
        return PhysicalPosition(self.x, self.y)


@dataclass(frozen=True, slots=True)
class SetMagnet:
    """Set the electromagnet state without prescribing electrical details."""

    enabled: bool


@dataclass(frozen=True, slots=True)
class Home:
    """Request controller homing without prescribing a hardware mechanism."""


@dataclass(frozen=True, slots=True)
class Stop:
    """Request an ordinary controlled stop."""


HardwareOperation = MoveTo | SetMagnet | Home | Stop


@dataclass(frozen=True, slots=True)
class PhysicalMoveRequest:
    """Immutable physical facts copied from a canonical executed move."""

    source_square: str
    target_square: str
    captured_square: str | None = None
    promotion: str | None = None
    is_castling: bool = False
    is_en_passant: bool = False

    @classmethod
    def from_event(cls, event: MoveExecuted) -> PhysicalMoveRequest:
        return cls(
            source_square=event.source_square,
            target_square=event.target_square,
            captured_square=event.captured_square,
            promotion=event.promotion,
            is_castling=event.is_castling,
            is_en_passant=event.is_en_passant,
        )


@dataclass(frozen=True, slots=True)
class HardwareResult:
    """Result returned by a controller for one operation sequence."""

    status: HardwareResultStatus
    operation_index: int | None = None
    operation: HardwareOperation | None = None
    message: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status is HardwareResultStatus.COMPLETED


@dataclass(frozen=True, slots=True)
class PhysicalExecutionResult:
    """Coordinator outcome retained without affecting the chess transaction."""

    event: MoveExecuted
    status: PhysicalExecutionStatus
    operations: tuple[HardwareOperation, ...] = ()
    hardware_result: HardwareResult | None = None
    message: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status is PhysicalExecutionStatus.COMPLETED
