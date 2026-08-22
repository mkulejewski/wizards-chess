"""Composition and entry points for the GUI and retained development CLI."""

import argparse
import sys
from collections.abc import Callable, Sequence

from wizard_chess.application.session import GameSession, SessionResult
from wizard_chess.domain.exceptions import WizardChessError
from wizard_chess.domain.game import ChessGame
from wizard_chess.domain.results import GameStatus
from wizard_chess.hardware.base import PhysicalBoard
from wizard_chess.speech.controller import VoiceController
from wizard_chess.speech.exceptions import VoiceCommandRejected, VoiceError
from wizard_chess.speech.factory import create_default_voice_controller
from wizard_chess.speech.models import VoiceState

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
        session: GameSession | None = None,
        voice_controller: VoiceController[SessionResult] | None = None,
    ) -> None:
        self._input = input_fn
        self._output = output_fn
        self._session = session or GameSession(physical_board)
        self._voice_controller = voice_controller or create_default_voice_controller(
            self._session.play_text
        )

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
                if text.strip().lower() == "voice":
                    if self._run_voice_command():
                        return 0
                    continue

                if self._handle_session_result(self._session.play_text(text)):
                    return 0
            except WizardChessError as error:
                self._output(f"Error: {error}")

    def _run_voice_command(self) -> bool:
        try:
            result = self._voice_controller.listen_once(self._announce_voice_state)
        except VoiceCommandRejected as error:
            self._output(f'Heard: "{error.recognition.transcript}"')
            self._output(f"Error: {error.cause}")
            self._output("Please try again.")
            return False
        except VoiceError as error:
            self._output(str(error))
            return False

        self._output(f'Heard: "{result.recognition.transcript}"')
        return self._handle_session_result(result.command_result)

    def _announce_voice_state(self, state: VoiceState) -> None:
        if state is VoiceState.LISTENING:
            self._output("Listening...")
        elif state is VoiceState.PROCESSING:
            self._output("Processing...")

    def _handle_session_result(self, result: SessionResult) -> bool:
        if result.message is not None:
            self._output(result.message)
        if result.move_event is not None:
            self._announce_state()
        return result.quit_requested

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
