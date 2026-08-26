"""Deterministic in-memory hardware controller for tests and debug tooling."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from wizard_chess.hardware.errors import (
    HardwareBusy,
    HardwareEmergencyStop,
    HardwareFault,
    HardwareNotReady,
    HardwareUnavailable,
)
from wizard_chess.hardware.models import (
    HardwareControllerState,
    HardwareOperation,
    HardwareResult,
    HardwareResultStatus,
)

OperationObserver = Callable[[int, HardwareOperation], None]


class FakeHardware:
    """Model controller lifecycle, traces, failures, timeouts, and E-stop."""

    def __init__(self, *, on_operation: OperationObserver | None = None) -> None:
        self._state = HardwareControllerState.DISCONNECTED
        self._trace: list[str] = []
        self._operations: list[HardwareOperation] = []
        self._failure_index: int | None = None
        self._failure_is_timeout = False
        self._on_operation = on_operation

    @property
    def state(self) -> HardwareControllerState:
        return self._state

    @property
    def trace(self) -> tuple[str, ...]:
        return tuple(self._trace)

    @property
    def operations(self) -> tuple[HardwareOperation, ...]:
        return tuple(self._operations)

    def status(self) -> HardwareControllerState:
        return self._state

    def connect(self) -> None:
        if self._state is not HardwareControllerState.DISCONNECTED:
            self._raise_for_invalid_state("connect")
        self._trace.append("CONNECT")
        self._state = HardwareControllerState.UNCALIBRATED

    def disconnect(self) -> None:
        if self._state is HardwareControllerState.EXECUTING:
            raise HardwareBusy("Cannot disconnect while hardware is executing")
        self._trace.append("DISCONNECT")
        self._state = HardwareControllerState.DISCONNECTED

    def home(self) -> HardwareResult:
        if self._state not in {
            HardwareControllerState.CONNECTED,
            HardwareControllerState.UNCALIBRATED,
        }:
            self._raise_for_invalid_state("home")
        self._trace.append("HOME")
        self._state = HardwareControllerState.READY
        return HardwareResult(HardwareResultStatus.COMPLETED)

    def execute(self, operations: Sequence[HardwareOperation]) -> HardwareResult:
        if self._state is not HardwareControllerState.READY:
            self._raise_for_invalid_state("execute")
        self._state = HardwareControllerState.EXECUTING
        self._trace.append("EXECUTE_START")
        for index, operation in enumerate(operations):
            self._operations.append(operation)
            self._trace.append(_format_operation(operation))
            if self._on_operation is not None:
                self._on_operation(index, operation)
            if self.status() is HardwareControllerState.ESTOP:
                return HardwareResult(
                    HardwareResultStatus.FAULT,
                    operation_index=index,
                    operation=operation,
                    message="Emergency stop activated during execution",
                )
            if self.status() is not HardwareControllerState.EXECUTING:
                return HardwareResult(
                    HardwareResultStatus.REJECTED,
                    operation_index=index,
                    operation=operation,
                    message="Execution was stopped",
                )
            if index == self._failure_index:
                status = (
                    HardwareResultStatus.TIMEOUT
                    if self._failure_is_timeout
                    else HardwareResultStatus.FAULT
                )
                self._state = HardwareControllerState.FAULT
                self._trace.append(status.value.upper())
                return HardwareResult(
                    status,
                    operation_index=index,
                    operation=operation,
                    message=f"Injected {status.value} at operation {index}",
                )
        self._state = HardwareControllerState.READY
        self._trace.append("EXECUTE_COMPLETE")
        return HardwareResult(HardwareResultStatus.COMPLETED)

    def stop(self) -> None:
        if self._state is HardwareControllerState.DISCONNECTED:
            raise HardwareUnavailable("Cannot stop disconnected hardware")
        if self._state is HardwareControllerState.ESTOP:
            raise HardwareEmergencyStop("Hardware is emergency-stopped")
        if self._state is HardwareControllerState.FAULT:
            raise HardwareFault("Hardware is faulted")
        self._trace.append("STOP")
        if self._state is HardwareControllerState.EXECUTING:
            self._state = HardwareControllerState.READY

    def emergency_stop(self) -> None:
        self._trace.append("EMERGENCY_STOP")
        self._state = HardwareControllerState.ESTOP

    def fail_on_operation(self, index: int, *, timeout: bool = False) -> None:
        """Inject a zero-based failure at one attempted operation."""
        if index < 0:
            raise ValueError("Operation index must be non-negative")
        self._failure_index = index
        self._failure_is_timeout = timeout

    def timeout_on_operation(self, index: int) -> None:
        self.fail_on_operation(index, timeout=True)

    def clear_failure(self) -> None:
        self._failure_index = None
        self._failure_is_timeout = False

    def close(self) -> None:
        if self._state is HardwareControllerState.EXECUTING:
            self.emergency_stop()
        if self._state is not HardwareControllerState.DISCONNECTED:
            self.disconnect()

    def _raise_for_invalid_state(self, action: str) -> None:
        if self._state is HardwareControllerState.DISCONNECTED:
            raise HardwareUnavailable(f"Cannot {action} disconnected hardware")
        if self._state is HardwareControllerState.EXECUTING:
            raise HardwareBusy(f"Cannot {action} while hardware is executing")
        if self._state is HardwareControllerState.FAULT:
            raise HardwareFault(f"Cannot {action} while hardware is faulted")
        if self._state is HardwareControllerState.ESTOP:
            raise HardwareEmergencyStop(f"Cannot {action} after emergency stop")
        raise HardwareNotReady(f"Cannot {action} while hardware is {self._state.value}")


def _format_operation(operation: HardwareOperation) -> str:
    from wizard_chess.hardware.models import Home, MoveTo, SetMagnet

    if isinstance(operation, MoveTo):
        return f"MOVE_TO {operation.x:g} {operation.y:g}"
    if isinstance(operation, SetMagnet):
        return "MAGNET_ON" if operation.enabled else "MAGNET_OFF"
    if isinstance(operation, Home):
        return "HOME"
    return "STOP"
