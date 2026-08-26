import pytest

from wizard_chess.domain.events import MoveExecuted
from wizard_chess.hardware.errors import UnsupportedPhysicalMove
from wizard_chess.hardware.geometry import BoardGeometry
from wizard_chess.hardware.models import (
    MoveTo,
    PhysicalPosition,
    SetMagnet,
    UnsupportedMoveReason,
)
from wizard_chess.hardware.planner import PhysicalMovePlanner


def _event(
    *,
    source_square: str = "e2",
    target_square: str = "e4",
    captured_square: str | None = None,
    promotion: str | None = None,
    is_castling: bool = False,
    is_en_passant: bool = False,
    san: str = "e4",
    uci: str = "e2e4",
) -> MoveExecuted:
    return MoveExecuted(
        source_square=source_square,
        target_square=target_square,
        captured_square=captured_square,
        promotion=promotion,
        is_castling=is_castling,
        is_en_passant=is_en_passant,
        san=san,
        uci=uci,
    )


@pytest.mark.parametrize(
    ("square", "expected"),
    [
        ("a1", PhysicalPosition(0.0, 0.0)),
        ("b1", PhysicalPosition(1.0, 0.0)),
        ("h8", PhysicalPosition(7.0, 7.0)),
    ],
)
def test_idealized_geometry_maps_square_centers(square: str, expected: PhysicalPosition) -> None:
    assert BoardGeometry().square_to_position(square) == expected


def test_geometry_supports_origin_pitch_and_orientation() -> None:
    geometry = BoardGeometry(
        origin_x=10.0,
        origin_y=20.0,
        square_pitch=2.5,
        invert_x=True,
        invert_y=True,
    )

    assert geometry.square_to_position("a1") == PhysicalPosition(27.5, 37.5)
    assert geometry.square_to_position("h8") == PhysicalPosition(10.0, 20.0)


def test_geometry_rejects_invalid_square_and_pitch() -> None:
    with pytest.raises(ValueError, match="Invalid chess square"):
        BoardGeometry().square_to_position("j4")
    with pytest.raises(ValueError, match="pitch"):
        BoardGeometry(square_pitch=0)


def test_simple_move_plan_is_deterministic_and_ordered() -> None:
    planner = PhysicalMovePlanner()
    event = _event()
    expected = (
        MoveTo(4.0, 1.0),
        SetMagnet(True),
        MoveTo(4.0, 3.0),
        SetMagnet(False),
    )

    assert planner.plan(event) == expected
    assert planner.plan(event) == expected


@pytest.mark.parametrize(
    ("event", "reason"),
    [
        (
            _event(captured_square="d5", san="exd5", uci="e4d5"),
            UnsupportedMoveReason.CAPTURE_NOT_IMPLEMENTED,
        ),
        (
            _event(is_castling=True, target_square="g1", san="O-O", uci="e1g1"),
            UnsupportedMoveReason.CASTLING_NOT_IMPLEMENTED,
        ),
        (
            _event(is_en_passant=True, captured_square="d5", target_square="d6"),
            UnsupportedMoveReason.EN_PASSANT_NOT_IMPLEMENTED,
        ),
        (
            _event(promotion="q", source_square="e7", target_square="e8"),
            UnsupportedMoveReason.PROMOTION_NOT_IMPLEMENTED,
        ),
    ],
)
def test_planner_explicitly_rejects_deferred_move_types(
    event: MoveExecuted, reason: UnsupportedMoveReason
) -> None:
    with pytest.raises(UnsupportedPhysicalMove) as raised:
        PhysicalMovePlanner().plan(event)

    assert raised.value.reason is reason
