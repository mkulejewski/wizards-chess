"""In-memory physical-board substitute."""

from wizard_chess.domain.events import MoveExecuted


class SimulatedPhysicalBoard:
    """Record move events without performing physical actions."""

    def __init__(self) -> None:
        self.events: list[MoveExecuted] = []
        self.position_replacements = 0
        self.closed = False

    def execute_move(self, event: MoveExecuted) -> None:
        self.events.append(event)

    def position_replaced(self) -> None:
        self.position_replacements += 1

    def close(self) -> None:
        self.closed = True
