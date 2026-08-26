from __future__ import annotations

import chess

from wizard_chess.application.session import GameSession
from wizard_chess.domain.events import MoveExecuted
from wizard_chess.domain.game import ChessGame
from wizard_chess.domain.move import ChessMove
from wizard_chess.hardware.board_state import PhysicalBoardState, UnknownLocation
from wizard_chess.hardware.coordinator import HardwareCoordinator
from wizard_chess.hardware.fake import FakeHardware
from wizard_chess.hardware.models import (
    HardwareControllerState,
    PhysicalExecutionStatus,
    PhysicalSynchronization,
)


def _ready_coordinator(
    *, fake: FakeHardware | None = None, board: chess.Board | None = None
) -> tuple[HardwareCoordinator, FakeHardware]:
    controller = fake or FakeHardware()
    coordinator = HardwareCoordinator(
        controller,
        PhysicalBoardState.from_chess_board(board if board is not None else chess.Board()),
    )
    coordinator.connect()
    coordinator.home()
    return coordinator, controller


def test_successful_event_executes_once_and_updates_only_after_completion() -> None:
    observed: list[tuple[PhysicalSynchronization, HardwareControllerState, bool]] = []
    holder: list[HardwareCoordinator] = []

    def observe(_index: int, _operation: object) -> None:
        coordinator = holder[0]
        observed.append(
            (
                coordinator.board_state.synchronization,
                coordinator.controller_state,
                coordinator.board_state.piece_at("e2") is not None,
            )
        )

    fake = FakeHardware(on_operation=observe)
    coordinator, _fake = _ready_coordinator(fake=fake)
    holder.append(coordinator)
    game = ChessGame()
    event = game.make_move(ChessMove("e2", "e4"))

    result = coordinator.execute_move(event)

    assert result.status is PhysicalExecutionStatus.COMPLETED
    assert len(fake.operations) == 4
    assert (
        observed
        == [(PhysicalSynchronization.EXECUTING, HardwareControllerState.EXECUTING, True)] * 4
    )
    assert coordinator.board_state.piece_at("e2") is None
    assert coordinator.board_state.piece_at("e4") is not None
    assert coordinator.board_state.synchronization is PhysicalSynchronization.SYNCHRONIZED
    assert game.board.piece_at(chess.E4) == chess.Piece(chess.PAWN, chess.WHITE)
    assert coordinator.is_synchronized(
        (chess.square_name(square), piece.symbol())
        for square, piece in game.board.piece_map().items()
    )


def test_partial_failure_keeps_digital_move_and_marks_physical_piece_unknown() -> None:
    coordinator, fake = _ready_coordinator()
    fake.fail_on_operation(2)
    game = ChessGame()
    event = game.make_move(ChessMove("e2", "e4"))

    result = coordinator.execute_move(event)

    assert result.status is PhysicalExecutionStatus.FAILED
    assert fake.state is HardwareControllerState.FAULT
    assert len(fake.operations) == 3
    assert coordinator.board_state.synchronization is PhysicalSynchronization.UNKNOWN
    assert coordinator.board_state.piece_at("e2") is None
    assert coordinator.board_state.piece_at("e4") is None
    assert any(
        isinstance(placement.location, UnknownLocation)
        for placement in coordinator.board_state.placements
    )
    assert game.board.piece_at(chess.E4) == chess.Piece(chess.PAWN, chess.WHITE)
    assert len(game.board.move_stack) == 1


def test_unsupported_capture_desynchronizes_without_hardware_execution() -> None:
    coordinator, fake = _ready_coordinator()
    game = ChessGame()
    coordinator.execute_move(game.make_move(ChessMove("e2", "e4")))
    coordinator.execute_move(game.make_move(ChessMove("d7", "d5")))
    operation_count = len(fake.operations)

    result = coordinator.execute_move(game.make_move(ChessMove("e4", "d5")))

    assert result.status is PhysicalExecutionStatus.UNSUPPORTED
    assert len(fake.operations) == operation_count
    assert coordinator.board_state.synchronization is PhysicalSynchronization.DESYNCHRONIZED
    assert game.board.piece_at(chess.D5) == chess.Piece(chess.PAWN, chess.WHITE)


def test_disconnected_and_unready_execution_are_rejected_without_motion() -> None:
    game = ChessGame()
    disconnected_fake = FakeHardware()
    disconnected = HardwareCoordinator(
        disconnected_fake, PhysicalBoardState.from_chess_board(game.board)
    )
    event = game.make_move(ChessMove("e2", "e4"))

    disconnected_result = disconnected.execute_move(event)

    assert disconnected_result.status is PhysicalExecutionStatus.REJECTED
    assert disconnected_fake.operations == ()
    assert disconnected.board_state.synchronization is PhysicalSynchronization.DESYNCHRONIZED

    unready_game = ChessGame()
    unready_fake = FakeHardware()
    unready_fake.connect()
    unready = HardwareCoordinator(
        unready_fake, PhysicalBoardState.from_chess_board(unready_game.board)
    )
    unready_result = unready.execute_move(unready_game.make_move(ChessMove("e2", "e4")))
    assert unready_result.status is PhysicalExecutionStatus.REJECTED
    assert unready_fake.operations == ()


def test_emergency_stop_marks_board_unknown_and_requires_lifecycle_recovery() -> None:
    coordinator, fake = _ready_coordinator()

    coordinator.emergency_stop()

    assert coordinator.controller_state is HardwareControllerState.ESTOP
    assert coordinator.board_state.synchronization is PhysicalSynchronization.UNKNOWN
    coordinator.disconnect()
    coordinator.connect()
    coordinator.home()
    assert fake.state is HardwareControllerState.READY
    assert coordinator.board_state.synchronization is PhysicalSynchronization.UNKNOWN


def test_overlapping_execution_is_rejected_and_cannot_claim_synchronization() -> None:
    game = ChessGame()
    first = game.make_move(ChessMove("e2", "e4"))
    second = game.make_move(ChessMove("e7", "e5"))
    nested_results: list[PhysicalExecutionStatus] = []
    holder: list[HardwareCoordinator] = []

    def overlap(index: int, _operation: object) -> None:
        if index == 0:
            nested_results.append(holder[0].execute_move(second).status)

    coordinator, _fake = _ready_coordinator(fake=FakeHardware(on_operation=overlap))
    holder.append(coordinator)

    outer = coordinator.execute_move(first)

    assert nested_results == [PhysicalExecutionStatus.REJECTED]
    assert outer.status is PhysicalExecutionStatus.FAILED
    assert coordinator.board_state.synchronization is PhysicalSynchronization.UNKNOWN


def test_reconciliation_compares_placement_without_mutating_chess_game() -> None:
    game = ChessGame()
    coordinator, _fake = _ready_coordinator()
    original_fen = game.fen()
    pieces = tuple(
        (chess.square_name(square), piece.symbol())
        for square, piece in game.board.piece_map().items()
    )

    assert coordinator.reconcile(pieces) is PhysicalSynchronization.SYNCHRONIZED
    mismatched = tuple(item for item in pieces if item[0] != "e2")
    assert coordinator.reconcile(mismatched) is PhysicalSynchronization.DESYNCHRONIZED
    assert game.fen() == original_fen


def test_game_session_routes_one_canonical_event_to_coordinator() -> None:
    coordinator, fake = _ready_coordinator()
    session = GameSession(coordinator)

    result = session.play_text("e4")

    assert result.move_event is not None
    assert [item.event for item in coordinator.results] == [result.move_event]
    assert len(fake.operations) == 4
    assert session.snapshot().piece_at("e4") == "P"
    assert coordinator.board_state.piece_at("e4") is not None


def test_digital_replacement_does_not_silently_reseed_physical_assumption() -> None:
    coordinator, _fake = _ready_coordinator()
    session = GameSession(coordinator)
    original_piece = coordinator.board_state.piece_at("e2")

    session.load_fen("4k3/8/8/8/8/8/4R3/4K3 b - - 0 1")

    assert coordinator.board_state.piece_at("e2") == original_piece
    assert coordinator.board_state.synchronization is PhysicalSynchronization.DESYNCHRONIZED
    coordinator.initialize_physical_state(session.snapshot().pieces)
    rook = coordinator.board_state.piece_at("e2")
    assert rook is not None
    assert rook.piece_type.value == "rook"
    assert coordinator.board_state.synchronization is PhysicalSynchronization.SYNCHRONIZED


def test_new_game_pgn_load_and_undo_each_mark_physical_state_desynchronized() -> None:
    new_coordinator, _new_fake = _ready_coordinator()
    new_session = GameSession(new_coordinator)
    new_session.new_game()
    assert new_coordinator.board_state.synchronization is PhysicalSynchronization.DESYNCHRONIZED

    pgn_coordinator, _pgn_fake = _ready_coordinator()
    pgn_session = GameSession(pgn_coordinator)
    pgn_session.load_pgn('[Result "*"]\n\n1. d4 *')
    assert pgn_coordinator.board_state.synchronization is PhysicalSynchronization.DESYNCHRONIZED

    undo_coordinator, _undo_fake = _ready_coordinator()
    undo_session = GameSession(undo_coordinator)
    undo_session.play_text("e4")
    assert undo_coordinator.board_state.synchronization is PhysicalSynchronization.SYNCHRONIZED
    undo_session.undo()
    assert undo_coordinator.board_state.synchronization is PhysicalSynchronization.DESYNCHRONIZED


def test_estop_during_execution_stops_remaining_operations_and_keeps_chess_move() -> None:
    holder: list[HardwareCoordinator] = []

    def trigger_estop(index: int, _operation: object) -> None:
        if index == 1:
            holder[0].emergency_stop()

    coordinator, fake = _ready_coordinator(fake=FakeHardware(on_operation=trigger_estop))
    holder.append(coordinator)
    game = ChessGame()
    event = game.make_move(ChessMove("e2", "e4"))

    result = coordinator.execute_move(event)

    assert result.status is PhysicalExecutionStatus.FAILED
    assert fake.state is HardwareControllerState.ESTOP
    assert len(fake.operations) == 2
    assert coordinator.board_state.synchronization is PhysicalSynchronization.UNKNOWN
    assert game.board.piece_at(chess.E4) == chess.Piece(chess.PAWN, chess.WHITE)


def test_ordinary_stop_during_execution_marks_only_active_move_unknown() -> None:
    holder: list[HardwareCoordinator] = []

    def trigger_stop(index: int, _operation: object) -> None:
        if index == 1:
            holder[0].stop()

    coordinator, fake = _ready_coordinator(fake=FakeHardware(on_operation=trigger_stop))
    holder.append(coordinator)
    game = ChessGame()
    event = game.make_move(ChessMove("e2", "e4"))

    result = coordinator.execute_move(event)

    assert result.status is PhysicalExecutionStatus.FAILED
    assert fake.state is HardwareControllerState.READY
    assert len(fake.operations) == 2
    assert coordinator.board_state.piece_at("e2") is None
    assert coordinator.board_state.piece_at("d2") is not None
    assert coordinator.board_state.synchronization is PhysicalSynchronization.UNKNOWN


def test_session_close_explicitly_disconnects_coordinator() -> None:
    coordinator, _fake = _ready_coordinator()
    session = GameSession(coordinator)

    session.close()

    assert coordinator.controller_state is HardwareControllerState.DISCONNECTED


def test_hardware_adapter_exception_does_not_roll_back_or_escape_session() -> None:
    class BrokenPhysicalBoard:
        def execute_move(self, event: MoveExecuted) -> None:
            del event
            raise RuntimeError("adapter broke")

    session = GameSession(BrokenPhysicalBoard())

    event = session.play_move(ChessMove("e2", "e4"))

    assert event.uci == "e2e4"
    assert session.snapshot().piece_at("e4") == "P"
