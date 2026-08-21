"""Physical-board output adapter contracts and simulations."""

from wizard_chess.hardware.base import PhysicalBoard
from wizard_chess.hardware.simulated_board import SimulatedPhysicalBoard

__all__ = ["PhysicalBoard", "SimulatedPhysicalBoard"]
