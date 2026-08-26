import pytest

from wizard_chess.hardware.errors import (
    HardwareBusy,
    HardwareEmergencyStop,
    HardwareFault,
    HardwareNotReady,
    HardwareUnavailable,
)
from wizard_chess.hardware.fake import FakeHardware
from wizard_chess.hardware.models import (
    HardwareControllerState,
    HardwareResultStatus,
    MoveTo,
    SetMagnet,
)

OPERATIONS = (MoveTo(4.0, 1.0), SetMagnet(True), MoveTo(4.0, 3.0), SetMagnet(False))


def _ready_fake() -> FakeHardware:
    fake = FakeHardware()
    fake.connect()
    assert fake.state is HardwareControllerState.UNCALIBRATED
    assert fake.home().succeeded
    return fake


def test_connect_home_execute_and_disconnect_have_explicit_states_and_trace() -> None:
    fake = _ready_fake()

    result = fake.execute(OPERATIONS)

    assert result.status is HardwareResultStatus.COMPLETED
    assert fake.state is HardwareControllerState.READY
    assert fake.operations == OPERATIONS
    assert fake.trace == (
        "CONNECT",
        "HOME",
        "EXECUTE_START",
        "MOVE_TO 4 1",
        "MAGNET_ON",
        "MOVE_TO 4 3",
        "MAGNET_OFF",
        "EXECUTE_COMPLETE",
    )
    fake.disconnect()
    assert fake.state is HardwareControllerState.DISCONNECTED


def test_injected_failure_is_fail_fast_and_faults_controller() -> None:
    fake = _ready_fake()
    fake.fail_on_operation(2)

    result = fake.execute(OPERATIONS)

    assert result.status is HardwareResultStatus.FAULT
    assert result.operation_index == 2
    assert result.operation == OPERATIONS[2]
    assert fake.operations == OPERATIONS[:3]
    assert fake.state is HardwareControllerState.FAULT
    with pytest.raises(HardwareFault):
        fake.execute(OPERATIONS)


def test_timeout_injection_is_deterministic_and_faults_controller() -> None:
    fake = _ready_fake()
    fake.timeout_on_operation(0)

    result = fake.execute(OPERATIONS)

    assert result.status is HardwareResultStatus.TIMEOUT
    assert result.operation_index == 0
    assert fake.operations == OPERATIONS[:1]
    assert fake.state is HardwareControllerState.FAULT


def test_invalid_lifecycle_operations_raise_controlled_errors() -> None:
    fake = FakeHardware()
    with pytest.raises(HardwareUnavailable):
        fake.execute(OPERATIONS)
    fake.connect()
    with pytest.raises(HardwareNotReady):
        fake.execute(OPERATIONS)


def test_emergency_stop_rejects_motion_until_disconnect_reconnect_and_home() -> None:
    fake = _ready_fake()

    fake.emergency_stop()

    assert fake.state is HardwareControllerState.ESTOP
    with pytest.raises(HardwareEmergencyStop):
        fake.execute(OPERATIONS)
    fake.disconnect()
    fake.connect()
    fake.home()
    assert fake.execute(OPERATIONS).succeeded


def test_execution_state_is_observable_without_timing_or_sleep() -> None:
    observed: list[HardwareControllerState] = []
    fake = FakeHardware(on_operation=lambda _index, _operation: observed.append(fake.status()))
    fake.connect()
    fake.home()

    fake.execute(OPERATIONS)

    assert observed == [HardwareControllerState.EXECUTING] * len(OPERATIONS)


def test_overlapping_controller_execution_is_rejected_as_busy() -> None:
    nested_errors: list[HardwareBusy] = []
    holder: list[FakeHardware] = []

    def overlap(index: int, _operation: object) -> None:
        if index != 0:
            return
        try:
            holder[0].execute(OPERATIONS)
        except HardwareBusy as error:
            nested_errors.append(error)

    fake = FakeHardware(on_operation=overlap)
    holder.append(fake)
    fake.connect()
    fake.home()

    assert fake.execute(OPERATIONS).succeeded
    assert len(nested_errors) == 1
