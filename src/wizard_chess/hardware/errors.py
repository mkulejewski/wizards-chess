"""Controlled failures raised by the hardware abstraction."""

from __future__ import annotations

from wizard_chess.hardware.models import (
    HardwareControllerState,
    HardwareOperation,
    UnsupportedMoveReason,
)


class HardwareError(Exception):
    """Base class for expected hardware-subsystem failures."""


class HardwareUnavailable(HardwareError):
    """Raised when no controller connection is available."""


class HardwareNotReady(HardwareError):
    """Raised when motion is requested before the controller is ready."""


class HardwareBusy(HardwareError):
    """Raised when another hardware execution is already active."""


class HardwareFault(HardwareError):
    """Raised when a faulted controller rejects an operation."""


class HardwareEmergencyStop(HardwareError):
    """Raised when an emergency-stopped controller rejects an operation."""


class HardwareTimeout(HardwareError):
    """Raised when the controller does not finish an operation in time."""


class PhysicalBoardUnknown(HardwareError):
    """Raised when believed physical placement is not reliable enough to use."""


class PhysicalBoardDesynchronized(HardwareError):
    """Raised when physical and authoritative placements are known to differ."""


class UnsupportedPhysicalMove(HardwareError):
    """Raised when a chess move needs physical logic deferred beyond Stage 3.1."""

    def __init__(self, reason: UnsupportedMoveReason) -> None:
        super().__init__(reason)
        self.reason = reason


class HardwareExecutionFailed(HardwareError):
    """Describe a controlled operation-sequence failure with diagnostic context."""

    def __init__(
        self,
        message: str,
        *,
        operation_index: int | None = None,
        operation: HardwareOperation | None = None,
        controller_state: HardwareControllerState | None = None,
    ) -> None:
        super().__init__(message)
        self.operation_index = operation_index
        self.operation = operation
        self.controller_state = controller_state
