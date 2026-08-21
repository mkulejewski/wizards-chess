"""In-memory physical-board substitute."""

from wizard_chess.domain.events import MoveExecuted


class SimulatedPhysicalBoard:
    """Record move events without performing physical actions."""

    def __init__(self) -> None:
        self.events: list[MoveExecuted] = []

    def execute_move(self, event: MoveExecuted) -> None:
        self.events.append(event)
