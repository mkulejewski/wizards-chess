"""Application-level orchestration of already-authorized physical moves."""

from __future__ import annotations

import logging
from threading import Lock

from wizard_chess.domain.events import MoveExecuted
from wizard_chess.hardware.board_state import PhysicalBoardState, PieceSymbols
from wizard_chess.hardware.errors import (
    HardwareError,
    HardwareExecutionFailed,
    UnsupportedPhysicalMove,
)
from wizard_chess.hardware.models import (
    HardwareControllerState,
    HardwareOperation,
    HardwareResult,
    PhysicalExecutionResult,
    PhysicalExecutionStatus,
    PhysicalSynchronization,
)
from wizard_chess.hardware.planner import PhysicalMovePlanner
from wizard_chess.hardware.port import HardwarePort

LOGGER = logging.getLogger(__name__)


class HardwareCoordinator:
    """Relate canonical move events to physical planning and controller execution."""

    def __init__(
        self,
        port: HardwarePort,
        board_state: PhysicalBoardState,
        planner: PhysicalMovePlanner | None = None,
    ) -> None:
        self._port = port
        self._board_state = board_state
        self._planner = planner or PhysicalMovePlanner()
        self._executing = False
        self._active_event: MoveExecuted | None = None
        self._execution_lock = Lock()
        self._results: list[PhysicalExecutionResult] = []
        LOGGER.info("Physical board initialized from assumed placement")
        LOGGER.debug("Initial physical board state: %r", self._board_state)

    @classmethod
    def from_piece_symbols(
        cls,
        port: HardwarePort,
        pieces: PieceSymbols,
        planner: PhysicalMovePlanner | None = None,
    ) -> HardwareCoordinator:
        return cls(port, PhysicalBoardState.from_piece_symbols(pieces), planner)

    @property
    def board_state(self) -> PhysicalBoardState:
        return self._board_state

    @property
    def controller_state(self) -> HardwareControllerState:
        return self._port.status()

    @property
    def results(self) -> tuple[PhysicalExecutionResult, ...]:
        return tuple(self._results)

    @property
    def last_result(self) -> PhysicalExecutionResult | None:
        return self._results[-1] if self._results else None

    def connect(self) -> None:
        self._port.connect()
        LOGGER.info("Hardware connected")

    def disconnect(self) -> None:
        self._port.disconnect()
        LOGGER.info("Hardware disconnected")

    def home(self) -> HardwareResult:
        result = self._port.home()
        LOGGER.info("Hardware ready")
        return result

    def stop(self) -> None:
        self._port.stop()
        if self._executing:
            self._board_state = self._mark_current_move_unknown("Physical execution stopped")

    def emergency_stop(self) -> None:
        self._port.emergency_stop()
        self._board_state = self._mark_current_move_unknown("Emergency stop")
        LOGGER.error("Hardware emergency stop; physical board marked unknown")

    def initialize_physical_state(self, pieces: PieceSymbols) -> None:
        """Explicitly reset the Stage 3.1 placement assumption after reconciliation."""
        if self._executing:
            from wizard_chess.hardware.errors import HardwareBusy

            raise HardwareBusy("Cannot initialize physical state during execution")
        self._board_state = PhysicalBoardState.from_piece_symbols(pieces)
        LOGGER.info("Physical board assumption explicitly initialized")

    def execute_move(self, event: MoveExecuted) -> PhysicalExecutionResult:
        """Consume one canonical event without changing or undoing its chess move."""
        if not self._execution_lock.acquire(blocking=False):
            self._board_state = self._board_state.with_synchronization(
                PhysicalSynchronization.UNKNOWN
            )
            return self._record(
                PhysicalExecutionResult(
                    event,
                    PhysicalExecutionStatus.REJECTED,
                    message="A physical move is already executing",
                )
            )
        try:
            return self._execute_move(event)
        finally:
            self._executing = False
            self._active_event = None
            self._execution_lock.release()

    def _execute_move(self, event: MoveExecuted) -> PhysicalExecutionResult:
        LOGGER.debug("Physical board state before %s: %r", event.uci, self._board_state)
        try:
            operations = self._planner.plan(event)
        except UnsupportedPhysicalMove as error:
            self._board_state = self._board_state.with_synchronization(
                PhysicalSynchronization.DESYNCHRONIZED
            )
            LOGGER.warning("Physical move unsupported: %s", error)
            return self._record(
                PhysicalExecutionResult(
                    event,
                    PhysicalExecutionStatus.UNSUPPORTED,
                    message=str(error),
                )
            )

        LOGGER.debug("Motion plan for %s: %r", event.uci, operations)

        if self.controller_state is not HardwareControllerState.READY:
            self._board_state = self._board_state.with_synchronization(
                PhysicalSynchronization.DESYNCHRONIZED
            )
            message = f"Hardware is not ready: {self.controller_state.value}"
            LOGGER.warning(message)
            return self._record(
                PhysicalExecutionResult(
                    event,
                    PhysicalExecutionStatus.REJECTED,
                    operations=operations,
                    message=message,
                )
            )

        try:
            self._board_state.validate_simple_move(event.source_square, event.target_square)
        except HardwareError as error:
            LOGGER.warning("Physical move rejected: %s", error)
            return self._record(
                PhysicalExecutionResult(
                    event,
                    PhysicalExecutionStatus.REJECTED,
                    operations=operations,
                    message=str(error),
                )
            )

        self._executing = True
        self._active_event = event
        self._board_state = self._board_state.with_synchronization(
            PhysicalSynchronization.EXECUTING
        )
        LOGGER.info("Physical execution started for %s", event.uci)
        try:
            hardware_result = self._port.execute(operations)
        except HardwareError as error:
            return self._fail_execution(event, operations, str(error))
        except Exception as error:  # Defensive adapter boundary.
            LOGGER.exception("Unexpected hardware adapter failure")
            wrapped = HardwareExecutionFailed(
                f"Unexpected hardware adapter failure: {error}",
                controller_state=self.controller_state,
            )
            return self._fail_execution(event, operations, str(wrapped))

        if not hardware_result.succeeded:
            return self._fail_execution(
                event,
                operations,
                hardware_result.message or hardware_result.status.value,
                hardware_result,
            )

        if self._board_state.synchronization is not PhysicalSynchronization.EXECUTING:
            return self._fail_execution(
                event,
                operations,
                "Physical state changed during controller execution",
                hardware_result,
            )

        try:
            self._board_state = self._board_state.complete_simple_move(
                event.source_square, event.target_square
            )
        except HardwareError as error:
            return self._fail_execution(event, operations, str(error), hardware_result)
        LOGGER.info("Physical execution completed and board synchronized for %s", event.uci)
        LOGGER.debug("Physical board state after %s: %r", event.uci, self._board_state)
        return self._record(
            PhysicalExecutionResult(
                event,
                PhysicalExecutionStatus.COMPLETED,
                operations=operations,
                hardware_result=hardware_result,
            )
        )

    def position_replaced(self) -> None:
        """Conservatively react when digital state changes without physical motion."""
        self._board_state = self._board_state.with_synchronization(
            PhysicalSynchronization.DESYNCHRONIZED
        )
        LOGGER.warning("Digital position replaced; physical board marked desynchronized")

    def reconcile(self, pieces: PieceSymbols) -> PhysicalSynchronization:
        """Compare placement only and update informational synchronization status."""
        if self._board_state.has_unknown_locations:
            self._board_state = self._board_state.with_synchronization(
                PhysicalSynchronization.UNKNOWN
            )
        elif self._board_state.matches_piece_symbols(pieces):
            self._board_state = self._board_state.with_synchronization(
                PhysicalSynchronization.SYNCHRONIZED
            )
        else:
            self._board_state = self._board_state.with_synchronization(
                PhysicalSynchronization.DESYNCHRONIZED
            )
        if self._board_state.synchronization is PhysicalSynchronization.SYNCHRONIZED:
            LOGGER.info("Physical and logical board placement reconciled")
        else:
            LOGGER.warning(
                "Physical/logical board reconciliation result: %s",
                self._board_state.synchronization.value,
            )
        LOGGER.debug("Physical board state after reconciliation: %r", self._board_state)
        return self._board_state.synchronization

    def is_synchronized(self, pieces: PieceSymbols | None = None) -> bool:
        if pieces is None:
            return self._board_state.synchronization is PhysicalSynchronization.SYNCHRONIZED
        return (
            self._board_state.synchronization is PhysicalSynchronization.SYNCHRONIZED
            and self._board_state.matches_piece_symbols(pieces)
        )

    def close(self) -> None:
        """Explicitly shut down the injected controller."""
        try:
            if self.controller_state is not HardwareControllerState.DISCONNECTED:
                self._port.disconnect()
        except HardwareError:
            LOGGER.exception("Hardware shutdown failed")

    def _fail_execution(
        self,
        event: MoveExecuted,
        operations: tuple[HardwareOperation, ...],
        message: str,
        hardware_result: HardwareResult | None = None,
    ) -> PhysicalExecutionResult:
        self._board_state = self._board_state.mark_move_uncertain(event.source_square, message)
        LOGGER.error("Physical execution failed for %s: %s", event.uci, message)
        return self._record(
            PhysicalExecutionResult(
                event,
                PhysicalExecutionStatus.FAILED,
                operations=operations,
                hardware_result=hardware_result,
                message=message,
            )
        )

    def _mark_current_move_unknown(self, reason: str) -> PhysicalBoardState:
        if self._active_event is None:
            return self._board_state.with_synchronization(PhysicalSynchronization.UNKNOWN)
        return self._board_state.mark_move_uncertain(self._active_event.source_square, reason)

    def _record(self, result: PhysicalExecutionResult) -> PhysicalExecutionResult:
        self._results.append(result)
        return result
