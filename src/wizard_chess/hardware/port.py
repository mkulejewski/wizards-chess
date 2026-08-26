"""Replaceable machine-controller port with no chess semantics."""

from collections.abc import Sequence
from typing import Protocol

from wizard_chess.hardware.models import (
    HardwareControllerState,
    HardwareOperation,
    HardwareResult,
)


class HardwarePort(Protocol):
    """Lifecycle and execution boundary implemented by fake and future adapters."""

    @property
    def state(self) -> HardwareControllerState: ...

    def status(self) -> HardwareControllerState: ...

    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def home(self) -> HardwareResult: ...

    def execute(self, operations: Sequence[HardwareOperation]) -> HardwareResult: ...

    def stop(self) -> None: ...

    def emergency_stop(self) -> None: ...
