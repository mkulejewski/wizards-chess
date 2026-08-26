"""Application-facing physical-board event consumer protocols."""

from typing import Protocol, runtime_checkable

from wizard_chess.domain.events import MoveExecuted


class PhysicalBoard(Protocol):
    """An output adapter capable of reflecting accepted digital moves."""

    def execute_move(self, event: MoveExecuted) -> object | None: ...


@runtime_checkable
class PhysicalBoardPositionObserver(Protocol):
    """Optional notification for digital changes with no physical movement."""

    def position_replaced(self) -> None: ...


@runtime_checkable
class ClosablePhysicalBoard(Protocol):
    """Optional explicit shutdown implemented by active hardware consumers."""

    def close(self) -> None: ...
