"""Composition and entry points for the GUI and retained development CLI."""

import argparse
import logging
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from wizard_chess.application.scripted_game import ScriptedGameRunner
from wizard_chess.application.session import GameSession, SessionResult
from wizard_chess.configuration import ApplicationSettings
from wizard_chess.domain.exceptions import WizardChessError
from wizard_chess.domain.game import ChessGame
from wizard_chess.domain.results import GameStatus
from wizard_chess.hardware.base import PhysicalBoard
from wizard_chess.persistence.game_store import GameStore
from wizard_chess.persistence.settings_store import SettingsStore
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
        self._engine_failed = False

    @property
    def game(self) -> ChessGame:
        return self._session.game

    def run(self) -> int:
        self._output("Wizard Chess")
        self._output("Type 'help' for commands.")

        while True:
            if (
                not self._engine_failed
                and self._session.engine_controls_turn()
                and not self.game.is_game_over()
            ):
                self._play_engine_turn()
            try:
                text = self._input(self._prompt())
            except (EOFError, KeyboardInterrupt):
                self._output("")
                self._session.close()
                return 0

            try:
                if text.strip().lower() == "voice":
                    if self._run_voice_command():
                        self._session.close()
                        return 0
                    continue

                if self._handle_session_result(self._session.play_text(text)):
                    self._session.close()
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
            if self._session.engine_controls_turn() and not self.game.is_game_over():
                self._play_engine_turn()
        return result.quit_requested

    def _play_engine_turn(self) -> None:
        self._output("Engine thinking...")
        try:
            event = self._session.play_engine_move()
        except WizardChessError as error:
            self._engine_failed = True
            self._output(f"Engine unavailable: {error}. Typed play remains available.")
            return
        if event is not None:
            self._output(f"Engine played: {event.san}")
            self._announce_state()

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
    parser.add_argument("--script", help="play a UTF-8 command script and exit")
    parser.add_argument("--setup", action="store_true", help="show Game Setup at GUI launch")
    arguments = parser.parse_args(list(argv) if argv is not None else None)
    settings_store = SettingsStore(_configuration_directory() / "settings.json")
    persistent_settings = settings_store.load()
    settings = ApplicationSettings.from_environment(persistent_settings)
    logging.basicConfig(
        level=settings.logging_level,
        format="%(asctime)s %(levelname)s %(name)s event=%(message)s",
    )
    logging.getLogger(__name__).info("application_startup")
    if arguments.script:
        scripted_session = _create_session(settings)
        result = ScriptedGameRunner(scripted_session).run_file(arguments.script)
        print(result.final_fen)
        scripted_session.close()
        return 0
    if arguments.cli:
        return CliApplication(session=_create_session(settings)).run()

    from wizard_chess.gui.application import run_gui

    return run_gui(
        sys.argv if argv is None else [sys.argv[0], *argv],
        session=_create_session(settings),
        settings_store=settings_store,
        persistent_settings=persistent_settings,
        force_setup=arguments.setup,
    )


def _create_session(settings: ApplicationSettings) -> GameSession:
    game_store = GameStore(_state_directory() / "games")
    session = GameSession(settings=settings, game_store=game_store)
    if settings.autosave:
        recovery = game_store.recover()
        if recovery is not None:
            try:
                session.load_pgn(recovery)
                logging.getLogger(__name__).info("game_recovered")
            except WizardChessError:
                logging.getLogger(__name__).warning("game_recovery_failed", exc_info=True)
    return session


def _configuration_directory() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME", "").strip()
    root = Path(configured) if configured else Path.home() / ".config"
    return root / "wizard-chess"


def _state_directory() -> Path:
    configured = os.environ.get("XDG_STATE_HOME", "").strip()
    root = Path(configured) if configured else Path.home() / ".local" / "state"
    return root / "wizard-chess"


if __name__ == "__main__":
    raise SystemExit(run())
