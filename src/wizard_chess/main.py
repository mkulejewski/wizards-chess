"""Composition and entry points for the GUI and retained development CLI."""

import argparse
import sys
from collections.abc import Callable, Sequence

from wizard_chess.application.session import GameSession
from wizard_chess.domain.exceptions import WizardChessError
from wizard_chess.domain.game import ChessGame
from wizard_chess.domain.results import GameStatus
from wizard_chess.hardware.base import PhysicalBoard

InputFunction = Callable[[str], str]
OutputFunction = Callable[[str], None]


class CliApplication:
    """Composition root for the temporary terminal interface."""

    def __init__(
        self,
        *,
        input_fn: InputFunction = input,
        output_fn: OutputFunction = print,
        physical_board: PhysicalBoard | None = None,
    ) -> None:
        self._input = input_fn
        self._output = output_fn
        self._session = GameSession(physical_board)

    @property
    def game(self) -> ChessGame:
        return self._session.game

    def run(self) -> int:
        self._output("Wizard Chess")
        self._output("Type 'help' for commands.")

        while True:
            try:
                text = self._input(self._prompt())
            except (EOFError, KeyboardInterrupt):
                self._output("")
                return 0

            try:
                result = self._session.play_text(text)
                if result.message is not None:
                    self._output(result.message)
                if result.quit_requested:
                    return 0
                if result.move_event is not None:
                    self._announce_state()
            except WizardChessError as error:
                self._output(f"Error: {error}")

    def _prompt(self) -> str:
        if self.game.is_game_over():
            return "\nGame over > "
        return f"\n{self.game.turn.value.title()} to move > "

    def _announce_state(self) -> None:
        result = self.game.result()
        if result.status is GameStatus.CHECK:
            self._output("Check.")
        elif result.is_over:
            label = result.status.value.replace("_", " ").title()
            self._output(f"{label}: {result.notation}")


def run(argv: Sequence[str] | None = None) -> int:
    """Launch the desktop GUI by default, or the retained CLI with ``--cli``."""
    parser = argparse.ArgumentParser(description="Wizard Chess")
    parser.add_argument("--cli", action="store_true", help="run the terminal interface")
    arguments = parser.parse_args(list(argv) if argv is not None else None)
    if arguments.cli:
        return CliApplication().run()

    from wizard_chess.gui.application import run_gui

    return run_gui(sys.argv if argv is None else [sys.argv[0], *argv])


if __name__ == "__main__":
    raise SystemExit(run())
