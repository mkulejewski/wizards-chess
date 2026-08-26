"""Hardware-neutral physical-board models, orchestration, and test doubles."""

from wizard_chess.hardware.base import (
    ClosablePhysicalBoard,
    PhysicalBoard,
    PhysicalBoardPositionObserver,
)
from wizard_chess.hardware.board_state import (
    OnSquare,
    PhysicalBoardState,
    PhysicalPiece,
    PhysicalPieceColor,
    PhysicalPiecePlacement,
    PhysicalPieceType,
    UnknownLocation,
)
from wizard_chess.hardware.coordinator import HardwareCoordinator
from wizard_chess.hardware.errors import (
    HardwareBusy,
    HardwareEmergencyStop,
    HardwareError,
    HardwareExecutionFailed,
    HardwareFault,
    HardwareNotReady,
    HardwareTimeout,
    HardwareUnavailable,
    PhysicalBoardDesynchronized,
    PhysicalBoardUnknown,
    UnsupportedPhysicalMove,
)
from wizard_chess.hardware.fake import FakeHardware
from wizard_chess.hardware.geometry import BoardGeometry
from wizard_chess.hardware.models import (
    HardwareControllerState,
    HardwareResult,
    HardwareResultStatus,
    Home,
    MoveTo,
    PhysicalExecutionResult,
    PhysicalExecutionStatus,
    PhysicalMoveRequest,
    PhysicalPosition,
    PhysicalSynchronization,
    SetMagnet,
    Stop,
    UnsupportedMoveReason,
)
from wizard_chess.hardware.planner import PhysicalMovePlanner
from wizard_chess.hardware.port import HardwarePort
from wizard_chess.hardware.simulated_board import SimulatedPhysicalBoard

__all__ = [
    "BoardGeometry",
    "ClosablePhysicalBoard",
    "FakeHardware",
    "HardwareBusy",
    "HardwareControllerState",
    "HardwareCoordinator",
    "HardwareEmergencyStop",
    "HardwareError",
    "HardwareExecutionFailed",
    "HardwareFault",
    "HardwareNotReady",
    "HardwarePort",
    "HardwareResult",
    "HardwareResultStatus",
    "HardwareTimeout",
    "HardwareUnavailable",
    "Home",
    "MoveTo",
    "OnSquare",
    "PhysicalBoard",
    "PhysicalBoardDesynchronized",
    "PhysicalBoardPositionObserver",
    "PhysicalBoardState",
    "PhysicalBoardUnknown",
    "PhysicalExecutionResult",
    "PhysicalExecutionStatus",
    "PhysicalMovePlanner",
    "PhysicalMoveRequest",
    "PhysicalPiece",
    "PhysicalPieceColor",
    "PhysicalPiecePlacement",
    "PhysicalPieceType",
    "PhysicalPosition",
    "PhysicalSynchronization",
    "SetMagnet",
    "SimulatedPhysicalBoard",
    "Stop",
    "UnknownLocation",
    "UnsupportedMoveReason",
    "UnsupportedPhysicalMove",
]
